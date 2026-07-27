import React from 'react';
import './Badge.css';

interface BadgeProps {
    children: React.ReactNode;
    variant?: 'primary' | 'success' | 'warning' | 'error' | 'neutral';
    pill?: boolean;
    className?: string;
}

const Badge: React.FC<BadgeProps> = ({
    children,
    variant = 'primary',
    pill = false,
    className = '',
}) => {
    return (
        <span className={`badge badge-${variant} ${pill ? 'badge-pill' : ''} ${className}`}>
            {children}
        </span>
    );
};

export default Badge;
