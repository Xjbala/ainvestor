interface ValuationControlsProps {
    wacc: number;
    onWaccChange: (value: number) => void;
    g: number;
    onGChange: (value: number) => void;
    currentScenario: 'conservative' | 'base' | 'optimistic';
    onScenarioChange: (scenario: 'conservative' | 'base' | 'optimistic') => void;
    currentTab: 'DCF' | 'RIM' | 'RELATIVE' | 'TRIANGULATE' | 'SOTP';
    // RIM模型参数
    costOfEquity?: number;
    onCostOfEquityChange?: (value: number) => void;
    growthRate?: number;
    onGrowthRateChange?: (value: number) => void;
    payoutRatio?: number;
    onPayoutRatioChange?: (value: number) => void;
}

export function ValuationControls({
    wacc,
    onWaccChange,
    g,
    onGChange,
    currentScenario,
    onScenarioChange,
    currentTab,
    costOfEquity = 9,
    onCostOfEquityChange,
    growthRate = 15,
    onGrowthRateChange,
    payoutRatio = 30,
    onPayoutRatioChange
}: ValuationControlsProps) {
    return (
        <div className="assumption-panel">
            <div className="panel-header">
                <div className="panel-title">参数假设</div>
                <div className="scenario-group">
                    <button
                        className={`scenario-btn ${currentScenario === 'conservative' ? 'active' : ''}`}
                        onClick={() => onScenarioChange('conservative')}
                    >
                        保守
                    </button>
                    <button
                        className={`scenario-btn ${currentScenario === 'base' ? 'active' : ''}`}
                        onClick={() => onScenarioChange('base')}
                    >
                        基准
                    </button>
                    <button
                        className={`scenario-btn ${currentScenario === 'optimistic' ? 'active' : ''}`}
                        onClick={() => onScenarioChange('optimistic')}
                    >
                        乐观
                    </button>
                </div>
            </div>
            
            {(currentTab === 'RELATIVE' || currentTab === 'TRIANGULATE' || currentTab === 'SOTP') && (
                <div className="text-sm text-muted-foreground py-2">
                    {currentTab === 'RELATIVE'
                        ? '相对估值使用同业中位数倍数，无需手动调参。切换到 DCF/RIM 可调整绝对估值假设。'
                        : currentTab === 'SOTP'
                          ? 'SOTP 依赖 company_segments 分部数据。可从年报 Markdown 抽取，或通过 API 手工导入。无 ≥2 分部时自动跳过。'
                          : '综合估值自动融合 DCF / RIM / 相对估值 / SOTP(如有) 并计算 WACC。可在其他 Tab 调参后重新计算单项。'}
                </div>
            )}

            {/* DCF模型参数 */}
            {currentTab === 'DCF' && (
                <div className="sliders-row">
                    <div className="slider-group">
                        <div className="slider-label">
                            <span>WACC (加权平均资本成本)</span>
                            <span>{wacc.toFixed(1)}%</span>
                        </div>
                        <input
                            type="range"
                            min={5}
                            max={15}
                            step={0.1}
                            value={wacc}
                            onChange={(e) => onWaccChange(parseFloat(e.target.value))}
                            className="lab-slider"
                        />
                    </div>
                    <div className="slider-group">
                        <div className="slider-label">
                            <span>永续增长率 (g)</span>
                            <span>{g.toFixed(1)}%</span>
                        </div>
                        <input
                            type="range"
                            min={0}
                            max={5}
                            step={0.1}
                            value={g}
                            onChange={(e) => onGChange(parseFloat(e.target.value))}
                            className="lab-slider"
                        />
                    </div>
                </div>
            )}
            
            {/* RIM模型参数 */}
            {currentTab === 'RIM' && (
                <div className="sliders-row">
                    <div className="slider-group">
                        <div className="slider-label">
                            <span>要求回报率 (r)</span>
                            <span>{costOfEquity.toFixed(1)}%</span>
                        </div>
                        <input
                            type="range"
                            min={5}
                            max={20}
                            step={0.5}
                            value={costOfEquity}
                            onChange={(e) => onCostOfEquityChange?.(parseFloat(e.target.value))}
                            className="lab-slider"
                        />
                    </div>
                    <div className="slider-group">
                        <div className="slider-label">
                            <span>增长率 (g)</span>
                            <span>{growthRate.toFixed(1)}%</span>
                        </div>
                        <input
                            type="range"
                            min={0}
                            max={30}
                            step={1}
                            value={growthRate}
                            onChange={(e) => onGrowthRateChange?.(parseFloat(e.target.value))}
                            className="lab-slider"
                        />
                    </div>
                    <div className="slider-group">
                        <div className="slider-label">
                            <span>股利支付率</span>
                            <span>{payoutRatio.toFixed(0)}%</span>
                        </div>
                        <input
                            type="range"
                            min={0}
                            max={100}
                            step={5}
                            value={payoutRatio}
                            onChange={(e) => onPayoutRatioChange?.(parseFloat(e.target.value))}
                            className="lab-slider"
                        />
                    </div>
                </div>
            )}
        </div>
    );
}