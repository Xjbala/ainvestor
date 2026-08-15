/**
 * 认证 API 与 authFetch
 *
 * - register/login/refresh/me/entitlements
 * - token 存 localStorage（access + refresh）
 * - authFetch：自动加 Authorization，401 尝试 refresh 一次，仍失败则清 token
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_BASE = `${API_URL}/api`;

const ACCESS_TOKEN_KEY = 'ainvestor.accessToken';
const REFRESH_TOKEN_KEY = 'ainvestor.refreshToken';

export interface TokenResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
    expires_in: number;
}

export interface UserInfo {
    id: string;
    username: string;
    email: string;
    role: string;
    is_active: boolean;
    created_at: string;
}

export interface Entitlement {
    used: number;
    quota: number;
    remaining: number;
    window_start: string;
    window_end: string;
}

export interface EntitlementsResponse {
    is_anonymous: boolean;
    plan_code: string;
    subscription: {
        plan_code: string;
        status: string;
        current_period_start: string;
        current_period_end: string;
        cancel_at_period_end: boolean;
    } | null;
    entitlements: {
        ai_analysis?: Entitlement;
        expert_valuation?: Entitlement;
        data_api?: Entitlement;
    };
}

// ============================================================
// token 持久化
// ============================================================

export function getAccessToken(): string | null {
    try {
        return localStorage.getItem(ACCESS_TOKEN_KEY);
    } catch {
        return null;
    }
}

export function getRefreshToken(): string | null {
    try {
        return localStorage.getItem(REFRESH_TOKEN_KEY);
    } catch {
        return null;
    }
}

export function setTokens(access: string, refresh: string): void {
    try {
        localStorage.setItem(ACCESS_TOKEN_KEY, access);
        localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
    } catch {
        // localStorage 不可用时仅影响登录态保持
    }
}

export function clearTokens(): void {
    try {
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
    } catch {
        // noop
    }
}

// ============================================================
// 配额耗尽错误（携带 detail 供 UI 展示引导）
// ============================================================

export class QuotaExceededError extends Error {
    status: number;
    detail: any;
    isAnonymous: boolean;

    constructor(status: number, detail: any) {
        const message =
            (detail && typeof detail === 'object' && detail.message) ||
            (typeof detail === 'string' && detail) ||
            '配额已用尽';
        super(message);
        this.name = 'QuotaExceededError';
        this.status = status;
        this.detail = detail;
        this.isAnonymous = status === 402;
    }
}

// ============================================================
// authFetch：自动加 Authorization + 402/429 抛 QuotaExceededError
// ============================================================

async function refreshOnce(): Promise<boolean> {
    const refresh = getRefreshToken();
    if (!refresh) return false;
    try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!res.ok) {
            clearTokens();
            return false;
        }
        const data: TokenResponse = await res.json();
        setTokens(data.access_token, data.refresh_token);
        return true;
    } catch {
        clearTokens();
        return false;
    }
}

export async function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
    const token = getAccessToken();
    const headers = new Headers(init.headers || {});
    if (token) {
        headers.set('Authorization', `Bearer ${token}`);
    }
    let res = await fetch(url, { ...init, headers, credentials: 'include' });

    // 401 → 尝试 refresh 一次再重试
    if (res.status === 401) {
        const refreshed = await refreshOnce();
        if (refreshed) {
            const newToken = getAccessToken();
            if (newToken) headers.set('Authorization', `Bearer ${newToken}`);
            res = await fetch(url, { ...init, headers, credentials: 'include' });
        }
    }
    return res;
}

async function authFetchJson<T>(url: string, init: RequestInit = {}): Promise<T> {
    const res = await authFetch(url, init);
    if (res.status === 402 || res.status === 429) {
        let detail: any = null;
        try {
            detail = await res.json();
        } catch {
            detail = await res.text();
        }
        throw new QuotaExceededError(res.status, detail?.detail ?? detail);
    }
    if (!res.ok) {
        const text = await res.text();
        throw new Error(`API ${res.status}: ${text}`);
    }
    return res.json();
}

// ============================================================
// 认证 API
// ============================================================

export const authApi = {
    async register(username: string, email: string, password: string): Promise<TokenResponse & { user: UserInfo }> {
        const res = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password }),
            credentials: 'include', // 让后端能读到 anon_id cookie 做配额迁移
        });
        if (!res.ok) {
            const text = await res.text();
            throw new Error(text);
        }
        const tokens: TokenResponse = await res.json();
        setTokens(tokens.access_token, tokens.refresh_token);
        const user = await this.me();
        return { ...tokens, user };
    },

    async login(username: string, password: string): Promise<TokenResponse & { user: UserInfo }> {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
            credentials: 'include',
        });
        if (!res.ok) {
            const text = await res.text();
            throw new Error(text);
        }
        const tokens: TokenResponse = await res.json();
        setTokens(tokens.access_token, tokens.refresh_token);
        const user = await this.me();
        return { ...tokens, user };
    },

    async me(): Promise<UserInfo> {
        return authFetchJson<UserInfo>(`${API_BASE}/auth/me`);
    },

    async getEntitlements(): Promise<EntitlementsResponse> {
        return authFetchJson<EntitlementsResponse>(`${API_BASE}/me/entitlements`);
    },

    async logout(): Promise<void> {
        try {
            await authFetch(`${API_BASE}/auth/logout`, { method: 'POST' });
        } catch {
            // logout 失败不阻塞前端清状态
        }
        clearTokens();
    },
};

// ============================================================
// Admin 订阅管理 API
// ============================================================

export interface Plan {
    code: string;
    name: string;
    ai_quota_monthly: number;
    expert_quota_monthly: number;
    data_api_quota_monthly: number;
    price_cents: number;
    is_active: boolean;
    sort_order: number;
}

export interface Subscription {
    id: string;
    user_id: string;
    plan_code: string;
    status: string;
    current_period_start: string;
    current_period_end: string;
    cancel_at_period_end: boolean;
    activated_by_admin_id: string | null;
    note: string | null;
    created_at: string;
    updated_at: string;
}

async function adminFetchJson<T>(url: string, init: RequestInit = {}): Promise<T> {
    const res = await authFetch(url, init);
    if (!res.ok) {
        const text = await res.text();
        throw new Error(`API ${res.status}: ${text}`);
    }
    return res.json();
}

export const adminApi = {
    async listPlans(): Promise<{ plans: Plan[] }> {
        return adminFetchJson(`${API_BASE}/admin/plans`);
    },

    async listSubscriptions(params?: { skip?: number; limit?: number; user_id?: string }): Promise<{ subscriptions: Subscription[]; total: number; skip: number; limit: number }> {
        const qs = new URLSearchParams();
        if (params?.skip !== undefined) qs.set('skip', String(params.skip));
        if (params?.limit !== undefined) qs.set('limit', String(params.limit));
        if (params?.user_id) qs.set('user_id', params.user_id);
        const q = qs.toString();
        return adminFetchJson(`${API_BASE}/admin/subscriptions${q ? '?' + q : ''}`);
    },

    async createSubscription(body: { user_id: string; plan_code: string; period_days?: number; note?: string }): Promise<Subscription> {
        const res = await authFetch(`${API_BASE}/admin/subscriptions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const text = await res.text();
            throw new Error(`开通失败: ${text}`);
        }
        return res.json();
    },

    async extendSubscription(subId: string, body: { period_days: number; plan_code?: string; note?: string }): Promise<Subscription> {
        const res = await authFetch(`${API_BASE}/admin/subscriptions/${subId}/extend`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const text = await res.text();
            throw new Error(`续期失败: ${text}`);
        }
        return res.json();
    },

    async updateSubscriptionStatus(subId: string, body: { status: string; cancel_at_period_end?: boolean }): Promise<Subscription> {
        const res = await authFetch(`${API_BASE}/admin/subscriptions/${subId}/status`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const text = await res.text();
            throw new Error(`更新状态失败: ${text}`);
        }
        return res.json();
    },

    async listUsers(): Promise<{ users: any[] }> {
        return adminFetchJson(`${API_BASE}/users?limit=100`);
    },
};
