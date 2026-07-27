interface ValuationHeaderProps {
    ticker?: string;
    name?: string;
    onSearch?: (ticker: string) => void;
    onRecalculate?: () => void;
    currentPrice?: number;
    marketCap?: number;
    recalculating?: boolean;
}

function formatMarketCap(mc?: number): string {
    if (mc == null || !Number.isFinite(mc) || mc <= 0) return '---';
    // 库内 market_cap 常见为万元；>1e6 时按万元→亿元展示
    if (mc >= 1e6) return `${(mc / 1e4).toFixed(2)}亿`;
    if (mc >= 100) return `${(mc / 100).toFixed(2)}亿`;
    return `${mc.toFixed(2)}亿`;
}

export function ValuationHeader({
    ticker,
    name,
    onRecalculate,
    currentPrice,
    marketCap,
    recalculating,
}: ValuationHeaderProps) {
    return (
        <div className="lab-header">
            <div className="lab-title">
                <h1>估值实验室</h1>
                {(ticker || name) && (
                    <div className="lab-subtitle" style={{ marginTop: 4, fontSize: 13, color: '#6b7280' }}>
                        {ticker && <span style={{ fontWeight: 600, color: '#111827' }}>{ticker}</span>}
                        {name && <span style={{ marginLeft: 8 }}>{name}</span>}
                        {currentPrice != null && Number.isFinite(currentPrice) && (
                            <span style={{ marginLeft: 12 }}>
                                现价 ¥{currentPrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                            </span>
                        )}
                        {marketCap != null && Number.isFinite(marketCap) && (
                            <span style={{ marginLeft: 12 }}>市值 {formatMarketCap(marketCap)}</span>
                        )}
                    </div>
                )}
            </div>
            <div className="header-actions">
                <button className="btn-lab" type="button" disabled title="导出功能即将上线">
                    导出报告
                </button>
                <button
                    className="btn-lab primary"
                    type="button"
                    onClick={onRecalculate}
                    disabled={recalculating || !ticker || ticker === '---'}
                >
                    {recalculating ? '计算中…' : '重新计算'}
                </button>
            </div>
        </div>
    );
}
