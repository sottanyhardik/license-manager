// Business-Grade Design System for License Manager

export const designTokens = {
    // Color Palette - Professional Business Colors
    colors: {
        // Primary - Professional Blue
        primary: {
            50: '#e3f2fd',
            100: '#bbdefb',
            200: '#90caf9',
            300: '#64b5f6',
            400: '#42a5f5',
            500: '#2196f3',
            600: '#1e88e5',
            700: '#1976d2',
            800: '#1565c0',
            900: '#0d47a1',
        },

        // Secondary - Elegant Purple
        secondary: {
            50: '#f3e5f5',
            100: '#e1bee7',
            200: '#ce93d8',
            300: '#ba68c8',
            400: '#ab47bc',
            500: '#9c27b0',
            600: '#8e24aa',
            700: '#7b1fa2',
            800: '#6a1b9a',
            900: '#4a148c',
        },

        // Success - Natural Green
        success: {
            light: '#81c784',
            main: '#2e7d32',
            dark: '#1b5e20',
            bg: '#e8f5e9',
        },

        // Warning - Warm Orange
        warning: {
            light: '#ffb74d',
            main: '#f57c00',
            dark: '#e65100',
            bg: '#fff3e0',
        },

        // Error - Refined Red
        error: {
            light: '#e57373',
            main: '#d32f2f',
            dark: '#c62828',
            bg: '#ffebee',
        },

        // Info - Cool Cyan
        info: {
            light: '#4fc3f7',
            main: '#00acc1',
            dark: '#00838f',
            bg: '#e0f7fa',
        },

        // Neutrals - Professional Grays
        neutral: {
            0: '#ffffff',
            50: '#fafafa',
            100: '#f5f5f5',
            200: '#eeeeee',
            300: '#e0e0e0',
            400: '#bdbdbd',
            500: '#9e9e9e',
            600: '#757575',
            700: '#616161',
            800: '#424242',
            900: '#212121',
        },

        // Text Colors
        text: {
            primary: '#2c3e50',
            secondary: '#5a6c7d',
            disabled: '#9e9e9e',
            white: '#ffffff',
        },

        // Background Colors
        background: {
            default: '#f8f9fa',
            paper: '#ffffff',
            elevated: '#ffffff',
        },

        // Gradient Backgrounds
        gradients: {
            primary: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            secondary: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
            success: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
            info: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
            warm: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
            cool: 'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
        },
    },

    // Typography
    typography: {
        fontFamily: {
            primary: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
            mono: '"Fira Code", "Courier New", monospace',
        },
        fontSize: {
            xs: '0.75rem',      // 12px
            sm: '0.875rem',     // 14px
            base: '1rem',       // 16px
            lg: '1.125rem',     // 18px
            xl: '1.25rem',      // 20px
            '2xl': '1.5rem',    // 24px
            '3xl': '1.875rem',  // 30px
            '4xl': '2.25rem',   // 36px
            '5xl': '3rem',      // 48px
        },
        fontWeight: {
            light: 300,
            normal: 400,
            medium: 500,
            semibold: 600,
            bold: 700,
            extrabold: 800,
        },
        lineHeight: {
            tight: 1.25,
            normal: 1.5,
            relaxed: 1.75,
        },
    },

    // Spacing Scale (8px base)
    spacing: {
        0: '0',
        1: '0.25rem',   // 4px
        2: '0.5rem',    // 8px
        3: '0.75rem',   // 12px
        4: '1rem',      // 16px
        5: '1.25rem',   // 20px
        6: '1.5rem',    // 24px
        8: '2rem',      // 32px
        10: '2.5rem',   // 40px
        12: '3rem',     // 48px
        16: '4rem',     // 64px
        20: '5rem',     // 80px
    },

    // Border Radius
    borderRadius: {
        none: '0',
        sm: '0.25rem',      // 4px
        base: '0.375rem',   // 6px
        md: '0.5rem',       // 8px
        lg: '0.75rem',      // 12px
        xl: '1rem',         // 16px
        '2xl': '1.5rem',    // 24px
        full: '9999px',
    },

    // Shadows - Professional Depth
    shadows: {
        none: 'none',
        sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        base: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
        md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
        xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
        '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
        inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)',
    },

    // Transitions
    transitions: {
        fast: '150ms ease-in-out',
        base: '200ms ease-in-out',
        slow: '300ms ease-in-out',
    },

    // Z-Index Scale
    zIndex: {
        dropdown: 1000,
        sticky: 1020,
        fixed: 1030,
        modalBackdrop: 1040,
        modal: 1050,
        popover: 1060,
        tooltip: 1070,
    },
};

// Component Styles - Reusable Style Objects
export const componentStyles = {
    // Card Styles
    card: {
        default: {
            backgroundColor: designTokens.colors.background.paper,
            borderRadius: designTokens.borderRadius.lg,
            boxShadow: designTokens.shadows.sm,
            border: 'none',
        },
        elevated: {
            backgroundColor: designTokens.colors.background.paper,
            borderRadius: designTokens.borderRadius.lg,
            boxShadow: designTokens.shadows.md,
            border: 'none',
        },
        hoverable: {
            transition: designTokens.transitions.base,
            cursor: 'pointer',
            ':hover': {
                boxShadow: designTokens.shadows.lg,
                transform: 'translateY(-2px)',
            },
        },
    },

    // Button Styles
    button: {
        base: {
            fontWeight: designTokens.typography.fontWeight.medium,
            borderRadius: designTokens.borderRadius.md,
            transition: designTokens.transitions.base,
            padding: `${designTokens.spacing[2]} ${designTokens.spacing[4]}`,
            fontSize: designTokens.typography.fontSize.sm,
        },
        primary: {
            background: designTokens.colors.gradients.primary,
            color: designTokens.colors.text.white,
            border: 'none',
        },
        secondary: {
            backgroundColor: designTokens.colors.neutral[100],
            color: designTokens.colors.text.primary,
            border: `1px solid ${designTokens.colors.neutral[300]}`,
        },
    },

    // Input Styles
    input: {
        base: {
            borderRadius: designTokens.borderRadius.md,
            border: `1px solid ${designTokens.colors.neutral[300]}`,
            padding: `${designTokens.spacing[2]} ${designTokens.spacing[3]}`,
            fontSize: designTokens.typography.fontSize.sm,
            transition: designTokens.transitions.base,
            ':focus': {
                outline: 'none',
                borderColor: designTokens.colors.primary[500],
                boxShadow: `0 0 0 3px ${designTokens.colors.primary[50]}`,
            },
        },
        error: {
            borderColor: designTokens.colors.error.main,
            ':focus': {
                boxShadow: `0 0 0 3px ${designTokens.colors.error.bg}`,
            },
        },
    },

    // Badge Styles
    badge: {
        base: {
            fontSize: designTokens.typography.fontSize.xs,
            fontWeight: designTokens.typography.fontWeight.semibold,
            padding: `${designTokens.spacing[1]} ${designTokens.spacing[3]}`,
            borderRadius: designTokens.borderRadius.base,
        },
    },

    // Table Styles
    table: {
        header: {
            backgroundColor: designTokens.colors.neutral[50],
            borderBottom: `2px solid ${designTokens.colors.neutral[200]}`,
            padding: designTokens.spacing[4],
            fontSize: designTokens.typography.fontSize.xs,
            fontWeight: designTokens.typography.fontWeight.bold,
            color: designTokens.colors.text.secondary,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
        },
        cell: {
            padding: designTokens.spacing[4],
            borderBottom: `1px solid ${designTokens.colors.neutral[100]}`,
            fontSize: designTokens.typography.fontSize.sm,
            verticalAlign: 'middle',
        },
        row: {
            transition: designTokens.transitions.fast,
            ':hover': {
                backgroundColor: designTokens.colors.neutral[50],
            },
        },
    },

    // Modal Styles
    modal: {
        backdrop: {
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            backdropFilter: 'blur(4px)',
        },
        content: {
            backgroundColor: designTokens.colors.background.paper,
            borderRadius: designTokens.borderRadius.xl,
            boxShadow: designTokens.shadows['2xl'],
            maxWidth: '600px',
            margin: 'auto',
        },
    },

    // Page Header Styles
    pageHeader: {
        gradient: {
            background: designTokens.colors.gradients.primary,
            padding: designTokens.spacing[8],
            borderRadius: designTokens.borderRadius.xl,
            boxShadow: designTokens.shadows.md,
            color: designTokens.colors.text.white,
        },
        simple: {
            marginBottom: designTokens.spacing[6],
        },
    },
};

// Utility Functions
export const utilities = {
    // Format Indian Currency
    formatIndianCurrency: (value, decimals = 2) => {
        return new Intl.NumberFormat('en-IN', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        }).format(value);
    },

    // Get Color by Status
    getStatusColor: (status) => {
        const statusColors = {
            success: designTokens.colors.success.main,
            warning: designTokens.colors.warning.main,
            error: designTokens.colors.error.main,
            info: designTokens.colors.info.main,
            pending: designTokens.colors.warning.main,
            active: designTokens.colors.success.main,
            inactive: designTokens.colors.neutral[400],
        };
        return statusColors[status?.toLowerCase()] || designTokens.colors.neutral[500];
    },

    // Responsive Breakpoints
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
