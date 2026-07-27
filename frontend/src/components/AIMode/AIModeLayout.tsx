import { StockHeader } from './StockHeader';
import { AnalystCard } from './AnalystCard';
import { CoordinationFlow, type AgentMessage } from './CoordinationFlow';
import { DecisionFooter } from './DecisionFooter';
import { ValuationMethodPanel } from './ValuationMethodPanel';
import './AIMode.css';
import { useState, useMemo, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { stripThinkingContent } from '../../utils/reportUtils';
import {
    extractValuationMethodBreakdown,
    parseTargetPriceNumber,
} from '../../utils/metricExtraction';
import { companyApi } from '../../services/companyApi';

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
    analysisStatus?: 'idle' | 'running' | 'completed' | 'failed';
    onStopAnalysis?: () => void;
}

export function AIModeLayout({ ticker, agents = [], messages = [], metrics, report, analysisStatus, onStopAnalysis }: AIModeLayoutProps) {

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
                <div className="analyst-dashboard" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
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

                <CoordinationFlow messages={displayedMessages} />
            </div>

            <DecisionFooter
                status={analysisStatus === 'completed' || analysisStatus === 'failed' ? 'ready' : 'analyzing'}
                recommendation={
                    analysisStatus === 'completed' || analysisStatus === 'failed'
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
                            : (analysisStatus === 'completed' || analysisStatus === 'failed' ? '—' : '计算中...'))
                }
                returnRate={
                    upsideFromBreakdown != null
                        ? Number(upsideFromBreakdown.toFixed(1))
                        : (analysisStatus === 'completed' || analysisStatus === 'failed' ? '—' : '计算中...')
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
                    if (report && report.trim().length > 0) {
                        const printWindow = window.open('', '_blank');
                        if (printWindow) {
                            printWindow.document.write(`
                                <html>
                                <head>
                                    <title>投资决策报告 - ${ticker}</title>
                                    <style>
                                        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; line-height: 1.6; }
                                        h1 { color: #1a2332; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; }
                                        h2 { color: #374151; margin-top: 30px; }
                                        pre { white-space: pre-wrap; word-wrap: break-word; }
                                    </style>
                                </head>
                                <body>
                                    <h1>投资决策报告 - ${ticker}</h1>
                                    <pre>${report.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
                                </body>
                                </html>
                            `);
                            printWindow.document.close();
                            setTimeout(() => { printWindow.print(); }, 500);
                        }
                    }
                }}
                onStopAnalysis={onStopAnalysis}
            />

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
        </div>
    );
}
