/**
 * 财务分析 API 服务（专业版）
 *
 * 提供与后端财务分析和估值 API 的通信功能
 * 基于 leofun 项目的专业估值实现
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_BASE = `${API_URL}/api`;

// ============================================================
// 类型定义
// ============================================================

export interface Company {
    stock_code: string;
    stock_name: string;
    company_name: string;
    industry?: string;
}

export interface Indicator {
    year: number;
    report_date: string;
    [key: string]: number | string;
}

export interface TrendAnalysis {
    [metric: string]: {
        latest_value: number;
        earliest_value: number;
        change: number;
        change_percent: number;
        trend: 'improving' | 'worsening' | 'stable';
    };
}

export interface Conclusion {
    summary: string;
    risk_level: 'low' | 'medium' | 'high' | 'unknown';
    detailed_assessment?: Record<string, string>;
    recommendations?: string[];
}

export interface AnalysisResult {
    company: Company | null;
    analysis_period?: {
        years: number;
        data_years: number[];
    };
    indicators: Indicator[];
    trend_analysis: TrendAnalysis;
    conclusion: Conclusion;
    error?: string;
}

export interface AnalysisSummary {
    stock_code: string;
    stock_name: string | null;
    solvency_risk: string;
    profitability_risk: string;
    growth_risk: string;
    operating_risk: string;
    overall_risk: string;
    summary: string;
}

// ============================================================
// DCF 估值结果类型
// ============================================================

export interface DCFValuationResult {
    company: Company | null;
    method: string;
    valuation_date: string;
    base_report_date: string;
    parameters: {
        growth_rate: number;
        terminal_growth_rate: number;
        discount_rate: number;
        tax_rate: number;
        projection_years: number;
        shares_outstanding: number;
        net_debt: number;
    };
    inputs: {
        revenue: number;
        operating_income: number;
        net_income: number;
        operating_cash_flow: number;
        capital_expenditure: number;
        base_fcf: number;
        net_debt: number;
        shares_outstanding: number;
    };
    valuation: {
        pv_projected_fcf: number;
        terminal_value: number;
        pv_terminal_value: number;
        enterprise_value: number;
        equity_value: number;
        intrinsic_value_per_share: number;
        calculation_detail: {
            base_fcf: number;
            projected_fcf: number[];
            pv_projected_fcf_detail: number[];
            terminal_fcf: number;
            terminal_value: number;
            discount_factors: number[];
        };
    };
    current_price: number;
    upside_downside: number | null;
    investment_rating: 'STRONG_BUY' | 'BUY' | 'HOLD' | 'REDUCE' | 'SELL' | null;
    margin_of_safety: {
        margin_percent: number;
        diff: number;
        status: string;
        recommendation: string;
    };
    error?: string;
}

// ============================================================
// 剩余收益估值结果类型
// ============================================================

export interface RIValuationResult {
    company: Company | null;
    method: string;
    valuation_date: string;
    base_report_date: string;
    parameters: {
        cost_of_equity: number;
        growth_rate: number;
        terminal_growth_rate: number;
        projection_years: number;
        payout_ratio: number;
        shares_outstanding: number;
    };
    inputs: {
        net_income: number;
        shareholders_equity: number;
        shares_outstanding: number;
        current_eps: number;
        current_bps: number;
        current_roe: number;
    };
    valuation: {
        base_book_value_per_share: number;
        pv_forecast_ri: number;
        terminal_value_per_share: number;
        pv_terminal_value: number;
        intrinsic_value_per_share: number;
        equity_value: number;
        calculation_detail: {
            current_eps: number;
            current_dps: number;
            current_bps: number;
            current_roe: number;
            dividend_payout_ratio: number;
            projected_eps: number[];
            projected_dps: number[];
            projected_bps: number[];
            projected_roe: number[];
            projected_ri: number[];
            pv_projected_ri_detail: number[];
            terminal_ri: number;
            discount_factors: number[];
        };
    };
    current_price: number;
    upside_downside: number | null;
    investment_rating: 'STRONG_BUY' | 'BUY' | 'HOLD' | 'REDUCE' | 'SELL' | null;
    margin_of_safety: {
        margin_percent: number;
        diff: number;
        status: string;
        recommendation: string;
    };
    error?: string;
}

// 通用估值结果类型（兼容旧代码）
export type ValuationResult = DCFValuationResult | RIValuationResult;

export interface ValuationComparison {
    stock_code: string;
    stock_name: string | null;
    dcf_value: number | null;
    ri_value: number | null;
    relative_value?: number | null;
    average_value: number | null;
    blended_price?: number | null;
    current_price: number | null;
    divergence_pct?: number | null;
    confidence?: string | null;
    recommendation: string;
    headline?: string | null;
}

export interface WACCBreakdown {
    stock_code: string;
    wacc: number;
    ke: number;
    kd: number;
    rf: number;
    beta: number;
    erp: number;
    size_premium: number;
    tax_rate: number;
    e_weight: number;
    d_weight: number;
    industry?: string;
    profile_key?: string;
    sources?: Record<string, string>;
    sanity?: { in_sector_band: boolean; band: number[]; message?: string | null };
    exit_ev_ebitda?: number;
    error?: string;
}

export interface RelativeValuationResult {
    company: Company | null;
    method: string;
    applicable?: boolean;
    industry?: string;
    primary_multiple?: string;
    adjustment?: { factor: number; reasons: string[] };
    medians?: { pe?: number | null; pb?: number | null; ps?: number | null };
    implied_by_multiple?: Record<string, number | null>;
    valuation?: {
        intrinsic_value_per_share: number;
        scenarios?: Record<string, unknown>;
    };
    peers?: Array<Record<string, unknown>>;
    target_metrics?: Record<string, unknown>;
    current_price?: number;
    upside_downside?: number | null;
    investment_rating?: string | null;
    margin_of_safety?: {
        margin_percent: number;
        diff: number;
        status: string;
        recommendation: string;
    };
    confidence?: string;
    error?: string;
}

export interface TriangulatedValuation {
    stock_code: string;
    company: Company | null;
    current_price: number;
    wacc?: WACCBreakdown;
    methods: Array<{
        method: string;
        applicable: boolean;
        implied_price: number | null;
        confidence?: string;
        skip_reason?: string | null;
        assumptions?: Record<string, unknown>;
        upside_downside?: number | null;
        investment_rating?: string | null;
    }>;
    weights: Record<string, number>;
    weights_used?: Record<string, number>;
    blended_price: number | null;
    upside_pct: number | null;
    divergence_pct: number | null;
    confidence: string;
    scenarios?: {
        bull: { price: number; levers: Record<string, string> };
        base: { price: number; levers: Record<string, string> };
        bear: { price: number; levers: Record<string, string> };
    };
    sensitivity?: {
        wacc_axis: number[];
        g_axis: number[];
        grid: Array<Array<number | null>>;
        base_wacc: number;
        base_g: number;
    };
    investment_rating?: string;
    margin_of_safety?: {
        margin_percent: number;
        diff: number;
        status: string;
        recommendation: string;
    };
    headline?: string;
    risks?: string[];
    industry_profile?: Record<string, unknown>;
    error?: string;
}

// ============================================================
// API 请求函数
// ============================================================

async function fetchJson<T>(url: string): Promise<T> {
    const response = await fetch(url);
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API request failed: ${response.status} - ${errorText}`);
    }
    return response.json();
}

// ============================================================
// 财务分析 API
// ============================================================

export const analysisApi = {
    /**
     * 偿债能力分析
     */
    async getSolvency(stockCode: string, years = 5): Promise<AnalysisResult> {
        return fetchJson(`${API_BASE}/analysis/solvency/${stockCode}?years=${years}`);
    },

    /**
     * 盈利能力分析
     */
    async getProfitability(stockCode: string, years = 5): Promise<AnalysisResult> {
        return fetchJson(`${API_BASE}/analysis/profitability/${stockCode}?years=${years}`);
    },

    /**
     * 发展能力分析
     */
    async getGrowth(stockCode: string, years = 5): Promise<AnalysisResult> {
        return fetchJson(`${API_BASE}/analysis/growth/${stockCode}?years=${years}`);
    },

    /**
     * 营运能力分析
     */
    async getOperating(stockCode: string, years = 5): Promise<AnalysisResult> {
        return fetchJson(`${API_BASE}/analysis/operating/${stockCode}?years=${years}`);
    },

    /**
     * 综合分析摘要
     */
    async getSummary(stockCode: string, years = 5): Promise<AnalysisSummary> {
        return fetchJson(`${API_BASE}/analysis/summary/${stockCode}?years=${years}`);
    },

    /**
     * 获取全部四维分析
     */
    async getFullAnalysis(stockCode: string, years = 5) {
        const [solvency, profitability, growth, operating, summary] = await Promise.all([
            this.getSolvency(stockCode, years),
            this.getProfitability(stockCode, years),
            this.getGrowth(stockCode, years),
            this.getOperating(stockCode, years),
            this.getSummary(stockCode, years),
        ]);

        return { solvency, profitability, growth, operating, summary };
    },
};

// ============================================================
// 估值 API
// ============================================================

export interface DCFParams {
    growth_rate?: number;
    terminal_growth_rate?: number;
    discount_rate?: number;
    tax_rate?: number;
    projection_years?: number;
}

export interface RIParams {
    cost_of_equity?: number;
    growth_rate?: number;
    terminal_growth_rate?: number;
    projection_years?: number;
    payout_ratio?: number;
}

export const valuationApi = {
    /**
     * DCF 估值（专业版，自动 WACC + 双终值 + 敏感性）
     */
    async getDCF(stockCode: string, params?: DCFParams): Promise<DCFValuationResult> {
        const queryParams = new URLSearchParams();
        if (params?.growth_rate !== undefined) queryParams.set('growth_rate', String(params.growth_rate));
        if (params?.terminal_growth_rate !== undefined) queryParams.set('terminal_growth_rate', String(params.terminal_growth_rate));
        if (params?.discount_rate !== undefined) queryParams.set('discount_rate', String(params.discount_rate));
        if (params?.tax_rate !== undefined) queryParams.set('tax_rate', String(params.tax_rate));
        if (params?.projection_years !== undefined) queryParams.set('projection_years', String(params.projection_years));

        const query = queryParams.toString();
        return fetchJson(`${API_BASE}/valuation/dcf/${stockCode}${query ? '?' + query : ''}`);
    },

    /**
     * 剩余收益估值（专业版）
     */
    async getResidualIncome(stockCode: string, params?: RIParams): Promise<RIValuationResult> {
        const queryParams = new URLSearchParams();
        if (params?.cost_of_equity !== undefined) queryParams.set('cost_of_equity', String(params.cost_of_equity));
        if (params?.growth_rate !== undefined) queryParams.set('growth_rate', String(params.growth_rate));
        if (params?.terminal_growth_rate !== undefined) queryParams.set('terminal_growth_rate', String(params.terminal_growth_rate));
        if (params?.projection_years !== undefined) queryParams.set('projection_years', String(params.projection_years));
        if (params?.payout_ratio !== undefined) queryParams.set('payout_ratio', String(params.payout_ratio));

        const query = queryParams.toString();
        return fetchJson(`${API_BASE}/valuation/residual-income/${stockCode}${query ? '?' + query : ''}`);
    },

    /**
     * 相对估值（同业倍数）
     */
    async getRelative(stockCode: string): Promise<RelativeValuationResult> {
        return fetchJson(`${API_BASE}/valuation/relative/${stockCode}`);
    },

    /**
     * WACC / CAPM 拆解
     */
    async getWACC(stockCode: string): Promise<WACCBreakdown> {
        return fetchJson(`${API_BASE}/valuation/wacc/${stockCode}`);
    },

    /**
     * 多方法三角验证综合估值
     */
    async getTriangulate(stockCode: string): Promise<TriangulatedValuation> {
        return fetchJson(`${API_BASE}/valuation/triangulate/${stockCode}`);
    },

    /**
     * SOTP 分部加总（无分部数据时 applicable=false）
     */
    async getSOTP(stockCode: string): Promise<Record<string, unknown>> {
        return fetchJson(`${API_BASE}/valuation/sotp/${stockCode}`);
    },

    /**
     * 查询 company_segments
     */
    async getSegments(stockCode: string, latestOnly = true): Promise<Array<Record<string, unknown>>> {
        return fetchJson(
            `${API_BASE}/segments/${stockCode}?latest_only=${latestOnly ? 'true' : 'false'}`
        );
    },

    /**
     * 从已采集年报 Markdown 抽取分部并入库
     */
    async extractSegments(
        stockCode: string,
        opts?: { use_llm_fallback?: boolean; persist?: boolean }
    ): Promise<Record<string, unknown>> {
        const res = await fetch(`${API_BASE}/segments/${stockCode}/extract`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                use_llm_fallback: opts?.use_llm_fallback ?? true,
                persist: opts?.persist ?? true,
            }),
        });
        if (!res.ok) {
            const t = await res.text();
            throw new Error(`extract segments failed: ${res.status} ${t}`);
        }
        return res.json();
    },

    /**
     * 批量写入分部
     */
    async bulkSegments(body: {
        company_code: string;
        report_period: string;
        report_type?: string;
        source?: string;
        segments: Array<Record<string, unknown>>;
    }): Promise<Record<string, unknown>> {
        const res = await fetch(`${API_BASE}/segments/bulk`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const t = await res.text();
            throw new Error(`bulk segments failed: ${res.status} ${t}`);
        }
        return res.json();
    },

    /**
     * 估值对比（含 relative + blended）
     */
    async getComparison(stockCode: string): Promise<ValuationComparison> {
        return fetchJson(`${API_BASE}/valuation/compare/${stockCode}`);
    },
};