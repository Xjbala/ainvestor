/**
 * 配额徽章
 *
 * 展示当前身份在指定资源上的剩余配额。
 * 用于 AIMode 入口、ExpertMode 入口、Dashboard。
 *
 * 点击跳转到"我的订阅"页面（onNavigateToAccount 回调）。
 */

import React, { useEffect } from 'react';
import { Sparkles, Gauge, Crown } from 'lucide-react';
import { useEntitlementsStore } from '../../stores/entitlementsStore';
import { useAuthStore } from '../../stores/authStore';

interface QuotaBadgeProps {
    resource: 'ai_analysis' | 'expert_valuation' | 'data_api';
    label?: string;
    onNavigateToAccount?: () => void;
    compact?: boolean;
}

const RESOURCE_LABELS: Record<string, string> = {
    ai_analysis: 'AI 分析',
    expert_valuation: '专家估值',
    data_api: '数据 API',
};

export const QuotaBadge: React.FC<QuotaBadgeProps> = ({
    resource,
    label,
    onNavigateToAccount,
    compact = false,
}) => {
    const { data, refresh } = useEntitlementsStore();
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    // 首次挂载拉一次
    useEffect(() => {
        if (!data) refresh();
    }, [data, refresh]);

    const ent = data?.entitlements?.[resource];
    if (!ent) {
        return compact ? null : (
            <button
                onClick={() => refresh()}
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
                <Gauge className="w-3.5 h-3.5" />
                加载中...
            </button>
        );
    }

    const { remaining, quota } = ent;
    const ratio = quota > 0 ? remaining / quota : 0;
    const isLow = ratio <= 0.2 && remaining > 0;
    const isExhausted = remaining === 0;
    const planCode = data?.plan_code || 'free';

    const colorClass = isExhausted
        ? 'bg-red-50 text-red-700 border-red-200'
        : isLow
            ? 'bg-amber-50 text-amber-700 border-amber-200'
            : 'bg-emerald-50 text-emerald-700 border-emerald-200';

    if (compact) {
        return (
            <button
                onClick={onNavigateToAccount}
                className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-vibe-sm border ${colorClass} hover:opacity-80 transition-opacity`}
                title={`${label || RESOURCE_LABELS[resource]}：剩余 ${remaining} / ${quota}`}
            >
                <Gauge className="w-3 h-3" />
                {remaining}/{quota}
            </button>
        );
    }

    return (
        <button
            onClick={onNavigateToAccount}
            className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-vibe-sm border text-sm ${colorClass} hover:opacity-80 transition-opacity`}
        >
            {planCode !== 'free' ? (
                <Crown className="w-4 h-4" />
            ) : (
                <Sparkles className="w-4 h-4" />
            )}
            <span className="font-medium">{label || RESOURCE_LABELS[resource]}</span>
            <span className="text-xs opacity-75">
                {isAuthenticated ? '' : '匿名 · '}
                剩余 {remaining} / {quota}
            </span>
            {isExhausted && (
                <span className="text-xs font-medium px-1.5 py-0.5 bg-red-600 text-white rounded-vibe-sm">
                    升级
                </span>
            )}
        </button>
    );
};
