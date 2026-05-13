/**
 * StatusBadge — small pill with consistent tone palette.
 *
 *   <StatusBadge tone="success">Active</StatusBadge>
 */
const TONE_MAP = {
    primary: { bg: "var(--indigo-50)",   fg: "var(--primary-deeper)", border: "var(--indigo-100)" },
    success: { bg: "var(--success-bg)",  fg: "var(--success-text)",   border: "var(--success-border)" },
    warning: { bg: "var(--warning-bg)",  fg: "var(--warning-text)",   border: "var(--warning-border)" },
    danger:  { bg: "var(--danger-bg)",   fg: "var(--danger-text)",    border: "var(--danger-border)"  },
    info:    { bg: "var(--info-bg)",     fg: "var(--info-text)",      border: "var(--info-border)"    },
    neutral: { bg: "var(--surface-sunken)", fg: "var(--text-secondary)", border: "var(--border-default)" },
};

export default function StatusBadge({ tone = "neutral", children, style = {}, ...rest }) {
    const t = TONE_MAP[tone] || TONE_MAP.neutral;
    return (
        <span
            {...rest}
            style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                padding: "2px 8px",
                fontSize: "0.7rem",
                fontWeight: 500,
                lineHeight: 1.5,
                borderRadius: 999,
                background: t.bg,
                color: t.fg,
                border: `1px solid ${t.border}`,
                letterSpacing: "0.01em",
                ...style,
            }}
        >
            {children}
        </span>
    );
}
