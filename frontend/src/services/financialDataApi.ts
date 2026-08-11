/**
 * 原始财务数据 API 服务
 *
 * 提供公司三大报表（资产负债表/利润表/现金流量表）原始科目数据查询，
 * 以及核心科目完整性 / 会计勾稽校验结果。
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_BASE = `${API_URL}/api/companies`;

// ============================================================
// 类型定义
// ============================================================

export type ReportType = 'BS' | 'IS' | 'CF';
export type ValidationStatus = 'pass' | 'partial' | 'fail' | 'empty';

export interface FinancialDataItem {
    subject_code: string;
    subject_name: string;
    value: number | null;
}

export interface SubjectCheckItem {
    code: string;
    name: string;
    required: boolean;
    present: boolean;
    value: number | null;
}

export interface AccountingCheckItem {
    key: string;
    name: string;
    passed: boolean;
    left_label: string;
    left_value: number | null;
    right_label: string;
    right_value: number | null;
    diff: number | null;
    message: string;
    severity: 'error' | 'warning' | string;
}

export interface PeriodValidation {
    report_type: string;
    report_date: string;
    status: ValidationStatus;
    subject_count: number;
    core_total: number;
    core_present: number;
    core_required_total: number;
    core_required_present: number;
    core_hit_rate: number;
    missing_required: Array<{ code: string; name: string }>;
    missing_optional: Array<{ code: string; name: string }>;
    core_subjects: SubjectCheckItem[];
    accounting_checks: AccountingCheckItem[];
    summary: string;
}

export interface ValidationSummary {
    overall_status: ValidationStatus;
    period_count: number;
    pass_count: number;
    partial_count: number;
    fail_count: number;
    empty_count: number;
    avg_core_hit_rate: number;
    summary: string;
}

export interface FinancialDataPeriod {
    report_date: string;
    report_period: string;
    items: FinancialDataItem[];
    validation?: PeriodValidation | null;
}

export interface FinancialDataResponse {
    company_code: string;
    company_name: string;
    report_type: ReportType;
    periods: FinancialDataPeriod[];
    validation_summary?: ValidationSummary | null;
    core_subjects?: Array<{ code: string; name: string; required: boolean }> | null;
}

export type CoverageCellStatus = 'complete' | 'partial' | 'missing';

export interface CoverageCell {
    year: number;
    report_type: ReportType | string;
    status: CoverageCellStatus;
    core_total: number;
    core_present: number;
    core_required_total: number;
    core_required_present: number;
    core_hit_rate: number;
    missing_required: Array<{ code: string; name: string }>;
    missing_optional: Array<{ code: string; name: string }>;
}

export interface CoverageCompany {
    stock_code: string;
    stock_name: string;
    overall_status: CoverageCellStatus;
    complete_cells: number;
    partial_cells: number;
    missing_cells: number;
    expected_cells: number;
    coverage_rate: number;
    cells?: CoverageCell[];
}

export interface CoverageSummary {
    company_count: number;
    matrix_total: number;
    complete_cells: number;
    partial_cells: number;
    missing_cells: number;
    coverage_rate: number;
    gap_company_count: number;
    by_report_type: Record<string, { complete: number; partial: number; missing: number; total: number }>;
    by_year: Record<string, { complete: number; partial: number; missing: number; total: number }>;
}

export interface FinancialCoverageResponse {
    years: number[];
    report_types: string[];
    summary: CoverageSummary;
    gap_companies: string[];
    page: number;
    page_size: number;
    total: number;
    companies: CoverageCompany[];
    core_subjects: Record<string, Array<{ code: string; name: string; required: boolean }>>;
    from_snapshot?: boolean;
    snapshot_id?: number | null;
    scanned_at?: string | null;
    scan_duration_ms?: number | null;
    source?: string | null;
    pagination_source?: 'snapshot_sql' | 'legacy_snapshot_json' | 'snapshot_created' | 'online_scan';
    scope_key?: string | null;
    status_filter?: string;
}

export interface CoverageSnapshotMeta {
    snapshot_id: number;
    scope_key: string;
    years: number[];
    report_types: string[];
    status_filter: string;
    source: string;
    trigger_task_id?: string | null;
    company_count: number;
    gap_company_count: number;
    coverage_rate: number;
    complete_cells: number;
    partial_cells: number;
    missing_cells: number;
    matrix_total: number;
    scan_duration_ms: number;
    scanned_at: string | null;
}

export interface FinancialGapItem {
    stock_code: string;
    stock_name: string;
    year: number;
    report_type: string;
    status: CoverageCellStatus;
    core_hit_rate: number;
    missing_required: Array<{ code: string; name: string }>;
    missing_optional: Array<{ code: string; name: string }>;
}

export interface RepairTarget {
    stock_code: string;
    stock_name: string;
    years: number[];
    report_types: string[];
    gap_count: number;
}

export interface FinancialGapsResponse {
    years: number[];
    report_types: string[];
    summary: CoverageSummary;
    gap_count: number;
    gaps: FinancialGapItem[];
    repair_targets: RepairTarget[];
}

export interface CoverageQuery {
    years?: number[];
    reportTypes?: ReportType[];
    statusFilter?: 'active' | 'all';
    search?: string;
    stockCodes?: string[];
    onlyGaps?: boolean;
    page?: number;
    pageSize?: number;
    includeCells?: boolean;
    useSnapshot?: boolean;
    refresh?: boolean;
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
     * 获取公司原始财务数据（多年对比 + 校验结果）
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

    /**
     * 市场覆盖率看板数据
     */
    async getCoverage(query: CoverageQuery = {}): Promise<FinancialCoverageResponse> {
        const params = new URLSearchParams();
        if (query.years?.length) params.set('years', query.years.join(','));
        if (query.reportTypes?.length) params.set('report_types', query.reportTypes.join(','));
        if (query.statusFilter) params.set('status_filter', query.statusFilter);
        if (query.search) params.set('search', query.search);
        if (query.stockCodes?.length) params.set('stock_codes', query.stockCodes.join(','));
        if (query.onlyGaps) params.set('only_gaps', 'true');
        if (query.page) params.set('page', String(query.page));
        if (query.pageSize) params.set('page_size', String(query.pageSize));
        if (query.includeCells === false) params.set('include_cells', 'false');
        if (query.useSnapshot === false) params.set('use_snapshot', 'false');
        if (query.refresh) params.set('refresh', 'true');
        const qs = params.toString();
        return fetchJson<FinancialCoverageResponse>(
            `${API_BASE}/financial-coverage${qs ? `?${qs}` : ''}`,
        );
    },

    /**
     * 强制扫描并落库快照
     */
    async scanCoverage(options?: {
        years?: number[];
        reportTypes?: ReportType[];
        statusFilter?: 'active' | 'all';
        persist?: boolean;
    }): Promise<FinancialCoverageResponse> {
        const params = new URLSearchParams();
        if (options?.years?.length) params.set('years', options.years.join(','));
        if (options?.reportTypes?.length) params.set('report_types', options.reportTypes.join(','));
        if (options?.statusFilter) params.set('status_filter', options.statusFilter);
        if (options?.persist === false) params.set('persist', 'false');
        const qs = params.toString();
        return fetchJson<FinancialCoverageResponse>(
            `${API_BASE}/financial-coverage/scan${qs ? `?${qs}` : ''}`,
            { method: 'POST' },
        );
    },

    /**
     * 快照历史
     */
    async listSnapshots(query: CoverageQuery = {}): Promise<{ scope_key: string; items: CoverageSnapshotMeta[] }> {
        const params = new URLSearchParams();
        if (query.years?.length) params.set('years', query.years.join(','));
        if (query.reportTypes?.length) params.set('report_types', query.reportTypes.join(','));
        if (query.statusFilter) params.set('status_filter', query.statusFilter);
        if (query.pageSize) params.set('limit', String(query.pageSize));
        const qs = params.toString();
        return fetchJson<{ scope_key: string; items: CoverageSnapshotMeta[] }>(
            `${API_BASE}/financial-coverage/snapshots${qs ? `?${qs}` : ''}`,
        );
    },

    /**
     * 缺口清单（可直接用于补采）
     */
    async getGaps(query: CoverageQuery = {}): Promise<FinancialGapsResponse> {
        const params = new URLSearchParams();
        if (query.years?.length) params.set('years', query.years.join(','));
        if (query.reportTypes?.length) params.set('report_types', query.reportTypes.join(','));
        if (query.statusFilter) params.set('status_filter', query.statusFilter);
        if (query.search) params.set('search', query.search);
        if (query.stockCodes?.length) params.set('stock_codes', query.stockCodes.join(','));
        if (query.pageSize) params.set('limit', String(query.pageSize));
        if (query.useSnapshot === false) params.set('use_snapshot', 'false');
        const qs = params.toString();
        return fetchJson<FinancialGapsResponse>(
            `${API_BASE}/financial-gaps${qs ? `?${qs}` : ''}`,
        );
    },
};
