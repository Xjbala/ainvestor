/**
 * 原始财务数据 API 服务
 *
 * 提供公司三大报表（资产负债表/利润表/现金流量表）原始科目数据查询。
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_BASE = `${API_URL}/api/companies`;

// ============================================================
// 类型定义
// ============================================================

export type ReportType = 'BS' | 'IS' | 'CF';

export interface FinancialDataItem {
    subject_code: string;
    subject_name: string;
    value: number | null;
}

export interface FinancialDataPeriod {
    report_date: string;
    report_period: string;
    items: FinancialDataItem[];
}

export interface FinancialDataResponse {
    company_code: string;
    company_name: string;
    report_type: ReportType;
    periods: FinancialDataPeriod[];
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

export const financialDataApi = {
    /**
     * 获取公司原始财务数据（多年对比）
     */
    async getFinancialData(
        stockCode: string,
        reportType: ReportType = 'BS',
        years: number = 5,
    ): Promise<FinancialDataResponse> {
        const params = new URLSearchParams({
            report_type: reportType,
            years: String(years),
        });
        return fetchJson<FinancialDataResponse>(
            `${API_BASE}/${stockCode}/financial-data?${params.toString()}`,
        );
    },
};
