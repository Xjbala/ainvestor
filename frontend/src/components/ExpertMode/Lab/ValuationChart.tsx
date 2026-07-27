interface ValuationChartProps {
    data: Array<{ year: number; fcf?: number; pv_fcf?: number; ri?: number; pv_ri?: number }>;
    type: 'DCF' | 'RIM';
}

export function ValuationChart({ data, type }: ValuationChartProps) {
    const maxValue = Math.max(...data.map(d => (type === 'DCF' ? (d.fcf || 0) : (d.ri || 0))), 1);

    return (
        <div className="chart-container">
            <div className="chart-title">
                {type === 'DCF' ? '自由现金流预测 (FCF)' : '剩余收益预测 (RI)'}
            </div>
            <div className="chart-placeholder">
                {data.map((item, index) => {
                    const value = type === 'DCF' ? (item.fcf || 0) : (item.ri || 0);
                    const height = Math.max((value / maxValue) * 100, 5);

                    return (
                        <div key={index} className="chart-bar" style={{ height: `${height}%` }}>
                            <div className="chart-value">
                                {value > 0 ? `¥${(value / 1000000).toFixed(1)}M` : '0'}
                            </div>
                            <div className="chart-label">{item.year}</div>
                        </div>
                    );
                })}
                {data.length > 0 && (
                    <div className="chart-line" style={{ top: '30%' }} />
                )}
            </div>
        </div>
    );
}