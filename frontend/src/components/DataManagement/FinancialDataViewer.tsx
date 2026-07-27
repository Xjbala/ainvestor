/**
 * 财务报表数据查看页
 *
 * 选择公司 → 查看三大报表（BS/IS/CF）多年对比数据。
 */

import React, { useState, useEffect } from 'react';
import { BookOpen, Loader2, AlertCircle } from 'lucide-react';
import { CompanySearchInput } from './CompanySearchInput';
import { financialDataApi, type ReportType, type FinancialDataResponse } from '../../services/financialDataApi';

const REPORT_TYPE_OPTIONS: { value: ReportType; label: string }[] = [
    { value: 'BS', label: '资产负债表' },
    { value: 'IS', label: '利润表' },
    { value: 'CF', label: '现金流量表' },
];

function formatValue(val: number | null): string {
    if (val === null || val === undefined) return '-';
    const abs = Math.abs(val);
    if (abs >= 1e8) return (val / 1e8).toFixed(2) + ' 亿';
    if (abs >= 1e4) return (val / 1e4).toFixed(2) + ' 万';
    return val.toFixed(2);
}

export const FinancialDataViewer: React.FC = () => {
    const [stockCode, setStockCode] = useState('');
    const [reportType, setReportType] = useState<ReportType>('BS');
    const [years, setYears] = useState(5);
    const [data, setData] = useState<FinancialDataResponse | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!stockCode) {
            setData(null);
            return;
        }
        let cancelled = false;
        setIsLoading(true);
        setError('');
        financialDataApi
            .getFinancialData(stockCode, reportType, years)
            .then((res) => {
                if (!cancelled) setData(res);
            })
            .catch((e) => {
                if (!cancelled) setError(e.message);
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false);
            });
        return () => { cancelled = true; };
    }, [stockCode, reportType, years]);

    // 收集所有科目：合并所有 period 的 subject_code，保持第一个 period 的顺序
    const periods = data?.periods || [];
    const subjectMap = new Map<string, { subject_code: string; subject_name: string }>();
    for (const p of periods) {
        for (const item of p.items) {
            if (!subjectMap.has(item.subject_code)) {
                subjectMap.set(item.subject_code, { subject_code: item.subject_code, subject_name: item.subject_name });
            }
        }
    }
    // 以第一个 period 的顺序为基准，后面追加新增的科目
    const firstItems = periods[0]?.items || [];
    const subjects = firstItems.map((it) => subjectMap.get(it.subject_code)!).filter(Boolean);
    for (const [, v] of subjectMap) {
        if (!subjects.find((s) => s.subject_code === v.subject_code)) {
            subjects.push(v);
        }
    }
    // 为每个 period 建立 subject_code → value 的索引
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
                <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
                    {REPORT_TYPE_OPTIONS.map((opt) => (
                        <button
                            key={opt.value}
                            onClick={() => setReportType(opt.value)}
                            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                                reportType === opt.value
                                    ? 'bg-white text-blue-600 shadow-sm'
                                    : 'text-gray-600 hover:text-gray-900'
                            }`}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>
                <select
                    value={years}
                    onChange={(e) => setYears(Number(e.target.value))}
                    className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm"
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
                <div className="flex items-center justify-center py-20 text-gray-500">
                    <Loader2 className="w-6 h-6 animate-spin mr-2" /> 加载中...
                </div>
            )}
            {error && (
                <div className="flex items-center gap-2 py-10 text-red-600">
                    <AlertCircle className="w-5 h-5" /> {error}
                </div>
            )}
            {!isLoading && !error && !stockCode && (
                <div className="flex flex-col items-center justify-center py-20 text-gray-400">
                    <BookOpen className="w-12 h-12 mb-3" />
                    <p>请先选择一家公司查看财务数据</p>
                </div>
            )}
            {!isLoading && !error && stockCode && periods.length === 0 && (
                <div className="text-center py-10 text-gray-500">暂无数据</div>
            )}

            {/* 数据表格 */}
            {periods.length > 0 && (
                <div className="overflow-x-auto border border-gray-200 rounded-xl">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="bg-gray-50">
                                <th className="text-left px-4 py-3 font-medium text-gray-600 sticky left-0 bg-gray-50 z-10 min-w-[200px]">
                                    科目
                                </th>
                                {periods.map((p) => (
                                    <th
                                        key={p.report_date}
                                        className="text-right px-4 py-3 font-medium text-gray-600 min-w-[140px]"
                                    >
                                        {p.report_date}
                                        <span className="ml-1 text-xs text-gray-400">
                                            ({p.report_period === 'annual' ? '年报' : p.report_period})
                                        </span>
                                    </th>
                                ))}
                            </tr>
                        </thead>
                            <tbody>
                                {subjects.map((subject) => (
                                    <tr
                                        key={subject.subject_code}
                                        className="border-t border-gray-100 hover:bg-blue-50/30"
                                    >
                                        <td className="px-4 py-2 text-gray-800 sticky left-0 bg-white z-10">
                                            <span className="font-mono text-xs text-gray-400 mr-2">
                                                {subject.subject_code}
                                            </span>
                                            {subject.subject_name}
                                        </td>
                                        {periodValueMaps.map((valMap, pi) => {
                                            const val = valMap.get(subject.subject_code);
                                            return (
                                                <td
                                                    key={periods[pi].report_date}
                                                    className={`px-4 py-2 text-right font-mono ${
                                                        val === null || val === undefined
                                                            ? 'text-gray-300'
                                                            : 'text-gray-800'
                                                    }`}
                                                >
                                                    {formatValue(val ?? null)}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                ))}
                            </tbody>
                    </table>
                </div>
            )}

            {data && (
                <p className="mt-3 text-xs text-gray-400">
                    {data.company_name}（{data.company_code}）· {REPORT_TYPE_OPTIONS.find((o) => o.value === data.report_type)?.label} ·
                    {periods.length} 个报告期 · {subjects.length} 个科目
                </p>
            )}
        </div>
    );
};
