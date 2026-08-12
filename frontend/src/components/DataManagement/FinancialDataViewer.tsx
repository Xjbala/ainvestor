/**
 * 财务报表数据查看页
 *
 * 选择公司 → 查看三大报表（BS/IS/CF）多年对比数据，
 * 并可视化核心科目完整性与会计勾稽校验结果。
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
    BookOpen,
    Loader2,
    AlertCircle,
    CheckCircle2,
    AlertTriangle,
    XCircle,
    ShieldCheck,
    ChevronDown,
    ChevronRight,
} from 'lucide-react';
import { CompanySearchInput } from './CompanySearchInput';
import {
    financialDataApi,
    type ReportType,
    type FinancialDataResponse,
    type PeriodValidation,
    type ValidationStatus,
    type AccountingCheckItem,
} from '../../services/financialDataApi';

const REPORT_TYPE_OPTIONS: { value: ReportType; label: string }[] = [
    { value: 'BS', label: '资产负债表' },
    { value: 'IS', label: '利润表' },
    { value: 'CF', label: '现金流量表' },
];

const STATUS_META: Record<
    ValidationStatus,
    { label: string; color: string; bg: string; border: string; icon: React.ReactNode }
> = {
    pass: {
        label: '通过',
        color: 'text-success',
        bg: 'bg-[rgba(19,177,90,0.06)]',
        border: 'border-[rgba(19,177,90,0.2)]',
        icon: <CheckCircle2 className="w-4 h-4" />,
    },
    partial: {
        label: '部分',
        color: 'text-warning',
        bg: 'bg-[rgba(244,179,102,0.1)]',
        border: 'border-[rgba(244,179,102,0.3)]',
        icon: <AlertTriangle className="w-4 h-4" />,
    },
    fail: {
        label: '失败',
        color: 'text-destructive',
        bg: 'bg-[rgba(239,68,68,0.06)]',
        border: 'border-[rgba(239,68,68,0.2)]',
        icon: <XCircle className="w-4 h-4" />,
    },
    empty: {
        label: '无数据',
        color: 'text-muted-foreground',
        bg: 'bg-muted',
        border: 'border-border',
        icon: <AlertCircle className="w-4 h-4" />,
    },
};

function formatValue(val: number | null | undefined): string {
    if (val === null || val === undefined) return '-';
    const abs = Math.abs(val);
    if (abs >= 1e8) return (val / 1e8).toFixed(2) + ' 亿';
    if (abs >= 1e4) return (val / 1e4).toFixed(2) + ' 万';
    return val.toFixed(2);
}

function formatPct(rate: number | null | undefined): string {
    if (rate === null || rate === undefined) return '-';
    return `${(rate * 100).toFixed(0)}%`;
}

function StatusBadge({ status }: { status: ValidationStatus }) {
    const meta = STATUS_META[status] || STATUS_META.empty;
    return (
        <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium ${meta.bg} ${meta.color} border ${meta.border}`}
        >
            {meta.icon}
            {meta.label}
        </span>
    );
}

function ValidationPanel({
    data,
    selectedDate,
    onSelectDate,
}: {
    data: FinancialDataResponse;
    selectedDate: string | null;
    onSelectDate: (date: string) => void;
}) {
    const [expanded, setExpanded] = useState(true);
    const summary = data.validation_summary;
    const periods = data.periods || [];
    const selected =
        periods.find((p) => p.report_date === selectedDate)?.validation ||
        periods[0]?.validation ||
        null;

    if (!summary && periods.length === 0) return null;

    const overall = (summary?.overall_status || 'empty') as ValidationStatus;
    const overallMeta = STATUS_META[overall] || STATUS_META.empty;

    return (
        <div className={`mb-5 border rounded-vibe ${overallMeta.border} overflow-hidden`}>
            <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className={`w-full flex items-center justify-between px-4 py-3 ${overallMeta.bg}`}
            >
                <div className="flex items-center gap-3 min-w-0">
                    <ShieldCheck className={`w-5 h-5 shrink-0 ${overallMeta.color}`} />
                    <div className="text-left min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-semibold text-foreground">数据完整性校验</span>
                            <StatusBadge status={overall} />
                            {summary && (
                                <span className="text-xs text-muted-foreground">
                                    核心科目覆盖 {formatPct(summary.avg_core_hit_rate)}
                                </span>
                            )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5 truncate">
                            {summary?.summary || '暂无校验摘要'}
                        </p>
                    </div>
                </div>
                {expanded ? (
                    <ChevronDown className="w-4 h-4 text-muted-foreground shrink-0" />
                ) : (
                    <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />
                )}
            </button>

            {expanded && (
                <div className="bg-card px-4 py-4 space-y-4">
                    {/* 总览计数 */}
                    {summary && (
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                            <MetricTile label="通过" value={summary.pass_count} tone="green" />
                            <MetricTile label="部分" value={summary.partial_count} tone="amber" />
                            <MetricTile label="失败" value={summary.fail_count} tone="red" />
                            <MetricTile
                                label="平均核心覆盖"
                                value={formatPct(summary.avg_core_hit_rate)}
                                tone="blue"
                            />
                        </div>
                    )}

                    {/* 各报告期状态条 */}
                    <div>
                        <div className="text-xs font-medium text-muted-foreground mb-2">报告期状态</div>
                        <div className="flex flex-wrap gap-2">
                            {periods.map((p) => {
                                const st = (p.validation?.status || 'empty') as ValidationStatus;
                                const active = (selectedDate || periods[0]?.report_date) === p.report_date;
                                const meta = STATUS_META[st] || STATUS_META.empty;
                                return (
                                    <button
                                        key={p.report_date}
                                        type="button"
                                        onClick={() => onSelectDate(p.report_date)}
                                        className={`px-3 py-1.5 rounded-vibe-sm border text-xs transition-all ${
                                            active
                                                ? `${meta.bg} ${meta.border} ${meta.color} ring-2 ring-offset-1 ring-ring`
                                                : 'bg-card border-border text-muted-foreground hover:border-input'
                                        }`}
                                    >
                                        <span className="font-medium">{p.report_date}</span>
                                        <span className="ml-1.5 opacity-80">{meta.label}</span>
                                        {p.validation && (
                                            <span className="ml-1.5 text-[10px] opacity-70">
                                                {formatPct(p.validation.core_hit_rate)}
                                            </span>
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* 选中期详情 */}
                    {selected && <PeriodValidationDetail validation={selected} />}
                </div>
            )}
        </div>
    );
}

function MetricTile({
    label,
    value,
    tone,
}: {
    label: string;
    value: string | number;
    tone: 'green' | 'amber' | 'red' | 'blue';
}) {
    const tones = {
        green: 'bg-[rgba(19,177,90,0.06)] text-success border-[rgba(19,177,90,0.15)]',
        amber: 'bg-[rgba(244,179,102,0.1)] text-warning border-[rgba(244,179,102,0.2)]',
        red: 'bg-[rgba(239,68,68,0.06)] text-destructive border-[rgba(239,68,68,0.15)]',
        blue: 'bg-brand-50 text-brand-700 border-brand-100',
    };
    return (
        <div className={`rounded-vibe-sm border px-3 py-2 ${tones[tone]}`}>
            <div className="text-[11px] opacity-80">{label}</div>
            <div className="text-lg font-semibold mt-0.5">{value}</div>
        </div>
    );
}

function PeriodValidationDetail({ validation }: { validation: PeriodValidation }) {
    return (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* 核心科目 */}
            <div className="border border-border rounded-vibe-sm overflow-hidden">
                <div className="px-3 py-2 bg-muted border-b border-border flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground">核心科目</span>
                    <span className="text-xs text-muted-foreground">
                        {validation.core_present}/{validation.core_total} · 必填{' '}
                        {validation.core_required_present}/{validation.core_required_total}
                    </span>
                </div>
                <div className="max-h-64 overflow-y-auto divide-y divide-border">
                    {validation.core_subjects.map((s) => (
                        <div
                            key={s.code}
                            className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
                        >
                            <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                    <span className="font-mono text-[11px] text-muted-foreground">{s.code}</span>
                                    <span className="text-foreground truncate">{s.name}</span>
                                    {s.required && (
                                        <span className="text-[10px] px-1 rounded bg-[rgba(239,68,68,0.06)] text-destructive border border-[rgba(239,68,68,0.15)]">
                                            必填
                                        </span>
                                    )}
                                </div>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                                <span className="font-mono text-xs text-muted-foreground">
                                    {formatValue(s.value)}
                                </span>
                                {s.present ? (
                                    <CheckCircle2 className="w-4 h-4 text-success" />
                                ) : (
                                    <XCircle
                                        className={`w-4 h-4 ${s.required ? 'text-destructive' : 'text-warning'}`}
                                    />
                                )}
                            </div>
                        </div>
                    ))}
                    {validation.core_subjects.length === 0 && (
                        <div className="px-3 py-6 text-center text-xs text-muted-foreground">无核心科目定义</div>
                    )}
                </div>
                {(validation.missing_required.length > 0 || validation.missing_optional.length > 0) && (
                    <div className="px-3 py-2 bg-muted border-t border-border text-xs text-muted-foreground space-y-1">
                        {validation.missing_required.length > 0 && (
                            <div>
                                <span className="text-destructive font-medium">缺必填：</span>
                                {validation.missing_required.map((m) => m.name).join('、')}
                            </div>
                        )}
                        {validation.missing_optional.length > 0 && (
                            <div>
                                <span className="text-warning font-medium">缺可选：</span>
                                {validation.missing_optional.map((m) => m.name).join('、')}
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* 勾稽校验 */}
            <div className="border border-border rounded-vibe-sm overflow-hidden">
                <div className="px-3 py-2 bg-muted border-b border-border flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground">会计勾稽</span>
                    <span className="text-xs text-muted-foreground">{validation.summary}</span>
                </div>
                <div className="max-h-64 overflow-y-auto divide-y divide-border">
                    {validation.accounting_checks.length === 0 ? (
                        <div className="px-3 py-6 text-center text-xs text-muted-foreground">
                            当前报表无可用勾稽规则或数据不足
                        </div>
                    ) : (
                        validation.accounting_checks.map((c) => (
                            <AccountingCheckRow key={c.key} check={c} />
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}

function AccountingCheckRow({ check }: { check: AccountingCheckItem }) {
    const ok = check.passed;
    const warn = !ok && check.severity === 'warning';
    return (
        <div className="px-3 py-2.5">
            <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                    <div className="flex items-center gap-2">
                        {ok ? (
                            <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                        ) : warn ? (
                            <AlertTriangle className="w-4 h-4 text-warning shrink-0" />
                        ) : (
                            <XCircle className="w-4 h-4 text-destructive shrink-0" />
                        )}
                        <span className="text-sm font-medium text-foreground">{check.name}</span>
                        {!ok && (
                            <span
                                className={`text-[10px] px-1 rounded border ${
                                    warn
                                        ? 'bg-[rgba(244,179,102,0.1)] text-warning border-[rgba(244,179,102,0.2)]'
                                        : 'bg-[rgba(239,68,68,0.06)] text-destructive border-[rgba(239,68,68,0.15)]'
                                }`}
                            >
                                {warn ? '预警' : '错误'}
                            </span>
                        )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 ml-6">{check.message}</p>
                </div>
            </div>
            <div className="mt-2 ml-6 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <div className="rounded-md bg-muted px-2 py-1.5">
                    <div className="text-muted-foreground truncate">{check.left_label}</div>
                    <div className="font-mono text-foreground mt-0.5">{formatValue(check.left_value)}</div>
                </div>
                <div className="rounded-md bg-muted px-2 py-1.5">
                    <div className="text-muted-foreground truncate">{check.right_label}</div>
                    <div className="font-mono text-foreground mt-0.5">{formatValue(check.right_value)}</div>
                </div>
            </div>
            {check.diff !== null && check.diff !== undefined && (
                <div className="mt-1.5 ml-6 text-[11px] text-muted-foreground">
                    差额：
                    <span className={`font-mono ml-1 ${ok ? 'text-success' : 'text-destructive'}`}>
                        {formatValue(check.diff)}
                    </span>
                </div>
            )}
        </div>
    );
}

export const FinancialDataViewer: React.FC<{
    initialStockCode?: string;
}> = ({ initialStockCode }) => {
    const [stockCode, setStockCode] = useState(initialStockCode || '');
    const [reportType, setReportType] = useState<ReportType>('BS');
    const [years, setYears] = useState(5);
    const [data, setData] = useState<FinancialDataResponse | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [selectedDate, setSelectedDate] = useState<string | null>(null);

    useEffect(() => {
        if (initialStockCode && initialStockCode !== stockCode) {
            setStockCode(initialStockCode);
        }
        // 仅在外部传入焦点公司时同步
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [initialStockCode]);

    useEffect(() => {
        if (!stockCode) {
            setData(null);
            setSelectedDate(null);
            return;
        }
        let cancelled = false;
        setIsLoading(true);
        setError('');
        financialDataApi
            .getFinancialData(stockCode, reportType, years)
            .then((res) => {
                if (!cancelled) {
                    setData(res);
                    setSelectedDate(res.periods[0]?.report_date || null);
                }
            })
            .catch((e) => {
                if (!cancelled) setError(e.message);
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [stockCode, reportType, years]);

    const periods = data?.periods || [];
    const subjectMap = useMemo(() => {
        const map = new Map<string, { subject_code: string; subject_name: string }>();
        for (const p of periods) {
            for (const item of p.items) {
                if (!map.has(item.subject_code)) {
                    map.set(item.subject_code, {
                        subject_code: item.subject_code,
                        subject_name: item.subject_name,
                    });
                }
            }
        }
        return map;
    }, [periods]);

    const coreCodeSet = useMemo(() => {
        const set = new Set<string>();
        for (const s of data?.core_subjects || []) set.add(s.code);
        // 也并入各期 core_subjects，避免定义缺失
        for (const p of periods) {
            for (const s of p.validation?.core_subjects || []) set.add(s.code);
        }
        return set;
    }, [data?.core_subjects, periods]);

    const requiredCoreSet = useMemo(() => {
        const set = new Set<string>();
        for (const s of data?.core_subjects || []) {
            if (s.required) set.add(s.code);
        }
        for (const p of periods) {
            for (const s of p.validation?.core_subjects || []) {
                if (s.required) set.add(s.code);
            }
        }
        return set;
    }, [data?.core_subjects, periods]);

    // 以第一个 period 的顺序为基准，后面追加新增的科目；核心科目优先置顶
    const subjects = useMemo(() => {
        const firstItems = periods[0]?.items || [];
        const ordered: { subject_code: string; subject_name: string }[] = [];
        const seen = new Set<string>();

        const push = (code: string) => {
            if (seen.has(code)) return;
            const v = subjectMap.get(code);
            if (!v) return;
            seen.add(code);
            ordered.push(v);
        };

        // 核心科目按定义顺序
        for (const s of data?.core_subjects || []) push(s.code);
        for (const it of firstItems) push(it.subject_code);
        for (const [, v] of subjectMap) push(v.subject_code);
        return ordered;
    }, [periods, subjectMap, data?.core_subjects]);

    const periodValueMaps = periods.map((p) => {
        const m = new Map<string, number | null>();
        for (const item of p.items) m.set(item.subject_code, item.value);
        return m;
    });

    return (
        <div>
            {/* 控制栏 */}
            <div className="flex flex-wrap items-center gap-4 mb-6">
                <CompanySearchInput value={stockCode} onChange={setStockCode} />
                <div className="flex gap-1 bg-muted p-1 rounded-vibe-sm">
                    {REPORT_TYPE_OPTIONS.map((opt) => (
                        <button
                            key={opt.value}
                            onClick={() => setReportType(opt.value)}
                            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                                reportType === opt.value
                                    ? 'bg-card text-primary shadow-sm'
                                    : 'text-muted-foreground hover:text-foreground'
                            }`}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>
                <select
                    value={years}
                    onChange={(e) => setYears(Number(e.target.value))}
                    className="px-3 py-1.5 border border-input rounded-vibe-sm text-sm"
                >
                    {[1, 2, 3, 5, 10].map((y) => (
                        <option key={y} value={y}>
                            近 {y} 年
                        </option>
                    ))}
                </select>
            </div>

            {/* 加载/错误/空状态 */}
            {isLoading && (
                <div className="flex items-center justify-center py-20 text-muted-foreground">
                    <Loader2 className="w-6 h-6 animate-spin mr-2" /> 加载中...
                </div>
            )}
            {error && (
                <div className="flex items-center gap-2 py-10 text-destructive">
                    <AlertCircle className="w-5 h-5" /> {error}
                </div>
            )}
            {!isLoading && !error && !stockCode && (
                <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
                    <BookOpen className="w-12 h-12 mb-3" />
                    <p>请先选择一家公司查看财务数据</p>
                </div>
            )}
            {!isLoading && !error && stockCode && periods.length === 0 && (
                <div className="text-center py-10 text-muted-foreground">暂无数据</div>
            )}

            {/* 校验面板 + 数据表格 */}
            {periods.length > 0 && data && (
                <>
                    <ValidationPanel
                        data={data}
                        selectedDate={selectedDate}
                        onSelectDate={setSelectedDate}
                    />

                    <div className="overflow-x-auto border border-border rounded-vibe">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="bg-muted">
                                    <th className="text-left px-4 py-3 font-medium text-muted-foreground sticky left-0 bg-muted z-10 min-w-[220px]">
                                        科目
                                    </th>
                                    {periods.map((p) => {
                                        const st = (p.validation?.status || 'empty') as ValidationStatus;
                                        const meta = STATUS_META[st] || STATUS_META.empty;
                                        const active = selectedDate === p.report_date;
                                        return (
                                            <th
                                                key={p.report_date}
                                                className={`text-right px-4 py-3 font-medium min-w-[150px] cursor-pointer ${
                                                    active ? 'bg-brand-50/60 text-brand-700' : 'text-muted-foreground'
                                                }`}
                                                onClick={() => setSelectedDate(p.report_date)}
                                                title={p.validation?.summary || ''}
                                            >
                                                <div>{p.report_date}</div>
                                                <div className="mt-1 flex items-center justify-end gap-1">
                                                    <span className="text-xs text-muted-foreground">
                                                        {p.report_period === 'annual' ? '年报' : p.report_period}
                                                    </span>
                                                    <span
                                                        className={`inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded ${meta.bg} ${meta.color}`}
                                                    >
                                                        {meta.label}
                                                    </span>
                                                </div>
                                            </th>
                                        );
                                    })}
                                </tr>
                            </thead>
                            <tbody>
                                {subjects.map((subject) => {
                                    const isCore = coreCodeSet.has(subject.subject_code);
                                    const isRequired = requiredCoreSet.has(subject.subject_code);
                                    return (
                                        <tr
                                            key={subject.subject_code}
                                            className={`border-t border-border hover:bg-brand-50/30 ${
                                                isCore ? 'bg-muted/60' : ''
                                            }`}
                                        >
                                            <td className="px-4 py-2 text-foreground sticky left-0 bg-inherit z-10">
                                                <div className="flex items-center gap-1.5 flex-wrap">
                                                    <span className="font-mono text-xs text-muted-foreground">
                                                        {subject.subject_code}
                                                    </span>
                                                    <span className={isCore ? 'font-medium' : ''}>
                                                        {subject.subject_name}
                                                    </span>
                                                    {isCore && (
                                                        <span
                                                            className={`text-[10px] px-1 rounded border ${
                                                                isRequired
                                                                    ? 'bg-[rgba(239,68,68,0.06)] text-destructive border-[rgba(239,68,68,0.15)]'
                                                                    : 'bg-brand-50 text-primary border-brand-100'
                                                            }`}
                                                        >
                                                            {isRequired ? '核心·必填' : '核心'}
                                                        </span>
                                                    )}
                                                </div>
                                            </td>
                                            {periodValueMaps.map((valMap, pi) => {
                                                const val = valMap.get(subject.subject_code);
                                                const missingCore =
                                                    isCore && (val === null || val === undefined);
                                                return (
                                                    <td
                                                        key={periods[pi].report_date}
                                                        className={`px-4 py-2 text-right font-mono ${
                                                            missingCore
                                                                ? 'text-destructive bg-[rgba(239,68,68,0.04)]'
                                                                : val === null || val === undefined
                                                                  ? 'text-muted-foreground'
                                                                  : 'text-foreground'
                                                        }`}
                                                    >
                                                        {formatValue(val ?? null)}
                                                    </td>
                                                );
                                            })}
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </>
            )}

            {data && periods.length > 0 && (
                <p className="mt-3 text-xs text-muted-foreground">
                    {data.company_name}（{data.company_code}）·{' '}
                    {REPORT_TYPE_OPTIONS.find((o) => o.value === data.report_type)?.label} ·
                    {periods.length} 个报告期 · {subjects.length} 个科目
                    {data.validation_summary
                        ? ` · 校验 ${STATUS_META[data.validation_summary.overall_status]?.label || data.validation_summary.overall_status}`
                        : ''}
                </p>
            )}
        </div>
    );
};
