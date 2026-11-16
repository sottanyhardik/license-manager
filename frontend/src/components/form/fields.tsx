import { useId, type ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

/** Presentational, controlled field primitives. The caller owns value, onChange and error state. */
export interface FieldBaseProps {
    label: string;
    /** Used to build stable a11y ids; defaults to the generated id only. */
    name?: string;
    description?: string;
    /** Validation message; rendered as role="alert" and linked via aria-describedby. */
    error?: string;
    required?: boolean;
    disabled?: boolean;
}

export interface FieldA11y {
    id: string;
    "aria-invalid": true | undefined;
    "aria-describedby": string | undefined;
    "aria-required": true | undefined;
}

interface FieldProps extends FieldBaseProps {
    children: (a11y: FieldA11y) => ReactNode;
    /** Control first, label after (checkboxes). */
    inline?: boolean;
}

/** Label + control + description + error, wired with ids. */
export function Field({ name, label, description, error, required, inline, children }: FieldProps) {
    const uid = useId();
    const id = name ? `${uid}-${name}` : uid;
    const descId = description ? `${id}-desc` : undefined;
    const errId = error ? `${id}-err` : undefined;
    const describedBy = [descId, errId].filter(Boolean).join(" ") || undefined;

    const control = children({
        id,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": describedBy,
        "aria-required": required ? true : undefined,
    });
    const labelEl = (
        <label htmlFor={id} className="text-sm font-medium text-foreground">
            {label}
            {required && <span aria-hidden="true" className="ml-0.5 text-destructive">*</span>}
        </label>
    );

    return (
        <div className="grid gap-1.5">
            {inline ? <div className="flex items-center gap-2">{control}{labelEl}</div> : <>{labelEl}{control}</>}
            {description && <p id={descId} className="text-xs text-muted-foreground">{description}</p>}
            {error && <p id={errId} role="alert" className="text-xs text-destructive">{error}</p>}
        </div>
    );
}

type ValueProps = { value: string; onChange: (value: string) => void };

export function TextField({ type = "text", placeholder, value, onChange, ...base }: FieldBaseProps & ValueProps & { type?: "text" | "email" | "password" | "tel"; placeholder?: string }) {
    return (
        <Field {...base}>
            {(a) => <Input type={type} placeholder={placeholder} disabled={base.disabled} value={value} onChange={(e) => onChange(e.target.value)} {...a} />}
        </Field>
    );
}

/** Number input. Value stays the raw string (no float conversion); the caller decides parsing. */
export function NumberField({ step, min, max, value, onChange, ...base }: FieldBaseProps & ValueProps & { step?: number | string; min?: number; max?: number }) {
    return (
        <Field {...base}>
            {(a) => <Input type="number" step={step} min={min} max={max} disabled={base.disabled} value={value} onChange={(e) => onChange(e.target.value)} {...a} />}
        </Field>
    );
}

export function DateField({ min, max, value, onChange, ...base }: FieldBaseProps & ValueProps & { min?: string; max?: string }) {
    return (
        <Field {...base}>
            {(a) => <Input type="date" min={min} max={max} disabled={base.disabled} value={value} onChange={(e) => onChange(e.target.value)} {...a} />}
        </Field>
    );
}

export function TextareaField({ rows = 3, value, onChange, ...base }: FieldBaseProps & ValueProps & { rows?: number }) {
    return (
        <Field {...base}>
            {(a) => <Textarea rows={rows} disabled={base.disabled} value={value} onChange={(e) => onChange(e.target.value)} {...a} />}
        </Field>
    );
}

export interface SelectOption { value: string; label: string }

/** Native select with static options (accessible, keyboard-native). */
export function SelectField({ options, placeholder, value, onChange, ...base }: FieldBaseProps & ValueProps & { options: SelectOption[]; placeholder?: string }) {
    return (
        <Field {...base}>
            {(a) => (
                <select
                    disabled={base.disabled}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    className={cn("h-10 w-full rounded-lg border border-input bg-card px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/30 aria-invalid:border-destructive disabled:opacity-50")}
                    {...a}
                >
                    {placeholder !== undefined && <option value="">{placeholder}</option>}
                    {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
            )}
        </Field>
    );
}

export function CheckboxField({ checked, onChange, ...base }: FieldBaseProps & { checked: boolean; onChange: (checked: boolean) => void }) {
    return (
        <Field {...base} inline>
            {(a) => <input type="checkbox" disabled={base.disabled} className="size-4 accent-primary" checked={checked} onChange={(e) => onChange(e.target.checked)} {...a} />}
        </Field>
    );
}
