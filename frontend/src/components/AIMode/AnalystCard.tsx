import { useEffect, useState } from 'react';
import { formatTimeShort } from '../../utils/timeFormat';
import './AIMode.css';

export interface AnalystCardProps {
    title: string;
    subtitle?: string;
    icon: React.ReactNode;
    iconClass: 'icon-fund' | 'icon-risk' | 'icon-decision' | 'icon-portfolio';
    status: 'pending' | 'active' | 'completed';
    progress: number;
    logs: string[];
    timestamp?: string;
    isActiveFilter?: boolean;
    onClick?: () => void;
}

export function AnalystCard({
    title,
    subtitle,
    icon,
    iconClass,
    status,
    progress,
    logs,
    timestamp,
    isActiveFilter,
    onClick
}: AnalystCardProps) {
    // Animation state for progress
    const [displayProgress, setDisplayProgress] = useState(0);

    useEffect(() => {
        setDisplayProgress(progress);
    }, [progress]);

    return (
        <div
            className={`analyst-card ${status === 'active' ? 'active' : ''} ${isActiveFilter ? 'filter-selected' : ''}`}
            onClick={onClick}
            style={{ cursor: onClick ? 'pointer' : 'default' }}
        >
            <div className="card-header">
                <div className="card-icon-title">
                    <div className={`card-icon ${iconClass}`}>
                        {icon}
                    </div>
                    <div className="card-title">
                        <h3>{title}</h3>
                        {subtitle && <div className="card-subtitle">{subtitle}</div>}
                    </div>
                </div>
                <div className={`card-status-icon ${status}`}>
                    {status === 'completed' ? '✓' : status === 'active' ? '⚡' : '○'}
                </div>
            </div>

            <div className="progress-section">
                <div className="progress-label">
                    <span>分析进度</span>
                    <span>{displayProgress}%</span>
                </div>
                <div className="progress-bar-bg">
                    <div
                        className="progress-bar-fill"
                        style={{ width: `${displayProgress}%` }}
                    ></div>
                </div>
            </div>

            <div className="card-logs">
                {logs.slice(-3).map((log, index) => (
                    <div key={index} className="log-item">
                        <span className="log-time">[{timestamp ? formatTimeShort(timestamp) : '--:--'}]</span>
                        <span className={`log-text ${log.includes('警告') || log.includes('风险') ? 'highlight' : ''}`}>{log}</span>
                    </div>
                ))}
                {status === 'active' && (
                    <div className="log-item">
                        <span className="log-time">...</span>
                    </div>
                )}
            </div>
        </div>
    );
}
