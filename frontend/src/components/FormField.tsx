/**
 * Reusable form field primitives.
 *
 * Uses MUI TextField, FormControl, and FormHelperText components
 * for Material Design form styling while maintaining accessibility.
 *
 * All fields:
 *  - Link <label> to <input> via htmlFor/id (WCAG 1.3.1)
 *  - Use aria-required and aria-invalid for screen readers
 *  - Show inline error messages tied to the field via aria-describedby
 */
import React, { useId } from "react";
import { AlertCircle } from "lucide-react";
import {
  TextField as MuiTextField,
  FormControl,
  FormHelperText,
  Select as MuiSelect,
  MenuItem,
  Box,
} from "@mui/material";
import { getFieldError } from "../utils/formErrors";

// ── Shared types ──────────────────────────────────────────────────────────────

interface BaseFieldProps {
    label: string;
    name: string;
    fieldErrors?: Record<string, unknown>;
    required?: boolean;
    className?: string;
}

// ── FormField (text input) ────────────────────────────────────────────────────

interface FormFieldProps
    extends BaseFieldProps,
        Omit<React.InputHTMLAttributes<HTMLInputElement>, "name" | "required" | "className" | "color"> {
    type?: string;
}

export const FormField = ({
    label,
    name,
    type = "text",
    fieldErrors = {},
    required = false,
    className = "",
    id: idProp,
    placeholder,
    value,
    onChange,
    disabled,
    ...props
}: FormFieldProps) => {
    const generatedId = useId();
    const id = idProp ?? generatedId;
    const errorId = `${id}-error`;
    const error = getFieldError(fieldErrors, name);

    // Filter out HTML input attributes that MUI doesn't support
    const muiProps = Object.fromEntries(
        Object.entries(props).filter(([key]) =>
            ![
                'step', 'min', 'max', 'pattern', 'accept', 'maxLength', 'autoComplete',
                'checked', 'defaultChecked', 'size'
            ].includes(key)
        )
    );

    return (
        <Box className={className}>
            <MuiTextField
                id={id}
                name={name}
                label={label}
                type={type}
                fullWidth
                size="small"
                variant="outlined"
                required={required}
                error={!!error}
                disabled={disabled}
                placeholder={placeholder as string | undefined}
                value={value}
                onChange={onChange as any}
                aria-invalid={!!error}
                aria-required={required}
                aria-describedby={error ? errorId : undefined}
                {...muiProps}
            />
            {error && (
                <FormHelperText id={errorId} error role="alert">
                    {error}
                </FormHelperText>
            )}
        </Box>
    );
};

// ── FormTextArea ──────────────────────────────────────────────────────────────

interface FormTextAreaProps
    extends BaseFieldProps,
        Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "name" | "required" | "className" | "color"> {
    rows?: number;
}

export const FormTextArea = ({
    label,
    name,
    fieldErrors = {},
    required = false,
    rows = 3,
    className = "",
    id: idProp,
    placeholder,
    value,
    onChange,
    disabled,
    ...props
}: FormTextAreaProps) => {
    const generatedId = useId();
    const id = idProp ?? generatedId;
    const errorId = `${id}-error`;
    const error = getFieldError(fieldErrors, name);

    // Filter out HTML textarea attributes that MUI doesn't support
    const muiProps = Object.fromEntries(
        Object.entries(props).filter(([key]) =>
            ![
                'step', 'min', 'max', 'pattern', 'accept', 'maxLength', 'autoComplete',
                'size', 'cols', 'wrap'
            ].includes(key)
        )
    );

    return (
        <Box className={className}>
            <MuiTextField
                id={id}
                name={name}
                label={label}
                fullWidth
                size="small"
                variant="outlined"
                multiline
                rows={rows as number}
                required={required}
                error={!!error}
                disabled={disabled}
                placeholder={placeholder as string | undefined}
                value={value}
                onChange={onChange as any}
                aria-invalid={!!error}
                aria-required={required}
                aria-describedby={error ? errorId : undefined}
                {...muiProps}
            />
            {error && (
                <FormHelperText id={errorId} error role="alert">
                    {error}
                </FormHelperText>
            )}
        </Box>
    );
};

// ── FormSelect ────────────────────────────────────────────────────────────────

interface SelectOption { value: string | number; label: string }

interface FormSelectProps
    extends BaseFieldProps,
        Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "name" | "required" | "className" | "color"> {
    options?: SelectOption[];
}

export const FormSelect = ({
    label,
    name,
    options = [],
    fieldErrors = {},
    required = false,
    className = "",
    id: idProp,
    value,
    onChange,
    disabled,
    ...props
}: FormSelectProps) => {
    const generatedId = useId();
    const id = idProp ?? generatedId;
    const errorId = `${id}-error`;
    const error = getFieldError(fieldErrors, name);

    // Filter out HTML select attributes that MUI doesn't support
    const muiProps = Object.fromEntries(
        Object.entries(props).filter(([key]) =>
            ![
                'step', 'min', 'max', 'pattern', 'accept', 'maxLength', 'autoComplete',
                'size', 'multiple'
            ].includes(key)
        )
    );

    return (
        <Box className={className}>
            <FormControl fullWidth size="small" error={!!error} required={required}>
                <MuiSelect
                    id={id}
                    name={name}
                    label={label}
                    disabled={disabled}
                    value={value}
                    onChange={onChange as any}
                    aria-invalid={!!error}
                    aria-required={required}
                    aria-describedby={error ? errorId : undefined}
                    {...muiProps}
                >
                    {options.map((opt, idx) => (
                        <MenuItem key={idx} value={opt.value}>
                            {opt.label}
                        </MenuItem>
                    ))}
                </MuiSelect>
                {error && (
                    <FormHelperText id={errorId} role="alert">
                        {error}
                    </FormHelperText>
                )}
            </FormControl>
        </Box>
    );
};

// ── NonFieldErrors ────────────────────────────────────────────────────────────

export const NonFieldErrors = ({
    errors = [],
    formatFunction,
}: {
    errors?: string[];
    formatFunction?: (errors: string[]) => string;
}) => {
    if (!errors || errors.length === 0) return null;
    const formattedErrors = formatFunction ? formatFunction(errors) : errors.join(" | ");

    return (
        <Box
            sx={{
                mb: 2,
                display: "flex",
                alignItems: "flex-start",
                gap: 1,
                padding: "8px 12px",
                borderRadius: "4px",
                border: "1px solid #f44336",
                backgroundColor: "rgba(244, 67, 54, 0.1)",
                color: "#f44336",
                fontSize: "0.875rem",
            }}
            role="alert"
        >
            <AlertCircle
                style={{
                    marginTop: "2px",
                    width: 16,
                    height: 16,
                    flexShrink: 0,
                    display: "flex",
                }}
                aria-hidden="true"
            />
            <div>
                <strong style={{ fontWeight: 600 }}>Error: </strong>
                <span style={{ fontWeight: 500 }}>{formattedErrors}</span>
            </div>
        </Box>
    );
};

export default FormField;
