import React from 'react';
import { designTokens } from '../../styles/designSystem';

/**
 * Business-Grade Card Component
 * Professional card with consistent styling
 */
export const Card = ({
    children,
    variant = 'default',
    hoverable = false,
    onClick,
    gradient,
    borderColor,
    className = '',
    style = {},
    ...props
}) => {
    const baseStyles = {
        backgroundColor: designTokens.colors.background.paper,
        borderRadius: designTokens.borderRadius.lg,
        boxShadow: variant === 'elevated' ? designTokens.shadows.md : designTokens.shadows.sm,
        border: borderColor ? `1px solid ${borderColor}` : 'none',
        transition: designTokens.transitions.base,
        ...(gradient && { background: gradient }),
        ...style,
    };

    const hoverStyles = hoverable ? {
        cursor: 'pointer',
        onMouseEnter: (e) => {
            e.currentTarget.style.boxShadow = designTokens.shadows.lg;
            e.currentTarget.style.transform = 'translateY(-2px)';
        },
        onMouseLeave: (e) => {
            e.currentTarget.style.boxShadow = variant === 'elevated' ? designTokens.shadows.md : designTokens.shadows.sm;
            e.currentTarget.style.transform = 'translateY(0)';
        },
    } : {};

    return (
        <div
            className={`card border-0 ${className}`}
            style={baseStyles}
            onClick={onClick}
            {...hoverStyles}
            {...props}
        >
            {children}
        </div>
    );
};

export const CardHeader = ({ children, gradient, icon, title, subtitle, actions, className = '', style = {} }) => {
    const headerStyles = {
        padding: designTokens.spacing[4],
        borderBottom: `1px solid ${designTokens.colors.neutral[200]}`,
        ...(gradient && {
            background: gradient,
            color: designTokens.colors.text.white,
            borderBottom: 'none',
        }),
        ...style,
    };

    return (
        <div className={`card-header bg-white border-0 ${className}`} style={headerStyles}>
            <div className="d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center">
                    {icon && (
                        <div style={{
                            width: '40px',
                            height: '40px',
                            borderRadius: designTokens.borderRadius.md,
                            background: gradient || designTokens.colors.gradients.primary,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            marginRight: designTokens.spacing[3],
                        }}>
                            <i className={`bi bi-${icon} text-white`} style={{ fontSize: '1.25rem' }}></i>
                        </div>
                    )}
                    <div>
                        {title && <h5 className="mb-0" style={{ fontWeight: designTokens.typography.fontWeight.semibold }}>{title}</h5>}
                        {subtitle && <p className="text-muted mb-0" style={{ fontSize: designTokens.typography.fontSize.sm }}>{subtitle}</p>}
                        {children && !title && children}
                    </div>
                </div>
                {actions && <div>{actions}</div>}
            </div>
        </div>
    );
};

export const CardBody = ({ children, padding = 4, className = '', style = {} }) => {
    const bodyStyles = {
        padding: designTokens.spacing[padding],
        ...style,
    };

    return (
        <div className={`card-body ${className}`} style={bodyStyles}>
            {children}
        </div>
    );
};

export const CardFooter = ({ children, className = '', style = {} }) => {
    const footerStyles = {
        padding: designTokens.spacing[4],
        borderTop: `1px solid ${designTokens.colors.neutral[200]}`,
        backgroundColor: designTokens.colors.neutral[50],
        ...style,
    };

    return (
        <div className={`card-footer border-0 ${className}`} style={footerStyles}>
            {children}
        </div>
    );
};

// Stat Card - Perfect for Dashboard KPIs
export const StatCard = ({
    title,
    value,
    subtitle,
    icon,
    color = 'primary',
    trend,
    onClick,
    gradient
}) => {
    const colorMap = {
        primary: { bg: designTokens.colors.primary[500], gradient: designTokens.colors.gradients.primary },
        success: { bg: designTokens.colors.success.main, gradient: designTokens.colors.gradients.success },
        warning: { bg: designTokens.colors.warning.main, gradient: designTokens.colors.gradients.warm },
        danger: { bg: designTokens.colors.error.main, gradient: designTokens.colors.gradients.secondary },
        info: { bg: designTokens.colors.info.main, gradient: designTokens.colors.gradients.info },
        secondary: { bg: designTokens.colors.neutral[600], gradient: designTokens.colors.gradients.cool },
    };

    const selectedColor = colorMap[color] || colorMap.primary;

    return (
        <Card hoverable={!!onClick} onClick={onClick}>
            <CardBody>
                <div className="d-flex justify-content-between align-items-start">
                    <div style={{ flex: 1 }}>
                        <p className="text-muted mb-2" style={{
                            fontSize: designTokens.typography.fontSize.sm,
                            fontWeight: designTokens.typography.fontWeight.medium,
                        }}>
                            {title}
                        </p>
                        <h2 className="mb-2" style={{
                            fontWeight: designTokens.typography.fontWeight.bold,
                            color: designTokens.colors.text.primary,
                        }}>
                            {value}
                        </h2>
                        {subtitle && (
                            <small className="text-muted d-flex align-items-center">
                                {trend && (
                                    <span className={`me-2 ${trend > 0 ? 'text-success' : 'text-danger'}`}>
                                        <i className={`bi bi-arrow-${trend > 0 ? 'up' : 'down'}`}></i>
                                        {Math.abs(trend)}%
                                    </span>
                                )}
                                {subtitle}
                            </small>
                        )}
                    </div>
                    <div style={{
                        width: '56px',
                        height: '56px',
                        borderRadius: designTokens.borderRadius.lg,
                        background: gradient || selectedColor.gradient,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        boxShadow: designTokens.shadows.sm,
                    }}>
                        <i className={`bi bi-${icon} text-white`} style={{ fontSize: '1.5rem' }}></i>
                    </div>
                </div>
            </CardBody>
        </Card>
    );
};

export default Card;
