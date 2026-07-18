/**
 * Reusable form field primitives.
 *
 * Uses shadcn Input/Textarea + Label components instead of the old TW_INPUT
 * hardcoded string, ensuring all updates to shadcn components propagate here
 * automatically and eliminating the duplicate class string.
 *
 * All fields:
 *  - Link <label> to <input> via htmlFor/id (WCAG 1.3.1)
 *  - Use aria-required and aria-invalid for screen readers
 *  - Show inline error messages tied to the field via aria-describedby
 */
import React, { useId } from "react";
import { TriangleAlert } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
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
        Omit<React.InputHTMLAttributes<HTMLInputElement>, "name" | "required" | "className"> {
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
    ...props
}: FormFieldProps) => {
    const generatedId = useId();
    const id = idProp ?? generatedId;
    const errorId = `${id}-error`;
    const error = getFieldError(fieldErrors, name);

    return (
        <div className={className}>
            <Label htmlFor={id} className={cn("mb-1.5", required && "required")}>
                {label}
            </Label>
            <Input
                id={id}
                type={type}
                name={name}
                aria-invalid={!!error}
                aria-required={required}
                aria-describedby={error ? errorId : undefined}
                {...props}
            />
            {error && (
                <p id={errorId} className="mt-0.5 text-[11.5px] text-destructive" role="alert">
                    {error}
                </p>
            )}
        </div>
    );
};

// ── FormTextArea ──────────────────────────────────────────────────────────────

interface FormTextAreaProps
    extends BaseFieldProps,
        Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "name" | "required" | "className"> {
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
    ...props
}: FormTextAreaProps) => {
    const generatedId = useId();
    const id = idProp ?? generatedId;
    const errorId = `${id}-error`;
    const error = getFieldError(fieldErrors, name);

    return (
        <div className={className}>
            <Label htmlFor={id} className={cn("mb-1.5", required && "required")}>
                {label}
            </Label>
            <Textarea
                id={id}
                name={name}
                rows={rows}
                aria-invalid={!!error}
                aria-required={required}
                aria-describedby={error ? errorId : undefined}
                {...props}
            />
            {error && (
                <p id={errorId} className="mt-0.5 text-[11.5px] text-destructive" role="alert">
                    {error}
                </p>
            )}
        </div>
    );
};

// ── FormSelect ────────────────────────────────────────────────────────────────

interface SelectOption { value: string | number; label: string }

interface FormSelectProps
    extends BaseFieldProps,
        Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "name" | "required" | "className"> {
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
    ...props
}: FormSelectProps) => {
    const generatedId = useId();
    const id = idProp ?? generatedId;
    const errorId = `${id}-error`;
    const error = getFieldError(fieldErrors, name);

    return (
        <div className={className}>
            <Label htmlFor={id} className={cn("mb-1.5", required && "required")}>
                {label}
            </Label>
            <select
                id={id}
                name={name}
                aria-invalid={!!error}
                aria-required={required}
                aria-describedby={error ? errorId : undefined}
                className="flex h-9 w-full cursor-pointer rounded-md border border-input bg-card px-3 py-1 text-sm outline-none transition-[color,box-shadow] focus-visible:border-ring aria-invalid:border-destructive disabled:cursor-not-allowed disabled:opacity-50"
                {...props}
            >
                {options.map((opt, idx) => (
                    <option key={idx} value={opt.value}>
                        {opt.label}
                    </option>
                ))}
            </select>
            {error && (
                <p id={errorId} className="mt-0.5 text-[11.5px] text-destructive" role="alert">
                    {error}
                </p>
            )}
        </div>
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
        <div
            className="mb-3 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive"
            role="alert"
        >
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <div>
                <strong className="font-semibold">Error: </strong>
                <span className="font-medium">{formattedErrors}</span>
            </div>
        </div>
    );
};

export default FormField;
