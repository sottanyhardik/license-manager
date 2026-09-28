import * as React from "react";
import { TextField as MuiTextField, TextFieldProps as MuiTextFieldProps } from "@mui/material";

interface TextareaProps extends Omit<MuiTextFieldProps, 'variant' | 'multiline'> {
    rows?: number;
}

/**
 * Textarea component wrapper around MUI TextField with multiline
 * Provides consistent textarea styling across the application
 */
const Textarea = React.forwardRef<HTMLDivElement, TextareaProps>(
    ({ className, rows = 4, size = "small", ...props }, ref) => {
        return (
            <MuiTextField
                ref={ref}
                variant="outlined"
                size={size}
                fullWidth={true}
                multiline
                rows={rows}
                className={className}
                data-slot="textarea"
                {...props}
            />
        );
    }
);

Textarea.displayName = 'Textarea';

export { Textarea };
