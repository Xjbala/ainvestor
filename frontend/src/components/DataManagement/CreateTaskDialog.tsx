/**
 * 创建任务弹窗组件
 *
 * 支持多种数据类型：
 * - 股票列表 / 股价数据 / 财务报表 / 批量采集（定量）
 * - 年报/季报PDF采集（定性）
 * - 新闻舆情采集（定性）
 *
 * 公司选择支持两种方式：
 * - 单选/多选：通过下拉选择已有公司
 * - 批量输入：手动输入6位股票代码
 */

import React, { useState, useEffect, useCallback } from 'react';
import { X, Plus, Trash2, Database, Sparkles, Building2, Users } from 'lucide-react';
import { crawlerApi, type DataType } from '../../services/crawlerApi';
import { companiesApi } from '../../services/companiesApi';

interface CreateTaskDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onTaskCreated: () => void;
}

// 公司接口（用于下拉选择）
interface CompanyOption {
    stock_code: string;
    stock_name: string;
}

// 数据源配置
const DATA_SOURCES = [
    { code: 'exchange_api', name: '交易所官方', description: '深交所+上交所官方数据，更准确' },
    { code: 'sina', name: '新浪财经', description: '新浪财经数据，支持财务报表' },
] as const;

// 数据类型支持的数据源映射
const DATA_TYPE_SOURCES: Record<DataType, readonly { code: string; name: string; description: string }[]> = {
    company_list: DATA_SOURCES,
    stock_price: [{ code: 'sina', name: '新浪财经', description: '新浪财经数据' }],
    balance_sheet: [{ code: 'sina', name: '新浪财经', description: '新浪财经财务数据' }],
    income_statement: [{ code: 'sina', name: '新浪财经', description: '新浪财经财务数据' }],
    cash_flow: [{ code: 'sina', name: '新浪财经', description: '新浪财经财务数据' }],
    batch_financial_data: [{ code: 'sina', name: '新浪财经', description: '批量采集所有公司三大报表' }],
    qualitative_report: [{ code: 'cninfo', name: '巨潮资讯网', description: '年报/季报PDF采集' }],
    news_sentiment: [{ code: 'sina_news', name: '新浪财经新闻', description: '新闻舆情采集' }],
};

// 默认数据源映射
const DEFAULT_DATA_SOURCE: Record<DataType, string> = {
    company_list: 'exchange_api',
    stock_price: 'sina',
    balance_sheet: 'sina',
    income_statement: 'sina',
    cash_flow: 'sina',
    batch_financial_data: 'sina',
    qualitative_report: 'cninfo',
    news_sentiment: 'sina_news',
};

// 数据类型显示标签
const DATA_TYPE_LABELS: Record<DataType, string> = {
    company_list: '股票列表',
    balance_sheet: '资产负债表（单公司）',
    income_statement: '利润表（单公司）',
    cash_flow: '现金流量表（单公司）',
    stock_price: '股票价格',
    batch_financial_data: '全量批量采集（三大报表·所有公司）',
    qualitative_report: '年报/季报PDF采集（定性）',
    news_sentiment: '新闻舆情采集（定性）',
};

// 常用年份快捷选项
const YEAR_PRESETS = [
    { label: '最近3年', years: [2023, 2024, 2025] },
    { label: '最近5年', years: [2021, 2022, 2023, 2024, 2025] },
    { label: '最近10年', years: [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025] },
];

// 报告类型选项
const REPORT_TYPE_OPTIONS = [
    { value: 'annual', label: '年报' },
    { value: 'semi', label: '中报' },
    { value: 'q1', label: '一季报' },
    { value: 'q3', label: '三季报' },
];

export const CreateTaskDialog: React.FC<CreateTaskDialogProps> = ({ isOpen, onClose, onTaskCreated }) => {
    const [taskName, setTaskName] = useState('');
    const [dataType, setDataType] = useState<DataType>('company_list');
    const [dataSourceCode, setDataSourceCode] = useState('exchange_api');
    const [companyInput, setCompanyInput] = useState('');
    const [companies, setCompanies] = useState<string[]>([]);
    const [selectedCompany, setSelectedCompany] = useState('');
    const [companyOptions, setCompanyOptions] = useState<CompanyOption[]>([]);
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    // 全量采集年份选择
    const [selectedYears, setSelectedYears] = useState<number[]>([2021, 2022, 2023, 2024, 2025]);
    // 定性数据：报告类型多选
    const [selectedReportTypes, setSelectedReportTypes] = useState<string[]>(['annual', 'semi', 'q1', 'q3']);
    // 新闻数据：天数
    const [newsDays, setNewsDays] = useState(90);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');
    const [companySelectionMode, setCompanySelectionMode] = useState<'dropdown' | 'manual'>('dropdown');
    const [isLoadingCompanies, setIsLoadingCompanies] = useState(false);
    const [companySearch, setCompanySearch] = useState('');

    // 数据类型变化时，更新可用数据源和默认值
    useEffect(() => {
        const availableSources = DATA_TYPE_SOURCES[dataType];
        const defaultSource = DEFAULT_DATA_SOURCE[dataType];
        if (availableSources.length > 0) {
            setDataSourceCode(defaultSource);
        }
    }, [dataType]);

    // 弹窗关闭时重置表单
    useEffect(() => {
        if (!isOpen) {
            resetForm();
        }
    }, [isOpen]);

    // 加载公司列表（下拉选择用）
    // 后端分页接口返回 { items, total, page, page_size }，支持 search 过滤
    const loadCompanies = useCallback(async (search?: string) => {
        setIsLoadingCompanies(true);
        try {
            const data = await companiesApi.listCompanies(1, 100, search?.trim() || undefined);
            const list = data.items || [];
            setCompanyOptions(
                list.map((c) => ({
                    stock_code: c.stock_code,
                    stock_name: c.stock_name || c.company_name || c.stock_code,
                }))
            );
        } catch (err) {
            console.error('Failed to load companies:', err);
            setCompanyOptions([]);
        } finally {
            setIsLoadingCompanies(false);
        }
    }, []);

    // 打开弹窗或切换到下拉模式时加载公司列表
    useEffect(() => {
        if (isOpen && companySelectionMode === 'dropdown') {
            loadCompanies(companySearch);
        }
    }, [isOpen, companySelectionMode, loadCompanies]);

    // 搜索防抖
    useEffect(() => {
        if (!isOpen || companySelectionMode !== 'dropdown') return;
        const timer = setTimeout(() => {
            loadCompanies(companySearch);
        }, 300);
        return () => clearTimeout(timer);
    }, [companySearch, isOpen, companySelectionMode, loadCompanies]);

    const resetForm = () => {
        setTaskName('');
        setDataType('company_list');
        setDataSourceCode('exchange_api');
        setCompanies([]);
        setSelectedCompany('');
        setCompanyInput('');
        setCompanySearch('');
        setStartDate('');
        setEndDate('');
        setSelectedYears([2021, 2022, 2023, 2024, 2025]);
        setSelectedReportTypes(['annual', 'semi', 'q1', 'q3']);
        setNewsDays(90);
        setError('');
        setCompanySelectionMode('dropdown');
    };

    const handleAddCompany = () => {
        const code = companyInput.trim().toUpperCase();
        // 验证6位股票代码格式
        if (!/^\d{6}$/.test(code)) {
            setError('请输入6位股票代码，如 600519');
            return;
        }
        if (!companies.includes(code)) {
            setCompanies([...companies, code]);
            setCompanyInput('');
            setError('');
        }
    };

    const handleRemoveCompany = (code: string) => {
        setCompanies(companies.filter(c => c !== code));
    };

    const handleDropdownAddCompany = () => {
        if (selectedCompany) {
            const code = selectedCompany;
            if (!companies.includes(code)) {
                setCompanies([...companies, code]);
                setSelectedCompany('');
                setError('');
            }
        }
    };

    const toggleYear = (year: number) => {
        setSelectedYears(prev =>
            prev.includes(year) ? prev.filter(y => y !== year) : [...prev, year].sort()
        );
    };

    const applyYearPreset = (presetsYears: number[]) => {
        setSelectedYears(presetsYears);
    };

    const toggleReportType = (type: string) => {
        setSelectedReportTypes(prev =>
            prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
        );
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        if (!taskName.trim()) {
            setError('请输入任务名称');
            return;
        }

        // 定性数据和新闻数据需要公司代码
        const needsCompany = ['qualitative_report', 'news_sentiment', 'balance_sheet', 'income_statement', 'cash_flow', 'stock_price'].includes(dataType);
        if (needsCompany && companies.length === 0) {
            setError('请至少选择一个公司');
            return;
        }

        // 全量批量采集需要年份
        if (dataType === 'batch_financial_data' && selectedYears.length === 0) {
            setError('请至少选择一个采集年份');
            return;
        }

        // 定性数据需要报告类型
        if (dataType === 'qualitative_report' && selectedReportTypes.length === 0) {
            setError('请至少选择一个报告类型');
            return;
        }

        setIsSubmitting(true);

        try {
            if (dataType === 'batch_financial_data') {
                // 全量批量采集走专用接口
                await crawlerApi.createBatchFinancialTask(selectedYears);
            } else if (dataType === 'qualitative_report') {
                // 定性数据采集
                await crawlerApi.createQualitativeTask({
                    task_name: taskName.trim(),
                    data_source_code: dataSourceCode,
                    target_companies: companies,
                    report_types: selectedReportTypes,
                    years: selectedYears.length > 0 ? selectedYears : undefined,
                });
            } else if (dataType === 'news_sentiment') {
                // 新闻舆情采集
                await crawlerApi.createNewsTask({
                    task_name: taskName.trim(),
                    data_source_code: dataSourceCode,
                    target_companies: companies,
                });
            } else {
                // 普通任务走原有接口
                await crawlerApi.createTask({
                    task_name: taskName.trim(),
                    data_source_code: dataSourceCode,
                    data_type: dataType,
                    target_companies: companies.length > 0 ? companies : undefined,
                    start_date: startDate || undefined,
                    end_date: endDate || undefined,
                });
            }

            onTaskCreated();
            handleClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : '创建任务失败');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleClose = () => {
        resetForm();
        onClose();
    };

    // 判断是否显示公司代码输入
    const showCompanyInput = needsCompanySelection(dataType);
    // 判断是否显示日期范围
    const showDateRange = ['balance_sheet', 'income_statement', 'cash_flow'].includes(dataType);
    // 判断是否显示数据源选择
    const availableSources = DATA_TYPE_SOURCES[dataType];
    const hasMultipleSources = availableSources.length > 1;

    function needsCompanySelection(dt: DataType): boolean {
        return ['qualitative_report', 'news_sentiment', 'balance_sheet', 'income_statement', 'cash_flow', 'stock_price'].includes(dt);
    }

    // 判断是否显示报告类型选择（仅定性数据）
    const showReportTypeSelection = dataType === 'qualitative_report';
    // 判断是否显示新闻天数选择（仅新闻数据）
    const showNewsDays = dataType === 'news_sentiment';

    if (!isOpen) return null;

    // 生成最近20年选项
    const currentYear = new Date().getFullYear();
    const yearOptions = Array.from({ length: 20 }, (_, i) => currentYear - i - 1);

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-gray-200 sticky top-0 bg-white z-10 rounded-t-2xl">
                    <h2 className="text-xl font-bold text-gray-900">创建数据同步任务</h2>
                    <button
                        onClick={handleClose}
                        className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                    >
                        <X className="w-5 h-5 text-gray-500" />
                    </button>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="p-6 space-y-6">
                    {/* Task Name */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            任务名称 <span className="text-red-500">*</span>
                        </label>
                        <input
                            type="text"
                            value={taskName}
                            onChange={(e) => setTaskName(e.target.value)}
                            placeholder={getTaskPlaceholder(dataType)}
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                    </div>

                    {/* Data Type */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            数据类型 <span className="text-red-500">*</span>
                        </label>
                        <select
                            value={dataType}
                            onChange={(e) => setDataType(e.target.value as DataType)}
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        >
                            {Object.entries(DATA_TYPE_LABELS).map(([value, label]) => (
                                <option key={value} value={value}>{label}</option>
                            ))}
                        </select>
                        {dataType === 'batch_financial_data' && (
                            <p className="mt-1 text-xs text-gray-500">
                                自动采集所有A股上市公司的三大报表，支持断点续采和并发控制
                            </p>
                        )}
                        {dataType === 'qualitative_report' && (
                            <p className="mt-1 text-xs text-gray-500">
                                从巨潮资讯网下载PDF年报/季报，通过AI解析提取管理层讨论与风险分析
                            </p>
                        )}
                        {dataType === 'news_sentiment' && (
                            <p className="mt-1 text-xs text-gray-500">
                                采集上市公司相关新闻，进行简单情绪分析（正面/负面/中性）
                            </p>
                        )}
                    </div>

                    {/* Data Source */}
                    {hasMultipleSources && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                <Database className="w-4 h-4 inline mr-1" />
                                数据源 <span className="text-red-500">*</span>
                            </label>
                            <div className="space-y-2">
                                {(availableSources as typeof DATA_SOURCES).map((source) => (
                                    <label
                                        key={source.code}
                                        className={`flex items-start p-3 border rounded-lg cursor-pointer transition-all ${
                                            dataSourceCode === source.code
                                                ? 'border-blue-500 bg-blue-50'
                                                : 'border-gray-200 hover:border-gray-300'
                                        }`}
                                    >
                                        <input
                                            type="radio"
                                            name="dataSource"
                                            value={source.code}
                                            checked={dataSourceCode === source.code}
                                            onChange={(e) => setDataSourceCode(e.target.value)}
                                            className="mt-1 mr-3"
                                        />
                                        <div>
                                            <div className="font-medium text-gray-900">{source.name}</div>
                                            <div className="text-sm text-gray-500">{source.description}</div>
                                        </div>
                                    </label>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Single Data Source Info */}
                    {!hasMultipleSources && (
                        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                            <div className="flex items-center gap-2 text-sm text-gray-600">
                                <Database className="w-4 h-4" />
                                <span>数据源：</span>
                                <span className="font-medium">{availableSources[0].name}</span>
                                <span className="text-gray-400">- {availableSources[0].description}</span>
                            </div>
                        </div>
                    )}

                    {/* Company Selection (for financial data, qualitative, news) */}
                    {showCompanyInput && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                目标公司 <span className="text-red-500">*</span>
                            </label>

                            {/* Selection mode toggle */}
                            <div className="flex gap-2 mb-3">
                                <button
                                    type="button"
                                    onClick={() => setCompanySelectionMode('dropdown')}
                                    className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm rounded-lg border transition-colors ${
                                        companySelectionMode === 'dropdown'
                                            ? 'bg-blue-50 border-blue-500 text-blue-700'
                                            : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                                    }`}
                                >
                                    <Building2 className="w-4 h-4" />
                                    从列表选择
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setCompanySelectionMode('manual')}
                                    className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm rounded-lg border transition-colors ${
                                        companySelectionMode === 'manual'
                                            ? 'bg-blue-50 border-blue-500 text-blue-700'
                                            : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                                    }`}
                                >
                                    <Users className="w-4 h-4" />
                                    手动输入代码
                                </button>
                            </div>

                            {/* Dropdown mode */}
                            {companySelectionMode === 'dropdown' && (
                                <div className="space-y-2 mb-3">
                                    <input
                                        type="text"
                                        value={companySearch}
                                        onChange={(e) => setCompanySearch(e.target.value)}
                                        placeholder="搜索股票代码或名称，如 600519 / 茅台"
                                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                    />
                                    <div className="flex gap-2">
                                        <select
                                            value={selectedCompany}
                                            onChange={(e) => setSelectedCompany(e.target.value)}
                                            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            disabled={isLoadingCompanies}
                                        >
                                            <option value="">
                                                {isLoadingCompanies
                                                    ? '-- 加载中... --'
                                                    : companyOptions.length === 0
                                                        ? '-- 无匹配公司，可切换手动输入 --'
                                                        : `-- 选择公司（${companyOptions.length}）--`}
                                            </option>
                                            {companyOptions.map((opt) => (
                                                <option key={opt.stock_code} value={opt.stock_code}>
                                                    {opt.stock_code} {opt.stock_name}
                                                </option>
                                            ))}
                                        </select>
                                        <button
                                            type="button"
                                            onClick={handleDropdownAddCompany}
                                            disabled={!selectedCompany}
                                            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:bg-gray-400 disabled:cursor-not-allowed"
                                        >
                                            <Plus className="w-4 h-4" />
                                            添加
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* Manual input mode */}
                            {companySelectionMode === 'manual' && (
                                <div className="flex gap-2 mb-3">
                                    <input
                                        type="text"
                                        value={companyInput}
                                        onChange={(e) => {
                                            setCompanyInput(e.target.value);
                                            if (error) setError('');
                                        }}
                                        onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddCompany())}
                                        placeholder="输入6位股票代码，如 600519"
                                        className={`flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                                            error ? 'border-red-300' : 'border-gray-300'
                                        }`}
                                        maxLength={6}
                                    />
                                    <button
                                        type="button"
                                        onClick={handleAddCompany}
                                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
                                    >
                                        <Plus className="w-4 h-4" />
                                        添加
                                    </button>
                                </div>
                            )}

                            {error && (
                                <p className="text-sm text-red-500 mb-2">{error}</p>
                            )}

                            {companies.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-2">
                                    {companies.map((code) => {
                                        const name = companyOptions.find(c => c.stock_code === code)?.stock_name || code;
                                        return (
                                            <div
                                                key={code}
                                                className="inline-flex items-center gap-1 px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm"
                                            >
                                                {code} {name}
                                                <button
                                                    type="button"
                                                    onClick={() => handleRemoveCompany(code)}
                                                    className="hover:text-blue-900"
                                                >
                                                    <Trash2 className="w-3 h-3" />
                                                </button>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Batch Financial: Year Selection */}
                    {dataType === 'batch_financial_data' && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                采集年份 <span className="text-red-500">*</span>
                            </label>
                            {/* Presets */}
                            <div className="flex gap-2 mb-3">
                                {YEAR_PRESETS.map((preset) => (
                                    <button
                                        key={preset.label}
                                        type="button"
                                        onClick={() => applyYearPreset(preset.years)}
                                        className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                                            JSON.stringify(selectedYears.sort()) === JSON.stringify(preset.years.sort())
                                                ? 'bg-blue-50 border-blue-500 text-blue-700'
                                                : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                                        }`}
                                    >
                                        {preset.label}
                                    </button>
                                ))}
                            </div>
                            {/* Year toggles */}
                            <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto p-2 bg-gray-50 rounded-lg">
                                {yearOptions.map((year) => (
                                    <button
                                        key={year}
                                        type="button"
                                        onClick={() => toggleYear(year)}
                                        className={`px-3 py-1.5 text-sm rounded-md border transition-colors font-mono ${
                                            selectedYears.includes(year)
                                                ? 'bg-blue-600 text-white border-blue-600'
                                                : 'bg-white text-gray-700 border-gray-200 hover:border-gray-300'
                                        }`}
                                    >
                                        {year}
                                    </button>
                                ))}
                            </div>
                            <p className="mt-1 text-xs text-gray-500">
                                已选 {selectedYears.length} 年 · 点击年份切换选中状态
                            </p>
                        </div>
                    )}

                    {/* Qualitative: Report Type + Year Selection */}
                    {showReportTypeSelection && (
                        <>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    报告类型 <span className="text-red-500">*</span>
                                </label>
                                <div className="flex flex-wrap gap-2">
                                    {REPORT_TYPE_OPTIONS.map((opt) => (
                                        <button
                                            key={opt.value}
                                            type="button"
                                            onClick={() => toggleReportType(opt.value)}
                                            className={`px-4 py-2 text-sm rounded-lg border transition-colors ${
                                                selectedReportTypes.includes(opt.value)
                                                    ? 'bg-purple-600 text-white border-purple-600'
                                                    : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                                            }`}
                                        >
                                            {opt.label}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    采集年份（可选，不选则采集所有年份）
                                </label>
                                <div className="flex gap-2 mb-3">
                                    {YEAR_PRESETS.map((preset) => (
                                        <button
                                            key={preset.label}
                                            type="button"
                                            onClick={() => applyYearPreset(preset.years)}
                                            className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                                                JSON.stringify(selectedYears.sort()) === JSON.stringify(preset.years.sort())
                                                    ? 'bg-purple-50 border-purple-500 text-purple-700'
                                                    : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                                            }`}
                                        >
                                            {preset.label}
                                        </button>
                                    ))}
                                </div>
                                <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto p-2 bg-gray-50 rounded-lg">
                                    {yearOptions.map((year) => (
                                        <button
                                            key={year}
                                            type="button"
                                            onClick={() => toggleYear(year)}
                                            className={`px-3 py-1.5 text-sm rounded-md border transition-colors font-mono ${
                                                selectedYears.includes(year)
                                                    ? 'bg-purple-600 text-white border-purple-600'
                                                    : 'bg-white text-gray-700 border-gray-200 hover:border-gray-300'
                                            }`}
                                        >
                                            {year}
                                        </button>
                                    ))}
                                </div>
                                <p className="mt-1 text-xs text-gray-500">
                                    已选 {selectedYears.length} 年 · 留空表示采集所有可用年份
                                </p>
                            </div>
                        </>
                    )}

                    {/* News: Days selector */}
                    {showNewsDays && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                最近天数 <span className="text-red-500">*</span>
                            </label>
                            <div className="flex gap-2">
                                {[30, 90, 180, 365].map((days) => (
                                    <button
                                        key={days}
                                        type="button"
                                        onClick={() => setNewsDays(days)}
                                        className={`px-4 py-2 text-sm rounded-lg border transition-colors ${
                                            newsDays === days
                                                ? 'bg-green-600 text-white border-green-600'
                                                : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                                        }`}
                                    >
                                        最近{days}天
                                    </button>
                                ))}
                                <input
                                    type="number"
                                    value={newsDays}
                                    onChange={(e) => setNewsDays(Math.max(1, parseInt(e.target.value) || 1))}
                                    className="w-20 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent text-center"
                                    min={1}
                                    max={3650}
                                />
                            </div>
                        </div>
                    )}

                    {/* Date Range */}
                    {showDateRange && (
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    开始日期
                                </label>
                                <input
                                    type="date"
                                    value={startDate}
                                    onChange={(e) => setStartDate(e.target.value)}
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    结束日期
                                </label>
                                <input
                                    type="date"
                                    value={endDate}
                                    onChange={(e) => setEndDate(e.target.value)}
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                />
                            </div>
                        </div>
                    )}

                    {/* Error Message */}
                    {error && (
                        <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
                            {error}
                        </div>
                    )}

                    {/* Footer */}
                    <div className="flex gap-3 pt-4">
                        <button
                            type="button"
                            onClick={handleClose}
                            className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                        >
                            取消
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                            {isSubmitting ? (
                                <>
                                    <span className="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full"></span>
                                    创建中...
                                </>
                            ) : dataType === 'batch_financial_data' ? (
                                <>
                                    <Sparkles className="w-4 h-4" />
                                    一键全量采集
                                </>
                            ) : (
                                '创建任务'
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

// 辅助函数：根据数据类型返回任务名称占位符
function getTaskPlaceholder(dataType: DataType): string {
    switch (dataType) {
        case 'batch_financial_data':
            return '全量财务数据批量采集';
        case 'qualitative_report':
            return '定性数据采集（年报/季报PDF）';
        case 'news_sentiment':
            return '新闻舆情采集';
        case 'company_list':
            return '同步沪深股票列表';
        default:
            return '例如：同步600519财务数据';
    }
}
