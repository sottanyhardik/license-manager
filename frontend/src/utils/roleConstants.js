/**
 * Single source of truth for role labels and badge colours.
 * Import from here everywhere roles are displayed.
 */

export const ROLE_LABELS = {
    USER_MANAGER:               'User Manager',
    LICENSE_MANAGER:            'License Manager',
    LICENSE_VIEWER:             'License Viewer',
    ALLOTMENT_MANAGER:          'Allotment Manager',
    ALLOTMENT_VIEWER:           'Allotment Viewer',
    BOE_MANAGER:                'BOE Manager',
    BOE_VIEWER:                 'BOE Viewer',
    TRADE_MANAGER:              'Trade Manager',
    TRADE_VIEWER:               'Trade Viewer',
    INCENTIVE_LICENSE_MANAGER:  'Incentive Manager',
    INCENTIVE_LICENSE_VIEWER:   'Incentive Viewer',
    REPORT_VIEWER:              'Report Viewer',
    TL_GENERATE:                'Transfer Letter',
    LEDGER_MANAGER:             'Ledger Manager',
    ACCOUNT_ACCESS:             'Account Access',
};

/**
 * Bootstrap colour variants per role.
 * Manager roles = saturated colour. Viewer roles = muted/lighter variant.
 * Special roles = distinct accent.
 */
export const ROLE_BADGE_COLOR = {
    USER_MANAGER:               'danger',     // admin — red, high attention
    LICENSE_MANAGER:            'primary',    // core business — indigo
    LICENSE_VIEWER:             'info',       // read-only — blue-teal
    ALLOTMENT_MANAGER:          'success',    // green — operations write
    ALLOTMENT_VIEWER:           'secondary',  // grey — read only
    BOE_MANAGER:                'warning',    // amber — BOE write
    BOE_VIEWER:                 'secondary',  // grey — read only
    TRADE_MANAGER:              'dark',       // dark — trade write
    TRADE_VIEWER:               'secondary',  // grey — read only
    INCENTIVE_LICENSE_MANAGER:  'primary',    // indigo — same family as LICENSE
    INCENTIVE_LICENSE_VIEWER:   'info',       // blue — same family as viewer
    REPORT_VIEWER:              'secondary',  // grey — read only
    TL_GENERATE:                'purple',     // accent — special action role
    LEDGER_MANAGER:             'teal',       // teal — ledger domain
};

/** Inline style overrides for colours not in Bootstrap's default palette. */
export const ROLE_BADGE_STYLE = {
    TL_GENERATE:    { background: '#ede9fe', color: '#6d28d9', border: '1px solid #c4b5fd' },
    LEDGER_MANAGER: { background: '#ccfbf1', color: '#0f766e', border: '1px solid #99f6e4' },
    ACCOUNT_ACCESS: { background: '#fef9c3', color: '#854d0e', border: '1px solid #fde68a' },
};

/** Returns the label for a role code, falling back to the code itself. */
export const getRoleLabel = (code) => ROLE_LABELS[code] ?? code;

/** Returns inline styles for a role badge (handles custom + Bootstrap variants). */
export const getRoleBadgeProps = (code) => {
    if (ROLE_BADGE_STYLE[code]) {
        return { className: 'badge', style: ROLE_BADGE_STYLE[code] };
    }
    return { className: `badge bg-${ROLE_BADGE_COLOR[code] ?? 'secondary'}` };
};
