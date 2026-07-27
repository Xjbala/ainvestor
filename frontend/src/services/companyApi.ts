/**
 * 公司管理 API 服务
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_BASE = `${API_URL}/api`;

export interface Company {
    stock_code: string;
    stock_name: string;
    company_name: string;
    exchange_id: number;
    exchange_name?: string;
    industry_id?: number | null;
    industry_name?: string;
    listing_date?: string | null;
    current_price?: number | null;
    market_cap?: number | null;
    pe_ratio?: number | null;
    pb_ratio?: number | null;
    status: string;
    updated_at: string;
}

export interface PaginatedCompanies {
    items: Company[];
    total: number;
    page: number;
    page_size: number;
}

export interface Exchange {
    id: number;
    code: string;
    name: string;
    country: string;
    is_active: boolean;
}

export interface CompanyStatistics {
    total_count: number;
    active_count: number;
    exchange_statistics: Array<{
        exchange: string;
        count: number;
    }>;
}

async function fetchApi<T>(url: string, options?: RequestInit): Promise<T> {
    const response = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options?.headers,
        },
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'API request failed' }));
        throw new Error(error.detail || `Error ${response.status}`);
    }
    return response.json();
}

export const companyApi = {
    /**
     * 获取单个公司详细信息
     */
    async getCompany(stockCode: string): Promise<Company> {
        return fetchApi<Company>(`${API_BASE}/companies/${stockCode}`);
    },

    /**
     * 获取公司列表
     */
    async listCompanies(page = 1, pageSize = 20, search?: string, exchangeId?: number): Promise<PaginatedCompanies> {
        const params = new URLSearchParams();
        params.set('page', String(page));
        params.set('page_size', String(pageSize));
        if (search) params.set('search', search);
        if (exchangeId) params.set('exchange_id', String(exchangeId));

        return fetchApi<PaginatedCompanies>(`${API_BASE}/companies?${params.toString()}`);
    },

    /**
     * 获取统计数据
     */
    async getStatistics(): Promise<CompanyStatistics> {
        return fetchApi<CompanyStatistics>(`${API_BASE}/companies/statistics`);
    },

    /**
     * 保存(创建或更新)公司
     */
    async saveCompany(company: Partial<Company>): Promise<Company> {
        const isUpdate = !!company.stock_code && !company.stock_code.startsWith('NEW_'); // Simplified logic
        // This is a bit tricky since create uses POST and update uses PUT. 
        // For simplicity, we'll let the component decide or implement split here.
        return fetchApi<Company>(`${API_BASE}/companies${isUpdate ? '/' + company.stock_code : ''}`, {
            method: isUpdate ? 'PUT' : 'POST',
            body: JSON.stringify(company),
        });
    },

    /**
     * 删除公司
     */
    async deleteCompany(stockCode: string): Promise<void> {
        await fetchApi(`${API_BASE}/companies/${stockCode}`, {
            method: 'DELETE',
        });
    },

    /**
     * 获取交易所列表
     */
    async listExchanges(): Promise<Exchange[]> {
        return fetchApi<Exchange[]>(`${API_BASE}/exchanges`);
    },

    async syncCompanies(): Promise<{ message: string; task_id: string }> {
        return fetchApi<{ message: string; task_id: string }>(`${API_BASE}/companies/sync`, {
            method: 'POST',
        });
    },

    /**
     * 实时更新单个公司行情
     */
    async refreshCompany(stockCode: string): Promise<Company> {
        return fetchApi<Company>(`${API_BASE}/companies/${stockCode}/refresh`, {
            method: 'POST',
        });
    },
};
