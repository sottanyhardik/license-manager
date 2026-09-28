/**
 * Typography configuration for Material UI theme
 * Uses Roboto font family (MUI default)
 * Provides consistent font scales for all text elements
 */

// MUI typography type is complex, using any for flexibility
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const typography: any = {
  fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',

  // Page titles and major headings
  h1: {
    fontSize: '2.5rem',
    fontWeight: 500,
    lineHeight: 1.2,
    letterSpacing: '-0.01562em',
  },

  // Section headings
  h2: {
    fontSize: '2rem',
    fontWeight: 500,
    lineHeight: 1.3,
    letterSpacing: '-0.0083em',
  },

  // Subsection headings
  h3: {
    fontSize: '1.75rem',
    fontWeight: 500,
    lineHeight: 1.4,
    letterSpacing: '0em',
  },

  // Minor headings
  h4: {
    fontSize: '1.5rem',
    fontWeight: 500,
    lineHeight: 1.4,
    letterSpacing: '0.0125em',
  },

  // Small headings
  h5: {
    fontSize: '1.25rem',
    fontWeight: 500,
    lineHeight: 1.5,
    letterSpacing: '0em',
  },

  // Smallest heading
  h6: {
    fontSize: '1rem',
    fontWeight: 500,
    lineHeight: 1.6,
    letterSpacing: '0.0125em',
  },

  // Body text - main paragraph text
  body1: {
    fontSize: '1rem',
    fontWeight: 400,
    lineHeight: 1.5,
    letterSpacing: '0.03125em',
  },

  // Body text - secondary, smaller
  body2: {
    fontSize: '0.875rem',
    fontWeight: 400,
    lineHeight: 1.43,
    letterSpacing: '0.0178em',
  },

  // Subheading - secondary text
  subtitle1: {
    fontSize: '1rem',
    fontWeight: 500,
    lineHeight: 1.75,
    letterSpacing: '0.009em',
  },

  // Subheading - smaller secondary text
  subtitle2: {
    fontSize: '0.875rem',
    fontWeight: 500,
    lineHeight: 1.57,
    letterSpacing: '0.0071em',
  },

  // Button text
  button: {
    fontSize: '0.875rem',
    fontWeight: 600,
    lineHeight: 1.75,
    letterSpacing: '0.0892em',
    textTransform: 'uppercase',
  },

  // Caption text - very small, supporting text
  caption: {
    fontSize: '0.75rem',
    fontWeight: 400,
    lineHeight: 1.66,
    letterSpacing: '0.0333em',
  },

  // Overline text - small labels and tags
  overline: {
    fontSize: '0.75rem',
    fontWeight: 600,
    lineHeight: 2.66,
    letterSpacing: '0.0833em',
    textTransform: 'uppercase',
  },
};

/**
 * Responsive font sizes for different breakpoints
 * Use with theme.breakpoints for adaptive typography
 */
export const responsiveTypography = {
  h1: {
    xs: { fontSize: '1.75rem', lineHeight: 1.3 },
    sm: { fontSize: '2rem', lineHeight: 1.3 },
    md: { fontSize: '2.5rem', lineHeight: 1.2 },
  },
  h2: {
    xs: { fontSize: '1.5rem', lineHeight: 1.4 },
    sm: { fontSize: '1.75rem', lineHeight: 1.3 },
    md: { fontSize: '2rem', lineHeight: 1.3 },
  },
  h3: {
    xs: { fontSize: '1.25rem', lineHeight: 1.5 },
    sm: { fontSize: '1.5rem', lineHeight: 1.4 },
    md: { fontSize: '1.75rem', lineHeight: 1.4 },
  },
};
