import { ValuationChart } from './ValuationChart';
import { SensitivityMatrix } from './SensitivityMatrix';

/* eslint-disable @typescript-eslint/no-explicit-any -- 后端返回的估值数据结构复杂且动态，使用 any 避免过度类型断言 */
interface DCFTabPanelProps {
    data: any;
    loading: boolean;
    scenario: 'conservative' | 'base' | 'optimistic';
    wacc: number;
    g: number;
    generateChartData: () => Array<{ year: number; fcf: number; pv_fcf: number }>;
    displayPrice: (type: 'conservative' | 'base' | 'optimistic') => string;
    displayChange: (type: 'conservative' | 'base' | 'optimistic') => string;
    isGrowthPositive: (type: 'conservative' | 'base' | 'optimistic') => boolean;
}

function fmtMoneyYi(v?: number | null): string {
    if (v == null || !Number.isFinite(Number(v))) return '—';
    const n = Number(v);
    // 报表金额通常为元；绝对值大时用亿元展示
    if (Math.abs(n) >= 1e6) return `¥${(n / 1e8).toFixed(2)}亿`;
    if (Math.abs(n) >= 1e4) return `¥${(n / 1e4).toFixed(2)}万`;
    return `¥${n.toFixed(2)}`;
}

function fmtShares(v?: number | null): string {
    if (v == null || !Number.isFinite(Number(v)) || Number(v) <= 0) return '—';
    const n = Number(v);
    if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿股`;
    if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万股`;
    return `${n.toFixed(0)}股`;
}

export function DCFTabPanel({
    data,
    loading,
    scenario,
    wacc,
    g,
    generateChartData,
    displayPrice,
    displayChange,
    isGrowthPositive
}: DCFTabPanelProps) {
    if (!data) {
        return (
            <div className="text-center py-12 text-muted-foreground">
                {loading ? '加载 DCF 估值...' : '暂无 DCF 数据'}
            </div>
        );
    }

    const chartData = generateChartData();
    const shares = Number(data.inputs?.shares_outstanding || 0);
    const baseFcf = Number(data.inputs?.base_fcf || 0);
    const fcfPerShare = shares > 0 ? baseFcf / shares : null;

    return (
        <>
            {/* 指标卡 - DCF 模型 */}
            <div className="metrics-grid">
                <div className="metric-card">
                    <div className="metric-title">现金流数据 (实际值)</div>
                    <div className="metric-item">
                        <span className="metric-label">经营活动现金流</span>
                        <span className="metric-value">
                            {fmtMoneyYi(data.inputs?.operating_cash_flow)}
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">资本性支出</span>
                        <span className="metric-value">
                            {fmtMoneyYi(data.inputs?.capital_expenditure)}
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">自由现金流 (FCF)</span>
                        <span className="metric-value">
                            {fmtMoneyYi(data.inputs?.base_fcf)}
                        </span>
                    </div>
                </div>
                <div className="metric-card">
                    <div className="metric-title">财务数据 (实际值)</div>
                    <div className="metric-item">
                        <span className="metric-label">净债务</span>
                        <span className="metric-value">
                            {fmtMoneyYi(data.inputs?.net_debt)}
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">总股本</span>
                        <span className="metric-value">
                            {fmtShares(data.inputs?.shares_outstanding)}
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">FCF/股</span>
                        <span className="metric-value">
                            {fcfPerShare != null ? `¥${fcfPerShare.toFixed(2)}` : '—'}
                        </span>
                    </div>
                </div>
            </div>

            {/* 情景估值结果 */}
            <div className="results-row">
                <div className={`result-card ${scenario === 'conservative' ? 'target' : ''}`}>
                    <div className="scenario-label">风险折价 (保守)</div>
                    <div className="valuation-price">{displayPrice('conservative')}</div>
                    <div className={`valuation-change ${isGrowthPositive('conservative') ? 'growth-green' : 'growth-red'}`}>
                        {displayChange('conservative')}
                    </div>
                </div>
                <div className={`result-card ${scenario === 'base' ? 'target' : ''}`}>
                    <div className="scenario-label">基准价值 (Base)</div>
                    <div className="valuation-price">{displayPrice('base')}</div>
                    <div className={`valuation-change ${isGrowthPositive('base') ? 'growth-green' : 'growth-red'}`}>
                        {displayChange('base')}
                    </div>
                </div>
                <div className={`result-card ${scenario === 'optimistic' ? 'target' : ''}`}>
                    <div className="scenario-label">乐观溢价 (Upside)</div>
                    <div className="valuation-price">{displayPrice('optimistic')}</div>
                    <div className={`valuation-change ${isGrowthPositive('optimistic') ? 'growth-green' : 'growth-red'}`}>
                        {displayChange('optimistic')}
                    </div>
                </div>
            </div>

            {/* 图表和敏感性分析 */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                    {chartData.length > 0 ? (
                        <ValuationChart data={chartData} type="DCF" />
                    ) : (
                        <div
                            className="chart-placeholder"
                            style={{
                                height: '300px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: 'var(--muted)',
                                borderRadius: '8px',
                                color: 'var(--muted-foreground)'
                            }}
                        >
                            {loading ? 'Loading Chart...' : data ? '无图表数据' : '等待估值模型数据...'}
                        </div>
                    )}
                </div>
                <div className="lg:col-span-1">
                    <SensitivityMatrix
                        baseWacc={wacc}
                        baseG={g}
                        basePrice={data?.valuation?.intrinsic_value_per_share ?? 0}
                        sensitivity={data?.valuation?.sensitivity}
                    />
                </div>
            </div>

            {/* WACC 拆解 + 双终值 + gates */}
            {(data?.wacc_breakdown || data?.valuation?.terminal_methods || data?.gates) && (
                <div className="mt-6 bg-card rounded-vibe-sm border border-border p-4">
                    <h3 className="text-lg font-semibold text-foreground mb-3">WACC / 终值交叉验证</h3>
                    {data?.wacc_breakdown && !data.wacc_breakdown.error && (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm mb-4">
                            <div>
                                <span className="text-muted-foreground">自动 WACC</span>
                                <div className="font-mono font-semibold">
                                    {data.wacc_breakdown.wacc != null
                                        ? `${(Number(data.wacc_breakdown.wacc) * 100).toFixed(2)}%`
                                        : '—'}
                                </div>
                            </div>
                            <div>
                                <span className="text-muted-foreground">Ke / β</span>
                                <div className="font-mono text-xs">
                                    {data.wacc_breakdown.ke != null
                                        ? `${(Number(data.wacc_breakdown.ke) * 100).toFixed(2)}%`
                                        : '—'}{' '}
                                    / {data.wacc_breakdown.beta != null
                                        ? Number(data.wacc_breakdown.beta).toFixed(2)
                                        : '—'}
                                </div>
                            </div>
                            <div>
                                <span className="text-muted-foreground">Rf / ERP</span>
                                <div className="font-mono text-xs">
                                    {data.wacc_breakdown.rf != null
                                        ? `${(Number(data.wacc_breakdown.rf) * 100).toFixed(1)}%`
                                        : '—'}{' '}
                                    / {data.wacc_breakdown.erp != null
                                        ? `${(Number(data.wacc_breakdown.erp) * 100).toFixed(1)}%`
                                        : '—'}
                                </div>
                            </div>
                            <div>
                                <span className="text-muted-foreground">Kd / 税率</span>
                                <div className="font-mono text-xs">
                                    {data.wacc_breakdown.kd != null
                                        ? `${(Number(data.wacc_breakdown.kd) * 100).toFixed(2)}%`
                                        : '—'}{' '}
                                    / {data.wacc_breakdown.tax_rate != null
                                        ? `${(Number(data.wacc_breakdown.tax_rate) * 100).toFixed(0)}%`
                                        : '—'}
                                </div>
                            </div>
                        </div>
                    )}
                    {data?.valuation?.terminal_methods && (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm mb-3">
                            <div>
                                <span className="text-muted-foreground">Gordon 终值</span>
                                <div className="font-mono text-xs">
                                    {fmtMoneyYi(data.valuation.terminal_methods.tv_gordon)}
                                </div>
                            </div>
                            <div>
                                <span className="text-muted-foreground">Exit Multiple</span>
                                <div className="font-mono text-xs">
                                    {fmtMoneyYi(data.valuation.terminal_methods.tv_exit_multiple)}
                                    <span className="text-muted-foreground ml-1">
                                        ({data.valuation.terminal_methods.exit_ev_ebitda ?? '—'}x)
                                    </span>
                                </div>
                            </div>
                            <div>
                                <span className="text-muted-foreground">中点终值</span>
                                <div className="font-mono text-xs">
                                    {fmtMoneyYi(data.valuation.terminal_methods.tv_blended)}
                                </div>
                            </div>
                            <div>
                                <span className="text-muted-foreground">终值偏差</span>
                                <div className="font-mono text-xs">
                                    {data.valuation.terminal_methods.divergence_pct != null
                                        ? `${data.valuation.terminal_methods.divergence_pct}%`
                                        : '—'}
                                </div>
                            </div>
                        </div>
                    )}
                    {Array.isArray(data.gates || data.valuation?.gates) && (
                        <div className="flex flex-wrap gap-2">
                            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                            {(data.gates || data.valuation?.gates || []).map((g: any, i: number) => (
                                <span
                                    key={i}
                                    className={`text-xs px-2 py-1 rounded ${
                                        g.ok ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning-foreground'
                                    }`}
                                    title={g.message || g.name}
                                >
                                    {g.ok ? '✓' : '⚠'} {g.name}
                                    {g.message && !g.ok ? `: ${g.message}` : ''}
                                </span>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* DCF 预测记录表格 */}
            {data?.valuation?.calculation_detail && (
                <div className="mt-6 bg-card rounded-vibe-sm border border-border p-4">
                    <h3 className="text-lg font-semibold text-foreground mb-4">
                        预测记录 (T1-T5)
                        <span className="ml-2 text-sm font-normal text-muted-foreground">
                            基准年: {data.base_report_date?.split('-')[0] || '---'}
                        </span>
                    </h3>
                    <div className="overflow-x-auto">
                        <table className="forecast-table">
                            <thead>
                                <tr>
                                    <th>年份</th>
                                    <th>FCF (预测值)</th>
                                    <th>折现因子</th>
                                    <th>FCF现值</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.valuation.calculation_detail.projected_fcf?.map((fcf: number, i: number) => (
                                    <tr key={i}>
                                        <td className="forecast-year">T{i + 1}</td>
                                        <td className="forecast-ep">¥{(fcf / 10000).toFixed(2)}亿</td>
                                        <td className="forecast-dps">
                                            {data.valuation.calculation_detail.discount_factors?.[i]?.toFixed(4) || '---'}
                                        </td>
                                        <td className="forecast-bps">
                                            ¥{(data.valuation.calculation_detail.pv_projected_fcf_detail?.[i] / 10000 || 0).toFixed(2)}亿
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <div className="mt-3 text-xs text-muted-foreground">
                        * 预测值基于 {data.parameters?.growth_rate ? (data.parameters.growth_rate * 100).toFixed(0) : '---'}% 增长率计算
                        {data.valuation.scenarios && (
                            <span className="ml-2">
                                | {scenario === 'conservative' ? '保守情景：低永续增长' : scenario === 'base' ? '基准情景：稳定增长' : '乐观情景：高增长'}
                            </span>
                        )}
                    </div>
                </div>
            )}

            {/* DCF 估值详情 */}
            {data?.valuation && (
                <div className="mt-6 bg-card rounded-vibe-sm border border-border p-4">
                    <h3 className="text-lg font-semibold text-foreground mb-3">估值详情</h3>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <span className="text-muted-foreground">内在价值:</span>
                            <span className="ml-2 font-mono">¥{data.valuation?.intrinsic_value_per_share?.toLocaleString() || '---'}</span>
                        </div>
                        <div>
                            <span className="text-muted-foreground">安全边际:</span>
                            <span className="ml-2 font-mono">{data.margin_of_safety?.margin_percent?.toFixed(1) || '---'}%</span>
                        </div>
                        <div>
                            <span className="text-muted-foreground">WACC:</span>
                            <span className="ml-2 font-mono">{(data.parameters?.discount_rate * 100).toFixed(1) || '---'}%</span>
                        </div>
                        <div>
                            <span className="text-muted-foreground">永续增长率:</span>
                            <span className="ml-2 font-mono">{(data.parameters?.terminal_growth_rate * 100).toFixed(1) || '---'}%</span>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
