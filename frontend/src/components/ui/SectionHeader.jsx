/**
 * SectionHeader — title + optional subtitle + right-aligned actions slot.
 */
export default function SectionHeader({
    icon,
    iconTone = "primary",
    title,
    subtitle,
    actions,
    style = {},
}) {
    return (
        <div
            className="d-flex align-items-center"
            style={{
                gap: 12,
                marginBottom: 16,
                ...style,
            }}
        >
            {icon && (
                <span
                    aria-hidden="true"
                    style={{
                        width: 36,
                        height: 36,
                        borderRadius: 10,
                        background:
                            iconTone === "success" ? "var(--success-bg)" :
                            iconTone === "warning" ? "var(--warning-bg)" :
                            iconTone === "danger"  ? "var(--danger-bg)"  :
                            iconTone === "info"    ? "var(--info-bg)"    :
                                                     "var(--indigo-50)",
                        color:
                            iconTone === "success" ? "var(--success-color)" :
                            iconTone === "warning" ? "var(--warning-color)" :
                            iconTone === "danger"  ? "var(--danger-color)"  :
                            iconTone === "info"    ? "var(--info-color)"    :
                                                     "var(--primary-color)",
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                    }}
                >
                    <i className={`bi bi-${icon}`} style={{ fontSize: "1rem" }}></i>
                </span>
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                    fontSize: "1rem",
                    fontWeight: 600,
                    color: "var(--text-primary)",
                    letterSpacing: "-0.01em",
                }}>
                    {title}
                </div>
                {subtitle && (
                    <div style={{
                        fontSize: "0.8125rem",
                        color: "var(--text-secondary)",
                        marginTop: 2,
                    }}>
                        {subtitle}
                    </div>
                )}
            </div>
            {actions && <div style={{ flexShrink: 0 }}>{actions}</div>}
        </div>
    );
}
