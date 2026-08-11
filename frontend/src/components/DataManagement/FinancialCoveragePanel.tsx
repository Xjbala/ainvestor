/**
 * 财务数据覆盖率看板
 *
 * 展示 公司 × 报表 × 年份 矩阵完整度，支持筛选缺口并一键补采。
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    AlertCircle,
    CheckCircle2,
    Loader2,
    RefreshCw,
    ShieldAlert,
    Wrench,
    XCircle,
    AlertTriangle,
} from 'lucide-react';
import {
    financialDataApi,
    type CoverageCellStatus,
    type CoverageCompany,
    type FinancialCoverageResponse,
    type ReportType,
} from '../../services/financialDataApi';
import { crawlerApi } from '../../services/crawlerApi';

const REPORT_LABEL: Record<string, string> = {
    BS: '资产负债',
    IS: '利润表',
    CF: '现金流',
};

const STATUS_STYLE: Record<
    CoverageCellStatus,
    { label: string; className: string; dot: string }
> = {
    complete: {
        label: '完整',
        className: 'bg-green-50 text-green-700 border-green-200',
        dot: 'bg-green-500',
    },
    partial: {
        label: '部分',
        className: 'bg-amber-50 text-amber-700 border-amber-200',
        dot: 'bg-amber-500',
    },
    missing: {
        label: '缺失',
        className: 'bg-red-50 text-red-700 border-red-200',
        dot: 'bg-red-500',
    },
};

function defaultYears(count = 5): number[] {
    const end = new Date().getFullYear() - 1;
    return Array.from({ length: count }, (_, i) => end - count + 1 + i);
}

function formatPct(rate: number | null | undefined): string {
    if (rate === null || rate === undefined) return '-';
    return `${(rate * 100).toFixed(1)}%`;
}

function cellKey(year: number, reportType: string) {
    return `${year}-${reportType}`;
}

export const FinancialCoveragePanel: React.FC<{
    onSelectCompany?: (stockCode: string) => void;
}> = ({ onSelectCompany }) => {
    const [years, setYears] = useState<number[]>(() => defaultYears(5));
    const [onlyGaps, setOnlyGaps] = useState(true);
    const [search, setSearch] = useState('');
    const [appliedSearch, setAppliedSearch] = useState('');
    const [page, setPage] = useState(1);
    const [pageSize] = useState(30);
    const [data, setData] = useState<FinancialCoverageResponse | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [repairMsg, setRepairMsg] = useState('');
    const [isRepairing, setIsRepairing] = useState(false);
    const [isScanning, setIsScanning] = useState(false);
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [expandedCode, setExpandedCode] = useState<string | null>(null);
    const [snapshotHint, setSnapshotHint] = useState('');
    const [reloadKey, setReloadKey] = useState(0);
    const latestRequest = useRef(0);

    const load = useCallback(async (opts?: { refresh?: boolean }) => {
        const requestId = ++latestRequest.current;
        setIsLoading(true);
        setError('');
        try {
            const res = await financialDataApi.getCoverage({
                years,
                reportTypes: ['BS', 'IS', 'CF'],
                statusFilter: 'active',
                search: appliedSearch || undefined,
                onlyGaps,
                page,
                pageSize,
                includeCells: true,
                useSnapshot: true,
                refresh: opts?.refresh,
            });
            if (requestId !== latestRequest.current) return;
            setData(res);
            setSelected(new Set());
            if (res.from_snapshot && res.scanned_at) {
                setSnapshotHint(
                    `快照 #${res.snapshot_id ?? '-'} · ${res.scanned_at.replace('T', ' ').slice(0, 19)} · ${res.source || 'snapshot'}`,
                );
            } else if (res.scan_duration_ms != null) {
                setSnapshotHint(`在线扫描 · ${res.scan_duration_ms}ms`);
            } else {
                setSnapshotHint('');
            }
        } catch (e) {
            if (requestId !== latestRequest.current) return;
            setError(e instanceof Error ? e.message : String(e));
        } finally {
            if (requestId === latestRequest.current) {
                setIsLoading(false);
            }
        }
    }, [years, onlyGaps, appliedSearch, page, pageSize]);

    useEffect(() => {
        load();
    }, [load, reloadKey]);

    const handleForceScan = async () => {
        setIsScanning(true);
        setRepairMsg('');
        try {
            const res = await financialDataApi.scanCoverage({
                years,
                reportTypes: ['BS', 'IS', 'CF'],
                statusFilter: 'active',
                persist: true,
            });
            setRepairMsg(
                `已扫描并落库快照 #${res.snapshot_id ?? '-'}，覆盖率 ${formatPct(res.summary?.coverage_rate)}，缺口公司 ${res.summary?.gap_company_count ?? 0}`,
            );
            setPage(1);
            setReloadKey((key) => key + 1);
        } catch (e) {
            setRepairMsg(e instanceof Error ? e.message : String(e));
        } finally {
            setIsScanning(false);
        }
    };

    const reportTypes = data?.report_types || ['BS', 'IS', 'CF'];
    const yearList = data?.years || years;
    const summary = data?.summary;

    const pageCodes = useMemo(
        () => (data?.companies || []).map((c) => c.stock_code),
        [data],
    );

    const allPageSelected =
        pageCodes.length > 0 && pageCodes.every((c) => selected.has(c));

    const toggleAllPage = () => {
        setSelected((prev) => {
            const next = new Set(prev);
            if (allPageSelected) {
                pageCodes.forEach((c) => next.delete(c));
            } else {
                pageCodes.forEach((c) => next.add(c));
            }
            return next;
        });
    };

    const toggleOne = (code: string) => {
        setSelected((prev) => {
            const next = new Set(prev);
            if (next.has(code)) next.delete(code);
            else next.add(code);
            return next;
        });
    };

    const handleRepair = async (codes?: string[]) => {
        setIsRepairing(true);
        setRepairMsg('');
        try {
            const targets = codes && codes.length > 0 ? codes : Array.from(selected);
            const task = await crawlerApi.createFinancialRepairTask({
                years: yearList,
                targetCompanies: targets.length > 0 ? targets : undefined,
                reportTypes: reportTypes as ReportType[],
                maxCompanies: 500,
                autoDetect: true,
            });
            setRepairMsg(
                `已创建补采任务：${task.task_name}（${task.id.slice(0, 8)}…），可在「数据采集」查看进度`,
            );
        } catch (e) {
            setRepairMsg(e instanceof Error ? e.message : String(e));
        } finally {
            setIsRepairing(false);
        }
    };

    const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

    return (
        <div className="space-y-4">
            {/* 控制栏 */}
            <div className="flex flex-wrap items-center gap-3">
                <select
                    value={years.length}
                    onChange={(e) => {
                        setYears(defaultYears(Number(e.target.value)));
                        setPage(1);
                    }}
                    className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm"
                >
                    {[3, 5, 8, 10].map((n) => (
                        <option key={n} value={n}>
                            近 {n} 个完整财年
                        </option>
                    ))}
                </select>

                <label className="inline-flex items-center gap-2 text-sm text-gray-700">
                    <input
                        type="checkbox"
                        checked={onlyGaps}
                        onChange={(e) => {
                            setOnlyGaps(e.target.checked);
                            setPage(1);
                        }}
                        className="rounded border-gray-300"
                    />
                    仅看缺口公司
                </label>

                <div className="flex items-center gap-2">
                    <input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                                setAppliedSearch(search.trim());
                                setPage(1);
                            }
                        }}
                        placeholder="搜索代码/名称"
                        className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm w-44"
                    />
                    <button
                        type="button"
                        onClick={() => {
                            setAppliedSearch(search.trim());
                            setPage(1);
                        }}
                        className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50"
                    >
                        搜索
                    </button>
                </div>

                <button
                    type="button"
                    onClick={() => load()}
                    disabled={isLoading}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                    <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                    刷新
                </button>

                <button
                    type="button"
                    onClick={handleForceScan}
                    disabled={isScanning || isLoading}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-indigo-200 text-indigo-700 bg-indigo-50 hover:bg-indigo-100 disabled:opacity-50"
                >
                    {isScanning ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                        <ShieldAlert className="w-4 h-4" />
                    )}
                    重新扫描落库
                </button>

                <button
                    type="button"
                    onClick={() => handleRepair()}
                    disabled={isRepairing}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                    {isRepairing ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                        <Wrench className="w-4 h-4" />
                    )}
                    {selected.size > 0 ? `补采选中(${selected.size})` : '扫描并补采缺口'}
                </button>
            </div>

            {snapshotHint && (
                <div className="text-xs text-gray-500">
                    数据来源：{snapshotHint}
                </div>
            )}

            {repairMsg && (
                <div
                    className={`text-sm rounded-lg px-3 py-2 border ${
                        repairMsg.includes('已创建') || repairMsg.includes('已扫描')
                            ? 'bg-green-50 border-green-200 text-green-700'
                            : 'bg-amber-50 border-amber-200 text-amber-800'
                    }`}
                >
                    {repairMsg}
                </div>
            )}

            {error && (
                <div className="flex items-center gap-2 text-red-600 text-sm">
                    <AlertCircle className="w-4 h-4" /> {error}
                </div>
            )}

            {/* 总览卡片 */}
            {summary && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    <SummaryCard
                        label="扫描公司"
                        value={summary.company_count}
                        hint={`缺口公司 ${summary.gap_company_count}`}
                    />
                    <SummaryCard
                        label="矩阵覆盖率"
                        value={formatPct(summary.coverage_rate)}
                        hint={`${summary.complete_cells}/${summary.matrix_total} 单元完整`}
                        tone="blue"
                    />
                    <SummaryCard
                        label="完整单元"
                        value={summary.complete_cells}
                        tone="green"
                    />
                    <SummaryCard
                        label="部分单元"
                        value={summary.partial_cells}
                        tone="amber"
                    />
                    <SummaryCard
                        label="缺失单元"
                        value={summary.missing_cells}
                        tone="red"
                    />
                </div>
            )}

            {/* 分报表 / 分年 */}
            {summary && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <BreakdownTable
                        title="按报表类型"
                        rows={Object.entries(summary.by_report_type).map(([k, v]) => ({
                            key: k,
                            label: REPORT_LABEL[k] || k,
                            ...v,
                        }))}
                    />
                    <BreakdownTable
                        title="按年份"
                        rows={Object.entries(summary.by_year)
                            .sort((a, b) => Number(b[0]) - Number(a[0]))
                            .map(([k, v]) => ({
                                key: k,
                                label: k,
                                ...v,
                            }))}
                    />
                </div>
            )}

            {/* 公司矩阵表 */}
            <div className="border border-gray-200 rounded-xl overflow-hidden bg-white">
                <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm font-medium text-gray-800">
                        <ShieldAlert className="w-4 h-4 text-indigo-600" />
                        公司覆盖矩阵
                        {data && (
                            <span className="text-xs text-gray-500 font-normal">
                                共 {data.total} 家 · 第 {page}/{totalPages} 页
                            </span>
                        )}
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-gray-500">
                        {(['complete', 'partial', 'missing'] as CoverageCellStatus[]).map((s) => (
                            <span key={s} className="inline-flex items-center gap-1">
                                <span className={`w-2 h-2 rounded-full ${STATUS_STYLE[s].dot}`} />
                                {STATUS_STYLE[s].label}
                            </span>
                        ))}
                    </div>
                </div>

                {isLoading && (
                    <div className="flex items-center justify-center py-16 text-gray-500">
                        <Loader2 className="w-5 h-5 animate-spin mr-2" /> 扫描中...
                    </div>
                )}

                {!isLoading && data && data.companies.length === 0 && (
                    <div className="py-14 text-center text-gray-500 text-sm">
                        {onlyGaps ? '当前范围内没有缺口公司' : '暂无公司数据'}
                    </div>
                )}

                {!isLoading && data && data.companies.length > 0 && (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="bg-white border-b border-gray-100">
                                    <th className="px-3 py-2 text-left sticky left-0 bg-white z-10">
                                        <input
                                            type="checkbox"
                                            checked={allPageSelected}
                                            onChange={toggleAllPage}
                                            className="rounded border-gray-300"
                                        />
                                    </th>
                                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 sticky left-8 bg-white z-10 min-w-[140px]">
                                        公司
                                    </th>
                                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">
                                        覆盖率
                                    </th>
                                    {yearList.map((y) =>
                                        reportTypes.map((rt) => (
                                            <th
                                                key={cellKey(y, rt)}
                                                className="px-2 py-2 text-center text-[11px] font-medium text-gray-500 min-w-[64px]"
                                            >
                                                <div>{y}</div>
                                                <div className="text-gray-400">{REPORT_LABEL[rt] || rt}</div>
                                            </th>
                                        )),
                                    )}
                                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">
                                        操作
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.companies.map((company) => (
                                    <CompanyCoverageRow
                                        key={company.stock_code}
                                        company={company}
                                        years={yearList}
                                        reportTypes={reportTypes}
                                        checked={selected.has(company.stock_code)}
                                        expanded={expandedCode === company.stock_code}
                                        onToggle={() => toggleOne(company.stock_code)}
                                        onExpand={() =>
                                            setExpandedCode((prev) =>
                                                prev === company.stock_code ? null : company.stock_code,
                                            )
                                        }
                                        onView={() => onSelectCompany?.(company.stock_code)}
                                        onRepair={() => handleRepair([company.stock_code])}
                                    />
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {data && totalPages > 1 && (
                    <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50">
                        <button
                            type="button"
                            disabled={isLoading || page <= 1}
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            className="px-3 py-1 text-sm rounded border border-gray-300 disabled:opacity-40"
                        >
                            上一页
                        </button>
                        <span className="text-xs text-gray-500">
                            {page} / {totalPages}
                        </span>
                        <button
                            type="button"
                            disabled={isLoading || page >= totalPages}
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            className="px-3 py-1 text-sm rounded border border-gray-300 disabled:opacity-40"
                        >
                            下一页
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

function SummaryCard({
    label,
    value,
    hint,
    tone = 'slate',
}: {
    label: string;
    value: string | number;
    hint?: string;
    tone?: 'slate' | 'blue' | 'green' | 'amber' | 'red';
}) {
    const tones = {
        slate: 'bg-white border-gray-200 text-gray-900',
        blue: 'bg-blue-50 border-blue-100 text-blue-800',
        green: 'bg-green-50 border-green-100 text-green-800',
        amber: 'bg-amber-50 border-amber-100 text-amber-800',
        red: 'bg-red-50 border-red-100 text-red-800',
    };
    return (
        <div className={`rounded-xl border px-3 py-3 ${tones[tone]}`}>
            <div className="text-[11px] opacity-70">{label}</div>
            <div className="text-xl font-semibold mt-1">{value}</div>
            {hint && <div className="text-[11px] opacity-70 mt-1">{hint}</div>}
        </div>
    );
}

function BreakdownTable({
    title,
    rows,
}: {
    title: string;
    rows: Array<{
        key: string;
        label: string;
        complete: number;
        partial: number;
        missing: number;
        total: number;
    }>;
}) {
    return (
        <div className="border border-gray-200 rounded-xl overflow-hidden bg-white">
            <div className="px-3 py-2 bg-gray-50 border-b border-gray-100 text-sm font-medium text-gray-800">
                {title}
            </div>
            <table className="w-full text-sm">
                <thead>
                    <tr className="text-xs text-gray-500 border-b border-gray-100">
                        <th className="text-left px-3 py-2 font-medium">维度</th>
                        <th className="text-right px-3 py-2 font-medium">完整</th>
                        <th className="text-right px-3 py-2 font-medium">部分</th>
                        <th className="text-right px-3 py-2 font-medium">缺失</th>
                        <th className="text-right px-3 py-2 font-medium">覆盖</th>
                    </tr>
                </thead>
                <tbody>
                    {rows.map((r) => {
                        const rate = r.total ? r.complete / r.total : 0;
                        return (
                            <tr key={r.key} className="border-t border-gray-50">
                                <td className="px-3 py-2 text-gray-800">{r.label}</td>
                                <td className="px-3 py-2 text-right text-green-700">{r.complete}</td>
                                <td className="px-3 py-2 text-right text-amber-700">{r.partial}</td>
                                <td className="px-3 py-2 text-right text-red-700">{r.missing}</td>
                                <td className="px-3 py-2 text-right font-mono text-gray-700">
                                    {formatPct(rate)}
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

function CompanyCoverageRow({
    company,
    years,
    reportTypes,
    checked,
    expanded,
    onToggle,
    onExpand,
    onView,
    onRepair,
}: {
    company: CoverageCompany;
    years: number[];
    reportTypes: string[];
    checked: boolean;
    expanded: boolean;
    onToggle: () => void;
    onExpand: () => void;
    onView: () => void;
    onRepair: () => void;
}) {
    const cellMap = useMemo(() => {
        const m = new Map<string, NonNullable<CoverageCompany['cells']>[number]>();
        for (const c of company.cells || []) {
            m.set(cellKey(c.year, String(c.report_type)), c);
        }
        return m;
    }, [company.cells]);

    const overall = STATUS_STYLE[company.overall_status] || STATUS_STYLE.missing;

    return (
        <>
            <tr className="border-t border-gray-100 hover:bg-slate-50/60">
                <td className="px-3 py-2 sticky left-0 bg-inherit z-10">
                    <input
                        type="checkbox"
                        checked={checked}
                        onChange={onToggle}
                        className="rounded border-gray-300"
                    />
                </td>
                <td className="px-3 py-2 sticky left-8 bg-inherit z-10">
                    <button type="button" onClick={onExpand} className="text-left">
                        <div className="font-medium text-gray-900">
                            {company.stock_code}
                            <span
                                className={`ml-2 text-[10px] px-1.5 py-0.5 rounded border ${overall.className}`}
                            >
                                {overall.label}
                            </span>
                        </div>
                        <div className="text-xs text-gray-500 truncate max-w-[160px]">
                            {company.stock_name}
                        </div>
                    </button>
                </td>
                <td className="px-3 py-2 text-right font-mono text-gray-700">
                    {formatPct(company.coverage_rate)}
                    <div className="text-[10px] text-gray-400">
                        {company.complete_cells}/{company.expected_cells}
                    </div>
                </td>
                {years.map((y) =>
                    reportTypes.map((rt) => {
                        const cell = cellMap.get(cellKey(y, rt));
                        const st = (cell?.status || 'missing') as CoverageCellStatus;
                        const style = STATUS_STYLE[st];
                        return (
                            <td key={cellKey(y, rt)} className="px-2 py-2 text-center">
                                <span
                                    title={
                                        cell
                                            ? `${st} · 核心 ${cell.core_present}/${cell.core_total}` +
                                              (cell.missing_required?.length
                                                  ? ` · 缺: ${cell.missing_required.map((m) => m.name).join(',')}`
                                                  : '')
                                            : 'missing'
                                    }
                                    className={`inline-flex items-center justify-center w-7 h-7 rounded-md border text-[10px] font-medium ${style.className}`}
                                >
                                    {st === 'complete' ? (
                                        <CheckCircle2 className="w-3.5 h-3.5" />
                                    ) : st === 'partial' ? (
                                        <AlertTriangle className="w-3.5 h-3.5" />
                                    ) : (
                                        <XCircle className="w-3.5 h-3.5" />
                                    )}
                                </span>
                            </td>
                        );
                    }),
                )}
                <td className="px-3 py-2 text-right whitespace-nowrap">
                    <button
                        type="button"
                        onClick={onView}
                        className="text-xs text-blue-600 hover:underline mr-2"
                    >
                        查看
                    </button>
                    <button
                        type="button"
                        onClick={onRepair}
                        className="text-xs text-indigo-600 hover:underline"
                    >
                        补采
                    </button>
                </td>
            </tr>
            {expanded && (
                <tr className="bg-slate-50/80">
                    <td colSpan={4 + years.length * reportTypes.length} className="px-4 py-3">
                        <div className="text-xs text-gray-600 space-y-1">
                            {(company.cells || [])
                                .filter((c) => c.status !== 'complete')
                                .map((c) => (
                                    <div key={cellKey(c.year, String(c.report_type))}>
                                        <span className="font-medium text-gray-800">
                                            {c.year} {REPORT_LABEL[String(c.report_type)] || c.report_type}
                                        </span>
                                        <span className="ml-2 text-gray-500">
                                            核心 {c.core_present}/{c.core_total} · {STATUS_STYLE[c.status].label}
                                        </span>
                                        {c.missing_required?.length > 0 && (
                                            <span className="ml-2 text-red-600">
                                                缺必填：
                                                {c.missing_required.map((m) => m.name).join('、')}
                                            </span>
                                        )}
                                    </div>
                                ))}
                            {(company.cells || []).every((c) => c.status === 'complete') && (
                                <div className="text-green-700">该矩阵范围内核心科目齐全</div>
                            )}
                        </div>
                    </td>
                </tr>
            )}
        </>
    );
}
