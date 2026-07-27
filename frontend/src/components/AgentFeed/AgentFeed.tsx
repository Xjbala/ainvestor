/**
 * Agent Feed - 智能体实时动态流
 * Modernist Grid (Vignelli) + Fluid Data (Anadol)
 */

import { useState } from 'react';
import {
    BrainCircuit,
    BarChart2,
    Calculator,
    TrendingUp,
    Target,
    ShieldCheck,
    Briefcase,
    FileText,
    Bot,
    ChevronUp,
    ChevronDown
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ConferenceMessage } from '../../types/message';
import Card from '../Common/Card';
import Badge from '../Common/Badge';
import Button from '../Common/Button';
import './AgentFeed.css';

interface AgentFeedProps {
    messages: ConferenceMessage[];
}

const MAX_COLLAPSED_LINES = 10;

export function AgentFeed({ messages }: AgentFeedProps) {
    const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());


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

    return (
        <div className="agent-feed-container">
            {/* Minimalist Header */}
            <div className="feed-header-v2">
                <div className="feed-header-content">
                    <h1 className="feed-title-v2">智能体动态流</h1>
                    <div className="feed-status-v2">
                        <span className="pulse-dot"></span>
                        <span className="mono">实时综合分析</span>
                    </div>
                </div>
                <div className="feed-meta mono">
                    共 {messages.length} 条记录
                </div>
            </div>

            <div className="feed-scroller">
                {messages.length === 0 ? (
                    <div className="feed-empty-v2">
                        <BrainCircuit size={48} className="empty-icon-v2" />
                        <h3 className="mono">等待输入</h3>
                        <p>分析开始后，此处将实时载入智能体动态。</p>
                    </div>
                ) : (
                    <div className="feed-list-v2">
                        {messages.map((msg) => {
                            const isExpanded = expandedIds.has(msg.id);
                            const needsTruncation = shouldTruncate(msg.content);
                            const displayContent = isExpanded || !needsTruncation ? msg.content : truncateContent(msg.content);

                            return (
                                <Card
                                    key={msg.id}
                                    variant="glass"
                                    padding="lg"
                                    className={`feed-card-v2 phase-${msg.phase || 'default'}`}
                                    title={
                                        <div className="agent-identity">
                                            <div className="agent-avatar">
                                                {(() => {
                                                    const Icon = getAgentIcon(msg.agent_id);
                                                    return <Icon size={20} />;
                                                })()}
                                            </div>
                                            <div className="agent-info">
                                                <span className="agent-name-v2 mono">{getAgentName(msg.agent_id)}</span>
                                                <div className="agent-meta-v2">
                                                    <Badge variant={msg.phase === 'conference' ? 'primary' : 'neutral'} pill>
                                                        {getPhaseLabel(msg.phase || '')}
                                                    </Badge>
                                                    <span className="mono timestamp-v2">{formatTime(msg.timestamp)}</span>
                                                </div>
                                            </div>
                                        </div>
                                    }
                                >
                                    <div className={`message-body markdown-content ${!isExpanded && needsTruncation ? 'is-truncated' : ''}`}>
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayContent}</ReactMarkdown>
                                    </div>

                                    {needsTruncation && (
                                        <div className="card-actions-v2">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => toggleExpand(msg.id)}
                                                className="expand-toggle"
                                            >
                                                {isExpanded ? '收起' : '展开全文'}
                                                {isExpanded ? <ChevronUp size={14} style={{ marginLeft: '4px' }} /> : <ChevronDown size={14} style={{ marginLeft: '4px' }} />}
                                            </Button>
                                        </div>
                                    )}
                                </Card>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}

function getAgentIcon(agentId: string): LucideIcon {
    const icons: Record<string, LucideIcon> = {
        fundamentals_analyst: BarChart2,
        valuation_analyst: Calculator,
        technical_analyst: TrendingUp,
        sentiment_analyst: Target,
        risk_manager: ShieldCheck,
        portfolio_manager: Briefcase,
        conference_summary: FileText,
    };
    return icons[agentId] || Bot;
}

function getAgentName(agentId: string): string {
    const names: Record<string, string> = {
        fundamentals_analyst: '基本面分析专家',
        valuation_analyst: '估值核心专家',
        technical_analyst: '量化技术专家',
        sentiment_analyst: '情绪监测专家',
        risk_manager: '风险管理专家',
        portfolio_manager: '决策中心专家',
        conference_summary: '会议总结专家',
    };
    return names[agentId] || agentId.toUpperCase();
}

function getPhaseLabel(phase: string): string {
    return phase === 'analysis' ? '核心分析' : '委员会讨论';
}

function formatTime(timestamp: string): string {
    try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch { return '--:--:--'; }
}