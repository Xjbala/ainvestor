/**
 * 爬虫任务 API 服务
 *
 * 提供与后端爬虫任务管理 API 的通信功能
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_BASE = `${API_URL}/api/crawler`;

// ============================================================
// 类型定义
// ============================================================

export type TaskStatus = 'pending' | 'running' | 'success' | 'completed' | 'failed' | 'cancelled';

export type DataType = 'company_list' | 'balance_sheet' | 'income_statement' | 'cash_flow' | 'stock_price' | 'batch_financial_data' | 'qualitative_report' | 'news_sentiment';

export interface DataSource {
    id: number;
    code: string;
    name: string;
    api_type: string;
    is_active: boolean;
    rate_limit: number;
    timeout: number;
}

export interface Task {
    id: string;
    task_name: string;
    data_source_id: number;
    data_type: string;
    status: TaskStatus;
    progress: number;
    total_count: number;
    success_count: number;
    error_count: number;
    /** 任务执行明细日志（过程/错误样本） */
    detail_log?: string | null;
    target_companies?: string[] | null;
    scheduled_time: string | null;
    started_at: string | null;
    completed_at: string | null;
    created_at: string;
}

export interface TaskListResponse {
    tasks: Task[];
    total: number;
    skip: number;
    limit: number;
}

export interface CreateTaskRequest {
    task_name: string;
    data_source_code?: string;
    data_type: DataType;
    target_companies?: string[];
    start_date?: string;
    end_date?: string;
    scheduled_time?: string;
    years?: number[];
}

export interface MessageResponse {
    message: string;
}

export interface QualitativeReport {
    id: number;
    company_code: string;
    report_type: string;
    report_period: string;
    publish_date: string | null;
    overview: string | null;
    revenue_analysis: string | null;
    cost_analysis: string | null;
    rd_investment: string | null;
    core_competencies: string | null;
    risk_factors: string | null;
    risk_keywords: Record<string, unknown> | null;
    future_outlook: string | null;
    capacity_plans: string | null;
    management_discussion: string | null;
    raw_markdown_length: number | null;
    extraction_method: string | null;
    source_url: string | null;
}

export interface NewsItem {
    id: number;
    title: string;
    url: string | null;
    publish_date: string;
    sentiment_score: number;
    sentiment_label: string;
    keywords: string[] | null;
}

export interface CreateQualitativeRequest {
    task_name: string;
    data_source_code?: string;
    target_companies: string[];
    report_types?: string[];
    years?: number[];
}

export interface CreateNewsRequest {
    task_name: string;
    data_source_code?: string;
    target_companies: string[];
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
// 爬虫 API
// ============================================================

export const crawlerApi = {
    /**
     * 获取可用数据源列表
     */
    async getDataSources(): Promise<DataSource[]> {
        return fetchJson<DataSource[]>(`${API_BASE}/sources`);
    },

    /**
     * 创建爬虫任务
     */
    async createTask(request: CreateTaskRequest): Promise<Task> {
        return fetchJson<Task>(`${API_BASE}/tasks`, {
            method: 'POST',
            body: JSON.stringify(request),
        });
    },

    /**
     * 获取任务列表
     */
    async getTasks(
        skip: number = 0,
        limit: number = 20,
        statusFilter?: TaskStatus
    ): Promise<TaskListResponse> {
        const params = new URLSearchParams({
            skip: String(skip),
            limit: String(limit),
        });
        if (statusFilter) {
            params.set('status_filter', statusFilter);
        }
        return fetchJson<TaskListResponse>(`${API_BASE}/tasks?${params.toString()}`);
    },

    /**
     * 获取任务详情
     */
    async getTask(taskId: string): Promise<Task> {
        return fetchJson<Task>(`${API_BASE}/tasks/${taskId}`);
    },

    /**
     * 取消任务
     */
    async cancelTask(taskId: string): Promise<MessageResponse> {
        return fetchJson<MessageResponse>(`${API_BASE}/tasks/${taskId}/cancel`, {
            method: 'POST',
        });
    },

    /**
     * 删除任务
     */
    async deleteTask(taskId: string): Promise<MessageResponse> {
        return fetchJson<MessageResponse>(`${API_BASE}/tasks/${taskId}`, {
            method: 'DELETE',
        });
    },

    /**
     * 全量财务数据批量采集
     * 自动获取所有活跃公司，并发采集三大报表
     */
    async createBatchFinancialTask(years?: number[]): Promise<Task> {
        return fetchJson<Task>(`${API_BASE}/tasks/batch-financial`, {
            method: 'POST',
            body: JSON.stringify({
                task_name: years ? `全量财务数据采集(${years.join('-')})` : '全量财务数据批量采集',
                data_source_code: 'sina',
                years,
            }),
        });
    },

    /**
     * 创建定性数据采集任务
     * 从巨潮资讯网下载年报/季报PDF，解析MD&A
     */
    async createQualitativeTask(request: CreateQualitativeRequest): Promise<Task> {
        return fetchJson<Task>(`${API_BASE}/tasks/qualitative`, {
            method: 'POST',
            body: JSON.stringify({
                task_name: request.task_name || '定性数据采集',
                data_source_code: request.data_source_code || 'cninfo',
                target_companies: request.target_companies,
                report_types: request.report_types || ['annual', 'semi', 'q1', 'q3'],
                years: request.years,
            }),
        });
    },

    /**
     * 创建新闻舆情采集任务
     */
    async createNewsTask(request: CreateNewsRequest): Promise<Task> {
        return fetchJson<Task>(`${API_BASE}/tasks/news`, {
            method: 'POST',
            body: JSON.stringify({
                task_name: request.task_name || '新闻舆情采集',
                data_source_code: request.data_source_code || 'sina_news',
                target_companies: request.target_companies,
            }),
        });
    },

    /**
     * 获取公司定性报告列表
     */
    async getQualitativeReports(stockCode: string, includeMarkdown: boolean = false): Promise<QualitativeReport[]> {
        const params = includeMarkdown ? '?include_markdown=true' : '';
        return fetchJson<QualitativeReport[]>(`${API_BASE}/qualitative/${stockCode}${params}`);
    },

    /**
     * 获取公司最新定性报告
     */
    async getLatestQualitativeReport(stockCode: string, includeMarkdown: boolean = false): Promise<QualitativeReport | null> {
        const params = includeMarkdown ? '?include_markdown=true' : '';
        return fetchJson<QualitativeReport | null>(`${API_BASE}/qualitative/${stockCode}/latest${params}`);
    },

    /**
     * 获取公司新闻情绪数据
     */
    async getNewsSentiment(stockCode: string, days: number = 90): Promise<NewsItem[]> {
        return fetchJson<NewsItem[]>(`${API_BASE}/news/${stockCode}?days=${days}`);
    },
};