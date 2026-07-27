/**
 * 公司信息 API 服务
 *
 * 提供与后端公司管理 API 的通信功能
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_BASE = `${API_URL}/api/companies`;

// ============================================================
// 类型定义
// ============================================================

export interface Company {
    stock_code: string;
    stock_name: string;
    company_name: string;
    exchange_id: number;
    exchange_name?: string;
    industry_id?: number;
    industry_name?: string;
    listing_date?: string;
    current_price?: number;
    market_cap?: number;
    pe_ratio?: number;
    pb_ratio?: number;
    status: string;
    updated_at: string;
}

export interface PaginatedCompaniesResponse {
    items: Company[];
    total: number;
    page: number;
    page_size: number;
}

export interface ExchangeStats {
    exchange: string;
    count: number;
}

export interface CompanyStatistics {
    total_count: number;
    active_count: number;
    exchange_statistics: ExchangeStats[];
}

// ============================================================
// API 请求函数
// ============================================================

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
    const response = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options?.headers,
        },
    });
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API request failed: ${response.status} - ${errorText}`);
    }
    return response.json();
}

// ============================================================
// 公司 API
// ============================================================

export const companiesApi = {
    /**
     * 获取公司列表（分页）
     */
    async listCompanies(
        page: number = 1,
        pageSize: number = 20,
        search?: string,
        exchangeId?: number
    ): Promise<PaginatedCompaniesResponse> {
        const params = new URLSearchParams({
            page: String(page),
            page_size: String(pageSize),
        });
        if (search) {
            params.set('search', search);
        }
        if (exchangeId !== undefined) {
            params.set('exchange_id', String(exchangeId));
        }
        return fetchJson<PaginatedCompaniesResponse>(`${API_BASE}?${params.toString()}`);
    },

    /**
     * 获取公司统计信息
     */
    async getStatistics(): Promise<CompanyStatistics> {
        return fetchJson<CompanyStatistics>(`${API_BASE}/statistics`);
    },

    /**
     * 获取单个公司详细信息
     */
    async getCompany(stockCode: string): Promise<Company> {
        return fetchJson<Company>(`${API_BASE}/${stockCode}`);
    },

    /**
     * 刷新公司行情信息
     */
    async refreshQuotes(stockCode: string): Promise<Company> {
        return fetchJson<Company>(`${API_BASE}/${stockCode}/refresh`, {
            method: 'POST',
        });
    },
};