/**
 * 股票列表页面组件
 */

import React, { useState, useEffect } from 'react';
import { Search, RefreshCw, Building2, ChevronLeft, ChevronRight, Zap, Terminal } from 'lucide-react';
import { companiesApi, type Company, type CompanyStatistics } from '../../services/companiesApi';

// Props for external navigation
interface StockListProps {
    onAnalyzeAI?: (ticker: string) => void;
    onAnalyzeExpert?: (ticker: string) => void;
}

export const StockList: React.FC<StockListProps> = ({ onAnalyzeAI, onAnalyzeExpert }) => {
    const [companies, setCompanies] = useState<Company[]>([]);
    const [statistics, setStatistics] = useState<CompanyStatistics | null>(null);
    const [page, setPage] = useState(1);
    const [pageSize] = useState(20);
    const [total, setTotal] = useState(0);
    const [search, setSearch] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');
    const [refreshingCodes, setRefreshingCodes] = useState<Set<string>>(new Set());
    // 右键菜单状态
    const [contextMenu, setContextMenu] = useState<{ stock: Company; x: number; y: number } | null>(null);

    // 双击行直接进入 AI 分析
    const handleRowDoubleClick = (stockCode: string) => {
        if (onAnalyzeAI) {
            onAnalyzeAI(stockCode);
        }
    };

    // 右键菜单
    const handleRowContextMenu = (e: React.MouseEvent, company: Company) => {
        e.preventDefault();
        setContextMenu({ stock: company, x: e.clientX, y: e.clientY });
    };

    const handleAnalyzeAI = (stockCode: string) => {
        setContextMenu(null);
        if (onAnalyzeAI) onAnalyzeAI(stockCode);
    };

    const handleAnalyzeExpert = (stockCode: string) => {
        setContextMenu(null);
        if (onAnalyzeExpert) onAnalyzeExpert(stockCode);
    };

    // 点击其他地方关闭菜单
    useEffect(() => {
        if (contextMenu) {
            const closeMenu = () => setContextMenu(null);
            document.addEventListener('click', closeMenu);
            return () => document.removeEventListener('click', closeMenu);
        }
    }, [contextMenu]);

    const fetchCompanies = async () => {
        setIsLoading(true);
        setError('');

        try {
            const response = await companiesApi.listCompanies(page, pageSize, search);
            setCompanies(response.items);
            setTotal(response.total);
        } catch (err) {
            setError(err instanceof Error ? err.message : '获取公司列表失败');
        } finally {
            setIsLoading(false);
        }
    };

    const fetchStatistics = async () => {
        try {
            const stats = await companiesApi.getStatistics();
            setStatistics(stats);
        } catch (err) {
            console.error('Failed to fetch statistics:', err);
        }
    };

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        setPage(1);
        fetchCompanies();
    };

    const handleRefreshQuotes = async (stockCode: string) => {
        setRefreshingCodes(prev => new Set(prev).add(stockCode));
        try {
            await companiesApi.refreshQuotes(stockCode);
            await fetchCompanies();
        } catch (err) {
            setError(err instanceof Error ? err.message : '刷新行情失败');
        } finally {
            setRefreshingCodes(prev => {
                const newSet = new Set(prev);
                newSet.delete(stockCode);
                return newSet;
            });
        }
    };

    useEffect(() => {
        fetchCompanies();
        fetchStatistics();
    }, [page]);

    const totalPages = Math.ceil(total / pageSize);

    const formatNumber = (num: number | undefined, decimals: number = 2) => {
        if (num === undefined || num === null) return '-';
        return num.toFixed(decimals);
    };

    const formatLargeNumber = (num: number | undefined) => {
        if (num === undefined || num === null) return '-';
        if (num >= 100000000) {
            return `${(num / 100000000).toFixed(2)}亿`;
        } else if (num >= 10000) {
            return `${(num / 10000).toFixed(2)}万`;
        }
        return num.toFixed(2);
    };

    return (
        <div className="h-full">
            {/* Header */}
            <div className="mb-6">
                <div className="flex items-center gap-3 mb-2">
                    <Building2 className="w-8 h-8 text-primary" />
                    <h1 className="text-2xl font-bold text-foreground">股票列表</h1>
                </div>
                <p className="text-muted-foreground">
                    查看和管理 A 股上市公司信息
                </p>
            </div>

            {/* Statistics Cards */}
            {statistics && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                    <div className="bg-card rounded-vibe border border-border p-5">
                        <div className="text-sm text-muted-foreground mb-1">股票总数</div>
                        <div className="text-3xl font-bold text-foreground">{statistics.total_count}</div>
                    </div>
                    <div className="bg-card rounded-vibe border border-border p-5">
                        <div className="text-sm text-muted-foreground mb-1">活跃股票</div>
                        <div className="text-3xl font-bold text-success">{statistics.active_count}</div>
                    </div>
                    <div className="bg-card rounded-vibe border border-border p-5">
                        <div className="text-sm text-muted-foreground mb-1">交易所分布</div>
                        <div className="flex gap-2 flex-wrap">
                            {statistics.exchange_statistics.map((stat) => (
                                <span key={stat.exchange} className="px-2 py-1 bg-brand-50 text-brand-700 rounded text-sm">
                                    {stat.exchange}: {stat.count}
                                </span>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {/* Search Bar */}
            <form onSubmit={handleSearch} className="mb-6">
                <div className="flex gap-3">
                    <div className="flex-1 relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground w-5 h-5" />
                        <input
                            type="text"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder="搜索股票代码或名称..."
                            className="w-full pl-10 pr-4 py-2 border border-input rounded-vibe-sm focus:ring-2 focus:ring-ring focus:border-transparent"
                        />
                    </div>
                    <button
                        type="submit"
                        className="px-6 py-2 bg-primary text-primary-foreground rounded-vibe-sm hover:bg-brand-700 transition-colors font-medium"
                    >
                        搜索
                    </button>
                </div>
            </form>

            {/* Error Message */}
            {error && (
                <div className="bg-[rgba(239,68,68,0.06)] border border-[rgba(239,68,68,0.2)] rounded-vibe p-4 mb-6 text-destructive">
                    {error}
                </div>
            )}

            {/* Loading State */}
            {isLoading && (
                <div className="flex items-center justify-center py-12">
                    <RefreshCw className="w-8 h-8 text-primary animate-spin" />
                </div>
            )}

            {/* Company Table */}
            {!isLoading && (
                <div className="bg-card rounded-vibe border border-border overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-muted border-b border-border">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">代码</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">名称</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">交易所</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">行业</th>
                                    <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">当前价格</th>
                                    <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">市值</th>
                                    <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">市盈率</th>
                                    <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">市净率</th>
                                    <th className="px-6 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">操作</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border">
                                {companies.map((company) => (
                                    <tr
                                        key={company.stock_code}
                                        className="hover:bg-muted transition-colors cursor-pointer"
                                        onDoubleClick={() => handleRowDoubleClick(company.stock_code)}
                                        onContextMenu={(e) => handleRowContextMenu(e, company)}
                                    >
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-primary">
                                            {company.stock_code}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                                            {company.stock_name}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                                            {company.exchange_name || '-'}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                                            {company.industry_name || '-'}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-foreground">
                                            {formatNumber(company.current_price)}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-muted-foreground">
                                            {formatLargeNumber(company.market_cap)}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-muted-foreground">
                                            {formatNumber(company.pe_ratio)}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-muted-foreground">
                                            {formatNumber(company.pb_ratio)}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-center">
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleRefreshQuotes(company.stock_code);
                                                }}
                                                disabled={refreshingCodes.has(company.stock_code)}
                                                className="p-2 text-primary hover:bg-brand-50 rounded-vibe-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                                title="刷新行情"
                                            >
                                                <RefreshCw className={`w-4 h-4 ${refreshingCodes.has(company.stock_code) ? 'animate-spin' : ''}`} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                                {companies.length === 0 && (
                                    <tr>
                                        <td colSpan={9} className="px-6 py-12 text-center text-muted-foreground">
                                            暂无数据
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>

                    {/* 右键菜单 */}
                    {contextMenu && (
                        <div
                            className="fixed bg-card border border-border rounded-vibe-sm shadow-xl z-50 py-1 w-48"
                            style={{ left: contextMenu.x, top: contextMenu.y }}
                        >
                            <button
                                className="w-full px-4 py-2 text-left text-sm text-foreground hover:bg-brand-50 hover:text-brand-700 flex items-center gap-2"
                                onClick={() => handleAnalyzeAI(contextMenu.stock.stock_code)}
                            >
                                <Zap className="w-4 h-4" />
                                AI 智能分析
                            </button>
                            <button
                                className="w-full px-4 py-2 text-left text-sm text-foreground hover:bg-brand-50 hover:text-brand-700 flex items-center gap-2"
                                onClick={() => handleAnalyzeExpert(contextMenu.stock.stock_code)}
                            >
                                <Terminal className="w-4 h-4" />
                                专家深度分析
                            </button>
                            <hr className="my-1 border-border" />
                            <button
                                className="w-full px-4 py-2 text-left text-sm text-foreground hover:bg-brand-50 hover:text-brand-700 flex items-center gap-2"
                                onClick={() => handleRefreshQuotes(contextMenu.stock.stock_code)}
                            >
                                <RefreshCw className="w-4 h-4" />
                                刷新行情
                            </button>
                        </div>
                    )}

                    {/* 双击提示 */}
                    <div className="px-6 py-3 bg-muted border-t border-border text-xs text-muted-foreground text-center">
                        双击股票行可快速进入 AI 分析 · 右键查看更多操作
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div className="flex items-center justify-between px-6 py-4 bg-muted border-t border-border">
                            <div className="text-sm text-muted-foreground">
                                第 {page} 页，共 {totalPages} 页，总计 {total} 条记录
                            </div>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => setPage(p => Math.max(1, p - 1))}
                                    disabled={page === 1}
                                    className="flex items-center gap-1 px-3 py-1 border border-input rounded-vibe-sm hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                                >
                                    <ChevronLeft className="w-4 h-4" />
                                    上一页
                                </button>
                                <button
                                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                                    disabled={page === totalPages}
                                    className="flex items-center gap-1 px-3 py-1 border border-input rounded-vibe-sm hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                                >
                                    下一页
                                    <ChevronRight className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
