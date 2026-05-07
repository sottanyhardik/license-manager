// Design token system — all values reference CSS variables defined in App.css

export const designTokens = {
    colors: {
        primary: {
            main:     'var(--primary-color)',
            light:    'var(--primary-light)',
            dark:     'var(--primary-dark)',
            deeper:   'var(--primary-deeper)',
            gradient: 'var(--primary-gradient)',
            50:  'var(--indigo-50)',
            100: 'var(--indigo-100)',
            200: 'var(--indigo-200)',
            300: 'var(--indigo-300)',
            400: 'var(--indigo-400)',
            500: 'var(--indigo-500)',
            600: 'var(--indigo-600)',
            700: 'var(--indigo-700)',
            800: 'var(--indigo-800)',
            900: 'var(--indigo-900)',
        },
        success: {
            main:   'var(--success-color)',
            light:  'var(--success-light)',
            bg:     'var(--success-bg)',
            border: 'var(--success-border)',
            text:   'var(--success-text)',
        },
        danger: {
            main:   'var(--danger-color)',
            light:  'var(--danger-light)',
            bg:     'var(--danger-bg)',
            border: 'var(--danger-border)',
            text:   'var(--danger-text)',
        },
        warning: {
            main:   'var(--warning-color)',
            light:  'var(--warning-light)',
            bg:     'var(--warning-bg)',
            border: 'var(--warning-border)',
            text:   'var(--warning-text)',
        },
        info: {
            main:   'var(--info-color)',
            light:  'var(--info-light)',
            bg:     'var(--info-bg)',
            border: 'var(--info-border)',
            text:   'var(--info-text)',
        },
        secondary: {
            main:  'var(--secondary-color)',
            light: 'var(--secondary-light)',
            dark:  'var(--secondary-dark)',
        },
        neutral: {
            0:   'var(--surface-color)',
            50:  'var(--gray-50)',
            100: 'var(--gray-100)',
            200: 'var(--gray-200)',
            300: 'var(--gray-300)',
            400: 'var(--gray-400)',
            500: 'var(--gray-500)',
            600: 'var(--gray-600)',
            700: 'var(--gray-700)',
            800: 'var(--gray-800)',
            900: 'var(--gray-900)',
        },
        text: {
            primary:   'var(--text-primary)',
            secondary: 'var(--text-secondary)',
            tertiary:  'var(--text-tertiary)',
            muted:     'var(--text-muted)',
            dark:      'var(--text-dark)',
            medium:    'var(--text-medium)',
            light:     'var(--text-light)',
            white:     '#ffffff',
        },
        background: {
            default:  'var(--background-color)',
            paper:    'var(--surface-color)',
            hover:    'var(--surface-hover)',
            elevated: 'var(--surface-color)',
        },
        gradients: {
            primary:   'var(--primary-gradient)',
            secondary: 'linear-gradient(135deg, var(--accent-color) 0%, var(--primary-dark) 100%)',
            success:   'linear-gradient(135deg, var(--success-color) 0%, var(--success-light) 100%)',
            info:      'linear-gradient(135deg, var(--info-color) 0%, var(--info-light) 100%)',
        },
    },

    typography: {
        fontFamily: {
            primary: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            mono:    '"Fira Code", "Courier New", monospace',
        },
        fontSize: {
            xs:   '0.75rem',
            sm:   '0.875rem',
            base: '1rem',
            lg:   '1.125rem',
            xl:   '1.25rem',
            '2xl': '1.5rem',
            '3xl': '1.875rem',
            '4xl': '2.25rem',
            '5xl': '3rem',
        },
        fontWeight: {
            light:     300,
            normal:    400,
            medium:    500,
            semibold:  600,
            bold:      700,
            extrabold: 800,
        },
        lineHeight: {
            tight:   1.25,
            normal:  1.5,
            relaxed: 1.75,
        },
    },

    spacing: {
        0: '0',
        1: '0.25rem',
        2: '0.5rem',
        3: '0.75rem',
        4: '1rem',
        5: '1.25rem',
        6: '1.5rem',
        8: '2rem',
        10: '2.5rem',
        12: '3rem',
        16: '4rem',
        20: '5rem',
    },

    borderRadius: {
        none: '0',
        sm:   '0.25rem',
        base: '0.375rem',
        md:   '0.5rem',
        lg:   '0.75rem',
        xl:   '1rem',
        '2xl': '1.5rem',
        full: '9999px',
        card: 'var(--card-radius)',
    },

    shadows: {
        none: 'none',
        sm:   'var(--shadow-sm)',
        md:   'var(--shadow-md)',
        lg:   'var(--shadow-lg)',
        xl:   'var(--shadow-xl)',
        card: 'var(--card-shadow)',
        cardHover: 'var(--card-shadow-hover)',
        modal: 'var(--card-shadow-modal)',
        // Material elevation
        e1: 'var(--elevation-1)',
        e2: 'var(--elevation-2)',
        e3: 'var(--elevation-3)',
        e4: 'var(--elevation-4)',
        e6: 'var(--elevation-6)',
    },

    transitions: {
        fast:   '150ms ease-in-out',
        base:   '200ms ease-in-out',
        slow:   '300ms ease-in-out',
    },

    zIndex: {
        dropdown:     1000,
        sticky:       1020,
        fixed:        1030,
        modalBackdrop: 1040,
        modal:        1050,
        popover:      1060,
        tooltip:      1070,
    },
};

// Pre-built component style objects — import these in JSX instead of hardcoding colors
export const componentStyles = {
    card: {
        default: {
            backgroundColor: 'var(--surface-color)',
            borderRadius:    'var(--card-radius)',
            boxShadow:       'var(--card-shadow)',
            border:          'none',
        },
        elevated: {
            backgroundColor: 'var(--surface-color)',
            borderRadius:    'var(--card-radius)',
            boxShadow:       'var(--elevation-3)',
            border:          'none',
        },
    },

    pageHeader: {
        gradient: {
            background:   'var(--primary-gradient)',
            padding:      '32px',
            borderRadius: 'var(--card-radius)',
            boxShadow:    'var(--elevation-2)',
            color:        '#ffffff',
            marginBottom: '24px',
        },
        container: {
            backgroundColor: 'var(--background-color)',
            minHeight:       '100vh',
            padding:         '24px',
        },
    },

    button: {
        base: {
            fontWeight:   500,
            borderRadius: '0.5rem',
            transition:   '200ms ease-in-out',
            fontSize:     '0.875rem',
        },
        primary: {
            background:   'var(--primary-gradient)',
            color:        '#ffffff',
            border:       'none',
        },
        ghost: {
            backgroundColor: 'rgba(255,255,255,0.15)',
            border:          '1px solid rgba(255,255,255,0.3)',
            color:           '#ffffff',
            backdropFilter:  'blur(10px)',
        },
    },

    badge: {
        primary: { backgroundColor: 'var(--badge-primary-bg)', color: 'var(--badge-primary-color)', borderRadius: '6px', padding: '3px 10px', fontSize: '0.78rem', fontWeight: 600 },
        success: { backgroundColor: 'var(--badge-success-bg)', color: 'var(--badge-success-color)', borderRadius: '6px', padding: '3px 10px', fontSize: '0.78rem', fontWeight: 600 },
        danger:  { backgroundColor: 'var(--badge-danger-bg)',  color: 'var(--badge-danger-color)',  borderRadius: '6px', padding: '3px 10px', fontSize: '0.78rem', fontWeight: 600 },
        warning: { backgroundColor: 'var(--badge-warning-bg)', color: 'var(--badge-warning-color)', borderRadius: '6px', padding: '3px 10px', fontSize: '0.78rem', fontWeight: 600 },
        info:    { backgroundColor: 'var(--badge-info-bg)',    color: 'var(--badge-info-color)',    borderRadius: '6px', padding: '3px 10px', fontSize: '0.78rem', fontWeight: 600 },
        gray:    { backgroundColor: 'var(--badge-gray-bg)',    color: 'var(--badge-gray-color)',    borderRadius: '6px', padding: '3px 10px', fontSize: '0.78rem', fontWeight: 600 },
    },

    table: {
        header: {
            backgroundColor: 'var(--gray-50)',
            borderBottom:    '2px solid var(--divider-color)',
            padding:         '1rem',
            fontSize:        '0.75rem',
            fontWeight:      700,
            color:           'var(--text-secondary)',
            textTransform:   'uppercase',
            letterSpacing:   '0.5px',
        },
        cell: {
            padding:      '1rem',
            borderBottom: '1px solid var(--divider-color)',
            fontSize:     '0.875rem',
            verticalAlign: 'middle',
        },
    },

    modal: {
        backdrop: {
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            backdropFilter:  'blur(4px)',
        },
        content: {
            backgroundColor: 'var(--surface-color)',
            borderRadius:    'var(--card-radius)',
            boxShadow:       'var(--card-shadow-modal)',
        },
    },

    input: {
        base: {
            borderRadius:    '0.5rem',
            border:          '1px solid var(--border-light)',
            padding:         '0.5rem 0.75rem',
            fontSize:        '0.875rem',
            backgroundColor: 'var(--surface-color)',
        },
    },

    // Status indicator strips (left-border cards)
    statusStrip: {
        success: { borderLeft: '4px solid var(--success-color)' },
        danger:  { borderLeft: '4px solid var(--danger-color)' },
        warning: { borderLeft: '4px solid var(--warning-color)' },
        info:    { borderLeft: '4px solid var(--info-color)' },
        primary: { borderLeft: '4px solid var(--primary-color)' },
    },
};

// Utility functions
export const utilities = {
    formatIndianCurrency: (value, decimals = 2) => {
        return new Intl.NumberFormat('en-IN', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        }).format(value);
    },

    getStatusColor: (status) => {
        const map = {
            success:  'var(--success-color)',
            warning:  'var(--warning-color)',
            error:    'var(--danger-color)',
            danger:   'var(--danger-color)',
            info:     'var(--info-color)',
            pending:  'var(--warning-color)',
            active:   'var(--success-color)',
            inactive: 'var(--gray-400)',
        };
        return map[status?.toLowerCase()] || 'var(--gray-500)';
    },

    breakpoints: {
        xs: '0px',
        sm: '576px',
        md: '768px',
        lg: '992px',
        xl: '1200px',
        xxl: '1400px',
    },
};

export default designTokens;
