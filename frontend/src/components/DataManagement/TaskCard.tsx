/**
 * 任务卡片组件
 */

import React, { useMemo, useState } from 'react';
import { Clock, CheckCircle2, XCircle, Loader2, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import { type Task } from '../../services/crawlerApi';

interface TaskCardProps {
    task: Task;
    onCancel: (taskId: string) => void;
    onDelete: (taskId: string) => void;
}

const DATA_TYPE_LABELS: Record<string, string> = {
    company_list: '股票列表',
    balance_sheet: '资产负债表',
    income_statement: '利润表',
    cash_flow: '现金流量表',
    stock_price: '股票价格',
    batch_financial_data: '全量批量采集',
    qualitative_report: '年报/季报PDF',
    news_sentiment: '新闻舆情',
};

const STATUS_CONFIG: Record<string, { label: string; color: string; bgColor: string; icon: React.ReactNode }> = {
    pending: {
        label: '等待中',
        color: 'text-muted-foreground',
        bgColor: 'bg-muted',
        icon: <Clock className="w-4 h-4" />,
    },
    running: {
        label: '执行中',
        color: 'text-primary',
        bgColor: 'bg-brand-100',
        icon: <Loader2 className="w-4 h-4 animate-spin" />,
    },
    success: {
        label: '已完成',
        color: 'text-success',
        bgColor: 'bg-[rgba(19,177,90,0.12)]',
        icon: <CheckCircle2 className="w-4 h-4" />,
    },
    completed: {
        label: '已完成',
        color: 'text-success',
        bgColor: 'bg-[rgba(19,177,90,0.12)]',
        icon: <CheckCircle2 className="w-4 h-4" />,
    },
    failed: {
        label: '失败',
        color: 'text-destructive',
        bgColor: 'bg-[rgba(239,68,68,0.12)]',
        icon: <XCircle className="w-4 h-4" />,
    },
    cancelled: {
        label: '已取消',
        color: 'text-muted-foreground',
        bgColor: 'bg-muted',
        icon: <XCircle className="w-4 h-4" />,
    },
};

export const TaskCard: React.FC<TaskCardProps> = ({ task, onCancel, onDelete }) => {
    const [showLog, setShowLog] = useState(false);
    const statusConfig = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
    const canCancel = task.status === 'pending' || task.status === 'running';
    const canDelete = task.status !== 'running';
    const detailLog = task.detail_log?.trim() || '';
    const hasLog = detailLog.length > 0;

    const logPreview = useMemo(() => {
        if (!detailLog) return '';
        const lines = detailLog.split('\n').filter(Boolean);
        return lines.slice(-3).join('\n');
    }, [detailLog]);

    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    return (
        <div className="bg-card rounded-vibe border border-border p-5 hover:shadow-md transition-shadow">
            {/* Header */}
            <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                    <h3 className="font-semibold text-foreground mb-1">{task.task_name}</h3>
                    <div className="flex items-center gap-2 flex-wrap">
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium ${statusConfig.bgColor} ${statusConfig.color}`}>
                            {statusConfig.icon}
                            {statusConfig.label}
                        </span>
                        <span className="text-xs text-muted-foreground">
                            {DATA_TYPE_LABELS[task.data_type] || task.data_type}
                        </span>
                        {task.target_companies && task.target_companies.length > 0 && (
                            <span className="text-xs text-muted-foreground">
                                目标: {task.target_companies.slice(0, 3).join(',')}
                                {task.target_companies.length > 3 ? ` +${task.target_companies.length - 3}` : ''}
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* Progress */}
            <div className="mb-4">
                <div className="flex justify-between text-sm text-muted-foreground mb-1">
                    <span>进度</span>
                    <span>{Number(task.progress || 0).toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-border rounded-full overflow-hidden">
                    <div
                        className="h-full bg-primary rounded-full transition-all duration-300"
                        style={{ width: `${Math.min(100, Number(task.progress || 0))}%` }}
                    />
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-3 mb-4 text-center">
                <div className="bg-muted rounded-vibe-sm p-2">
                    <div className="text-lg font-semibold text-foreground">{task.total_count}</div>
                    <div className="text-xs text-muted-foreground">总数</div>
                </div>
                <div className="bg-[rgba(19,177,90,0.06)] rounded-vibe-sm p-2">
                    <div className="text-lg font-semibold text-success">{task.success_count}</div>
                    <div className="text-xs text-muted-foreground">成功</div>
                </div>
                <div className="bg-[rgba(239,68,68,0.06)] rounded-vibe-sm p-2">
                    <div className="text-lg font-semibold text-destructive">{task.error_count}</div>
                    <div className="text-xs text-muted-foreground">失败</div>
                </div>
            </div>

            {/* Time Info */}
            <div className="text-xs text-muted-foreground space-y-1 mb-4">
                <div className="flex justify-between">
                    <span>创建时间:</span>
                    <span>{formatDate(task.created_at)}</span>
                </div>
                {task.started_at && (
                    <div className="flex justify-between">
                        <span>开始时间:</span>
                        <span>{formatDate(task.started_at)}</span>
                    </div>
                )}
                {task.completed_at && (
                    <div className="flex justify-between">
                        <span>完成时间:</span>
                        <span>{formatDate(task.completed_at)}</span>
                    </div>
                )}
            </div>

            {/* Detail Log */}
            {hasLog && (
                <div className="mb-4 border border-border rounded-vibe-sm overflow-hidden">
                    <button
                        type="button"
                        onClick={() => setShowLog(v => !v)}
                        className="w-full flex items-center justify-between px-3 py-2 bg-muted hover:bg-muted text-sm text-foreground"
                    >
                        <span className="font-medium">执行明细</span>
                        {showLog ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                    {!showLog && (
                        <pre className="px-3 py-2 text-[11px] leading-relaxed text-muted-foreground bg-card whitespace-pre-wrap break-words max-h-16 overflow-hidden">
                            {logPreview}
                        </pre>
                    )}
                    {showLog && (
                        <pre className="px-3 py-2 text-[11px] leading-relaxed text-foreground bg-[#1e1a16] text-[#f2ede7] whitespace-pre-wrap break-words max-h-64 overflow-auto">
                            {detailLog}
                        </pre>
                    )}
                </div>
            )}

            {/* Actions */}
            <div className="flex gap-2">
                {canCancel && (
                    <button
                        onClick={() => onCancel(task.id)}
                        className="flex-1 px-3 py-2 bg-[rgba(244,179,102,0.1)] text-warning rounded-vibe-sm hover:bg-[rgba(244,179,102,0.15)] transition-colors text-sm font-medium"
                    >
                        取消任务
                    </button>
                )}
                {canDelete && (
                    <button
                        onClick={() => onDelete(task.id)}
                        className="flex-1 px-3 py-2 bg-[rgba(239,68,68,0.06)] text-destructive rounded-vibe-sm hover:bg-[rgba(239,68,68,0.12)] transition-colors text-sm font-medium flex items-center justify-center gap-1"
                    >
                        <Trash2 className="w-4 h-4" />
                        删除
                    </button>
                )}
            </div>
        </div>
    );
};
