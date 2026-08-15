/**
 * 我的账户页面
 *
 * 展示：
 *  - 当前登录状态（未登录展示登录/注册按钮）
 *  - 订阅状态（plan、到期时间、是否到期后取消）
 *  - 各资源配额使用情况（剩余/上限、窗口、重置时间）
 *  - 登出按钮
 */

import React, { useEffect, useState } from 'react';
import { User, Crown, LogOut, Gauge, Clock, RefreshCw, LogIn, UserPlus } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { useEntitlementsStore } from '../../stores/entitlementsStore';
import { useToast } from '../Common/Toast';
import { openAuthModal } from '../Common/AuthModal';
import type { AnalysisMode } from '../../stores/modeStore';

const RESOURCE_LABELS: Record<string, string> = {
    ai_analysis: 'AI 分析',
    expert_valuation: '专家估值',
    data_api: '数据 API',
};

const PLAN_LABELS: Record<string, string> = {
    free: '免费版',
    pro: '专业版',
    enterprise: '企业版',
};

interface AccountPageProps {
    onSwitchMode?: (mode: AnalysisMode) => void;
}

export const AccountPage: React.FC<AccountPageProps> = ({ onSwitchMode: _onSwitchMode }) => {
    const { user, isAuthenticated, logout } = useAuthStore();
    const { data, refresh, isLoading } = useEntitlementsStore();
    const toast = useToast();
    const [loggingOut, setLoggingOut] = useState(false);

    useEffect(() => {
        refresh();
    }, [refresh, isAuthenticated]);

    const handleLogout = async () => {
        setLoggingOut(true);
        await logout();
        await refresh();
        toast.success('已登出');
        setLoggingOut(false);
    };

    // 未登录
    if (!isAuthenticated) {
        return (
            <div className="max-w-2xl mx-auto">
                <header className="mb-6">
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <User className="w-6 h-6" /> 我的账户
                    </h1>
                    <p className="text-muted-foreground mt-1">登录以解锁更多配额与订阅功能</p>
                </header>

                <div className="bg-card border border-border rounded-vibe p-8 text-center">
                    <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-primary-foreground">
                        <Crown className="w-8 h-8" />
                    </div>
                    <h2 className="text-lg font-semibold mb-2">您当前是匿名用户</h2>
                    <p className="text-sm text-muted-foreground mb-6">
                        匿名用户享有限量免费配额。注册即可获得更多月度配额，订阅解锁完整能力。
                    </p>

                    {/* 匿名额度预览 */}
                    {data && (
                        <div className="mb-6 text-left bg-background/50 rounded-vibe-sm p-4">
                            <h3 className="text-sm font-medium mb-2 text-muted-foreground">当前匿名配额</h3>
                            {Object.entries(data.entitlements || {}).map(([key, ent]: [string, any]) => (
                                <div key={key} className="flex justify-between text-sm py-1">
                                    <span>{RESOURCE_LABELS[key] || key}</span>
                                    <span className="font-data">{ent.remaining} / {ent.quota}</span>
                                </div>
                            ))}
                        </div>
                    )}

                    <div className="flex gap-3 justify-center">
                        <button
                            onClick={() => openAuthModal({ onSuccess: () => refresh() })}
                            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 text-primary-foreground rounded-vibe-sm hover:bg-brand-700 transition-colors"
                        >
                            <LogIn className="w-4 h-4" /> 登录
                        </button>
                        <button
                            onClick={() => openAuthModal({ onSuccess: () => refresh() })}
                            className="inline-flex items-center gap-2 px-4 py-2 border border-border rounded-vibe-sm hover:bg-accent transition-colors"
                        >
                            <UserPlus className="w-4 h-4" /> 注册
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-3xl mx-auto">
            <header className="mb-6 flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <User className="w-6 h-6" /> 我的账户
                    </h1>
                    <p className="text-muted-foreground mt-1">{user?.username} · {user?.email}</p>
                </div>
                <button
                    onClick={handleLogout}
                    disabled={loggingOut}
                    className="inline-flex items-center gap-2 px-3 py-1.5 text-sm border border-border rounded-vibe-sm hover:bg-accent transition-colors disabled:opacity-50"
                >
                    <LogOut className="w-4 h-4" /> {loggingOut ? '登出中...' : '登出'}
                </button>
            </header>

            {/* 订阅卡片 */}
            <section className="bg-card border border-border rounded-vibe p-5 mb-4">
                <div className="flex items-center justify-between mb-3">
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                        <Crown className="w-5 h-5" /> 当前订阅
                    </h2>
                    <button
                        onClick={() => refresh()}
                        disabled={isLoading}
                        className="text-muted-foreground hover:text-foreground disabled:opacity-50"
                        title="刷新"
                    >
                        <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
                {data?.subscription ? (
                    <div>
                        <div className="flex items-center gap-3 mb-2">
                            <span className="text-xl font-bold">{PLAN_LABELS[data.subscription.plan_code] || data.subscription.plan_code}</span>
                            <span className="text-xs px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-vibe-sm">
                                {data.subscription.status}
                            </span>
                            {data.subscription.cancel_at_period_end && (
                                <span className="text-xs px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded-vibe-sm">
                                    到期取消
                                </span>
                            )}
                        </div>
                        <p className="text-sm text-muted-foreground flex items-center gap-2">
                            <Clock className="w-4 h-4" />
                            到期时间：{new Date(data.subscription.current_period_end).toLocaleString('zh-CN')}
                        </p>
                    </div>
                ) : (
                    <div>
                        <p className="text-lg font-bold mb-1">{PLAN_LABELS[data?.plan_code || 'free'] || '免费版'}</p>
                        <p className="text-sm text-muted-foreground">
                            您当前使用免费版配额。如需更多配额，请联系管理员开通订阅。
                        </p>
                    </div>
                )}
            </section>

            {/* 配额详情 */}
            <section className="bg-card border border-border rounded-vibe p-5">
                <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
                    <Gauge className="w-5 h-5" /> 配额使用
                </h2>
                <div className="space-y-4">
                    {data && Object.entries(data.entitlements || {}).map(([key, ent]: [string, any]) => {
                        const ratio = ent.quota > 0 ? ent.remaining / ent.quota : 0;
                        const isExhausted = ent.remaining === 0;
                        const isLow = ratio <= 0.2 && !isExhausted;
                        const barColor = isExhausted
                            ? 'bg-red-500'
                            : isLow
                                ? 'bg-amber-500'
                                : 'bg-emerald-500';
                        return (
                            <div key={key}>
                                <div className="flex justify-between text-sm mb-1">
                                    <span className="font-medium">{RESOURCE_LABELS[key] || key}</span>
                                    <span className="text-muted-foreground font-data">
                                        {ent.used} / {ent.quota} · 剩余 {ent.remaining}
                                    </span>
                                </div>
                                <div className="h-2 bg-muted rounded-full overflow-hidden">
                                    <div
                                        className={`h-full ${barColor} transition-all`}
                                        style={{ width: `${Math.max(0, ratio) * 100}%` }}
                                    />
                                </div>
                                <p className="text-xs text-muted-foreground mt-1">
                                    窗口：{new Date(ent.window_start).toLocaleString('zh-CN')} ~ {new Date(ent.window_end).toLocaleString('zh-CN')}
                                </p>
                            </div>
                        );
                    })}
                    {!data && (
                        <p className="text-sm text-muted-foreground">加载中...</p>
                    )}
                </div>
            </section>
        </div>
    );
};
