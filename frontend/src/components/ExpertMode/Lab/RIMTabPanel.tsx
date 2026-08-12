import { ValuationChart } from './ValuationChart';
import { SensitivityMatrix } from './SensitivityMatrix';

/* eslint-disable @typescript-eslint/no-explicit-any -- 后端返回的 RIM 估值数据结构复杂且动态，使用 any 避免过度类型断言 */
interface RIMTabPanelProps {
    data: any;
    loading: boolean;
    scenario: 'conservative' | 'base' | 'optimistic';
    wacc: number;
    g: number;
    generateChartData: () => Array<{ year: number; ri: number; pv_ri: number }>;
    displayPrice: (type: 'conservative' | 'base' | 'optimistic') => string;
    displayChange: (type: 'conservative' | 'base' | 'optimistic') => string;
    isGrowthPositive: (type: 'conservative' | 'base' | 'optimistic') => boolean;
}

export function RIMTabPanel({
    data,
    loading,
    scenario,
    wacc,
    g,
    generateChartData,
    displayPrice,
    displayChange,
    isGrowthPositive
}: RIMTabPanelProps) {
    const chartData = generateChartData();

    // 计算剩余收益
    const calculateRE = () => {
        const eps = Number(data?.inputs?.current_eps ?? 0);
        const bps = Number(data?.inputs?.current_bps ?? 0);
        const costOfEquity = Number(data?.parameters?.cost_of_equity ?? 0.09);
        if (!Number.isFinite(eps) || !Number.isFinite(bps)) return '---';
        const re = eps - costOfEquity * bps;
        return `${re.toFixed(3)}元`;
    };

    if (!data) {
        return (
            <div className="text-center py-12 text-muted-foreground">
                {loading ? '加载 RIM 估值...' : '暂无 RIM 数据'}
            </div>
        );
    }

    return (
        <>
            {/* 指标卡 - RIM 模型 */}
            <div className="metrics-grid">
                <div className="metric-card">
                    <div className="metric-title">每股数据 (实际值)</div>
                    <div className="metric-item">
                        <span className="metric-label">EPS</span>
                        <span className="metric-value">
                            {data.inputs?.current_eps?.toFixed(2) || '---'}元
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">BPS</span>
                        <span className="metric-value">
                            {data.inputs?.current_bps?.toFixed(2) || '---'}元
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">DPS</span>
                        <span className="metric-value">
                            {data.inputs?.current_eps != null
                                ? (
                                      Number(data.inputs.current_eps) *
                                      Number(data.parameters?.payout_ratio ?? 0.3)
                                  ).toFixed(2)
                                : '---'}
                            元
                        </span>
                    </div>
                </div>
                <div className="metric-card">
                    <div className="metric-title">计算指标 (实际值)</div>
                    <div className="metric-item">
                        <span className="metric-label">ROE</span>
                        <span className="metric-value">
                            {data.inputs?.current_roe ? (data.inputs.current_roe * 100).toFixed(2) : '---'}%
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">剩余收益 (RE)</span>
                        <span className="metric-value">
                            {calculateRE()}
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
                        <ValuationChart data={chartData} type="RIM" />
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
                        basePrice={data?.valuation.intrinsic_value_per_share ?? 0}
                    />
                </div>
            </div>

            {/* RIM 预测记录表格 */}
            {data?.valuation?.calculation_detail && (
                <div className="mt-6 bg-card rounded-vibe-sm border border-border p-4">
                    <h3 className="text-lg font-semibold text-foreground mb-4">
                        预测记录 (T1-T5)
                        <span className="ml-2 text-sm font-normal text-muted-foreground">
                            基准年: {data.base_report_date?.split('-')[0] || '---'}
                            | 情景: {scenario === 'conservative' ? '保守' : scenario === 'base' ? '基准' : '乐观'}
                        </span>
                    </h3>
                    <div className="overflow-x-auto">
                        <table className="forecast-table">
                            <thead>
                                <tr>
                                    <th>年份</th>
                                    <th>EPS (预测值)</th>
                                    <th>DPS (预测值)</th>
                                    <th>BPS (预测值)</th>
                                    <th>ROE (预测值)</th>
                                    <th>RE (预测值)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.valuation.calculation_detail.projected_eps?.map((_eps: number, i: number) => {
                                    let ri = data.valuation.calculation_detail.projected_ri?.[i] || 0;
                                    if (data.valuation.scenarios) {
                                        const scenarioRi = data.valuation.scenarios[scenario]?.projected_ri?.[i];
                                        if (scenarioRi !== undefined) {
                                            ri = scenarioRi;
                                        }
                                    }

                                    return (
                                        <tr key={i}>
                                            <td className="forecast-year">T{i + 1}</td>
                                            <td className="forecast-ep">
                                                {_eps?.toFixed(3) || '---'}
                                            </td>
                                            <td className="forecast-dps">
                                                {data.valuation.calculation_detail.projected_dps?.[i]?.toFixed(3) || '---'}
                                            </td>
                                            <td className="forecast-bps">
                                                ¥{(data.valuation.calculation_detail.projected_bps?.[i] || 0).toFixed(2)}
                                            </td>
                                            <td className="forecast-roe">
                                                {(data.valuation.calculation_detail.projected_roe?.[i] || 0) * 100}%
                                            </td>
                                            <td className="forecast-re">
                                                ¥{ri.toFixed(3)}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                    <div className="mt-3 text-xs text-muted-foreground">
                        * 预测值基于 {data.parameters?.growth_rate ? (data.parameters.growth_rate * 100).toFixed(0) : '---'}% 增长率和 {data.parameters?.payout_ratio ? (data.parameters.payout_ratio * 100).toFixed(0) : '---'}% 股利支付率计算
                        <span className="ml-2">
                            | {scenario === 'conservative' ? '保守情景：RE递减至0' : scenario === 'base' ? '基准情景：RE保持稳定' : '乐观情景：RE持续增长'}
                        </span>
                    </div>
                </div>
            )}

            {/* RIM 估值详情 */}
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
                            <span className="text-muted-foreground">股权成本:</span>
                            <span className="ml-2 font-mono">
                                {data.parameters?.cost_of_equity != null
                                    ? (Number(data.parameters.cost_of_equity) * 100).toFixed(1)
                                    : '---'}
                                %
                            </span>
                        </div>
                        <div>
                            <span className="text-muted-foreground">增长率:</span>
                            <span className="ml-2 font-mono">
                                {data.parameters?.growth_rate != null
                                    ? (Number(data.parameters.growth_rate) * 100).toFixed(1)
                                    : '---'}
                                %
                            </span>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
