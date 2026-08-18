/**
 * 认证状态管理
 *
 * - user / isAuthenticated
 * - login/register/logout actions
 * - 启动时尝试用本地 token 恢复 user
 */

import { create } from 'zustand';
import { authApi, getAccessToken, clearTokens, type UserInfo } from '../services/authApi';

interface AuthState {
    user: UserInfo | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    error: string | null;

    bootstrap: () => Promise<void>;
    login: (username: string, password: string) => Promise<void>;
    register: (
        username: string,
        email: string,
        password: string,
        code: string,
        turnstileToken: string,
    ) => Promise<void>;
    logout: () => Promise<void>;
    clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,

    bootstrap: async () => {
        const token = getAccessToken();
        if (!token) {
            set({ user: null, isAuthenticated: false });
            return;
        }
        try {
            const user = await authApi.me();
            set({ user, isAuthenticated: true });
        } catch {
            clearTokens();
            set({ user: null, isAuthenticated: false });
        }
    },

    login: async (username: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
            const { user } = await authApi.login(username, password);
            set({ user, isAuthenticated: true, isLoading: false });
        } catch (e: any) {
            const msg = e?.message || '登录失败';
            set({ error: msg, isLoading: false, isAuthenticated: false });
            throw e;
        }
    },

    register: async (
        username: string,
        email: string,
        password: string,
        code: string,
        turnstileToken: string,
    ) => {
        set({ isLoading: true, error: null });
        try {
            const { user } = await authApi.register(username, email, password, code, turnstileToken);
            set({ user, isAuthenticated: true, isLoading: false });
        } catch (e: any) {
            const msg = e?.message || '注册失败';
            set({ error: msg, isLoading: false, isAuthenticated: false });
            throw e;
        }
    },

    logout: async () => {
        await authApi.logout();
        set({ user: null, isAuthenticated: false });
    },

    clearError: () => set({ error: null }),
}));
