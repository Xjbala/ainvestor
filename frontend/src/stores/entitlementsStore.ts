/**
 * 配额与订阅状态
 *
 * - entitlements：当前身份各资源剩余配额
 * - 登录后立即拉取一次，每次消耗后调 refreshEntitlements 刷新
 * - 匿名用户也调（cookie 自动带）
 */

import { create } from 'zustand';
import { authApi, type EntitlementsResponse } from '../services/authApi';

interface EntitlementsState {
    data: EntitlementsResponse | null;
    isLoading: boolean;
    error: string | null;

    refresh: () => Promise<EntitlementsResponse | null>;
    clear: () => void;
}

export const useEntitlementsStore = create<EntitlementsState>((set) => ({
    data: null,
    isLoading: false,
    error: null,

    refresh: async () => {
        set({ isLoading: true, error: null });
        try {
            const data = await authApi.getEntitlements();
            set({ data, isLoading: false });
            return data;
        } catch (e: any) {
            const msg = e?.message || '获取配额失败';
            set({ error: msg, isLoading: false });
            return null;
        }
    },

    clear: () => set({ data: null, error: null }),
}));

// 资源中文名映射
export const RESOURCE_LABELS: Record<string, string> = {
    ai_analysis: 'AI 分析',
    expert_valuation: '专家估值',
    data_api: '数据 API',
};
