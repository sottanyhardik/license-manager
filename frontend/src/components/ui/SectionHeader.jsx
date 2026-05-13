/*
 * SectionHeader — title + optional subtitle + right-aligned actions slot.
 *
 *   <SectionHeader
 *     icon="file-earmark-text"
 *     iconTone="primary"
 *     title="Active Licenses"
 *     subtitle="Auto-refreshes every 5 minutes"
 *     actions={<Button size="sm">Refresh</Button>}
 *   />
 */
const ALLOWED_TONES = new Set(["primary", "success", "warning", "danger", "info", "neutral"]);

export default function SectionHeader({
    icon,
    iconTone = "primary",
    title,
    subtitle,
    actions,
    className = "",
    style,
}) {
    const safeTone = ALLOWED_TONES.has(iconTone) ? iconTone : "primary";
    return (
        <div className={`tb-section-head ${className}`.trim()} style={style}>
            {icon && (
                <span className={`tb-section-icon tone-${safeTone}`} aria-hidden="true">
                    <i className={`bi bi-${icon}`} />
                </span>
            )}
            <div className="tb-section-body">
                {title && <div className="tb-section-title">{title}</div>}
                {subtitle && <div className="tb-section-subtitle">{subtitle}</div>}
            </div>
            {actions && <div style={{ flexShrink: 0 }}>{actions}</div>}
        </div>
    );
}
