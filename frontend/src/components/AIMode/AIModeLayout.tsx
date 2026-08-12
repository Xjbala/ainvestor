import { StockHeader } from './StockHeader';
import { AnalystCard } from './AnalystCard';
import { CoordinationFlow, type AgentMessage } from './CoordinationFlow';
import { DecisionFooter } from './DecisionFooter';
import { ValuationMethodPanel } from './ValuationMethodPanel';
import './AIMode.css';
import { useState, useMemo, useEffect, Fragment } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { stripThinkingContent } from '../../utils/reportUtils';
import {
    extractValuationMethodBreakdown,
    isUnavailableTargetPrice,
    parseTargetPriceNumber,
} from '../../utils/metricExtraction';
import { companyApi } from '../../services/companyApi';
import { exportReport } from '../../utils/reportExport';

// Use this interface to accept props from App.tsx
// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface AIModeLayoutProps {
    ticker?: string;
    // agents/metrics 来自 store，结构动态，使用 any 避免过度类型断言
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    agents?: any[];
    messages?: AgentMessage[];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    metrics?: any;
    report?: string;
    analysisStatus?: 'idle' | 'running' | 'completed' | 'failed' | 'cancelled';
    onStopAnalysis?: () => void;
    isStopRequested?: boolean;
}

export function AIModeLayout({ ticker, agents = [], messages = [], metrics, report, analysisStatus, onStopAnalysis, isStopRequested }: AIModeLayoutProps) {

    // Selected Agent for Filtering: null = show all
    const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

    // Report visibility state
    const [showReport, setShowReport] = useState(false);

    // 现价：优先 metrics，其次从估值文案/breakdown 推断空间时留给面板自行展示
    const [headerPrice, setHeaderPrice] = useState<number | null>(null);

    // Extract a meaningful summary from agent content
    const extractSummary = (content?: string): string[] => {
        if (!content || content.trim().length === 0) return [];

        // Strip thinking blocks
        const cleaned = content
            .replace(/\{['"]\s*type['"]\s*:\s*['"]\s*thinking['"]\s*,[\s\S]*?\}/g, '')
            .replace(/<think>[\s\S]*?<\/think>/gi, '')
            .trim();

        if (!cleaned) return [];

        // Extract first 2 meaningful lines (skip empty lines, headings-only lines)
        const lines = cleaned.split('\n')
            .map(l => l.trim())
            .filter(l => l.length > 4 && !l.match(/^#{1,4}\s*$/) && !l.startsWith('{'));

        return lines.slice(0, 2).map(l => {
            // Truncate long lines
            const stripped = l.replace(/^#+\s*/, '').replace(/\*\*/g, '');
            return stripped.length > 40 ? stripped.substring(0, 40) + '...' : stripped;
        });
    };

    // Helper to get agent data by ID
    const getAgentData = (id: string) => {
        const agent = agents.find(a => a.id === id);
        const summaryLines = extractSummary(agent?.content);

        let logs: string[];
        if (agent?.status === 'complete' && summaryLines.length > 0) {
            logs = summaryLines;
        } else if (agent?.status === 'analyzing') {
            logs = ['正在进行深度分析...'];
        } else {
            logs = ['等待任务启动...'];
        }

        return {
            status: agent?.status === 'complete' ? 'completed' : (agent?.status === 'analyzing' ? 'active' : 'pending'),
            progress: agent?.progress || (agent?.status === 'complete' ? 100 : 0),
            logs,
        };
    };

    const fundData = getAgentData('fundamentals_analyst');
    const valData = getAgentData('valuation_analyst');
    const riskData = getAgentData('risk_manager');
    const portData = getAgentData('portfolio_manager');

    // 整体进度与阶段追踪
    const allAgentData = [fundData, valData, riskData, portData];
    const overallProgress = Math.round(
        allAgentData.reduce((sum, a) => sum + a.progress, 0) / allAgentData.length
    );

    const phases = useMemo(() => {
        const fundDone = fundData.status === 'completed';
        const valDone = valData.status === 'completed';
        const riskDone = riskData.status === 'completed';
        const portDone = portData.status === 'completed';
        const portActive = portData.status === 'active';

        // 阶段完成判定
        const phaseDone = [fundDone && valDone, riskDone, portActive || portDone, portDone];
        // 当前活跃阶段 = 第一个未完成的
        const activeIdx = phaseDone.indexOf(false);

        return [
            { label: '评估', done: phaseDone[0], active: activeIdx === 0 },
            { label: '风险', done: phaseDone[1], active: activeIdx === 1 },
            { label: '会议', done: phaseDone[2], active: activeIdx === 2 },
            { label: '决策', done: phaseDone[3], active: activeIdx === 3 },
        ];
    }, [fundData.status, valData.status, riskData.status, portData.status]);

    // 估值分析师多方法拆解（从 agent content / metrics 解析）
    const valuationBreakdown = useMemo(() => {
        if (metrics?.methodBreakdown) return metrics.methodBreakdown;
        const agent = agents.find(a => a.id === 'valuation_analyst');
        if (!agent?.content) return null;
        return extractValuationMethodBreakdown(agent.content);
    }, [agents, metrics?.methodBreakdown]);

    // 从 StockHeader 同路径拉取现价，供 ValuationMethodPanel / 预期收益使用
    useEffect(() => {
        if (!ticker) {
            setHeaderPrice(null);
            return;
        }
        let cancelled = false;
        companyApi
            .getCompany(ticker)
            .then((c) => {
                if (!cancelled && c?.current_price != null) {
                    setHeaderPrice(Number(c.current_price));
                }
            })
            .catch(() => {
                if (!cancelled) setHeaderPrice(null);
            });
        return () => {
            cancelled = true;
        };
    }, [ticker]);

    const valuationLoading =
        valData.status === 'active' ||
        (valData.status === 'pending' && !valuationBreakdown);

    const upsideFromBreakdown = useMemo(() => {
        if (isUnavailableTargetPrice(metrics?.targetPrice)) {
            return null;
        }

        // 1) 文案中的上涨/下跌空间（已排除“方法分歧”误匹配）
        if (metrics?.valuationGap != null && Number.isFinite(Number(metrics.valuationGap))) {
            return Number(metrics.valuationGap);
        }
        // 2) 目标价中点 vs 现价
        const targetNum = parseTargetPriceNumber(metrics?.targetPrice);
        if (targetNum != null && headerPrice != null && headerPrice > 0) {
            return ((targetNum - headerPrice) / headerPrice) * 100;
        }
        // 3) 综合公允价 vs 现价（仅正值公允价）
        if (
            valuationBreakdown?.blendedPrice != null &&
            valuationBreakdown.blendedPrice > 0 &&
            headerPrice != null &&
            headerPrice > 0
        ) {
            return (
                ((valuationBreakdown.blendedPrice - headerPrice) / headerPrice) * 100
            );
        }
        return null;
    }, [
        metrics?.valuationGap,
        metrics?.targetPrice,
        valuationBreakdown?.blendedPrice,
        headerPrice,
    ]);

    // Use real messages or empty array
    const allFlowMessages: AgentMessage[] = messages;

    // Agent ID → 中文显示名映射（用于筛选匹配）
    const agentNameToIdMap: Record<string, string> = {
        '基本面': 'fundamentals_analyst',
        '基本面分析师': 'fundamentals_analyst',
        '估值': 'valuation_analyst',
        '估值分析师': 'valuation_analyst',
        '风险': 'risk_manager',
        '风险管理': 'risk_manager',
        '风险管理师': 'risk_manager',
        '投资': 'portfolio_manager',
        '投资顾问': 'portfolio_manager',
        '投资分析师': 'portfolio_manager',
    };

    // Filter messages based on selection
    const displayedMessages = useMemo(() => {
        if (!selectedAgentId) return allFlowMessages;
        // Map agent ID to Chinese display name for filtering
        const displayName = Object.entries(agentNameToIdMap)
            .find(([, id]) => id === selectedAgentId)?.[0];
        if (!displayName) return allFlowMessages;
        return allFlowMessages.filter(msg => msg.agentName.includes(displayName));
    }, [selectedAgentId, allFlowMessages, agentNameToIdMap]);

    const handleCardClick = (displayName: string) => {
        const agentId = agentNameToIdMap[displayName];
        if (!agentId) return;
        // Toggle: 如果已选中同一 agent，则清除筛选（显示全部）
        if (selectedAgentId === agentId) {
            setSelectedAgentId(null);
        } else {
            setSelectedAgentId(agentId);
        }
    };

    // Scroll to first matching message after filter changes
    useEffect(() => {
        if (!selectedAgentId) return;
        // Map English ID to Chinese display name
        const displayName = Object.entries(agentNameToIdMap)
            .find(([, id]) => id === selectedAgentId)?.[0];
        if (!displayName) return;

        setTimeout(() => {
            const items = document.querySelectorAll('.timeline-item');
            for (const item of items) {
                const nameEl = item.querySelector('.agent-name');
                if (nameEl && nameEl.textContent?.includes(displayName)) {
                    item.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    break;
                }
            }
        }, 150);
    }, [selectedAgentId]);

    return (
        <div className="ai-mode-container">
            <StockHeader
                ticker={ticker}
                lastUpdated={new Date().toLocaleTimeString()} // Use current time as update time for now
            />

            <div className="ai-mode-content">
                <div className="ai-left-column">
                <div className="analyst-dashboard">
                    <AnalystCard
                        title="基本面分析师"
                        subtitle="财务指标与竞争优势"
                        icon="📈"
                        iconClass="icon-fund"
                        status={fundData.status as 'pending' | 'active' | 'completed'}
                        progress={fundData.progress}
                        logs={fundData.logs}
                        isActiveFilter={selectedAgentId === 'fundamentals_analyst'}
                        onClick={() => handleCardClick('基本面分析师')}
                    />
                    <AnalystCard
                        title="估值分析师"
                        subtitle="DCF / RI / 相对估值三角验证"
                        icon="💎"
                        iconClass="icon-decision"
                        status={valData.status as 'pending' | 'active' | 'completed'}
                        progress={valData.progress}
                        logs={
                            valuationBreakdown?.blendedPrice != null
                                ? [
                                      `综合公允价 ¥${valuationBreakdown.blendedPrice.toFixed(2)}`,
                                      ...(valData.logs || []),
                                  ].slice(0, 3)
                                : valData.logs
                        }
                        isActiveFilter={selectedAgentId === 'valuation_analyst'}
                        onClick={() => handleCardClick('估值分析师')}
                    />
                    <AnalystCard
                        title="风险管理师"
                        subtitle="合规性与压力测试"
                        icon="🛡️"
                        iconClass="icon-risk"
                        status={riskData.status as 'pending' | 'active' | 'completed'}
                        progress={riskData.progress}
                        logs={riskData.logs}
                        isActiveFilter={selectedAgentId === 'risk_manager'}
                        onClick={() => handleCardClick('风险管理师')}
                    />
                    <AnalystCard
                        title="投资顾问"
                        subtitle="综合判断与仓位建议"
                        icon="🧠"
                        iconClass="icon-portfolio"
                        status={portData.status as 'pending' | 'active' | 'completed'}
                        progress={portData.progress}
                        logs={portData.logs}
                        isActiveFilter={selectedAgentId === 'portfolio_manager'}
                        onClick={() => handleCardClick('投资顾问')}
                    />
                </div>

                <CoordinationFlow messages={displayedMessages} />
                </div>

                <div className="ai-right-column">
                {/* Agent 进度总览 —— 增强版：整体进度 + 阶段追踪 + 各Agent进度 */}
                <div className="agent-overview-card">
                    <div className="agent-overview-header">
                        <div className="agent-overview-title">智能体进度</div>
                        <div className="agent-overview-total">{overallProgress}%</div>
                    </div>
                    <div className="agent-overview-phases">
                        {phases.map((phase, i) => (
                            <Fragment key={phase.label}>
                                <div className={`agent-overview-phase ${phase.done ? 'done' : ''} ${phase.active ? 'active' : ''}`}>
                                    <div className="agent-overview-phase-dot">
                                        {phase.done ? '✓' : i + 1}
                                    </div>
                                    <div className="agent-overview-phase-label">{phase.label}</div>
                                </div>
                                {i < phases.length - 1 && <span className="agent-overview-phase-arrow">›</span>}
                            </Fragment>
                        ))}
                    </div>
                    {[
                        { name: '基本面分析师', data: fundData, icon: '📈' },
                        { name: '估值分析师', data: valData, icon: '💎' },
                        { name: '风险管理师', data: riskData, icon: '🛡️' },
                        { name: '投资顾问', data: portData, icon: '🧠' },
                    ].map(({ name, data, icon }) => (
                        <div key={name} className={`agent-overview-row status-${data.status}`}>
                            <span className="agent-overview-icon">{icon}</span>
                            <span className="agent-overview-name">{name}</span>
                            <span className="agent-overview-bar">
                                <span className="agent-overview-bar-fill" style={{ width: `${data.progress}%` }} />
                            </span>
                            <span className="agent-overview-status">
                                {data.status === 'completed' ? '✓' : data.status === 'active' ? '··' : '—'}
                            </span>
                        </div>
                    ))}
                </div>

                {/* 分析概览 —— 元信息（不与左栏卡片重复） */}
                <div className="meta-card">
                    <div className="meta-title">分析概览</div>
                    <div className="meta-grid">
                        <div className="meta-item">
                            <div className="meta-label">标的代码</div>
                            <div className="meta-value">{ticker || '—'}</div>
                        </div>
                        <div className="meta-item">
                            <div className="meta-label">分析日期</div>
                            <div className="meta-value">{new Date().toISOString().slice(0, 10)}</div>
                        </div>
                        <div className="meta-item">
                            <div className="meta-label">智能体</div>
                            <div className="meta-value">4 位协作</div>
                        </div>
                        <div className="meta-item">
                            <div className="meta-label">协作消息</div>
                            <div className="meta-value">{messages.length} 条</div>
                        </div>
                        <div className="meta-item">
                            <div className="meta-label">估值方法</div>
                            <div className="meta-value">{valuationBreakdown?.methods?.length || 0} 种验证</div>
                        </div>
                        <div className="meta-item">
                            <div className="meta-label">分析状态</div>
                            <div className={`meta-value status-${analysisStatus || 'idle'}`}>
                                {analysisStatus === 'completed' ? '已完成' : analysisStatus === 'running' ? '进行中' : analysisStatus === 'cancelled' ? '已取消' : analysisStatus === 'failed' ? '执行失败' : '待启动'}
                            </div>
                        </div>
                    </div>
                </div>

                <ValuationMethodPanel
                    loading={valuationLoading && !valuationBreakdown}
                    blendedPrice={valuationBreakdown?.blendedPrice}
                    currentPrice={headerPrice}
                    upsidePct={upsideFromBreakdown ?? undefined}
                    divergencePct={
                        valuationBreakdown?.divergencePct ?? metrics?.divergencePct
                    }
                    confidence={
                        valuationBreakdown?.confidence ?? metrics?.confidence
                    }
                    methods={valuationBreakdown?.methods || []}
                    headline={valuationBreakdown?.headline}
                    risks={valuationBreakdown?.risks}
                />

                <DecisionFooter
                status={analysisStatus === 'completed' || analysisStatus === 'failed' || analysisStatus === 'cancelled' ? 'ready' : 'analyzing'}
                recommendation={
                    analysisStatus === 'completed' || analysisStatus === 'failed' || analysisStatus === 'cancelled'
                        ? (metrics?.recommendation && metrics.recommendation !== '分析中'
                            ? metrics.recommendation
                            : '—')
                        : (metrics?.recommendation || '分析中')
                }
                targetPrice={
                    metrics?.targetPrice && metrics.targetPrice !== '计算中...'
                        ? metrics.targetPrice
                        : (valuationBreakdown?.blendedPrice != null && valuationBreakdown.blendedPrice > 0
                            ? `¥${valuationBreakdown.blendedPrice.toFixed(2)}`
                            : (analysisStatus === 'completed' || analysisStatus === 'failed' || analysisStatus === 'cancelled' ? '—' : '计算中...'))
                }
                returnRate={
                    isUnavailableTargetPrice(metrics?.targetPrice)
                        ? '无法评估'
                        : (upsideFromBreakdown != null
                            ? Number(upsideFromBreakdown.toFixed(1))
                            : (analysisStatus === 'completed' || analysisStatus === 'failed' || analysisStatus === 'cancelled' ? '—' : '计算中...'))
                }
                onViewDetail={() => {
                    if (report && report.trim().length > 0) {
                        setShowReport(true);
                        setTimeout(() => {
                            const reportContent = document.getElementById('ai-report-content');
                            if (reportContent) {
                                reportContent.scrollIntoView({ behavior: 'smooth' });
                            }
                        }, 100);
                    }
                }}
                onExportPDF={() => {
                    if (!report || report.trim().length === 0) return;
                    // 从隐藏容器中提取已渲染的 Markdown HTML
                    const hiddenBody = document.getElementById('hidden-report-render');
                    const reportHtml = hiddenBody?.innerHTML || '';
                    exportReport({
                        ticker: ticker || '',
                        reportHtml,
                        recommendation: metrics?.recommendation,
                        targetPrice: metrics?.targetPrice,
                        returnRate: upsideFromBreakdown != null
                            ? `${upsideFromBreakdown > 0 ? '+' : ''}${upsideFromBreakdown.toFixed(1)}%`
                            : undefined,
                        blendedPrice: valuationBreakdown?.blendedPrice,
                        currentPrice: headerPrice,
                        upsidePct: upsideFromBreakdown,
                        agents: [
                            { name: '基本面分析师', icon: '📈', status: fundData.status, summary: fundData.logs[0] || '' },
                            { name: '估值分析师', icon: '💎', status: valData.status, summary: valuationBreakdown?.blendedPrice != null
                                ? `综合公允价 ¥${valuationBreakdown.blendedPrice.toFixed(2)}` : valData.logs[0] || '' },
                            { name: '风险管理师', icon: '🛡️', status: riskData.status, summary: riskData.logs[0] || '' },
                            { name: '投资顾问', icon: '🧠', status: portData.status, summary: portData.logs[0] || '' },
                        ],
                    });
                }}
                onStopAnalysis={onStopAnalysis}
                isStopRequested={isStopRequested}
            />
                </div>
            </div>

            {/* Report Content Section */}
            {showReport && report && (
                <div id="ai-report-content" className="report-section">
                    <div className="report-section-header">
                        <h2>📋 完整投资决策报告</h2>
                        <button
                            className="report-close-btn"
                            onClick={() => setShowReport(false)}
                        >
                            ✕ 关闭
                        </button>
                    </div>
                    <div className="report-markdown-body agent-markdown">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {stripThinkingContent(report)}
                        </ReactMarkdown>
                    </div>
                </div>
            )}
            {/* 隐藏容器：始终渲染报告 Markdown，供导出时提取 HTML */}
            {report && (
                <div id="hidden-report-render" style={{ position: 'absolute', left: '-9999px', top: 0, width: '800px' }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {stripThinkingContent(report)}
                    </ReactMarkdown>
                </div>
            )}
        </div>
    );
}
