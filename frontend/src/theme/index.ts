import { createTheme, ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { lightPalette, darkPalette, restrictionColors } from './palette';
import { typography } from './typography';
import { components } from './components';
import { shadows } from './shadows';

/**
 * Create Material UI theme for License Manager
 * Supports both light and dark modes
 */

const createAppTheme = (mode: 'light' | 'dark') => {
  const palette = mode === 'light' ? lightPalette : darkPalette;

  return createTheme({
    palette: {
      ...palette,
      mode,
    },
    typography,
    components,
    shadows,
    spacing: 8, // Base spacing unit (8px)
    shape: {
      borderRadius: 4, // Default border radius
    },
  });
};

// Export theme instances
export const lightTheme = createAppTheme('light');
export const darkTheme = createAppTheme('dark');

// Export helper function
export { createAppTheme };

// Export palette and restriction colors
export { lightPalette, darkPalette, restrictionColors };

// Export MUI components for convenience
export { MuiThemeProvider as ThemeProvider, CssBaseline };

// Export shadow system
export { shadows, elevationLevels } from './shadows';
