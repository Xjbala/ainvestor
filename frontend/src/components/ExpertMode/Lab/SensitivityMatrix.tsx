interface SensitivityMatrixProps {
    baseWacc: number;
    baseG: number;
    basePrice: number;
    /** 后端 5×5 网格；有则优先使用，无则回退启发式 */
    sensitivity?: {
        wacc_axis: number[];
        g_axis: number[];
        grid: Array<Array<number | null>>;
        base_wacc?: number;
        base_g?: number;
    } | null;
}

export function SensitivityMatrix({ baseWacc, baseG, basePrice, sensitivity }: SensitivityMatrixProps) {
    const hasBackend =
        sensitivity &&
        Array.isArray(sensitivity.wacc_axis) &&
        sensitivity.wacc_axis.length > 0 &&
        Array.isArray(sensitivity.grid) &&
        sensitivity.grid.length > 0;

    if (hasBackend && sensitivity) {
        const { wacc_axis, g_axis, grid } = sensitivity;
        const baseW = sensitivity.base_wacc ?? baseWacc / 100;
        const baseGRate = sensitivity.base_g ?? baseG / 100;

        return (
            <div className="matrix-container">
                <div className="panel-title" style={{ marginBottom: '16px' }}>
                    敏感性分析矩阵 (WACC × g)
                    <span style={{ fontSize: 11, color: 'var(--muted-foreground)', marginLeft: 8 }}>后端计算</span>
                </div>
                <div style={{ overflowX: 'auto' }}>
                    <table className="matrix-table">
                        <thead>
                            <tr>
                                <th>WACC \\ g</th>
                                {g_axis.map((g, i) => (
                                    <th key={i}>{(g * 100).toFixed(1)}%</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {wacc_axis.map((w, wi) => (
                                <tr key={wi}>
                                    <td className="matrix-cell-header">{(w * 100).toFixed(1)}%</td>
                                    {(grid[wi] || []).map((price, gi) => {
                                        const isBase =
                                            Math.abs(w - baseW) < 0.0005 &&
                                            Math.abs(g_axis[gi] - baseGRate) < 0.0005;
                                        return (
                                            <td key={gi} className={`matrix-cell ${isBase ? 'base' : ''}`}>
                                                {price == null ? '—' : `¥${Math.round(price).toLocaleString()}`}
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    }

    // 回退：3×3 启发式（无后端数据时）
    const waccVariations = [-1, 0, 1];
    const gVariations = [-0.5, 0, 0.5];

    const calculatePrice = (waccDelta: number, gDelta: number) => {
        const waccFactor = 1 - waccDelta / Math.max(baseWacc, 0.1);
        const gFactor = 1 + gDelta / Math.max(baseG, 0.1);
        return Math.round(basePrice * waccFactor * gFactor);
    };

    return (
        <div className="matrix-container">
            <div className="panel-title" style={{ marginBottom: '16px' }}>敏感性分析矩阵</div>
            <table className="matrix-table">
                <thead>
                    <tr>
                        <th></th>
                        <th>g-0.5%</th>
                        <th>g {baseG.toFixed(1)}%</th>
                        <th>g+0.5%</th>
                    </tr>
                </thead>
                <tbody>
                    {waccVariations.map((waccDelta, waccIndex) => (
                        <tr key={waccIndex}>
                            <td className="matrix-cell-header">
                                WACC {waccDelta >= 0 ? '+' : ''}{waccDelta}%
                            </td>
                            {gVariations.map((gDelta, gIndex) => {
                                const isBase = waccDelta === 0 && gDelta === 0;
                                const price = calculatePrice(waccDelta, gDelta);
                                return (
                                    <td key={gIndex} className={`matrix-cell ${isBase ? 'base' : ''}`}>
                                        ¥{price.toLocaleString()}
                                    </td>
                                );
                            })}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
