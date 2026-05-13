/**
 * IconChip — small/medium icon container, used as a visual anchor
 * for section headers, list items, or inline labels.
 *
 *   <IconChip icon="check2-square" tone="primary" />
 */
const TONE_MAP = {
    primary: { bg: "var(--indigo-50)",  fg: "var(--primary-color)" },
    success: { bg: "var(--success-bg)", fg: "var(--success-color)" },
    warning: { bg: "var(--warning-bg)", fg: "var(--warning-color)" },
    danger:  { bg: "var(--danger-bg)",  fg: "var(--danger-color)"  },
    info:    { bg: "var(--info-bg)",    fg: "var(--info-color)"    },
    neutral: { bg: "var(--surface-sunken)", fg: "var(--text-secondary)" },
};

const SIZE_MAP = {
    sm: { box: 24, icon: "0.78rem", radius: 6 },
    md: { box: 32, icon: "0.95rem", radius: 8 },
    lg: { box: 44, icon: "1.15rem", radius: 12 },
};

export default function IconChip({
    icon = "circle",
    tone = "primary",
    size = "md",
    style = {},
}) {
    const t = TONE_MAP[tone] || TONE_MAP.primary;
    const s = SIZE_MAP[size] || SIZE_MAP.md;
    return (
        <span
            aria-hidden="true"
            style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: s.box,
                height: s.box,
                borderRadius: s.radius,
                background: t.bg,
                color: t.fg,
                flexShrink: 0,
                ...style,
            }}
        >
            <i className={`bi bi-${icon}`} style={{ fontSize: s.icon }}></i>
        </span>
    );
}
