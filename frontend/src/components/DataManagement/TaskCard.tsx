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
        color: 'text-gray-600',
        bgColor: 'bg-gray-100',
        icon: <Clock className="w-4 h-4" />,
    },
    running: {
        label: '执行中',
        color: 'text-blue-600',
        bgColor: 'bg-blue-100',
        icon: <Loader2 className="w-4 h-4 animate-spin" />,
    },
    success: {
        label: '已完成',
        color: 'text-green-600',
        bgColor: 'bg-green-100',
        icon: <CheckCircle2 className="w-4 h-4" />,
    },
    completed: {
        label: '已完成',
        color: 'text-green-600',
        bgColor: 'bg-green-100',
        icon: <CheckCircle2 className="w-4 h-4" />,
    },
    failed: {
        label: '失败',
        color: 'text-red-600',
        bgColor: 'bg-red-100',
        icon: <XCircle className="w-4 h-4" />,
    },
    cancelled: {
        label: '已取消',
        color: 'text-gray-500',
        bgColor: 'bg-gray-100',
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
        <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
            {/* Header */}
            <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 mb-1">{task.task_name}</h3>
                    <div className="flex items-center gap-2 flex-wrap">
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium ${statusConfig.bgColor} ${statusConfig.color}`}>
                            {statusConfig.icon}
                            {statusConfig.label}
                        </span>
                        <span className="text-xs text-gray-500">
                            {DATA_TYPE_LABELS[task.data_type] || task.data_type}
                        </span>
                        {task.target_companies && task.target_companies.length > 0 && (
                            <span className="text-xs text-gray-400">
                                目标: {task.target_companies.slice(0, 3).join(',')}
                                {task.target_companies.length > 3 ? ` +${task.target_companies.length - 3}` : ''}
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* Progress */}
            <div className="mb-4">
                <div className="flex justify-between text-sm text-gray-600 mb-1">
                    <span>进度</span>
                    <span>{Number(task.progress || 0).toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-blue-600 rounded-full transition-all duration-300"
                        style={{ width: `${Math.min(100, Number(task.progress || 0))}%` }}
                    />
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-3 mb-4 text-center">
                <div className="bg-gray-50 rounded-lg p-2">
                    <div className="text-lg font-semibold text-gray-900">{task.total_count}</div>
                    <div className="text-xs text-gray-500">总数</div>
                </div>
                <div className="bg-green-50 rounded-lg p-2">
                    <div className="text-lg font-semibold text-green-600">{task.success_count}</div>
                    <div className="text-xs text-gray-500">成功</div>
                </div>
                <div className="bg-red-50 rounded-lg p-2">
                    <div className="text-lg font-semibold text-red-600">{task.error_count}</div>
                    <div className="text-xs text-gray-500">失败</div>
                </div>
            </div>

            {/* Time Info */}
            <div className="text-xs text-gray-500 space-y-1 mb-4">
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
                <div className="mb-4 border border-gray-100 rounded-lg overflow-hidden">
                    <button
                        type="button"
                        onClick={() => setShowLog(v => !v)}
                        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 text-sm text-gray-700"
                    >
                        <span className="font-medium">执行明细</span>
                        {showLog ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                    {!showLog && (
                        <pre className="px-3 py-2 text-[11px] leading-relaxed text-gray-500 bg-white whitespace-pre-wrap break-words max-h-16 overflow-hidden">
                            {logPreview}
                        </pre>
                    )}
                    {showLog && (
                        <pre className="px-3 py-2 text-[11px] leading-relaxed text-gray-700 bg-slate-950 text-slate-100 whitespace-pre-wrap break-words max-h-64 overflow-auto">
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
                        className="flex-1 px-3 py-2 bg-yellow-50 text-yellow-700 rounded-lg hover:bg-yellow-100 transition-colors text-sm font-medium"
                    >
                        取消任务
                    </button>
                )}
                {canDelete && (
                    <button
                        onClick={() => onDelete(task.id)}
                        className="flex-1 px-3 py-2 bg-red-50 text-red-700 rounded-lg hover:bg-red-100 transition-colors text-sm font-medium flex items-center justify-center gap-1"
                    >
                        <Trash2 className="w-4 h-4" />
                        删除
                    </button>
                )}
            </div>
        </div>
    );
};