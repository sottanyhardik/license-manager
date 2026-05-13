import { useState } from "react";
import { ACTION_TONE_MAP, CHIP_TONE_MAP, TEXT_TONE_MAP, tone as resolveTone } from "../../theme/tokens";

/*
 * EntityCard — shared card layout for list rows (Allotment, BOE, Trade…).
 *
 * Props
 *   accent       primary | success | warning | danger | info | neutral
 *   title        ReactNode (typically a reference number)
 *   headerChips  array of { icon?, label, tone? }
 *   statusBadges array of { tone, label, icon? }
 *   summary      array of { label, value, tone? }
 *   actions      array of { icon, title, onClick, tone?, label? }
 *   onView       () => void  (controlled)  — toggles detail
 *   viewOpen     bool        (controlled)  — open state
 *   detail       () => ReactNode           — renders the expanded detail section
 *   detailLabel  string                    — label next to the View button
 *   defaultOpen  bool                      — initial open state
 */
const ALLOWED_TONES = new Set(["primary", "success", "warning", "danger", "info", "neutral"]);

function HeaderChip({ icon, label, tone = "neutral", style }) {
    const safe = ALLOWED_TONES.has(tone) ? tone : "neutral";
    const c = resolveTone(CHIP_TONE_MAP, safe);
    return (
        <span
            className="entity-card-chip"
            style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontSize: "11px",
                color: c.fg,
                background: c.bg,
                padding: "2px 7px",
                borderRadius: 4,
                border: `1px solid ${c.border}`,
                fontWeight: 500,
                lineHeight: 1.5,
                ...style,
            }}
        >
            {icon && <i className={`bi bi-${icon}`} style={{ fontSize: "10.5px" }} />}
            {label}
        </span>
    );
}

function ActionButton({ icon, title, onClick, tone = "neutral", children, disabled }) {
    const safe = ALLOWED_TONES.has(tone) ? tone : "neutral";
    const c = resolveTone(ACTION_TONE_MAP, safe);
    return (
        <button
            type="button"
            title={title}
            onClick={onClick}
            disabled={disabled}
            className="entity-card-action-btn"
            style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontWeight: 500,
                color: c.fg,
                background: c.bg,
                border: `1px solid ${c.border}`,
                cursor: disabled ? "not-allowed" : "pointer",
                opacity: disabled ? 0.55 : 1,
                lineHeight: 1.4,
                transition: "background var(--tb-tx-fast), box-shadow var(--tb-tx-fast)",
            }}
        >
            {icon && <i className={`bi bi-${icon}`} aria-hidden="true" />}
            {children}
        </button>
    );
}

function Stat({ label, value, tone }) {
    const valueColor =
        tone && TEXT_TONE_MAP[tone] ? TEXT_TONE_MAP[tone] : "var(--tb-text)";
    return (
        <div>
            <div className="entity-card-stat-label">{label}</div>
            <div className="entity-card-stat-value" style={{ color: valueColor }}>
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
    children,
    summary = [],
    actions = [],
    onView,
    viewOpen,
    detail,
    detailLabel,
    defaultOpen = false,
    className = "",
    style,
}) {
    const [internalOpen, setInternalOpen] = useState(defaultOpen);
    const isControlled = typeof onView === "function";
    const open = isControlled ? !!viewOpen : internalOpen;
    const toggle = () => {
        if (isControlled) onView();
        else setInternalOpen(v => !v);
    };

    const showViewBtn = !!detail;
    const safeAccent = ALLOWED_TONES.has(accent) ? accent : "primary";

    return (
        <article
            className={`entity-card tone-${safeAccent} ${className}`.trim()}
            style={style}
        >
            <header className="entity-card-header">
                <span className="entity-card-title" style={{ marginRight: 4 }}>
                    {title}
                </span>
                {headerChips.map((chip, i) => (
                    <HeaderChip key={i} {...chip} />
                ))}
                {statusBadges.map((b, i) => (
                    <HeaderChip key={`s-${i}`} tone={b.tone} label={b.label} icon={b.icon} />
                ))}
            </header>

            {children && (
                <div
                    className="entity-card-body"
                    style={{ borderBottom: "1px solid var(--tb-border-soft)" }}
                >
                    {children}
                </div>
            )}

            <div className="entity-card-body entity-card-body-row">
                <div className="entity-card-summary">
                    {summary.map((s, i) => (
                        <Stat key={i} {...s} />
                    ))}
                </div>
                <div className="entity-card-actions">
                    {actions.map((a, i) => (
                        <ActionButton key={i} {...a}>
                            {a.label}
                        </ActionButton>
                    ))}
                    {showViewBtn && (
                        <ActionButton
                            icon={open ? "chevron-up" : "chevron-down"}
                            title={open ? "Hide details" : "View details"}
                            tone="primary"
                            onClick={toggle}
                        >
                            <span style={{ marginLeft: 2 }}>
                                {open ? "Hide" : "View"}
                                {detailLabel ? ` · ${detailLabel}` : ""}
                            </span>
                        </ActionButton>
                    )}
                </div>
            </div>

            {showViewBtn && open && (
                <div className="entity-card-detail">
                    {detail()}
                </div>
            )}
        </article>
    );
}
