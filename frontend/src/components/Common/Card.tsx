import React from 'react';
import './Card.css';

interface CardProps {
    children: React.ReactNode;
    title?: React.ReactNode;
    subtitle?: React.ReactNode;
    footer?: React.ReactNode;
    variant?: 'glass' | 'solid' | 'outline';
    padding?: 'none' | 'sm' | 'md' | 'lg';
    className?: string;
    onClick?: () => void;
}

const Card: React.FC<CardProps> = ({
    children,
    title,
    subtitle,
    footer,
    variant = 'glass',
    padding = 'md',
    className = '',
    onClick,
}) => {
    return (
        <div
            className={`card card-${variant} card-p-${padding} ${onClick ? 'card-interactive' : ''} ${className}`}
            onClick={onClick}
        >
            {(title || subtitle) && (
                <div className="card-header">
                    {title && <h3 className="card-title">{title}</h3>}
                    {subtitle && <p className="card-subtitle">{subtitle}</p>}
                </div>
            )}
            <div className="card-body">{children}</div>
            {footer && <div className="card-footer">{footer}</div>}
        </div>
    );
};

export default Card;
