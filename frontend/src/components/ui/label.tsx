import * as React from "react";
import { FormLabel as MuiFormLabel, FormLabelProps as MuiFormLabelProps } from "@mui/material";

interface LabelProps extends MuiFormLabelProps {
    required?: boolean;
}

/**
 * Label component wrapper around MUI FormLabel
 * Provides consistent label styling across the application
 */
const Label = React.forwardRef<HTMLLabelElement, LabelProps>(
    ({ className, required, children, ...props }, ref) => {
        return (
            <MuiFormLabel
                ref={ref}
                component="label"
                className={className}
                data-slot="label"
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    fontSize: '0.875rem',
                    fontWeight: 500,
                    marginBottom: '4px',
                    userSelect: 'none',
                    '&.Mui-disabled': {
                        pointerEvents: 'none',
                        opacity: 0.5,
                    }
                }}
                {...props}
            >
                {children}
                {required && <span style={{ color: '#d32f2f' }}>*</span>}
            </MuiFormLabel>
        );
    }
);

Label.displayName = 'Label';

export { Label };
