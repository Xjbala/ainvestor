/**
 * 任务列表组件
 *
 * 支持多种Tab类型：
 * - 'stock': 股票数据（company_list, stock_price）
 * - 'financial': 财务报表（balance_sheet, income_statement, cash_flow）
 * - 'batch': 批量采集（batch_financial_data）
 * - 'qualitative': 定性数据（qualitative_report）
 * - 'news': 新闻舆情（news_sentiment）
 */

import React, { useEffect, useState, useRef } from 'react';
import { RefreshCw, AlertCircle, Loader2 } from 'lucide-react';
import { crawlerApi, type Task } from '../../services/crawlerApi';
import { TaskCard } from './TaskCard';

type ActiveTabType = 'stock' | 'financial' | 'batch' | 'qualitative' | 'news';

interface TaskListProps {
    activeTab: ActiveTabType;
    onRefresh?: () => void;
    showBatchTab?: boolean;
}

export const TaskList: React.FC<TaskListProps> = ({ activeTab, onRefresh }) => {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetchTasks = async () => {
        setIsLoading(true);
        setError('');

        try {
            const response = await crawlerApi.getTasks(0, 50);
            setTasks(response.tasks);
        } catch (err) {
            setError(err instanceof Error ? err.message : '获取任务列表失败');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchTasks();
    }, [activeTab]);

    // Auto-refresh for running tasks
    useEffect(() => {
        // Clear previous interval
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }

        // Check if any task is running
        const hasRunningTasks = tasks.some(t => t.status === 'running');
        if (hasRunningTasks) {
            intervalRef.current = setInterval(fetchTasks, 5000); // Refresh every 5 seconds
        }

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }
        };
    }, [tasks]);

    const handleRefresh = () => {
        fetchTasks();
        onRefresh?.();
    };

    const handleCancel = async (taskId: string) => {
        const confirmed = window.confirm('确定要取消这个任务吗？');
        if (!confirmed) return;

        try {
            await crawlerApi.cancelTask(taskId);
            fetchTasks();
        } catch (err) {
            setError(err instanceof Error ? err.message : '取消任务失败');
        }
    };

    const handleDelete = async (taskId: string) => {
        const confirmed = window.confirm('确定要删除这个任务吗？此操作不可恢复。');
        if (!confirmed) return;

        try {
            await crawlerApi.deleteTask(taskId);
            fetchTasks();
        } catch (err) {
            setError(err instanceof Error ? err.message : '删除任务失败');
        }
    };

    // Filter tasks based on active tab
    const filteredTasks = tasks.filter(task => {
        switch (activeTab) {
            case 'stock':
                return task.data_type === 'company_list' || task.data_type === 'stock_price';
            case 'financial':
                return task.data_type === 'balance_sheet' ||
                       task.data_type === 'income_statement' ||
                       task.data_type === 'cash_flow' ||
                       task.data_type === 'batch_financial_data';
            case 'batch':
                return task.data_type === 'batch_financial_data';
            case 'qualitative':
                return task.data_type === 'qualitative_report';
            case 'news':
                return task.data_type === 'news_sentiment';
            default:
                return true;
        }
    });

    // Sort by creation date (newest first)
    const sortedTasks = [...filteredTasks].sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

    // Count running tasks for display
    const runningCount = sortedTasks.filter(t => t.status === 'running').length;

    if (isLoading && tasks.length === 0) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="text-center">
                    <Loader2 className="w-8 h-8 text-primary animate-spin mx-auto mb-3" />
                    <p className="text-muted-foreground">加载中...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-[rgba(239,68,68,0.06)] border border-[rgba(239,68,68,0.2)] rounded-vibe p-6 text-center">
                <AlertCircle className="w-8 h-8 text-destructive mx-auto mb-3" />
                <p className="text-destructive mb-3">{error}</p>
                <button
                    onClick={handleRefresh}
                    className="px-4 py-2 bg-[rgba(239,68,68,0.12)] text-destructive rounded-vibe-sm hover:bg-[rgba(239,68,68,0.2)] transition-colors"
                >
                    重试
                </button>
            </div>
        );
    }

    if (sortedTasks.length === 0) {
        return (
            <div className="text-center py-12">
                <p className="text-muted-foreground mb-4">暂无任务</p>
                <button
                    onClick={handleRefresh}
                    className="px-4 py-2 bg-brand-50 text-primary rounded-vibe-sm hover:bg-brand-100 transition-colors"
                >
                    刷新
                </button>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-muted-foreground">
                    共 {sortedTasks.length} 个任务
                    {runningCount > 0 && (
                        <span className="ml-2 inline-flex items-center gap-1 text-primary">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            {runningCount} 个执行中
                        </span>
                    )}
                </p>
                <button
                    onClick={handleRefresh}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:bg-muted rounded-vibe-sm transition-colors"
                >
                    <RefreshCw className="w-4 h-4" />
                    刷新
                </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {sortedTasks.map(task => (
                    <TaskCard
                        key={task.id}
                        task={task}
                        onCancel={handleCancel}
                        onDelete={handleDelete}
                    />
                ))}
            </div>
        </div>
    );
};
