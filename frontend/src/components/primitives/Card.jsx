/*
 * Card / CardHeader / CardBody / CardFooter / StatCard
 *
 * Thin wrappers around the .card / .card-header / .card-body / .card-footer
 * classes defined in theme/tabler.css. Kept for backwards compatibility — new
 * code should use the more focused primitives in ui/ (e.g. ui/StatCard,
 * ui/SectionHeader, ui/Surface).
 */
import LegacyStatCard from "./StatCard";

export const Card = ({
    children,
    variant = "default",
    hoverable = false,
    onClick,
    className = "",
    style,
    ...props
}) => (
    <div
        className={[
            "card",
            variant === "elevated" ? "shadow-sm" : "",
            hoverable ? "card-hoverable" : "",
            className,
        ].filter(Boolean).join(" ")}
        onClick={onClick}
        style={style}
        {...props}
    >
        {children}
    </div>
);

export const CardHeader = ({
    children,
    icon,
    title,
    subtitle,
    actions,
    className = "",
    style,
}) => (
    <div className={`card-header ${className}`.trim()} style={style}>
        <div className="flex justify-between items-center" style={{ gap: 12 }}>
            <div className="flex items-center" style={{ gap: 12, minWidth: 0 }}>
                {icon && (
                    <span
                        aria-hidden="true"
                        style={{
                            width: 32,
                            height: 32,
                            borderRadius: 6,
                            background: "var(--tb-brand-50)",
                            color: "var(--tb-brand)",
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexShrink: 0,
                        }}
                    >
                        <i className={`bi bi-${icon}`} />
                    </span>
                )}
                <div style={{ minWidth: 0 }}>
                    {title && <div style={{ fontWeight: 600, color: "var(--tb-text)" }}>{title}</div>}
                    {subtitle && (
                        <div style={{ fontSize: "12.5px", color: "var(--tb-text-secondary)" }}>
                            {subtitle}
                        </div>
                    )}
                    {children && !title && children}
                </div>
            </div>
            {actions && <div style={{ flexShrink: 0 }}>{actions}</div>}
        </div>
    </div>
);

export const CardBody = ({ children, className = "", style }) => (
    <div className={`card-body ${className}`.trim()} style={style}>
        {children}
    </div>
);

export const CardFooter = ({ children, className = "", style }) => (
    <div className={`card-footer ${className}`.trim()} style={style}>
        {children}
    </div>
);

// Re-export StatCard for legacy imports.
export const StatCard = LegacyStatCard;

export default Card;
