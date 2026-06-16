/**
 * Surface — a unified container primitive.
 *
 * variant: 'card' (raised, soft shadow) | 'panel' (no shadow) | 'sunken' (subtle gray)
 * tone:    optional accent color for the left edge.
 */
const TONE_TO_COLOR = {
    primary: "var(--primary-color)",
    success: "var(--success-color)",
    warning: "var(--warning-color)",
    danger:  "var(--danger-color)",
    info:    "var(--info-color)",
};

export default function Surface({
    variant = "card",
    tone,
    as,
    className = "",
    style = {},
    children,
    ...rest
}) {
    const Element = as || "div";

    const variantClass =
        variant === "panel"  ? "surface-panel"  :
        variant === "sunken" ? "surface-sunken" :
                               "surface-card";

    const toneStyles = tone && TONE_TO_COLOR[tone]
        ? { borderLeft: `3px solid ${TONE_TO_COLOR[tone]}` }
        : {};

    return (
        <Element
            className={`${variantClass} ${className}`.trim()}
            style={{ ...toneStyles, ...style }}
            {...rest}
        >
            {children}
        </Element>
    );
}
