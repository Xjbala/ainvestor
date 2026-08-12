import './AIMode.css';

interface DecisionFooterProps {
    status?: 'analyzing' | 'ready';
    targetPrice?: number | string;
    currentPrice?: number;
    recommendation?: string;
    returnRate?: number | string;
    onViewDetail?: () => void;
    onExportPDF?: () => void;
    onStopAnalysis?: () => void;
}

export function DecisionFooter({
    status: _status = 'ready',
    targetPrice = '计算中...',
    currentPrice,
    recommendation = '分析中',
    returnRate,
    onViewDetail,
    onExportPDF,
    onStopAnalysis,
}: DecisionFooterProps) {

    let displayReturn: string | number = '—';
    if (returnRate !== undefined && returnRate !== null && returnRate !== '计算中...') {
        displayReturn = returnRate;
    } else if (currentPrice && typeof targetPrice === 'number' && currentPrice > 0) {
        displayReturn = ((targetPrice - currentPrice) / currentPrice * 100).toFixed(1);
    } else if (returnRate === '计算中...') {
        displayReturn = '计算中...';
    }

    const isAnalyzing = _status === 'analyzing';

    // 一致性校验：评级与预期收益方向矛盾时显示警告
    const hasContradiction = !isAnalyzing && (() => {
        const bullRatings = ['强烈推荐', '推荐', '买入', '增持'];
        const bearRatings = ['谨慎', '回避', '卖出', '减持'];
        const isBull = bullRatings.some(r => recommendation.includes(r));
        const isBear = bearRatings.some(r => recommendation.includes(r));
        if (typeof displayReturn === 'number' || (typeof displayReturn === 'string' && displayReturn !== '—' && displayReturn !== '计算中...')) {
            const raw = String(displayReturn).replace(/%/g, '').trim();
            const n = Number(raw);
            if (Number.isFinite(n)) {
                if (isBull && n < -5) return true;   // 看多但预期收益<-5%
                if (isBear && n > 5) return true;    // 看空但预期收益>5%
            }
        }
        // 目标价远低于现价但评级为看多
        if (isBull && currentPrice && typeof targetPrice === 'number' && currentPrice > 0) {
            if (targetPrice < currentPrice * 0.85) return true;
        }
        return false;
    })();

    const formatReturn = () => {
        if (isAnalyzing && (displayReturn === '计算中...' || displayReturn === '—')) return '计算中...';
        if (displayReturn === '—' || displayReturn === '' || displayReturn == null) return '—';
        if (displayReturn === '计算中...') return isAnalyzing ? '计算中...' : '—';
        const raw = String(displayReturn).replace(/%/g, '').trim();
        const n = Number(raw);
        if (!Number.isFinite(n)) return String(displayReturn);
        const sign = n > 0 ? '+' : '';
        return `${sign}${n}%`;
    };

    const formatTarget = () => {
        if (isAnalyzing && (targetPrice === '计算中...' || !targetPrice)) return '计算中...';
        if (!targetPrice || targetPrice === '—' || targetPrice === '计算中...') return '—';
        if (targetPrice === '无法评估') return targetPrice;
        if (typeof targetPrice === 'string' && (targetPrice.includes('¥') || targetPrice.includes('-'))) {
            return targetPrice;
        }
        if (typeof targetPrice === 'number') return `¥${targetPrice.toLocaleString()}`;
        return String(targetPrice).startsWith('¥') ? String(targetPrice) : `¥${targetPrice}`;
    };

    return (
        <footer className="decision-footer">
            <div className="footer-top">
                <div className="status-summary">
                    <h3>{isAnalyzing ? '投资决策报告编制中' : '投资决策报告就绪'}</h3>
                    <p>
                        {isAnalyzing
                            ? '四位智能体正在进行深度分析，预计1-2分钟内完成报告编制。'
                            : (recommendation && recommendation !== '分析中' && recommendation !== '—'
                                ? `四位智能体已完成分析，综合评级：${recommendation}。请结合报告详情与风险提示决策。`
                                : '四位智能体已完成分析，请查看完整报告与风险提示。')}
                    </p>
                </div>
                <div className="footer-actions">
                    {isAnalyzing && onStopAnalysis && (
                        <button
                            className="btn-danger"
                            onClick={onStopAnalysis}
                        >
                            ⏹ 停止分析
                        </button>
                    )}
                    <button className="btn-secondary" onClick={onViewDetail} disabled={isAnalyzing}>
                        👁 查看详情
                    </button>
                    <button className="btn-primary" onClick={onExportPDF} disabled={isAnalyzing}>
                        📥 导出PDF报告
                    </button>
                </div>
            </div>

            <div className="footer-stats">
                {hasContradiction && (
                    <div
                        className="w-full mb-2 px-3 py-2 rounded-lg text-xs flex items-center gap-2"
                        style={{
                            background: 'rgba(244, 179, 102, 0.15)',
                            border: '1px solid rgba(244, 179, 102, 0.4)',
                            color: 'var(--warning-foreground)',
                        }}
                    >
                        <span>⚠️</span>
                        <span>评级与预期收益方向矛盾，建议以会议讨论结论为准，谨慎参考此建议</span>
                    </div>
                )}
                <div className="stat-item">
                    <div className="stat-label">投资建议</div>
                    <div className={`stat-value action-buy ${isAnalyzing ? 'analyzing' : ''}`}>
                        {isAnalyzing && (recommendation === '分析中' || recommendation === '分析中...')
                            ? '分析中...'
                            : (recommendation || '—')}
                    </div>
                </div>

                <div className="stat-item">
                    <div className="stat-label">目标价位</div>
                    <div className={`stat-value ${isAnalyzing ? 'analyzing' : ''}`}>
                        {formatTarget()}
                    </div>
                </div>

                <div className="stat-item">
                    <div className="stat-label">预期收益</div>
                    <div
                        className={`stat-value ${
                            typeof displayReturn === 'number' && displayReturn < 0
                                ? 'negative'
                                : 'positive'
                        } ${isAnalyzing ? 'analyzing' : ''}`}
                    >
                        {formatReturn()}
                    </div>
                </div>
            </div>
        </footer>
    );
}
