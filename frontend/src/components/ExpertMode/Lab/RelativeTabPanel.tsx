/* eslint-disable @typescript-eslint/no-explicit-any -- 后端返回的相对估值数据结构复杂且动态，使用 any 避免过度类型断言 */
interface RelativeTabPanelProps {
    data: any;
    loading: boolean;
    scenario: 'conservative' | 'base' | 'optimistic';
    displayPrice: (type: 'conservative' | 'base' | 'optimistic') => string;
    displayChange: (type: 'conservative' | 'base' | 'optimistic') => string;
    isGrowthPositive: (type: 'conservative' | 'base' | 'optimistic') => boolean;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export function RelativeTabPanel({
    data,
    loading,
    scenario,
    displayPrice,
    displayChange,
    isGrowthPositive,
}: RelativeTabPanelProps) {
    if (!data) {
        return (
            <div className="text-center py-12 text-muted-foreground">
                {loading ? '加载相对估值...' : '暂无相对估值数据'}
            </div>
        );
    }

    if (data.error && !data.valuation) {
        return (
            <div className="text-center py-12 text-muted-foreground">
                <p className="text-lg mb-2">相对估值不可用</p>
                <p className="text-sm">{data.error}</p>
            </div>
        );
    }

    const peers = data.peers || [];
    const medians = data.medians || {};
    const implied = data.implied_by_multiple || {};
    const intrinsic = data.valuation?.intrinsic_value_per_share;

    return (
        <>
            <div className="metrics-grid">
                <div className="metric-card">
                    <div className="metric-title">同业中位数</div>
                    <div className="metric-item">
                        <span className="metric-label">PE</span>
                        <span className="metric-value">
                            {medians.pe != null ? `${Number(medians.pe).toFixed(1)}x` : '—'}
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">PB</span>
                        <span className="metric-value">
                            {medians.pb != null ? `${Number(medians.pb).toFixed(1)}x` : '—'}
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">PS</span>
                        <span className="metric-value">
                            {medians.ps != null ? `${Number(medians.ps).toFixed(1)}x` : '—'}
                        </span>
                    </div>
                </div>
                <div className="metric-card">
                    <div className="metric-title">隐含股价</div>
                    <div className="metric-item">
                        <span className="metric-label">基于 PE</span>
                        <span className="metric-value">
                            {implied.pe != null ? `¥${Number(implied.pe).toFixed(2)}` : '—'}
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">基于 PB</span>
                        <span className="metric-value">
                            {implied.pb != null ? `¥${Number(implied.pb).toFixed(2)}` : '—'}
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">综合（主倍数: {data.primary_multiple || '—'}）</span>
                        <span className="metric-value">
                            {intrinsic != null ? `¥${Number(intrinsic).toFixed(2)}` : '—'}
                        </span>
                    </div>
                </div>
            </div>

            {Array.isArray(data.adjustment?.reasons) && data.adjustment.reasons.length > 0 && (
                <div className="mt-4 mb-4 p-3 bg-brand-50 border border-brand-200 rounded text-sm text-foreground">
                    <strong>倍数调整：</strong>
                    {data.adjustment.factor != null
                        ? `${(Number(data.adjustment.factor) * 100).toFixed(0)}%`
                        : '—'}{' '}
                    — {data.adjustment.reasons.join('；')}
                </div>
            )}

            <div className="results-row">
                {(['conservative', 'base', 'optimistic'] as const).map((key) => (
                    <div key={key} className={`result-card ${scenario === key ? 'target' : ''}`}>
                        <div className="scenario-label">
                            {key === 'conservative' ? '熊市压力' : key === 'base' ? '基准（中位数）' : '牛市扩张'}
                        </div>
                        <div className="result-price">{displayPrice(key)}</div>
                        <div className={`result-change ${isGrowthPositive(key) ? 'positive' : 'negative'}`}>
                            {displayChange(key)}
                        </div>
                    </div>
                ))}
            </div>

            <div className="mt-6 bg-card rounded-vibe-sm border border-border p-4">
                <h3 className="text-lg font-semibold text-foreground mb-4">
                    同业对比 ({peers.length} 家)
                </h3>
                <div className="overflow-x-auto">
                    <table className="forecast-table">
                        <thead>
                            <tr>
                                <th>代码</th>
                                <th>名称</th>
                                <th>股价</th>
                                <th>PE</th>
                                <th>PB</th>
                                <th>PS</th>
                                <th>ROE</th>
                            </tr>
                        </thead>
                        <tbody>
                            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                            {peers.map((p: any) => (
                                <tr key={p.stock_code}>
                                    <td>{p.stock_code}</td>
                                    <td>{p.stock_name || '—'}</td>
                                    <td>{p.current_price ? `¥${Number(p.current_price).toFixed(2)}` : '—'}</td>
                                    <td>{p.pe != null ? Number(p.pe).toFixed(1) : '—'}</td>
                                    <td>{p.pb != null ? Number(p.pb).toFixed(1) : '—'}</td>
                                    <td>{p.ps != null ? Number(p.ps).toFixed(1) : '—'}</td>
                                    <td>
                                        {p.roe != null
                                            ? `${(Number(p.roe) * 100).toFixed(1)}%`
                                            : '—'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </>
    );
}
