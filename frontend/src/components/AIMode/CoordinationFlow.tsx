import { useRef, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
    extractInvestmentRecommendations,
    type InvestmentRecommendation,
} from '../../utils/metricExtraction';
import { stripThinkingContent } from '../../utils/reportUtils';
import { formatTimeShort } from '../../utils/timeFormat';
import './AIMode.css';

export interface AgentMessage {
    id: string;
    agentId: string;
    agentName: string;
    content: string;
    timestamp: string;
    type: 'info' | 'warning' | 'success' | 'alert';
}

interface CoordinationFlowProps {
    messages: AgentMessage[];
}

const MAX_COLLAPSED_LINES = 12;

function formatTargetPrice(recommendation: InvestmentRecommendation): string {
    const targetPrice = recommendation.target_price;
    if (targetPrice !== null && targetPrice !== undefined && targetPrice !== '') {
        const value = Number(targetPrice);
        if (Number.isFinite(value)) return `¥${value.toFixed(2)}`;
        return String(targetPrice);
    }

    const targetRange = recommendation.target_price_range?.trim();
    if (targetRange && !/^(null|none)$/i.test(targetRange)) {
        return targetRange;
    }

    return '—';
}

function getRatingClass(rating?: string): string {
    if (/强烈推荐|推荐/.test(rating || '')) return 'is-bullish';
    if (/谨慎|回避/.test(rating || '')) return 'is-bearish';
    return 'is-neutral';
}

function InvestmentDecisionSummary({ recommendations }: { recommendations: InvestmentRecommendation[] }) {
    return (
        <section className="investment-decision-summary" aria-label="最终投资建议">
            <div className="investment-decision-heading">最终投资建议</div>
            {recommendations.map((recommendation, index) => (
                <div
                    className="investment-decision-row"
                    key={`${recommendation.ticker || 'recommendation'}-${index}`}
                >
                    <div className="investment-decision-title">
                        <span className="investment-decision-ticker">
                            {recommendation.ticker || '未标注股票'}
                        </span>
                        <span className={`investment-rating ${getRatingClass(recommendation.rating)}`}>
                            {recommendation.rating || '中性'}
                        </span>
                    </div>
                    <dl className="investment-decision-grid">
                        <div>
                            <dt>目标价位</dt>
                            <dd>{formatTargetPrice(recommendation)}</dd>
                        </div>
                        <div>
                            <dt>持有期限</dt>
                            <dd>{recommendation.holding_period || '—'}</dd>
                        </div>
                    </dl>
                    {recommendation.core_logic && (
                        <div className="investment-decision-detail">
                            <span>核心逻辑</span>
                            <p>{recommendation.core_logic}</p>
                        </div>
                    )}
                    {recommendation.risk_warnings && (
                        <div className="investment-decision-risk">
                            <span>风险提示</span>
                            <p>{recommendation.risk_warnings}</p>
                        </div>
                    )}
                </div>
            ))}
        </section>
    );
}

export function CoordinationFlow({ messages }: CoordinationFlowProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

    // Auto-scroll to bottom when messages change
    useEffect(() => {
        if (containerRef.current) {
            containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
    }, [messages]);

    const toggleExpand = (id: string) => {
        setExpandedIds(prev => {
            const newSet = new Set(prev);
            if (newSet.has(id)) newSet.delete(id);
            else newSet.add(id);
            return newSet;
        });
    };

    const shouldTruncate = (content: string) => content.split('\n').length > MAX_COLLAPSED_LINES;
    const truncateContent = (content: string) => content.split('\n').slice(0, MAX_COLLAPSED_LINES).join('\n');

    const getAgentIcon = (name?: string) => {
        if (!name) return '🤖';
        if (name.includes('基本面')) return '📈';
        if (name.includes('估值')) return '💎';
        if (name.includes('风险')) return '🛡️';
        if (name.includes('决策') || name.includes('投资') || name.includes('顾问')) return '🧠';
        if (name.includes('会议')) return '📋';
        return '🤖';
    };

    const getTypeClass = (type: string) => {
        if (type === 'warning' || type === 'alert') return 'active';
        if (type === 'success') return 'completed';
        return '';
    };

    const getAgentBadgeClass = (name?: string) => {
        if (!name) return 'badge-default';
        if (name.includes('基本面')) return 'badge-fundamentals';
        if (name.includes('估值')) return 'badge-valuation';
        if (name.includes('风险')) return 'badge-risk';
        if (name.includes('决策') || name.includes('投资') || name.includes('顾问')) return 'badge-portfolio';
        if (name.includes('会议')) return 'badge-conference';
        return 'badge-default';
    };

    return (
        <div className="coordination-flow" ref={containerRef}>
            <div className="flow-header">
                <div className="flow-title">
                    <span>⚡ 多智能体协作流</span>
                </div>
                <div className="sync-badge">
                    <div className="sync-dot"></div>
                    实时同步中
                </div>
            </div>

            <div className="flow-timeline">
                {messages.map((msg) => {
                    const typeClass = getTypeClass(msg.type);
                    const cleanedContent = stripThinkingContent(msg.content);
                    const isExpanded = expandedIds.has(msg.id);
                    const needsTruncation = shouldTruncate(cleanedContent);
                    const displayContent = isExpanded || !needsTruncation ? cleanedContent : truncateContent(cleanedContent);
                    const recommendations = msg.agentId === 'portfolio_manager'
                        ? extractInvestmentRecommendations(cleanedContent)
                        : null;

                    return (
                        <div key={msg.id} className="timeline-item">
                            <div className="timeline-line"></div>
                            <div className={`timeline-icon ${typeClass}`}>
                                {getAgentIcon(msg.agentName)}
                            </div>
                            <div className={`timeline-content ${msg.type === 'warning' ? 'highlight' : ''}`}>
                                <div className="content-header">
                                    <div className="agent-name-row">
                                        <span className={`agent-badge ${getAgentBadgeClass(msg.agentName)}`}>
                                            {getAgentIcon(msg.agentName)}
                                        </span>
                                        <span className="agent-name">{msg.agentName}</span>
                                    </div>
                                    <span className="time-stamp">{formatTimeShort(msg.timestamp)}</span>
                                </div>
                                {recommendations ? (
                                    <InvestmentDecisionSummary recommendations={recommendations} />
                                ) : (
                                    <>
                                        <div className={`message-body agent-markdown ${!isExpanded && needsTruncation ? 'is-truncated' : ''}`}>
                                            {msg.type === 'warning' && <strong>⚠️ 警告：</strong>}
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayContent}</ReactMarkdown>
                                        </div>
                                        {needsTruncation && (
                                            <button
                                                className="expand-toggle-btn"
                                                onClick={() => toggleExpand(msg.id)}
                                            >
                                                {isExpanded ? '收起 ↑' : '展开全文 ↓'}
                                            </button>
                                        )}
                                    </>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
