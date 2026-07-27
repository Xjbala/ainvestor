/**
 * Metric Card - 指标卡片（FinTech Futurism 风格）
 *
 * 展示关键指标，采用现代化金融科技设计语言
 */

import { useState } from 'react';
import './MetricCard.css';

export interface MetricCardProps {
    title: string;
    value: string | number;
    subtext?: string;
    tooltip: string;
    valueType?: 'success' | 'warning' | 'danger' | 'neutral';
    className?: string;
}

export function MetricCard({
    title,
    value,
    subtext,
    tooltip,
    valueType = 'neutral',
    className = ''
}: MetricCardProps) {
    const [showTooltip, setShowTooltip] = useState(false);

    return (
        <div
            className={`metric-card ${className} type-${valueType}`}
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
        >
            <div className="card-glow"></div>
            <div className="card-border"></div>
            
            <h3 className="card-title">{title}</h3>
            <div className={`card-value value-${valueType}`}>
                {value || '--'}
            </div>
            {subtext && <div className="card-subtext">{subtext}</div>}

            {showTooltip && (
                <div className="metric-tooltip">
                    <div className="tooltip-arrow"></div>
                    <div className="tooltip-content">{tooltip}</div>
                </div>
            )}
        </div>
    );
}