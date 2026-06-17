import React, { useState } from "react";
import {
    AlertTriangle, ArrowLeftRight, Award, Building2, Calendar,
    CalendarCheck, CalendarRange, Check, CheckCircle2, Clipboard,
    CloudDownload, Copy, Download, Eye, FileText, Fingerprint,
    Globe, Info, Layers, Link as LinkIcon, LogIn, MapPin,
    MoreHorizontal, Network, Pencil, Plus, Receipt, RefreshCw,
    Trash2, TriangleAlert, X, ChevronDown, ChevronUp,
} from "lucide-react";
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

// ── Icon lookup: maps bi-name strings AND lucide component-name strings ───────
const ICON_MAP: Record<string, React.ElementType> = {
    // Lucide component-name strings (from Phase 4c-2 migration)
    "Pencil": Pencil, "pencil": Pencil, "pencil-fill": Pencil,
    "Eye": Eye, "eye": Eye,
    "Copy": Copy, "copy": Copy,
    "Download": Download, "download": Download,
    "FileText": FileText, "file-earmark-text": FileText, "file-pdf": FileText,
    "LogIn": LogIn, "box-arrow-in-down": LogIn,
    "ArrowLeftRight": ArrowLeftRight, "arrow-left-right": ArrowLeftRight,
    "RefreshCw": RefreshCw, "arrow-repeat": RefreshCw, "bi bi-arrow-repeat": RefreshCw,
    "Trash2": Trash2, "trash": Trash2,
    "Check": Check, "check2-circle": CheckCircle2,
    "AlertTriangle": AlertTriangle, "exclamation-triangle-fill": AlertTriangle,
    "Building2": Building2, "building": Building2, "building2": Building2,
    "Calendar": Calendar, "calendar3": Calendar,
    "MapPin": MapPin, "geo-alt": MapPin,
    "Layers": Layers, "intersect": Layers, "intersect2": Layers,
    "LinkIcon": LinkIcon, "link-45deg": LinkIcon,
    "CloudDownload": CloudDownload,
    "Plus": Plus,
    "Info": Info,
    "Fingerprint": Fingerprint,
    "Globe": Globe,
    "Receipt": Receipt,
    "Network": Network,
    "MoreHorizontal": MoreHorizontal,
    "Clipboard": Clipboard,
    "X": X,
    "chevron-down": ChevronDown, "chevron-up": ChevronUp,
};

function IconFromString({ name, className = "size-3.5" }: { name?: string; className?: string }) {
    if (!name) return null;
    const Comp = ICON_MAP[name];
    if (Comp) return <Comp className={className} aria-hidden="true" />;
    return null; // unknown icon — show nothing rather than broken bi- tag
}

const ALLOWED_TONES = new Set(["primary", "success", "warning", "danger", "info", "neutral"]);

function HeaderChip({ icon, label, tone = "neutral", style }: { icon?: string; label: React.ReactNode; tone?: string; style?: React.CSSProperties }) {
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
            <IconFromString name={icon} className="size-3" />
            {label}
        </span>
    );
}

function ActionButton({ icon, title, onClick, tone = "neutral", children, disabled }: { icon?: string; title?: string; onClick?: () => void; tone?: string; children?: React.ReactNode; disabled?: boolean }) {
    const safe = ALLOWED_TONES.has(tone) ? tone : "neutral";
    const c = resolveTone(ACTION_TONE_MAP, safe);
    const hasLabel = !!children;
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
                gap: hasLabel ? 4 : 0,
                fontWeight: 500,
                fontSize: 12,
                padding: hasLabel ? "4px 9px" : "4px 7px",
                color: c.fg,
                background: c.bg,
                border: `1px solid ${c.border}`,
                borderRadius: 6,
                cursor: disabled ? "not-allowed" : "pointer",
                opacity: disabled ? 0.55 : 1,
                lineHeight: 1.4,
                transition: "background var(--tb-tx-fast), box-shadow var(--tb-tx-fast)",
                whiteSpace: "nowrap",
            }}
        >
            <IconFromString name={icon} className="size-3.5" />
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
}: {
    accent?: string;
    title?: React.ReactNode;
    headerChips?: any[];
    statusBadges?: any[];
    children?: React.ReactNode;
    summary?: any[];
    actions?: any[];
    onView?: () => void;
    viewOpen?: boolean;
    detail?: () => React.ReactNode;
    detailLabel?: string;
    defaultOpen?: boolean;
    className?: string;
    style?: React.CSSProperties;
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
