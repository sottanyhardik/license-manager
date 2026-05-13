import { useState } from "react";

/**
 * EntityCard — shared card layout for list rows (Allotment, BOE, Trade…).
 *
 * Props
 *   accent       primary | success | warning | danger | info | neutral
 *   title        ReactNode (typically a reference number)
 *   headerChips  array of { icon?, label, tone? }   — small tinted chips next to the title
 *   statusBadges array of { tone, label } — strong status indicators
 *   summary      array of { label, value, tone? }  — three or four KPIs above the actions
 *   actions      array of { icon, title, onClick, tone? } — small action buttons (Edit, Copy, Delete, etc)
 *   onView       () => void  — controlled toggle handler; if omitted, View button uses internal state
 *   viewOpen     bool — controlled `open` state when onView is provided
 *   detail       () => ReactNode — renders the expanded detail section
 *   detailLabel  string — label next to the View button (e.g. "5 Items")
 *   defaultOpen  bool — initial open state for uncontrolled mode
 */
const ACCENT_MAP = {
    primary: "var(--primary-color)",
    success: "var(--success-color)",
    warning: "var(--warning-color)",
    danger:  "var(--danger-color)",
    info:    "var(--info-color)",
    neutral: "var(--border-default)",
};

const ACTION_TONE_MAP = {
    primary: { fg: "var(--primary-color)",  bg: "var(--indigo-50)",  border: "var(--indigo-100)" },
    success: { fg: "var(--success-color)",  bg: "var(--success-bg)", border: "var(--success-border)" },
    warning: { fg: "var(--warning-color)",  bg: "var(--warning-bg)", border: "var(--warning-border)" },
    danger:  { fg: "var(--danger-color)",   bg: "var(--danger-bg)",  border: "var(--danger-border)"  },
    info:    { fg: "var(--info-color)",     fg2:"var(--info-color)", bg: "var(--info-bg)",    border: "var(--info-border)"    },
    neutral: { fg: "var(--text-secondary)", bg: "var(--surface-sunken)", border: "var(--border-default)" },
};

const CHIP_TONE_MAP = {
    primary: { fg: "var(--primary-deeper)", bg: "var(--indigo-50)",  border: "var(--indigo-100)" },
    success: { fg: "var(--success-text)",   bg: "var(--success-bg)", border: "var(--success-border)" },
    warning: { fg: "var(--warning-text)",   bg: "var(--warning-bg)", border: "var(--warning-border)" },
    danger:  { fg: "var(--danger-text)",    bg: "var(--danger-bg)",  border: "var(--danger-border)"  },
    info:    { fg: "var(--info-text)",      bg: "var(--info-bg)",    border: "var(--info-border)"    },
    neutral: { fg: "var(--text-secondary)", bg: "var(--surface-sunken)", border: "var(--border-default)" },
};

function HeaderChip({ icon, label, tone = "neutral", style = {} }) {
    const c = CHIP_TONE_MAP[tone] || CHIP_TONE_MAP.neutral;
    return (
        <span
            className="entity-card-chip"
            style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontSize: "0.82rem",
                color: c.fg,
                background: c.bg,
                padding: "3px 8px",
                borderRadius: 6,
                border: `1px solid ${c.border}`,
                fontWeight: 500,
                lineHeight: 1.5,
                ...style,
            }}
        >
            {icon && <i className={`bi bi-${icon}`} style={{ fontSize: "0.78rem" }}></i>}
            {label}
        </span>
    );
}

function ActionButton({ icon, title, onClick, tone = "neutral", children, disabled }) {
    const c = ACTION_TONE_MAP[tone] || ACTION_TONE_MAP.neutral;
    return (
        <button
            type="button"
            title={title}
            onClick={onClick}
            disabled={disabled}
            style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontSize: "0.78rem",
                fontWeight: 500,
                color: c.fg,
                background: c.bg,
                border: `1px solid ${c.border}`,
                borderRadius: 8,
                padding: "4px 9px",
                cursor: disabled ? "not-allowed" : "pointer",
                opacity: disabled ? 0.5 : 1,
                lineHeight: 1.4,
                transition: "background 150ms ease, box-shadow 150ms ease",
            }}
            onMouseEnter={(e) => { if (!disabled) e.currentTarget.style.boxShadow = "var(--elevation-1)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.boxShadow = "none"; }}
        >
            {icon && <i className={`bi bi-${icon}`} aria-hidden="true"></i>}
            {children}
        </button>
    );
}

function Stat({ label, value, tone }) {
    const valueColor =
        tone === "success" ? "var(--success-text)" :
        tone === "danger"  ? "var(--danger-text)" :
        tone === "warning" ? "var(--warning-text)" :
        "var(--text-primary)";
    return (
        <div>
            <div style={{
                fontSize: "0.66rem",
                color: "var(--text-tertiary)",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: 2,
            }}>
                {label}
            </div>
            <div style={{ fontSize: "0.875rem", color: valueColor, fontWeight: 600 }}>
                {value ?? "—"}
            </div>
        </div>
    );
}

export default function EntityCard({
    accent = "primary",
    title,
    headerChips = [],
    statusBadges = [],
    children,            // optional middle section (e.g. item name + licenses row)
    summary = [],
    actions = [],
    onView,
    viewOpen,
    detail,
    detailLabel,
    defaultOpen = false,
    style = {},
}) {
    const [internalOpen, setInternalOpen] = useState(defaultOpen);
    const isControlled = typeof onView === "function";
    const open = isControlled ? !!viewOpen : internalOpen;
    const toggle = () => {
        if (isControlled) onView();
        else setInternalOpen(v => !v);
    };

    const showViewBtn = !!detail;
    const accentColor = ACCENT_MAP[accent] || ACCENT_MAP.primary;

    return (
        <article
            style={{
                background: "var(--surface-raised)",
                border: "1px solid var(--border-subtle)",
                borderLeft: `4px solid ${accentColor}`,
                borderRadius: 12,
                marginBottom: 12,
                overflow: "hidden",
                boxShadow: "var(--elevation-1)",
                transition: "box-shadow 180ms cubic-bezier(0.16,1,0.3,1)",
                ...style,
            }}
            onMouseEnter={(e) => { e.currentTarget.style.boxShadow = "var(--elevation-2)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.boxShadow = "var(--elevation-1)"; }}
        >
            {/* Row 1: title + chips + status */}
            <header
                style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "10px 16px",
                    background: "var(--surface-sunken)",
                    borderBottom: "1px solid var(--border-subtle)",
                    flexWrap: "wrap",
                }}
            >
                <span style={{
                    fontWeight: 600,
                    fontSize: "0.95rem",
                    color: "var(--text-primary)",
                    letterSpacing: "-0.01em",
                    marginRight: 4,
                }}>
                    {title}
                </span>
                {headerChips.map((chip, i) => (
                    <HeaderChip key={i} {...chip} />
                ))}
                {statusBadges.map((b, i) => (
                    <HeaderChip key={`s-${i}`} tone={b.tone} label={b.label} icon={b.icon} />
                ))}
            </header>

            {/* Optional middle section */}
            {children && (
                <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border-subtle)" }}>
                    {children}
                </div>
            )}

            {/* Row 3: stats + actions */}
            <div
                style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "10px 16px",
                    background: "var(--surface-raised)",
                    flexWrap: "wrap",
                }}
            >
                <div className="entity-card-summary">
                    {summary.map((s, i) => (
                        <Stat key={i} {...s} />
                    ))}
                </div>
                <div className="entity-card-actions">
                    {actions.map((a, i) => (
                        <ActionButton key={i} {...a} />
                    ))}
                    {showViewBtn && (
                        <ActionButton
                            icon={open ? "chevron-up" : "chevron-down"}
                            title={open ? "Hide details" : "View details"}
                            tone="primary"
                            onClick={toggle}
                        >
                            <span className="entity-card-action-label" style={{ marginLeft: 2 }}>
                                {open ? "Hide" : "View"}
                                {detailLabel ? ` · ${detailLabel}` : ""}
                            </span>
                        </ActionButton>
                    )}
                </div>
            </div>

            {/* Expandable detail */}
            {showViewBtn && open && (
                <div
                    style={{
                        padding: "12px 16px",
                        background: "var(--surface-sunken)",
                        borderTop: "1px solid var(--border-subtle)",
                    }}
                >
                    {detail()}
                </div>
            )}
        </article>
    );
}
