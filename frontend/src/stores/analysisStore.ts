import { useCallback, useMemo, useReducer, useRef } from 'react';
import type {
    AnalysisSession,
    WebSocketMessage,
    AgentData,
    ConferenceData,
    PredictionData,
    SessionData,
    ConferenceMessage,
} from '../types/message';
import {
    extractValuationGap,
    extractTargetPrice,
    extractValuationMethodBreakdown,
    extractRecommendation,
    extractSafetyMargin,
    extractRiskLevel,
    isUnavailableTargetPrice,
} from '../utils/metricExtraction';
import { stripThinkingContent } from '../utils/reportUtils';

// 初始状态
const initialState: AnalysisSession = {
    id: null,
    tickers: [],
    date: '',
    status: 'idle',
    agents: {},
    conferenceMessages: [],
    predictions: {},
    report: '',
    currentRound: 0,
    totalRounds: 0,
};

// Action 类型
type Action =
    | { type: 'SESSION_START'; payload: SessionData & { id: string } }
    | { type: 'SESSION_END'; payload: { success: boolean; status?: AnalysisSession['status'] } }
    | { type: 'AGENT_START'; payload: AgentData }
    | { type: 'AGENT_PROGRESS'; payload: AgentData }
    | { type: 'AGENT_COMPLETE'; payload: AgentData & { timestamp?: string; message_id?: string } }
    | { type: 'AGENT_FAILED'; payload: AgentData }
    | { type: 'CONFERENCE_START' }
    | { type: 'ROUND_START'; payload: { round: number; total_rounds: number } }
    | { type: 'CONFERENCE_MESSAGE'; payload: ConferenceData & { timestamp: string; id: string } }
    | { type: 'ROUND_END'; payload: { round: number } }
    | { type: 'CONFERENCE_END' }
    | { type: 'PREDICTION_UPDATE'; payload: PredictionData }
    | { type: 'REPORT_GENERATED'; payload: { report: string } }
    | { type: 'ERROR'; payload: { error: string } }
    | { type: 'RESET' }
    | { type: 'RESTORE_SESSION'; payload: { session: SessionData & { id: string; status: string; report?: string }; outputs: AgentOutput[] } };

export interface AgentOutput {
    id: string;
    agent_id: string;
    agent_type: string;
    phase: string;
    content: string;
    created_at: string;
}

export interface AnalysisMetrics {
    currentFocus: string;
    valuationGap: number | null;
    targetPrice: string | null;
    recommendation: string;
    safetyMargin: string;
    riskLevel: string;
    methodBreakdown?: import('../utils/metricExtraction').ValuationMethodBreakdown | null;
    confidence?: string | null;
    divergencePct?: number | null;
}



// Reducer
function analysisReducer(state: AnalysisSession, action: Action): AnalysisSession {
    switch (action.type) {
        case 'SESSION_START':
            if (state.id === action.payload.id && state.status === 'running') {
                return {
                    ...state,
                    tickers: action.payload.tickers,
                    date: action.payload.date,
                };
            }
            return {
                ...initialState,
                id: action.payload.id,
                tickers: action.payload.tickers,
                date: action.payload.date,
                status: 'running',
            };

        case 'SESSION_END':
            return {
                ...state,
                status: action.payload.status || (action.payload.success ? 'completed' : 'failed'),
            };

        case 'AGENT_START': {
            const agentId = action.payload.agent_id;
            return {
                ...state,
                agents: {
                    ...state.agents,
                    [agentId]: {
                        id: agentId,
                        name: getAgentDisplayName(agentId),
                        status: 'analyzing',
                        content: action.payload.content || '正在准备分析任务',
                        progress: 0,
                        phase: action.payload.phase || '',
                    },
                },
            };
        }

        case 'AGENT_PROGRESS': {
            const agentId = action.payload.agent_id;
            return {
                ...state,
                agents: {
                    ...state.agents,
                    [agentId]: {
                        ...state.agents[agentId],
                        progress: action.payload.progress || 0,
                        content: action.payload.content || state.agents[agentId]?.content || '',
                    },
                },
            };
        }

        case 'AGENT_COMPLETE': {
            const agentId = action.payload.agent_id;
            const agentContent = stripThinkingContent(action.payload.content || '');
            return {
                ...state,
                agents: {
                    ...state.agents,
                    [agentId]: {
                        id: agentId,
                        name: getAgentDisplayName(agentId),
                        status: 'complete',
                        content: agentContent,
                        progress: 100,
                        phase: action.payload.phase || '',
                    },
                },
                // Removed: conferenceMessages addition to prevent duplicates
                // Analysis phase outputs should not appear in conference feed
            };
        }

        case 'AGENT_FAILED': {
            const agentId = action.payload.agent_id;
            return {
                ...state,
                agents: {
                    ...state.agents,
                    [agentId]: {
                        id: agentId,
                        name: getAgentDisplayName(agentId),
                        status: 'error',
                        content: action.payload.content || '分析执行失败',
                        progress: 0,
                        phase: action.payload.phase || '',
                    },
                },
            };
        }

        case 'ROUND_START':
            return {
                ...state,
                currentRound: action.payload.round,
                totalRounds: action.payload.total_rounds,
            };

        case 'CONFERENCE_MESSAGE': {
            const newMessage = {
                id: action.payload.id,
                agent_id: action.payload.agent_id || '',
                content: stripThinkingContent(action.payload.content || ''),
                timestamp: action.payload.timestamp,
            };
            return {
                ...state,
                conferenceMessages: [
                    ...state.conferenceMessages,
                    newMessage,
                ],
            };
        }

        case 'PREDICTION_UPDATE': {
            return {
                ...state,
                predictions: {
                    ...state.predictions,
                    [action.payload.agent_id]: action.payload.predictions,
                },
            };
        }

        case 'REPORT_GENERATED': {
            // 报告到达即视为本轮分析可展示；即使 session_end 延迟/丢失，也切换到就绪态
            // 入库的历史脏数据（content blocks 字面量）在此统一清洗
            const rawReport = action.payload.report || state.report || '';
            const cleanedReport = stripThinkingContent(rawReport);
            return {
                ...state,
                report: cleanedReport,
                status: cleanedReport ? 'completed' : state.status,
            };
        }

        case 'ERROR':
            return {
                ...state,
                status: 'failed',
            };

        case 'RESET':
            return initialState;

        case 'RESTORE_SESSION': {
            const { session, outputs } = action.payload;

            // Reconstruct agents state
            const restoredAgents = { ...initialState.agents };
            // Reconstruct conference messages
            const restoredMessages: ConferenceMessage[] = [];

            outputs.forEach(output => {
                const cleaned = stripThinkingContent(output.content || '');
                if (output.phase === 'analysis' || output.phase === 'prediction' || output.phase === 'risk_assessment' || output.phase === 'investment_recommendation') {
                    restoredAgents[output.agent_id] = {
                        id: output.agent_id,
                        name: getAgentDisplayName(output.agent_id),
                        status: 'complete',
                        content: cleaned,
                        progress: 100,
                        phase: output.phase || 'analysis',
                    };
                } else if (output.phase === 'conference') {
                    restoredMessages.push({
                        id: output.id,
                        agent_id: output.agent_id,
                        content: cleaned,
                        timestamp: output.created_at,
                    });
                }
            });

            return {
                ...initialState,
                id: session.id,
                tickers: session.tickers,
                date: session.date,
                status: session.status as AnalysisSession['status'],
                report: stripThinkingContent(session.report || ''),
                agents: restoredAgents,
                conferenceMessages: restoredMessages,
            };
        }

        default:
            return state;
    }
}

// Agent 显示名称映射
function getAgentDisplayName(agentId: string): string {
    const names: Record<string, string> = {
        fundamentals_analyst: '基本面分析师',
        valuation_analyst: '估值分析师',
        technical_analyst: '技术分析师',
        sentiment_analyst: '情绪分析师',
        risk_manager: '风险管理',
        portfolio_manager: '投资顾问',
    };
    return names[agentId] || agentId;
}

// 类型安全的数据提取函数
function extractSessionData(data: Record<string, unknown>): SessionData {
    return {
        tickers: Array.isArray(data.tickers) ? data.tickers as string[] : [],
        date: typeof data.date === 'string' ? data.date : '',
    };
}

function extractAgentData(data: Record<string, unknown>): AgentData {
    return {
        agent_id: typeof data.agent_id === 'string' ? data.agent_id : '',
        content: typeof data.content === 'string' ? data.content : '',
        phase: typeof data.phase === 'string' ? data.phase : undefined,
        progress: typeof data.progress === 'number' ? data.progress : undefined,
    };
}

function extractPredictionData(data: Record<string, unknown>): PredictionData {
    return {
        agent_id: typeof data.agent_id === 'string' ? data.agent_id : '',
        predictions: Array.isArray(data.predictions) ? data.predictions : [],
    };
}

export function useAnalysisStore() {
    const [state, dispatch] = useReducer(analysisReducer, initialState);
    const activeSessionIdRef = useRef<string | null>(null);

    // 处理 WebSocket 消息
    const handleMessage = useCallback((message: WebSocketMessage) => {
        const { event, data, session_id, timestamp, message_id } = message;

        console.debug('[handleMessage] Received WebSocket event:', {
            event,
            session_id,
            data_keys: Object.keys(data || {}),
        });

        if (
            event !== 'session_start'
            && session_id
            && activeSessionIdRef.current
            && session_id !== activeSessionIdRef.current
        ) {
            console.debug('[handleMessage] Ignoring event from another session:', session_id);
            return;
        }

        switch (event) {
            case 'session_start': {
                activeSessionIdRef.current = session_id || null;
                const sessionData = extractSessionData(data);
                dispatch({
                    type: 'SESSION_START',
                    payload: {
                        id: session_id || '',
                        ...sessionData,
                    },
                });
                break;
            }

            case 'session_end': {
                const status = data.status;
                dispatch({
                    type: 'SESSION_END',
                    payload: {
                        success: Boolean(data.success),
                        status: status === 'cancelled' || status === 'completed' || status === 'failed'
                            ? status
                            : undefined,
                    },
                });
                break;
            }

            case 'analysis_start':
                dispatch({ type: 'AGENT_START', payload: extractAgentData(data) });
                break;

            case 'analysis_progress':
                dispatch({ type: 'AGENT_PROGRESS', payload: extractAgentData(data) });
                break;

            case 'analysis_complete':
                dispatch({
                    type: 'AGENT_COMPLETE',
                    payload: {
                        ...extractAgentData(data),
                        timestamp,
                        message_id
                    }
                });
                break;

            case 'analysis_failed':
                dispatch({ type: 'AGENT_FAILED', payload: extractAgentData(data) });
                break;

            case 'conference_start':
                dispatch({ type: 'CONFERENCE_START' });
                break;

            case 'round_start':
                dispatch({
                    type: 'ROUND_START',
                    payload: {
                        round: typeof data.round === 'number' ? data.round : 0,
                        total_rounds: typeof data.total_rounds === 'number' ? data.total_rounds : 0,
                    },
                });
                break;

            case 'message':
            case 'summary':
                console.debug('[WebSocket] Conference event received:', {
                    type: message.type,
                    agent_id: data.agent_id,
                });
                dispatch({
                    type: 'CONFERENCE_MESSAGE',
                    payload: {
                        agent_id: typeof data.agent_id === 'string' ? data.agent_id : '',
                        content: typeof data.content === 'string' ? data.content : '',
                        timestamp,
                        id: message_id,
                    },
                });
                break;

            case 'round_end':
                dispatch({
                    type: 'ROUND_END',
                    payload: { round: typeof data.round === 'number' ? data.round : 0 },
                });
                break;

            case 'conference_end':
                dispatch({ type: 'CONFERENCE_END' });
                break;

            case 'prediction_update':
                dispatch({
                    type: 'PREDICTION_UPDATE',
                    payload: extractPredictionData(data),
                });
                break;

            case 'report_generated':
                dispatch({
                    type: 'REPORT_GENERATED',
                    payload: { report: typeof data.report === 'string' ? data.report : '' },
                });
                break;

            case 'error':
                dispatch({
                    type: 'ERROR',
                    payload: { error: typeof data.error === 'string' ? data.error : 'Unknown error' },
                });
                break;
        }
    }, []);

    const reset = useCallback(() => {
        activeSessionIdRef.current = null;
        dispatch({ type: 'RESET' });
    }, []);

    // 计算派生状态
    const agentList = useMemo(() => Object.values(state.agents), [state.agents]);
    const isAnalyzing = state.status === 'running';
    const hasReport = state.report.length > 0;

    // 计算指标数据
    const metrics = useMemo((): AnalysisMetrics => {
        // Current Focus - from tickers
        const currentFocus = state.tickers.length > 0
            ? state.tickers.join(', ')
            : 'No Analysis';

        // Extract from portfolio_manager's final recommendation or report
        // Priority: state.report > portfolio_manager.content
        const portfolioManager = state.agents['portfolio_manager'];
        const valuationAnalyst = state.agents['valuation_analyst'];
        const sourceContent = state.report || portfolioManager?.content || '';
        const valuationContent =
            valuationAnalyst?.content || sourceContent || '';

        // Valuation Gap - from portfolio_manager recommendation
        let valuationGap: number | null = null;
        if (sourceContent) {
            valuationGap = extractValuationGap(sourceContent);
        }
        const finalTargetPrice = sourceContent ? extractTargetPrice(sourceContent) : null;
        const hasUnavailableTargetPrice = isUnavailableTargetPrice(finalTargetPrice);

        // PM 明确无法评估时，不以估值模型的上涨空间替代最终建议。
        if (valuationGap == null && !hasUnavailableTargetPrice && valuationContent) {
            valuationGap = extractValuationGap(valuationContent);
        }

        // Safety Margin - from portfolio_manager recommendation
        let safetyMargin = 'Unknown';
        if (sourceContent) {
            safetyMargin = extractSafetyMargin(sourceContent);
        }

        // Risk Level - from portfolio_manager recommendation
        let riskLevel = 'Unknown';
        if (sourceContent) {
            riskLevel = extractRiskLevel(sourceContent);
        }

        const methodBreakdown = valuationContent
            ? extractValuationMethodBreakdown(valuationContent)
            : null;

        // 目标价优先：PM/报告 → 综合公允价 → 估值分析师
        let targetPrice = finalTargetPrice;
        if (!hasUnavailableTargetPrice && (!targetPrice || targetPrice === '—') && methodBreakdown?.blendedPrice != null && methodBreakdown.blendedPrice > 0) {
            targetPrice = `¥${methodBreakdown.blendedPrice.toFixed(2)}`;
        }
        if (!hasUnavailableTargetPrice && (!targetPrice || targetPrice === '—') && valuationContent) {
            targetPrice = extractTargetPrice(valuationContent) || targetPrice;
        }

        let recommendation = sourceContent ? extractRecommendation(sourceContent) : '分析中';
        // 完成后仍解析失败时，不要一直显示“分析中”
        if (recommendation === '分析中' && state.status === 'completed') {
            recommendation = '—';
        }
        if (recommendation === '分析中' && (state.status === 'failed' || state.status === 'cancelled')) {
            recommendation = '—';
        }

        return {
            currentFocus,
            valuationGap,
            targetPrice,
            recommendation,
            safetyMargin,
            riskLevel,
            methodBreakdown,
            confidence: methodBreakdown?.confidence ?? null,
            divergencePct: methodBreakdown?.divergencePct ?? null,
        };
    }, [state.tickers, state.agents, state.report, state.status]);

    return {
        state,
        handleMessage,
        dispatch, // Export dispatch to allow external actions
        reset,
        agentList,
        isAnalyzing,
        hasReport,
        metrics, // Export computed metrics
    };
}
