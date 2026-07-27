/* eslint-disable @typescript-eslint/no-explicit-any -- 后端返回的 SOTP 估值数据结构复杂且动态，使用 any 避免过度类型断言 */
interface SOTPTabPanelProps {
    data: any;
    loading: boolean;
    onExtract?: () => void;
    extracting?: boolean;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export function SOTPTabPanel({ data, loading, onExtract, extracting }: SOTPTabPanelProps) {
    if (loading && !data) {
        return <div className="text-center py-12 text-gray-500">加载 SOTP…</div>;
    }

    if (!data) {
        return (
            <div className="text-center py-12 text-gray-500">
                <p className="text-lg mb-2">暂无 SOTP 数据</p>
                <p className="text-sm mb-4">需先有 ≥2 个经营分部（年报抽取或手工导入）</p>
                {onExtract && (
                    <button className="scenario-btn active" onClick={onExtract} disabled={extracting}>
                        {extracting ? '抽取中…' : '从年报抽取分部'}
                    </button>
                )}
            </div>
        );
    }

    if (data.error && !data.applicable) {
        return (
            <div className="text-center py-12 text-gray-500">
                <p className="text-lg mb-2">SOTP 暂不可用</p>
                <p className="text-sm mb-4">{data.error}</p>
                {onExtract && (
                    <button className="scenario-btn active" onClick={onExtract} disabled={extracting}>
                        {extracting ? '抽取中…' : '从年报抽取分部'}
                    </button>
                )}
            </div>
        );
    }

    const segments = data.segments || [];
    const intrinsic = data.valuation?.intrinsic_value_per_share;
    const discount = data.discount_pct;
    const adj = data.adjustments || {};

    return (
        <>
            <div className="mb-4 flex flex-wrap justify-between items-center gap-2">
                <div className="text-sm text-gray-600">
                    报告期: {data.report_period || '—'} | 来源: {data.segment_source || '—'} | 置信度:{' '}
                    {data.segment_confidence || data.confidence || '—'}
                </div>
                {onExtract && (
                    <button className="scenario-btn" onClick={onExtract} disabled={extracting}>
                        {extracting ? '重新抽取中…' : '重新从年报抽取'}
                    </button>
                )}
            </div>

            <div className="metrics-grid">
                <div className="metric-card">
                    <div className="metric-title">SOTP 结果</div>
                    <div className="metric-item">
                        <span className="metric-label">每股价值</span>
                        <span className="metric-value">
                            {intrinsic != null ? `¥${Number(intrinsic).toFixed(2)}` : '—'}
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">现价</span>
                        <span className="metric-value">
                            {data.current_price ? `¥${Number(data.current_price).toFixed(2)}` : '—'}
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">vs 现价空间</span>
                        <span className="metric-value">
                            {data.upside_downside != null
                                ? `${data.upside_downside > 0 ? '+' : ''}${data.upside_downside}%`
                                : '—'}
                        </span>
                    </div>
                </div>
                <div className="metric-card">
                    <div className="metric-title">集团折价 / 调整</div>
                    <div className="metric-item">
                        <span className="metric-label">SOTP 折价</span>
                        <span className="metric-value">
                            {discount != null ? `${discount}%` : '—'}
                            {data.conglomerate_discount_flag && (
                                <span className="ml-1 text-amber-600 text-xs">⚠ 显著</span>
                            )}
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">分部 EV 合计</span>
                        <span className="metric-value">
                            {data.total_segment_ev != null
                                ? `¥${(data.total_segment_ev / 1e8).toFixed(2)}亿`
                                : '—'}
                        </span>
                    </div>
                    <div className="metric-item">
                        <span className="metric-label">总部费用 / 净债务</span>
                        <span className="metric-value text-xs">
                            {adj.corporate_cost != null
                                ? `¥${(adj.corporate_cost / 1e8).toFixed(2)}亿`
                                : '—'}{' '}
                            / {adj.net_debt != null ? `¥${(adj.net_debt / 1e8).toFixed(2)}亿` : '—'}
                        </span>
                    </div>
                </div>
            </div>

            <div className="mt-6 bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                    分部明细 ({segments.length})
                </h3>
                <div className="overflow-x-auto">
                    <table className="forecast-table">
                        <thead>
                            <tr>
                                <th>分部</th>
                                <th>指标</th>
                                <th>基数</th>
                                <th>倍数</th>
                                <th>分部 EV</th>
                            </tr>
                        </thead>
                        <tbody>
                            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                            {segments.map((s: any, i: number) => (
                                <tr key={s.name || i}>
                                    <td>{s.name || s.segment_name || '—'}</td>
                                    <td>{s.metric || s.multiple_type || '—'}</td>
                                    <td>
                                        {s.base != null
                                            ? `¥${(Number(s.base) / 1e8).toFixed(2)}亿`
                                            : s.revenue != null
                                              ? `¥${(Number(s.revenue) / 1e8).toFixed(2)}亿`
                                              : '—'}
                                    </td>
                                    <td>{s.multiple != null ? `${s.multiple}x` : '—'}</td>
                                    <td>
                                        {s.enterprise_value != null
                                            ? `¥${(Number(s.enterprise_value) / 1e8).toFixed(2)}亿`
                                            : '—'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {Array.isArray(data.notes) && data.notes.length > 0 && (
                <div className="mt-4 p-3 bg-amber-50 border border-amber-100 rounded text-sm text-amber-900">
                    <ul className="list-disc list-inside space-y-1">
                        {data.notes.map((n: string, i: number) => (
                            <li key={i}>{n}</li>
                        ))}
                    </ul>
                </div>
            )}
        </>
    );
}
