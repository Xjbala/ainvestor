import './AIMode.css';

export interface MethodRow {
    method: string;
    price: number | null;
    note?: string;
}

interface ValuationMethodPanelProps {
    blendedPrice?: number | null;
    currentPrice?: number | null;
    upsidePct?: number | null;
    divergencePct?: number | null;
    confidence?: string | null;
    methods?: MethodRow[];
    headline?: string | null;
    risks?: string[];
    loading?: boolean;
}

const METHOD_LABEL: Record<string, string> = {
    DCF: 'DCF 现金流',
    RI: '剩余收益',
    RIM: '剩余收益',
    RELATIVE: '相对估值',
    SOTP: 'SOTP 分部',
};

const CONF_LABEL: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低',
    高: '高',
    中: '中',
    低: '低',
};

export function ValuationMethodPanel({
    blendedPrice,
    currentPrice,
    upsidePct,
    divergencePct,
    confidence,
    methods = [],
    headline,
    risks = [],
    loading,
}: ValuationMethodPanelProps) {
    if (loading) {
        return (
            <div className="valuation-method-panel">
                <div className="vmp-title">估值方法拆解</div>
                <div className="vmp-loading">估值分析师计算中…</div>
            </div>
        );
    }

    const hasData =
        blendedPrice != null ||
        methods.length > 0 ||
        !!headline;

    if (!hasData) {
        return (
            <div className="valuation-method-panel muted">
                <div className="vmp-title">估值方法拆解</div>
                <div className="vmp-empty">
                    等待估值分析师完成多方法三角验证（DCF / RI / 相对估值）
                </div>
            </div>
        );
    }

    const confText = confidence ? CONF_LABEL[confidence] || confidence : '—';
    const divHigh = divergencePct != null && divergencePct > 30;

    return (
        <div className="valuation-method-panel">
            <div className="vmp-header">
                <div className="vmp-title">估值方法拆解</div>
                <div className="vmp-badges">
                    {confidence && (
                        <span className={`vmp-badge conf-${(confidence || '').toLowerCase()}`}>
                            置信度 {confText}
                        </span>
                    )}
                    {divergencePct != null && (
                        <span className={`vmp-badge ${divHigh ? 'warn' : ''}`}>
                            方法分歧 {divergencePct}%
                        </span>
                    )}
                </div>
            </div>

            {headline && <div className="vmp-headline">{headline}</div>}

            <div className="vmp-summary">
                <div className="vmp-stat">
                    <div className="vmp-stat-label">综合公允价</div>
                    <div className="vmp-stat-value">
                        {blendedPrice != null ? `¥${blendedPrice.toFixed(2)}` : '—'}
                    </div>
                </div>
                <div className="vmp-stat">
                    <div className="vmp-stat-label">现价</div>
                    <div className="vmp-stat-value secondary">
                        {currentPrice != null && currentPrice > 0
                            ? `¥${currentPrice.toFixed(2)}`
                            : '—'}
                    </div>
                </div>
                <div className="vmp-stat">
                    <div className="vmp-stat-label">潜在空间</div>
                    <div
                        className={`vmp-stat-value ${
                            upsidePct == null
                                ? ''
                                : upsidePct >= 0
                                  ? 'positive'
                                  : 'negative'
                        }`}
                    >
                        {upsidePct != null
                            ? `${upsidePct > 0 ? '+' : ''}${upsidePct.toFixed(1)}%`
                            : '—'}
                    </div>
                </div>
            </div>

            {methods.length > 0 && (
                <table className="vmp-table">
                    <thead>
                        <tr>
                            <th>方法</th>
                            <th>隐含价</th>
                            <th>备注</th>
                        </tr>
                    </thead>
                    <tbody>
                        {methods.map((m) => (
                            <tr key={m.method}>
                                <td>{METHOD_LABEL[m.method] || m.method}</td>
                                <td className="mono">
                                    {m.price != null ? `¥${m.price.toFixed(2)}` : '—'}
                                </td>
                                <td className="note">{m.note || '—'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}

            {/* 价格对比条形图 */}
            {(() => {
                const allPrices = [
                    ...methods.map(m => ({ label: METHOD_LABEL[m.method] || m.method, price: m.price, type: m.method.toLowerCase() })),
                    ...(blendedPrice != null ? [{ label: '综合公允价', price: blendedPrice, type: 'blended' }] : []),
                ].filter(p => p.price != null && p.price > 0);

                if (allPrices.length === 0) return null;

                const maxPrice = Math.max(...allPrices.map(p => p.price!), currentPrice ?? 0);
                const currentPct = currentPrice && maxPrice > 0 ? (currentPrice / maxPrice) * 100 : 0;

                return (
                    <div className="vmp-bars">
                        {allPrices.map(({ label, price, type }) => {
                            const widthPct = maxPrice > 0 ? (price! / maxPrice) * 100 : 0;
                            return (
                                <div key={label} className="vmp-bar-row">
                                    <span className="vmp-bar-label">{label}</span>
                                    <div className="vmp-bar-track">
                                        <div
                                            className={`vmp-bar-fill fill-${type}`}
                                            style={{ width: `${Math.max(widthPct, 8)}%` }}
                                        />
                                        {currentPct > 0 && currentPct < 100 && (
                                            <div
                                                className="vmp-bar-current-line"
                                                style={{ left: `${currentPct}%` }}
                                            />
                                        )}
                                    </div>
                                    <span className="vmp-bar-price">¥{price!.toFixed(2)}</span>
                                </div>
                            );
                        })}
                        {currentPrice != null && currentPrice > 0 && (
                            <div className="vmp-bar-row is-current">
                                <span className="vmp-bar-label">现价</span>
                                <div className="vmp-bar-track">
                                    <div
                                        className="vmp-bar-fill"
                                        style={{
                                            width: `${Math.max(currentPct, 4)}%`,
                                            background: 'var(--destructive)',
                                        }}
                                    />
                                </div>
                                <span className="vmp-bar-price">¥{currentPrice.toFixed(2)}</span>
                            </div>
                        )}
                    </div>
                );
            })()}

            {divHigh && (
                <div className="vmp-warn">
                    方法分歧较大（&gt;30%），综合价置信度下降，请结合假设与行业特性判断。
                </div>
            )}

            {risks.length > 0 && (
                <ul className="vmp-risks">
                    {risks.slice(0, 3).map((r, i) => (
                        <li key={i}>{r}</li>
                    ))}
                </ul>
            )}
        </div>
    );
}
