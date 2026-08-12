/**
 * 报告页面组件
 *
 * 展示所有历史分析报告，支持预览、筛选和导出。
 */

import React, { useState, useEffect } from 'react';
import { FileText, Clock, Search, RefreshCw, ExternalLink, Eye, ChevronLeft, ChevronRight, Trash2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { stripThinkingContent } from '../../utils/reportUtils';

interface ReportItem {
    id: string;
    tickers: string[];
    date: string;
    status: string;
    mode: string;
    created_at: string;
    completed_at?: string;
    report_content?: string;
    recommendation?: string;
    targetPrice?: string;
}

export const ReportsPage: React.FC<{ onSwitchMode?: (mode: 'dashboard' | 'ai' | 'expert') => void }> = () => {
    const [reports, setReports] = useState<ReportItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState<string>('all');
    const [previewReport, setPreviewReport] = useState<ReportItem | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const pageSize = 20;

    const fetchReports = async () => {
        setLoading(true);
        setError('');
        try {
            const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            // 获取最近 N 个会话
            const sessionsRes = await fetch(`${API_URL}/api/sessions?limit=${pageSize * 3}`);
            if (!sessionsRes.ok) throw new Error('获取报告列表失败');
            const sessions = await sessionsRes.json();

            // 并行获取每个会话的报告
            const reportsWithContent: ReportItem[] = [];
            for (const session of sessions) {
                if (session.status === 'completed') {
                    try {
                        const reportRes = await fetch(`${API_URL}/api/sessions/${session.id}/report`);
                        let reportContent = '';
                        if (reportRes.ok) {
                            const reportData = await reportRes.json();
                            reportContent = stripThinkingContent(reportData.report_content || '');
                        }
                        reportsWithContent.push({
                            ...session,
                            report_content: reportContent,
                        });
                    } catch {
                        // Skip sessions without reports
                    }
                } else {
                    reportsWithContent.push({ ...session });
                }
            }

            setReports(reportsWithContent);
        } catch (err) {
            setError(err instanceof Error ? err.message : '获取报告列表失败');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchReports();
    }, []);

    const deleteReport = async (report: ReportItem) => {
        if (report.status === 'running' || report.status === 'pending') return;
        if (!window.confirm(`删除 ${report.tickers.join(', ')} 的这条分析记录？此操作不可恢复。`)) {
            return;
        }

        setDeletingId(report.id);
        try {
            const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const response = await fetch(`${API_URL}/api/sessions/${report.id}`, {
                method: 'DELETE',
            });
            if (!response.ok) {
                throw new Error(`删除失败: ${response.status}`);
            }
            setReports((current) => current.filter((item) => item.id !== report.id));
            if (previewReport?.id === report.id) setPreviewReport(null);
        } catch (error) {
            console.error('[ReportsPage] Failed to delete session:', error);
            setError('删除分析记录失败，请重试');
        } finally {
            setDeletingId(null);
        }
    };

    // 从报告内容中提取关键指标
    const extractRecommendation = (content: string): string => {
        if (!content) return '—';
        const match = content.match(/投资评级[：:]\s*(\S+)/);
        if (match) return match[1];
        return '—';
    };

    const extractTargetPrice = (content: string): string => {
        if (!content) return '—';
        const match = content.match(/目标价[位]?[：:]\s*[¥￥]?\s*([\d.]+)/);
        if (match) return `¥${match[1]}`;
        return '—';
    };

    // 过滤和搜索
    const filteredReports = reports.filter(r => {
        const matchesSearch = searchTerm
            ? r.tickers.some(t => t.includes(searchTerm)) ||
              extractRecommendation(r.report_content || '').includes(searchTerm)
            : true;
        const matchesStatus = statusFilter === 'all' || r.status === statusFilter;
        return matchesSearch && matchesStatus;
    });

    const totalPages = Math.ceil(filteredReports.length / pageSize);
    const paginatedReports = filteredReports.slice((page - 1) * pageSize, page * pageSize);

    const formatTimeAgo = (dateString: string) => {
        const now = new Date();
        const date = new Date(dateString);
        const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
        if (seconds < 60) return '刚刚';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟前`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}小时前`;
        if (seconds < 2592000) return `${Math.floor(seconds / 86400)}天前`;
        return date.toLocaleDateString('zh-CN');
    };

    const getStatusBadge = (status: string) => {
        const map: Record<string, { label: string; color: string; bg: string }> = {
            completed: { label: '已完成', color: 'text-success', bg: 'bg-[rgba(19,177,90,0.06)]' },
            running: { label: '分析中', color: 'text-brand-700', bg: 'bg-brand-50' },
            failed: { label: '失败', color: 'text-destructive', bg: 'bg-[rgba(239,68,68,0.06)]' },
            cancelled: { label: '已取消', color: 'text-muted-foreground', bg: 'bg-muted' },
        };
        const s = map[status] || { label: status, color: 'text-muted-foreground', bg: 'bg-muted' };
        return (
            <span className={`px-2 py-0.5 text-xs rounded font-medium ${s.bg} ${s.color}`}>
                {s.label}
            </span>
        );
    };

    return (
        <div className="h-full">
            {/* Header */}
            <div className="mb-6">
                <div className="flex items-center gap-3 mb-2">
                    <FileText className="w-8 h-8 text-primary" />
                    <h1 className="text-2xl font-bold text-foreground">投资分析报告</h1>
                </div>
                <p className="text-muted-foreground">查看和管理所有 AI 生成的投资决策报告</p>
            </div>

            {/* Filters */}
            <div className="flex gap-3 mb-6 items-center">
                <div className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground w-4 h-4" />
                    <input
                        type="text"
                        placeholder="搜索股票代码或评级..."
                        value={searchTerm}
                        onChange={(e) => { setSearchTerm(e.target.value); setPage(1); }}
                        className="w-full pl-9 pr-4 py-2 border border-input rounded-vibe-sm focus:ring-2 focus:ring-ring focus:border-transparent text-sm"
                    />
                </div>
                <select
                    value={statusFilter}
                    onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                    className="px-3 py-2 border border-input rounded-vibe-sm text-sm focus:ring-2 focus:ring-ring"
                >
                    <option value="all">全部状态</option>
                    <option value="completed">已完成</option>
                    <option value="running">分析中</option>
                    <option value="failed">失败</option>
                </select>
                <button
                    onClick={fetchReports}
                    className="px-3 py-2 text-muted-foreground hover:bg-muted rounded-vibe-sm transition-colors"
                    title="刷新"
                >
                    <RefreshCw className="w-4 h-4" />
                </button>
            </div>

            {/* Content */}
            {loading ? (
                <div className="flex items-center justify-center py-12">
                    <RefreshCw className="w-8 h-8 text-primary animate-spin" />
                </div>
            ) : error ? (
                <div className="bg-[rgba(239,68,68,0.06)] border border-[rgba(239,68,68,0.2)] rounded-vibe p-6 text-center text-destructive">{error}</div>
            ) : paginatedReports.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                    <FileText className="w-12 h-12 mx-auto mb-3 text-muted-foreground" />
                    <p>暂无分析报告</p>
                    <p className="text-sm mt-1">在 AI 分析模式下生成报告后将在此显示</p>
                </div>
            ) : (
                <>
                    <div className="bg-card rounded-vibe border border-border overflow-hidden">
                        <table className="w-full">
                            <thead className="bg-muted border-b border-border">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">股票代码</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">状态</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">评级</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">目标价</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">模式</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">时间</th>
                                    <th className="px-6 py-3 text-center text-xs font-medium text-muted-foreground uppercase">操作</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border">
                                {paginatedReports.map((report) => (
                                    <tr key={report.id} className="hover:bg-muted transition-colors">
                                        <td className="px-6 py-4 text-sm font-medium text-primary">
                                            {report.tickers.join(', ')}
                                        </td>
                                        <td className="px-6 py-4">{getStatusBadge(report.status)}</td>
                                        <td className="px-6 py-4 text-sm text-foreground">
                                            {report.status === 'completed' ? extractRecommendation(report.report_content || '') : '—'}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-foreground">
                                            {report.status === 'completed' ? extractTargetPrice(report.report_content || '') : '—'}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-muted-foreground">
                                            {report.mode === 'expert' ? '专家模式' : 'AI分析'}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-muted-foreground">
                                            <Clock className="w-3 h-3 inline mr-1" />
                                            {formatTimeAgo(report.created_at)}
                                        </td>
                                        <td className="px-6 py-4 text-center">
                                            <button
                                                onClick={() => setPreviewReport(report)}
                                                disabled={report.status !== 'completed' || !report.report_content}
                                                className="p-1.5 text-primary hover:bg-brand-50 rounded-vibe-sm transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                                                title="预览报告"
                                            >
                                                <Eye className="w-4 h-4" />
                                            </button>
                                            <button
                                                onClick={() => void deleteReport(report)}
                                                disabled={report.status === 'running' || report.status === 'pending' || deletingId === report.id}
                                                className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-vibe-sm transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                                                title={report.status === 'running' || report.status === 'pending' ? '运行中的分析不能删除' : '删除分析记录'}
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div className="flex items-center justify-between mt-4 px-2">
                            <div className="text-sm text-muted-foreground">
                                第 {page} 页，共 {totalPages} 页
                            </div>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => setPage(p => Math.max(1, p - 1))}
                                    disabled={page === 1}
                                    className="px-3 py-1 border border-input rounded-vibe-sm hover:bg-muted disabled:opacity-50 text-sm"
                                >
                                    <ChevronLeft className="w-4 h-4" />
                                </button>
                                <button
                                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                                    disabled={page === totalPages}
                                    className="px-3 py-1 border border-input rounded-vibe-sm hover:bg-muted disabled:opacity-50 text-sm"
                                >
                                    <ChevronRight className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    )}
                </>
            )}

            {/* Preview Modal */}
            {previewReport && (
                <div className="fixed inset-0 bg-[rgba(59,53,43,0.5)] flex items-center justify-center z-50 p-4" onClick={() => setPreviewReport(null)}>
                    <div
                        className="bg-card rounded-vibe shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Modal Header */}
                        <div className="flex items-center justify-between p-6 border-b border-border bg-muted">
                            <div>
                                <h2 className="text-xl font-bold text-foreground">
                                    投资分析报告 — {previewReport.tickers.join(', ')}
                                </h2>
                                <p className="text-sm text-muted-foreground mt-1">
                                    {previewReport.mode === 'expert' ? '专家模式' : 'AI分析'} · {formatTimeAgo(previewReport.created_at)}
                                </p>
                            </div>
                            <button
                                onClick={() => setPreviewReport(null)}
                                className="p-2 hover:bg-border rounded-vibe-sm transition-colors"
                            >
                                <ExternalLink className="w-5 h-5 rotate-45 text-muted-foreground" />
                            </button>
                        </div>

                        {/* Modal Body */}
                        <div className="flex-1 overflow-y-auto p-6">
                            {previewReport.report_content ? (
                                <div className="prose prose-sm max-w-none">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                        {stripThinkingContent(previewReport.report_content)}
                                    </ReactMarkdown>
                                </div>
                            ) : (
                                <div className="text-center py-12 text-muted-foreground">暂无报告内容</div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
