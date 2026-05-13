/*
 * Centralized design tokens for the JS layer.
 *
 * - All values reference CSS variables defined in theme/tabler.css.
 * - Use TONE_MAP / CHIP_TONE_MAP / ACTION_TONE_MAP as the single source
 *   of truth for status-tinted UI (badges, chips, action buttons).
 * - Components must import from here instead of redefining their own maps.
 */

export const TONES = ["primary", "success", "warning", "danger", "info", "neutral"];

// Strong fill — for badges/chips where contrast matters.
export const TONE_MAP = {
    primary: { bg: "var(--tb-brand-50)",       fg: "var(--tb-brand-active)",   border: "var(--tb-brand-100)" },
    success: { bg: "var(--tb-success-soft)",   fg: "var(--tb-success-text)",   border: "var(--tb-success-border, #B7E2BE)" },
    warning: { bg: "var(--tb-warning-soft)",   fg: "var(--tb-warning-text)",   border: "var(--tb-warning-border, #FAC9A8)" },
    danger:  { bg: "var(--tb-danger-soft)",    fg: "var(--tb-danger-text)",    border: "var(--tb-danger-border, #F0B8B8)" },
    info:    { bg: "var(--tb-info-soft)",      fg: "var(--tb-info-text)",      border: "var(--tb-info-border, #BBD4ED)" },
    neutral: { bg: "var(--tb-sunken)",         fg: "var(--tb-text-secondary)", border: "var(--tb-border)" },
};

// Soft chip — looser presence, used inside dense lists/cards.
export const CHIP_TONE_MAP = TONE_MAP;

// Action button — same surface palette, slightly different border emphasis.
export const ACTION_TONE_MAP = {
    primary: { bg: "var(--tb-brand-50)",     fg: "var(--tb-brand)",          border: "var(--tb-brand-100)" },
    success: { bg: "var(--tb-success-soft)", fg: "var(--tb-success-text)",   border: "var(--tb-success-border, #B7E2BE)" },
    warning: { bg: "var(--tb-warning-soft)", fg: "var(--tb-warning-text)",   border: "var(--tb-warning-border, #FAC9A8)" },
    danger:  { bg: "var(--tb-danger-soft)",  fg: "var(--tb-danger-text)",    border: "var(--tb-danger-border, #F0B8B8)" },
    info:    { bg: "var(--tb-info-soft)",    fg: "var(--tb-info-text)",      border: "var(--tb-info-border, #BBD4ED)" },
    neutral: { bg: "var(--tb-card-bg)",      fg: "var(--tb-text-secondary)", border: "var(--tb-border)" },
};

// Strong accent (left edge / divider) — flat colors, not soft.
export const ACCENT_MAP = {
    primary: "var(--tb-brand)",
    success: "var(--tb-success)",
    warning: "var(--tb-warning)",
    danger:  "var(--tb-danger)",
    info:    "var(--tb-info)",
    neutral: "var(--tb-border)",
};

// Text color used for emphasis (e.g. a stat value when delta is positive).
export const TEXT_TONE_MAP = {
    primary: "var(--tb-brand)",
    success: "var(--tb-success-text)",
    warning: "var(--tb-warning-text)",
    danger:  "var(--tb-danger-text)",
    info:    "var(--tb-info-text)",
    neutral: "var(--tb-text)",
};

// Generic resolver — returns the requested map entry or the neutral fallback.
export function tone(map, key) {
    return map[key] || map.neutral || Object.values(map)[0];
}

// Bootstrap color name → status tone. Useful when adapting old code.
export const BOOTSTRAP_TO_TONE = {
    primary:   "primary",
    secondary: "neutral",
    success:   "success",
    danger:    "danger",
    warning:   "warning",
    info:      "info",
    light:     "neutral",
    dark:      "neutral",
};

export const tokens = {
    // Spacing scale (px)
    spacing: { 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 8: 32, 10: 40, 12: 48 },
    // Radii
    radius:  { sm: 4, md: 6, lg: 8, xl: 12, pill: 999 },
    // Font sizes (px) — match tabler.css
    fs: { xs: 11, sm: 12, base: 14, md: 15, lg: 16, xl: 19, "2xl": 24 },
    // Font weights
    fw: { normal: 400, medium: 500, semibold: 600, bold: 700 },
    // Z-index strata
    z: { dropdown: 1000, sticky: 1020, fixed: 1030, modal: 1050, tooltip: 1070 },
    // Breakpoints (px)
    bp: { sm: 480, md: 720, lg: 1024, xl: 1280, "2xl": 1640 },
};

export default tokens;
