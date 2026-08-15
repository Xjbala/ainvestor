/**
 * 工作台（Dashboard）组件
 *
 * 用户入口页面：搜索股票代码、选择分析模式、查看最近分析记录。
 * 样式对齐 Golden Time 浅色主题：暖白底 + 深棕主色 + 32px 大圆角。
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, Zap, Terminal, ArrowRight, Clock, ChevronRight, Trash2 } from 'lucide-react';
import { createStartAnalysisCommand } from '../../hooks/useWebSocket';
import { valuationApi } from '../../services/analysisApi';
import { QuotaExceededError } from '../../services/authApi';
import { companiesApi, type Company } from '../../services/companiesApi';
import { QuotaBadge } from '../Common/QuotaBadge';
import { useToast } from '../Common/Toast';
import { openAuthModal } from '../Common/AuthModal';
import { useEntitlementsStore } from '../../stores/entitlementsStore';

interface WorkstationProps {
    onSwitchMode: (mode: 'dashboard' | 'ai' | 'expert' | 'reports' | 'account', ticker?: string) => void;
    onSendCommand: (command: object) => void;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    dispatch: React.Dispatch<any>;
}

interface SessionRecord {
    id: string;
    tickers: string[];
    date: string;
    status: string;
    created_at: string;
    mode?: string;
}

export function Workstation({ onSwitchMode, onSendCommand, dispatch }: WorkstationProps) {
    const [searchInput, setSearchInput] = useState('');
    const [sessions, setSessions] = useState<SessionRecord[]>([]);
    const [loadingSessions, setLoadingSessions] = useState(false);
    const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
    // 搜索联想状态
    const [suggestions, setSuggestions] = useState<Company[]>([]);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [loadingSuggestions, setLoadingSuggestions] = useState(false);
    const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const searchRef = useRef<HTMLDivElement>(null);
    const toast = useToast();
    const refreshEntitlements = useEntitlementsStore((s) => s.refresh);

    // 点击外部关闭联想下拉
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
                setShowSuggestions(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    // 获取最近分析记录
    const fetchSessions = async () => {
        setLoadingSessions(true);
        try {
            const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const res = await fetch(`${API_URL}/api/sessions?limit=5`);
            if (res.ok) {
                const data = await res.json();
                setSessions(data || []);
            }
        } catch (e) {
            console.error('[Workstation] Failed to fetch sessions:', e);
        } finally {
            setLoadingSessions(false);
        }
    };

    useEffect(() => {
        fetchSessions();
    }, []);

    const handleDeleteSession = async (session: SessionRecord) => {
        if (session.status === 'running' || session.status === 'pending') return;
        if (!window.confirm(`删除 ${session.tickers.join(', ')} 的这条分析记录？此操作不可恢复。`)) {
            return;
        }

        setDeletingSessionId(session.id);
        try {
            const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const response = await fetch(`${API_URL}/api/sessions/${session.id}`, {
                method: 'DELETE',
            });
            if (!response.ok) {
                throw new Error(`删除失败: ${response.status}`);
            }
            setSessions((current) => current.filter((item) => item.id !== session.id));
        } catch (error) {
            console.error('[Workstation] Failed to delete session:', error);
            alert('删除分析记录失败，请重试');
        } finally {
            setDeletingSessionId(null);
        }
    };

    // 搜索联想：防抖调用公司列表 API
    const fetchSuggestions = useCallback(async (query: string) => {
        if (!query || query.length < 1) {
            setSuggestions([]);
            setShowSuggestions(false);
            return;
        }

        setLoadingSuggestions(true);
        try {
            // 支持股票代码或名称搜索
            const result = await companiesApi.listCompanies(1, 8, query);
            setSuggestions(result.items || []);
            setShowSuggestions(true);
        } catch (e) {
            console.error('[Workstation] Failed to fetch suggestions:', e);
            setSuggestions([]);
        } finally {
            setLoadingSuggestions(false);
        }
    }, []);

    // 输入变化时触发防抖搜索
    const handleInputChange = (value: string) => {
        setSearchInput(value);
        setShowSuggestions(false);

        // 清除之前的定时器
        if (debounceTimerRef.current) {
            clearTimeout(debounceTimerRef.current);
        }

        // 防抖 300ms
        debounceTimerRef.current = setTimeout(() => {
            fetchSuggestions(value);
        }, 300);
    };

    // 选择联想结果
    const selectSuggestion = (company: Company) => {
        setSearchInput(company.stock_code);
        setShowSuggestions(false);
    };

    // 处理开始分析
    const handleStartAnalysis = async (mode: 'ai' | 'expert') => {
        if (searchInput.trim()) {
            const ticker = searchInput.toUpperCase();

            // 配额预检：剩余为 0 直接拦截，避免发 WS/HTTP
            const ents = useEntitlementsStore.getState().data;
            const resource = mode === 'ai' ? 'ai_analysis' : 'expert_valuation';
            const ent = ents?.entitlements?.[resource];
            if (ent && ent.remaining <= 0) {
                const isAnon = ents?.is_anonymous ?? true;
                toast.warning('配额已用尽');
                if (isAnon) {
                    openAuthModal({ onSuccess: () => refreshEntitlements(), title: '注册以解锁更多配额' });
                } else {
                    onSwitchMode('account');
                }
                return;
            }

            if (mode === 'ai') {
                onSendCommand(createStartAnalysisCommand(
                    [ticker],
                    new Date().toISOString().split('T')[0],
                ));
                onSwitchMode(mode);
            } else if (mode === 'expert') {
                try {
                    await Promise.all([
                        valuationApi.getDCF(ticker),
                        valuationApi.getResidualIncome(ticker),
                    ]);

                    try {
                        const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                        const saveResponse = await fetch(`${API_URL}/api/sessions`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                tickers: [ticker],
                                date: new Date().toISOString().split('T')[0],
                                status: 'completed',
                                mode: 'expert'
                            })
                        });
                        if (saveResponse.ok) {
                            const savedSession = await saveResponse.json();
                            dispatch({
                                type: 'SESSION_START',
                                payload: {
                                    id: savedSession.id,
                                    tickers: savedSession.tickers,
                                    date: savedSession.date,
                                }
                            });
                        } else {
                            dispatch({
                                type: 'SESSION_START',
                                payload: {
                                    id: `expert-${Date.now()}`,
                                    tickers: [ticker],
                                    date: new Date().toISOString(),
                                }
                            });
                        }
                    } catch {
                        dispatch({
                            type: 'SESSION_START',
                            payload: {
                                id: `expert-${Date.now()}`,
                                tickers: [ticker],
                                date: new Date().toISOString(),
                            }
                        });
                    }

                    onSwitchMode(mode, ticker);
                } catch (e: any) {
                    // 配额耗尽：匿名引导注册，登录引导去账户页
                    if (e instanceof QuotaExceededError) {
                        await refreshEntitlements();
                        if (e.isAnonymous) {
                            toast.warning('专家估值配额已用尽，请注册以解锁更多配额');
                            openAuthModal({ onSuccess: () => refreshEntitlements(), title: '注册以解锁更多配额' });
                        } else {
                            toast.warning('专家估值配额已用尽，请升级订阅');
                            onSwitchMode('account');
                        }
                        return;
                    }
                    dispatch({
                        type: 'SESSION_START',
                        payload: {
                            id: `expert-${Date.now()}`,
                            tickers: [ticker],
                            date: new Date().toISOString(),
                        }
                    });
                    onSwitchMode(mode, ticker);
                }
            }
        } else {
            onSwitchMode(mode);
        }
    };

    return (
        <div className="max-w-5xl mx-auto p-8 animate-fade-in">
            {/* 搜索区 */}
            <div className="text-center mb-12 mt-8">
                <h1 className="text-4xl font-bold text-foreground mb-4 tracking-tight">V-Agent 智能投研系统</h1>
                <p className="text-muted-foreground mb-8 text-lg">AI驱动基本面分析 · 专业级财务建模 · 实时多维度风险评估</p>

                <div className="relative max-w-2xl mx-auto" ref={searchRef}>
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground w-5 h-5" />
                    <input
                        type="text"
                        placeholder="输入股票代码或公司名称（如：600519 或 贵州茅台）"
                        className="w-full pl-12 pr-4 py-4 bg-card border border-border rounded-vibe shadow-rams text-lg focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-shadow text-foreground"
                        value={searchInput}
                        onChange={(e) => handleInputChange(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                                setShowSuggestions(false);
                                handleStartAnalysis('ai');
                            }
                            if (e.key === 'Escape') {
                                setShowSuggestions(false);
                            }
                        }}
                        autoComplete="off"
                    />

                    {/* 搜索联想下拉 */}
                    {showSuggestions && suggestions.length > 0 && (
                        <div className="absolute top-full left-0 right-0 mt-2 bg-popover border border-border rounded-vibe shadow-rams z-50 max-h-80 overflow-y-auto">
                            {suggestions.map((company) => (
                                <button
                                    key={company.stock_code}
                                    onMouseDown={() => selectSuggestion(company)}
                                    className="w-full px-4 py-3 flex items-center justify-between hover:bg-accent transition-colors text-left border-b border-border last:border-b-0"
                                >
                                    <div className="flex items-center gap-3">
                                        <span className="font-data text-brand-700 font-medium text-sm">
                                            {company.stock_code}
                                        </span>
                                        <span className="text-foreground text-sm">
                                            {company.stock_name}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                        {company.exchange_name && (
                                            <span className="px-1.5 py-0.5 bg-muted rounded">{company.exchange_name}</span>
                                        )}
                                        {company.pe_ratio !== undefined && company.pe_ratio !== null && (
                                            <span className="hidden sm:inline">PE: {company.pe_ratio.toFixed(1)}</span>
                                        )}
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}

                    {/* 加载中提示 */}
                    {showSuggestions && loadingSuggestions && (
                        <div className="absolute top-full left-0 right-0 mt-2 bg-popover border border-border rounded-vibe shadow-rams z-50 py-3 text-center text-muted-foreground text-sm">
                            搜索中...
                        </div>
                    )}

                    {/* 无结果提示 */}
                    {showSuggestions && !loadingSuggestions && suggestions.length === 0 && searchInput.trim().length > 0 && (
                        <div className="absolute top-full left-0 right-0 mt-2 bg-popover border border-border rounded-vibe shadow-rams z-50 py-3 text-center text-muted-foreground text-sm">
                            未找到匹配的结果
                        </div>
                    )}
                </div>
            </div>

            {/* 模式选择卡片 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
                {/* AI 模式 —— 品牌橙红渐变主卡 */}
                <button
                    onClick={() => handleStartAnalysis('ai')}
                    className="group relative overflow-hidden bg-gradient-to-br from-brand-500 via-brand-600 to-brand-800 rounded-vibe p-8 text-left text-primary-foreground shadow-rams hover:shadow-rams-elevated transition-all hover:-translate-y-1"
                >
                    <div className="absolute inset-0 opacity-20 bg-[url('data:image/svg+xml,%3Csvg width=\'60\' height=\'60\' viewBox=\'0 0 60 60\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cg fill=\'none\' fill-rule=\'evenodd\'%3E%3Cg fill=\'%23ffffff\' fill-opacity=\'0.4\'%3E%3Cpath d=\'M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z\'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E')]"></div>
                    <div className="absolute top-6 right-6 w-12 h-12 bg-white/10 rounded-vibe-sm flex items-center justify-center group-hover:scale-110 transition-transform backdrop-blur-sm border border-white/20">
                        <Zap className="w-6 h-6" />
                    </div>
                    <div className="absolute top-6 right-20">
                        <QuotaBadge resource="ai_analysis" compact onNavigateToAccount={() => onSwitchMode('account')} />
                    </div>
                    <div className="relative z-10">
                        <h3 className="text-2xl font-bold mb-3">AI智能分析模式</h3>
                        <p className="text-white/85 leading-relaxed mb-6 text-sm">
                            多智能体并行分析，实时展示推理过程。基本面分析师、风险审计师、决策中枢协同工作，适合快速筛选标的。
                        </p>
                        <div className="flex items-center gap-2 text-sm font-medium text-white/80 group-hover:text-white transition-colors">
                            开始分析 <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                        </div>
                    </div>
                </button>

                {/* 专家模式 —— 浅色描边卡 */}
                <button
                    onClick={() => handleStartAnalysis('expert')}
                    className="group relative bg-card border border-border rounded-vibe p-8 text-left hover:border-ring hover:shadow-rams-elevated transition-all hover:-translate-y-1 shadow-rams"
                >
                    <div className="absolute top-6 right-6 w-12 h-12 bg-muted rounded-vibe-sm flex items-center justify-center group-hover:bg-brand-50 group-hover:text-brand-600 transition-colors">
                        <Terminal className="w-6 h-6 text-muted-foreground group-hover:text-brand-600" />
                    </div>
                    <div className="absolute top-6 right-20">
                        <QuotaBadge resource="expert_valuation" compact onNavigateToAccount={() => onSwitchMode('account')} />
                    </div>
                    <h3 className="text-2xl font-bold text-foreground mb-3">专家深度模式</h3>
                    <p className="text-muted-foreground leading-relaxed mb-6 text-sm">
                        DCF/RIM估值建模、财务数据抓取、敏感性分析。华尔街级专业工具，适合深度研究与投资决策。
                    </p>
                    <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground group-hover:text-brand-600 transition-colors">
                        进入实验室 <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                    </div>
                </button>
            </div>

            {/* 最近历史 */}
            <div>
                <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                    <Clock className="w-5 h-5 text-muted-foreground" />
                    最近分析记录
                </h3>
                <div className="bg-card rounded-vibe border border-border shadow-rams divide-y divide-border">
                    {loadingSessions ? (
                        <div className="p-8 text-center text-muted-foreground text-sm">
                            加载中...
                        </div>
                    ) : sessions.length === 0 ? (
                        <div className="p-8 text-center text-muted-foreground text-sm">
                            暂无历史记录
                        </div>
                    ) : (
                        sessions.map((session) => (
                            <div
                                key={session.id}
                                className="p-4 flex items-center justify-between hover:bg-muted transition-colors cursor-pointer group"
                                onClick={async () => {
                                    try {
                                        const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                                        const outputsRes = await fetch(`${API_URL}/api/sessions/${session.id}/outputs`);
                                        if (!outputsRes.ok) {
                                            throw new Error(`Failed to fetch outputs: ${outputsRes.status}`);
                                        }
                                        const outputs = await outputsRes.json();

                                        let report = '';
                                        if (session.status === 'completed') {
                                            try {
                                                const reportRes = await fetch(`${API_URL}/api/sessions/${session.id}/report`);
                                                if (reportRes.ok) {
                                                    const reportData = await reportRes.json();
                                                    report = reportData.report_content || '';
                                                }
                                            } catch {
                                                // No report
                                            }
                                        }

                                        dispatch({
                                            type: 'RESTORE_SESSION',
                                            payload: {
                                                session: { ...session, report },
                                                outputs
                                            }
                                        });

                                        const mode = session.mode === 'expert' ? 'expert' : 'ai';
                                        const ticker = session.tickers[0];
                                        onSwitchMode(mode, ticker);
                                    } catch (e) {
                                        console.error('[Workstation] Failed to load session data:', e);
                                        alert('加载历史记录失败，请重试');
                                    }
                                }}
                            >
                                <div className="flex items-center gap-4">
                                    <div className={`w-2 h-2 rounded-full ${
                                        session.status === 'completed' ? 'bg-success' :
                                        session.status === 'running' ? 'bg-brand-500' :
                                        session.status === 'failed' ? 'bg-destructive' :
                                        session.status === 'cancelled' ? 'bg-muted-foreground' :
                                        'bg-warning'
                                    }`}></div>
                                    <div>
                                        <div className="font-medium text-foreground">
                                            {session.tickers.join(', ')}
                                        </div>
                                        <div className="text-sm text-muted-foreground">
                                            {session.status === 'completed' ? (session.mode === 'expert' ? '专家模式' : 'AI分析') :
                                             session.status === 'running' ? '分析中' :
                                             session.status === 'failed' ? '分析失败' :
                                             session.status === 'cancelled' ? '已取消' : '未知'}
                                            {' · '}
                                            {formatTimeAgo(session.created_at)}
                                        </div>
                                    </div>
                                </div>
                                <div className="flex items-center gap-4">
                                    {session.status === 'completed' && (
                                        <span className="px-2 py-1 bg-success/10 text-success text-xs rounded font-medium">
                                            已完成
                                        </span>
                                    )}
                                    {session.status === 'running' && (
                                        <span className="px-2 py-1 bg-brand-50 text-brand-700 text-xs rounded font-medium">
                                            进行中
                                        </span>
                                    )}
                                    {session.status === 'failed' && (
                                        <span className="px-2 py-1 bg-destructive/10 text-destructive text-xs rounded font-medium">
                                            失败
                                        </span>
                                    )}
                                    {session.status === 'cancelled' && (
                                        <span className="px-2 py-1 bg-muted text-muted-foreground text-xs rounded font-medium">
                                            已取消
                                        </span>
                                    )}
                                    <button
                                        type="button"
                                        onClick={(event) => {
                                            event.stopPropagation();
                                            void handleDeleteSession(session);
                                        }}
                                        disabled={
                                            session.status === 'running'
                                            || session.status === 'pending'
                                            || deletingSessionId === session.id
                                        }
                                        className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-vibe-sm disabled:opacity-30 disabled:cursor-not-allowed"
                                        title={
                                            session.status === 'running' || session.status === 'pending'
                                                ? '运行中的分析不能删除'
                                                : '删除分析记录'
                                        }
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                    <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-foreground" />
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}

// Helper function to format time ago
function formatTimeAgo(dateString: string): string {
    const now = new Date();
    const date = new Date(dateString);
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (seconds < 60) return '刚刚';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟前`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}小时前`;
    if (seconds < 2592000) return `${Math.floor(seconds / 86400)}天前`;
    return date.toLocaleDateString('zh-CN');
}
