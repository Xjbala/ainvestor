/* eslint-disable @typescript-eslint/no-explicit-any -- 后端返回的综合估值数据结构复杂且动态，使用 any 避免过度类型断言 */
interface TriangulateTabPanelProps {
    data: any;
    loading: boolean;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export function TriangulateTabPanel({ data, loading }: TriangulateTabPanelProps) {
    if (loading && !data) {
        return <div className="text-center py-12 text-gray-500">正在综合多方法估值...</div>;
    }
    if (!data) {
        return <div className="text-center py-12 text-gray-500">暂无综合估值数据</div>;
    }
    if (data.error && !data.blended_price) {
        return (
            <div className="text-center py-12 text-gray-500">
                <p className="text-lg mb-2">综合估值失败</p>
                <p className="text-sm">{data.error}</p>
            </div>
        );
    }

    const methods = data.methods || [];
    const weights = data.weights_used || data.weights || {};
    const scenarios = data.scenarios;
    const wacc = data.wacc;
    const risks = (data.risks as string[]) || [];
    const confMap: Record<string, string> = { high: '高', medium: '中', low: '低' };

    return (
        <>
            {/* Headline */}
            <div className="mb-4 p-4 bg-gradient-to-r from-slate-50 to-blue-50 border border-blue-100 rounded-lg">
                <div className="text-sm text-gray-500 mb-1">综合结论</div>
                <div className="text-base text-gray-900 leading-relaxed">{data.headline || '—'}</div>
                <div className="mt-3 flex flex-wrap gap-4 text-sm">
                    <span>
                        综合公允价:{' '}
                        <strong className="font-mono text-lg">
                            {data.blended_price != null ? `¥${Number(data.blended_price).toFixed(2)}` : '—'}
                        </strong>
                    </span>
                    <span>
                        vs 现价:{' '}
                        <strong className="font-mono">
                            {data.current_price ? `¥${Number(data.current_price).toFixed(2)}` : '—'}
                        </strong>
                    </span>
                    <span>
                        空间:{' '}
                        <strong
                            className={
                                (data.upside_pct ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'
                            }
                        >
                            {data.upside_pct != null
                                ? `${data.upside_pct > 0 ? '+' : ''}${data.upside_pct}%`
                                : '—'}
                        </strong>
                    </span>
                    <span>
                        方法分歧:{' '}
                        <strong>
                            {data.divergence_pct != null ? `${data.divergence_pct}%` : '—'}
                        </strong>
                    </span>
                    <span>
                        置信度: <strong>{confMap[data.confidence] || data.confidence || '—'}</strong>
                    </span>
                    <span>
                        评级: <strong>{data.investment_rating || '—'}</strong>
                    </span>
                </div>
            </div>

            {/* Methods table */}
            <div className="mt-4 bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-3">方法对比</h3>
                <div className="overflow-x-auto">
                    <table className="forecast-table">
                        <thead>
                            <tr>
                                <th>方法</th>
                                <th>适用</th>
                                <th>隐含价</th>
                                <th>权重</th>
                                <th>涨跌空间</th>
                                <th>说明</th>
                            </tr>
                        </thead>
                        <tbody>
                            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                            {methods.map((m: any) => (
                                <tr key={m.method}>
                                    <td className="font-medium">{m.method}</td>
                                    <td>{m.applicable ? '✓' : '✗'}</td>
                                    <td className="font-mono">
                                        {m.implied_price != null
                                            ? `¥${Number(m.implied_price).toFixed(2)}`
                                            : '—'}
                                    </td>
                                    <td>
                                        {weights[m.method] != null
                                            ? `${(weights[m.method] * 100).toFixed(0)}%`
                                            : '—'}
                                    </td>
                                    <td>
                                        {m.upside_downside != null
                                            ? `${m.upside_downside > 0 ? '+' : ''}${m.upside_downside}%`
                                            : '—'}
                                    </td>
                                    <td className="text-xs text-gray-500">
                                        {m.skip_reason || m.investment_rating || '—'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Bull Base Bear */}
            {scenarios && (
                <div className="results-row mt-4">
                    {(['bear', 'base', 'bull'] as const).map((key) => {
                        const s = scenarios[key];
                        if (!s) return null;
                        const label = key === 'bear' ? '熊市 Bear' : key === 'base' ? '基准 Base' : '牛市 Bull';
                        return (
                            <div key={key} className={`result-card ${key === 'base' ? 'target' : ''}`}>
                                <div className="scenario-label">{label}</div>
                                <div className="result-price">
                                    ¥{Number(s.price).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                                </div>
                                <div className="text-xs text-gray-500 mt-2">
                                    {s.levers
                                        ? Object.entries(s.levers)
                                              .map(([k, v]) => `${k}: ${v}`)
                                              .join(' · ')
                                        : ''}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* WACC breakdown */}
            {wacc && !wacc.error && (
                <div className="mt-6 bg-white rounded-lg border border-gray-200 p-4">
                    <h3 className="text-lg font-semibold text-gray-900 mb-3">WACC / CAPM 拆解</h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                        <div>
                            <span className="text-gray-500">WACC</span>
                            <div className="font-mono font-semibold">
                                {wacc.wacc != null ? `${(Number(wacc.wacc) * 100).toFixed(2)}%` : '—'}
                            </div>
                        </div>
                        <div>
                            <span className="text-gray-500">Ke (股权成本)</span>
                            <div className="font-mono">
                                {wacc.ke != null ? `${(Number(wacc.ke) * 100).toFixed(2)}%` : '—'}
                            </div>
                        </div>
                        <div>
                            <span className="text-gray-500">Kd (债务成本)</span>
                            <div className="font-mono">
                                {wacc.kd != null ? `${(Number(wacc.kd) * 100).toFixed(2)}%` : '—'}
                            </div>
                        </div>
                        <div>
                            <span className="text-gray-500">β / ERP / Rf</span>
                            <div className="font-mono text-xs">
                                {wacc.beta != null ? Number(wacc.beta).toFixed(2) : '—'} /{' '}
                                {wacc.erp != null ? `${(Number(wacc.erp) * 100).toFixed(1)}%` : '—'} /{' '}
                                {wacc.rf != null ? `${(Number(wacc.rf) * 100).toFixed(1)}%` : '—'}
                            </div>
                        </div>
                        <div>
                            <span className="text-gray-500">权益/债务权重</span>
                            <div className="font-mono text-xs">
                                {wacc.e_weight != null ? `${(Number(wacc.e_weight) * 100).toFixed(0)}%` : '—'} /{' '}
                                {wacc.d_weight != null ? `${(Number(wacc.d_weight) * 100).toFixed(0)}%` : '—'}
                            </div>
                        </div>
                        <div>
                            <span className="text-gray-500">税率</span>
                            <div className="font-mono">
                                {wacc.tax_rate != null
                                    ? `${(Number(wacc.tax_rate) * 100).toFixed(0)}%`
                                    : '—'}
                            </div>
                        </div>
                        <div>
                            <span className="text-gray-500">行业画像</span>
                            <div className="font-mono text-xs">{wacc.profile_key || 'default'}</div>
                        </div>
                        <div>
                            <span className="text-gray-500">行业 band</span>
                            <div className="font-mono text-xs">
                                {Array.isArray(wacc.sanity?.band) && wacc.sanity.band.length >= 2
                                    ? `${(Number(wacc.sanity.band[0]) * 100).toFixed(0)}%-${(
                                          Number(wacc.sanity.band[1]) * 100
                                      ).toFixed(0)}%`
                                    : '—'}
                                {wacc.sanity?.in_sector_band === false && (
                                    <span className="text-amber-600 ml-1">⚠</span>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Risks */}
            {risks.length > 0 && (
                <div className="mt-4 p-4 bg-amber-50 border border-amber-100 rounded-lg">
                    <h3 className="text-sm font-semibold text-amber-900 mb-2">风险与注意</h3>
                    <ul className="list-disc list-inside text-sm text-amber-900 space-y-1">
                        {risks.map((r: string, i: number) => (
                            <li key={i}>{r}</li>
                        ))}
                    </ul>
                </div>
            )}
        </>
    );
}
