import { Components, Theme } from '@mui/material/styles';

/**
 * Component-specific style overrides for Material UI theme
 * This file defines default styles for all MUI components
 */

export const components: Components<Theme> = {
  // Button component overrides
  MuiButton: {
    styleOverrides: {
      root: {
        textTransform: 'uppercase',
        fontWeight: 600,
        letterSpacing: '0.0892em',
        borderRadius: '4px',
        padding: '10px 16px',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        '&:hover': {
          transform: 'translateY(-2px)',
        },
      },
      sizeLarge: {
        padding: '12px 24px',
        fontSize: '1rem',
      },
      sizeMedium: {
        padding: '10px 16px',
        fontSize: '0.875rem',
      },
      sizeSmall: {
        padding: '6px 12px',
        fontSize: '0.75rem',
      },
      contained: {
        boxShadow:
          '0px 2px 4px -1px rgba(25, 118, 210, 0.2),0px 4px 5px 0px rgba(25, 118, 210, 0.14),0px 1px 10px 0px rgba(25, 118, 210, 0.12)',
        '&:hover': {
          boxShadow:
            '0px 3px 5px -1px rgba(25, 118, 210, 0.2),0px 5px 8px 0px rgba(25, 118, 210, 0.14),0px 1px 14px 0px rgba(25, 118, 210, 0.12)',
        },
      },
      outlined: {
        border: '2px solid #1976D2',
        '&:hover': {
          backgroundColor: 'rgba(25, 118, 210, 0.08)',
        },
      },
      text: {
        '&:hover': {
          backgroundColor: 'rgba(25, 118, 210, 0.08)',
        },
      },
    },
    defaultProps: {
      disableElevation: false,
      variant: 'contained',
    },
  },

  // TextField component overrides
  MuiTextField: {
    styleOverrides: {
      root: {
        '& .MuiOutlinedInput-root': {
          borderRadius: '4px',
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: '#1976D2',
          },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderWidth: '2px',
          },
        },
        '& .MuiOutlinedInput-input': {
          padding: '12px 14px',
          fontSize: '0.875rem',
          '&::placeholder': {
            opacity: 0.6,
          },
        },
      },
    },
    defaultProps: {
      variant: 'outlined',
      fullWidth: false,
    },
  },

  // Card component overrides
  MuiCard: {
    styleOverrides: {
      root: {
        borderRadius: '8px',
        boxShadow:
          '0px 3px 1px -2px rgba(0,0,0,0.2),0px 2px 2px 0px rgba(0,0,0,0.14),0px 1px 5px 0px rgba(0,0,0,0.12)',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        '&:hover': {
          boxShadow:
            '0px 5px 5px -3px rgba(0,0,0,0.2),0px 8px 10px 1px rgba(0,0,0,0.14),0px 3px 14px 2px rgba(0,0,0,0.12)',
        },
      },
    },
  },

  // CardContent padding
  MuiCardContent: {
    styleOverrides: {
      root: {
        padding: '24px',
        '&:last-child': {
          paddingBottom: '24px',
        },
      },
    },
  },

  // Dialog component overrides
  MuiDialog: {
    styleOverrides: {
      paper: {
        borderRadius: '8px',
        boxShadow:
          '0px 5px 5px -3px rgba(0,0,0,0.2),0px 8px 10px 1px rgba(0,0,0,0.14),0px 3px 14px 2px rgba(0,0,0,0.12)',
      },
    },
  },

  // DialogTitle styling
  MuiDialogTitle: {
    styleOverrides: {
      root: {
        fontSize: '1.25rem',
        fontWeight: 600,
        padding: '24px',
      },
    },
  },

  // DialogContent styling
  MuiDialogContent: {
    styleOverrides: {
      root: {
        padding: '20px 24px',
        '&:first-of-type': {
          paddingTop: '20px',
        },
      },
    },
  },

  // Input label styling
  MuiInputLabel: {
    styleOverrides: {
      root: {
        fontSize: '0.875rem',
        fontWeight: 500,
        '&.Mui-focused': {
          fontWeight: 600,
        },
      },
    },
  },

  // Select component overrides
  MuiSelect: {
    styleOverrides: {
      root: {
        '& .MuiOutlinedInput-input': {
          padding: '12px 14px',
        },
      },
    },
  },

  // Tabs component overrides
  MuiTabs: {
    styleOverrides: {
      root: {
        borderBottom: '1px solid rgba(0, 0, 0, 0.12)',
        minHeight: '48px',
      },
      indicator: {
        height: '4px',
        borderRadius: '4px 4px 0 0',
      },
    },
  },

  // Tab styling
  MuiTab: {
    styleOverrides: {
      root: {
        textTransform: 'uppercase',
        fontWeight: 600,
        fontSize: '0.75rem',
        letterSpacing: '0.0833em',
        minWidth: '120px',
        padding: '12px 16px',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        '&:hover': {
          backgroundColor: 'rgba(0, 0, 0, 0.04)',
        },
        '&.Mui-selected': {
          fontWeight: 700,
        },
      },
    },
  },

  // Chip component overrides
  MuiChip: {
    styleOverrides: {
      root: {
        borderRadius: '16px',
        fontWeight: 600,
        fontSize: '0.75rem',
        padding: '4px 12px',
      },
      filled: {
        backgroundColor: 'rgba(0, 0, 0, 0.08)',
      },
      outlined: {
        border: '1px solid rgba(0, 0, 0, 0.23)',
      },
    },
  },

  // TableHead styling
  MuiTableHead: {
    styleOverrides: {
      root: {
        backgroundColor: 'rgba(0, 0, 0, 0.04)',
        '& .MuiTableCell-head': {
          fontWeight: 600,
          fontSize: '0.875rem',
          backgroundColor: 'rgba(0, 0, 0, 0.04)',
          borderBottom: '2px solid rgba(0, 0, 0, 0.12)',
        },
      },
    },
  },

  // TableCell styling
  MuiTableCell: {
    styleOverrides: {
      root: {
        borderBottom: '1px solid rgba(0, 0, 0, 0.12)',
        padding: '16px',
      },
      body: {
        fontSize: '0.875rem',
      },
    },
  },

  // TableRow hover effect
  MuiTableBody: {
    styleOverrides: {
      root: {
        '& .MuiTableRow-root:hover': {
          backgroundColor: 'rgba(0, 0, 0, 0.02)',
        },
      },
    },
  },

  // Alert component overrides
  MuiAlert: {
    styleOverrides: {
      root: {
        borderRadius: '4px',
        fontSize: '0.875rem',
        '& .MuiAlertTitle-root': {
          fontWeight: 600,
          marginBottom: '8px',
        },
      },
    },
  },

  // Checkbox styling
  MuiCheckbox: {
    styleOverrides: {
      root: {
        borderRadius: '4px',
        '&.Mui-checked': {
          color: '#1976D2',
        },
      },
    },
  },

  // Radio styling
  MuiRadio: {
    styleOverrides: {
      root: {
        '&.Mui-checked': {
          color: '#1976D2',
        },
      },
    },
  },

  // Switch styling
  MuiSwitch: {
    styleOverrides: {
      root: {
        width: '58px',
        height: '38px',
        padding: '12px',
        '& .MuiButtonBase-root': {
          position: 'absolute',
          padding: '12px',
          top: '-8px',
          left: '-8px',
        },
      },
      switchBase: {
        color: 'rgba(0, 0, 0, 0.26)',
        '&.Mui-checked': {
          color: '#1976D2',
          '& + .MuiSwitch-track': {
            backgroundColor: '#1976D2',
            opacity: 0.5,
          },
        },
      },
      track: {
        backgroundColor: 'rgba(0, 0, 0, 0.26)',
        opacity: 1,
      },
    },
  },

  // Tooltip styling
  MuiTooltip: {
    styleOverrides: {
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.87)',
        color: 'rgba(255, 255, 255, 1)',
        fontSize: '0.75rem',
        padding: '8px 12px',
        borderRadius: '4px',
      },
    },
  },

  // CircularProgress styling
  MuiCircularProgress: {
    styleOverrides: {
      root: {
        color: '#1976D2',
      },
    },
  },

  // LinearProgress styling
  MuiLinearProgress: {
    styleOverrides: {
      root: {
        height: '4px',
        borderRadius: '2px',
      },
      bar: {
        borderRadius: '2px',
      },
    },
  },

  // Backdrop styling (for modals)
  MuiBackdrop: {
    styleOverrides: {
      root: {
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
      },
    },
  },

  // Paper component styling
  MuiPaper: {
    styleOverrides: {
      root: {
        backgroundImage: 'none',
      },
      elevation0: {
        boxShadow: 'none',
      },
      elevation1: {
        boxShadow:
          '0px 2px 1px -1px rgba(0,0,0,0.2),0px 1px 1px 0px rgba(0,0,0,0.14),0px 1px 3px 0px rgba(0,0,0,0.12)',
      },
      elevation2: {
        boxShadow:
          '0px 3px 1px -2px rgba(0,0,0,0.2),0px 2px 2px 0px rgba(0,0,0,0.14),0px 1px 5px 0px rgba(0,0,0,0.12)',
      },
      elevation4: {
        boxShadow:
          '0px 2px 4px -1px rgba(0,0,0,0.2),0px 4px 5px 0px rgba(0,0,0,0.14),0px 1px 10px 0px rgba(0,0,0,0.12)',
      },
    },
  },

  // AppBar styling
  MuiAppBar: {
    styleOverrides: {
      root: {
        backgroundColor: '#1976D2',
        color: '#FFFFFF',
        boxShadow:
          '0px 2px 4px -1px rgba(0,0,0,0.2),0px 4px 5px 0px rgba(0,0,0,0.14),0px 1px 10px 0px rgba(0,0,0,0.12)',
      },
    },
  },

  // Drawer styling
  MuiDrawer: {
    styleOverrides: {
      paper: {
        borderRadius: '0px',
        boxShadow:
          '0px 3px 5px -1px rgba(0,0,0,0.2),0px 5px 8px 0px rgba(0,0,0,0.14),0px 1px 14px 0px rgba(0,0,0,0.12)',
      },
    },
  },

  // FormHelperText styling
  MuiFormHelperText: {
    styleOverrides: {
      root: {
        fontSize: '0.75rem',
        marginTop: '4px',
      },
    },
  },

  // MenuItem styling
  MuiMenuItem: {
    styleOverrides: {
      root: {
        fontSize: '0.875rem',
        padding: '8px 16px',
        minHeight: '40px',
        '&:hover': {
          backgroundColor: 'rgba(0, 0, 0, 0.04)',
        },
        '&.Mui-selected': {
          backgroundColor: 'rgba(25, 118, 210, 0.08)',
          '&:hover': {
            backgroundColor: 'rgba(25, 118, 210, 0.12)',
          },
        },
      },
    },
  },
};
