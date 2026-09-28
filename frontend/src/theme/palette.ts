import { PaletteOptions } from '@mui/material/styles';

/**
 * Color palette for Material UI theme
 * Includes light and dark mode colors
 */

export const lightPalette: PaletteOptions = {
  mode: 'light',
  primary: {
    main: '#1976D2',
    light: '#42A5F5',
    dark: '#1565C0',
    contrastText: '#ffffff',
  },
  secondary: {
    main: '#00897B',
    light: '#26A69A',
    dark: '#00695C',
    contrastText: '#ffffff',
  },
  success: {
    main: '#2E7D32',
    light: '#4CAF50',
    dark: '#1B5E20',
    contrastText: '#ffffff',
  },
  warning: {
    main: '#F57C00',
    light: '#FB8C00',
    dark: '#E65100',
    contrastText: '#ffffff',
  },
  error: {
    main: '#D32F2F',
    light: '#EF5350',
    dark: '#C62828',
    contrastText: '#ffffff',
  },
  info: {
    main: '#0288D1',
    light: '#03A9F4',
    dark: '#01579B',
    contrastText: '#ffffff',
  },
  background: {
    default: '#FAFAFA',
    paper: '#FFFFFF',
  },
  text: {
    primary: 'rgba(0, 0, 0, 0.87)',
    secondary: 'rgba(0, 0, 0, 0.60)',
    disabled: 'rgba(0, 0, 0, 0.38)',
  },
  divider: 'rgba(0, 0, 0, 0.12)',
  // Restriction-specific colors
  // These will be used in RestrictionValueCard for visual indication
  // Orange for warning (80%+ usage), red for exceeded, green for healthy
  action: {
    active: '#1976D2',
    hover: 'rgba(25, 118, 210, 0.04)',
    hoverOpacity: 0.04,
    selected: 'rgba(25, 118, 210, 0.08)',
    selectedOpacity: 0.08,
    disabled: 'rgba(0, 0, 0, 0.26)',
    disabledBackground: 'rgba(0, 0, 0, 0.12)',
    disabledOpacity: 0.38,
    focus: 'rgba(25, 118, 210, 0.05)',
    focusOpacity: 0.05,
    activatedOpacity: 0.12,
  } as any, // eslint-disable-line @typescript-eslint/no-explicit-any
};

export const darkPalette: PaletteOptions = {
  mode: 'dark',
  primary: {
    main: '#90CAF9',
    light: '#BBDEFB',
    dark: '#42A5F5',
    contrastText: '#000000',
  },
  secondary: {
    main: '#80CBC4',
    light: '#A1887F',
    dark: '#4DB6AC',
    contrastText: '#000000',
  },
  success: {
    main: '#66BB6A',
    light: '#81C784',
    dark: '#43A047',
    contrastText: '#000000',
  },
  warning: {
    main: '#FFA726',
    light: '#FFB74D',
    dark: '#FB8C00',
    contrastText: '#000000',
  },
  error: {
    main: '#EF5350',
    light: '#E57373',
    dark: '#E53935',
    contrastText: '#000000',
  },
  info: {
    main: '#29B6F6',
    light: '#4FC3F7',
    dark: '#0288D1',
    contrastText: '#000000',
  },
  background: {
    default: '#121212',
    paper: '#1E1E1E',
  },
  text: {
    primary: '#FFFFFF',
    secondary: 'rgba(255, 255, 255, 0.70)',
    disabled: 'rgba(255, 255, 255, 0.50)',
  },
  divider: 'rgba(255, 255, 255, 0.12)',
  // Dark mode action colors
  action: {
    active: '#90CAF9',
    hover: 'rgba(144, 202, 249, 0.08)',
    hoverOpacity: 0.08,
    selected: 'rgba(144, 202, 249, 0.16)',
    selectedOpacity: 0.16,
    disabled: 'rgba(255, 255, 255, 0.27)',
    disabledBackground: 'rgba(255, 255, 255, 0.12)',
    disabledOpacity: 0.38,
    focus: 'rgba(144, 202, 249, 0.05)',
    focusOpacity: 0.05,
    activatedOpacity: 0.24,
  } as any,
};

/**
 * Restriction-specific colors for display in RestrictionValueCard
 * These provide clear visual indication of restriction status
 */
export const restrictionColors = {
  healthy: {
    light: '#2E7D32', // MUI success dark
    dark: '#66BB6A', // MUI success light
  },
  warning: {
    light: '#F57C00', // MUI warning main
    dark: '#FFA726', // MUI warning light
  },
  exceeded: {
    light: '#D32F2F', // MUI error main
    dark: '#EF5350', // MUI error light
  },
};

/**
 * Helper function to get the appropriate palette based on mode
 */
export const getPalette = (mode: 'light' | 'dark'): PaletteOptions => {
  return mode === 'light' ? lightPalette : darkPalette;
};
