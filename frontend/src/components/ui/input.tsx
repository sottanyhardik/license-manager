import * as React from "react";
import { TextField as MuiTextField, TextFieldProps as MuiTextFieldProps } from "@mui/material";

interface InputProps extends Omit<MuiTextFieldProps, 'variant' | 'size'> {
    type?: string;
    // HTML input attributes that MUI might not directly support
    step?: string | number;
    min?: string | number;
    max?: string | number;
    pattern?: string;
    accept?: string;
    maxLength?: number;
    readOnly?: boolean;
    size?: 'small' | 'medium';
}

/**
 * Input component wrapper around MUI TextField
 * Provides a consistent input field styling across the application
 * Accepts HTML input attributes and maps them to MUI TextField props
 */
const Input = React.forwardRef<HTMLDivElement, InputProps>(
    ({
        className,
        type = "text",
        size = "small",
        step,
        min,
        max,
        pattern,
        accept,
        maxLength,
        readOnly,
        ...props
    }, ref) => {
        // Build inputProps to pass HTML attributes to the underlying input element
        const inputProps: Record<string, any> = {};
        if (step !== undefined) inputProps.step = step;
        if (min !== undefined) inputProps.min = min;
        if (max !== undefined) inputProps.max = max;
        if (pattern !== undefined) inputProps.pattern = pattern;
        if (accept !== undefined) inputProps.accept = accept;
        if (maxLength !== undefined) inputProps.maxLength = maxLength;
        if (readOnly) inputProps.readOnly = readOnly;

        return (
            <MuiTextField
                ref={ref}
                type={type}
                variant="outlined"
                size={size as 'small' | 'medium'}
                fullWidth={true}
                className={className}
                data-slot="input"
                slotProps={{
                    input: {
                        ...inputProps,
                    },
                }}
                {...props}
            />
        );
    }
);

Input.displayName = 'Input';

export { Input };
