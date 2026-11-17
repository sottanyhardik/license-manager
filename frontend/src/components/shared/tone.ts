/** Single semantic tone vocabulary. Token classes only (no raw palette / hex). */
export type Tone = "primary" | "success" | "warning" | "danger" | "info" | "neutral";

export const TONES: readonly Tone[] = ["primary", "success", "warning", "danger", "info", "neutral"];

export interface ToneClasses {
    soft: string;
    solid: string;
    outline: string;
    dot: string;
}

/** The one tone -> class map. Components never pick colours themselves. */
export const TONE_MAP: Record<Tone, ToneClasses> = {
    primary: {
        soft: "border-transparent bg-primary/10 text-primary",
        solid: "border-transparent bg-primary text-primary-foreground",
        outline: "border-primary/40 bg-transparent text-primary",
        dot: "bg-primary",
    },
    success: {
        soft: "border-transparent bg-success/10 text-[var(--tb-success-text)]",
        solid: "border-transparent bg-success text-white",
        outline: "border-success/40 bg-transparent text-[var(--tb-success-text)]",
        dot: "bg-success",
    },
    warning: {
        soft: "border-transparent bg-warning/10 text-[var(--tb-warning-text)]",
        solid: "border-transparent bg-warning text-black",
        outline: "border-warning/40 bg-transparent text-[var(--tb-warning-text)]",
        dot: "bg-warning",
    },
    danger: {
        soft: "border-transparent bg-destructive/10 text-destructive",
        solid: "border-transparent bg-destructive text-white",
        outline: "border-destructive/40 bg-transparent text-destructive",
        dot: "bg-destructive",
    },
    info: {
        soft: "border-transparent bg-info/10 text-[var(--tb-info-text)]",
        solid: "border-transparent bg-info text-white",
        outline: "border-info/40 bg-transparent text-[var(--tb-info-text)]",
        dot: "bg-info",
    },
    neutral: {
        soft: "border-transparent bg-muted text-muted-foreground",
        solid: "border-transparent bg-foreground text-background",
        outline: "border-border bg-transparent text-muted-foreground",
        dot: "bg-muted-foreground",
    },
};

/**
 * Domain status -> tone (AA-checked: soft tones use the `--tb-*-text` tokens).
 * Licence: Active / Expired / Planned / Exhausted. BOE: Invoiced / Pending / Dispute.
 */
export const STATUS_TONE: Record<string, Tone> = {
    active: "success",
    expired: "danger",
    planned: "info",
    exhausted: "neutral",
    invoiced: "success",
    pending: "warning",
    dispute: "danger",
};

/** Case-insensitive lookup; unknown statuses fall back to neutral. */
export function statusTone(status: string | null | undefined): Tone {
    return STATUS_TONE[String(status ?? "").trim().toLowerCase()] ?? "neutral";
}
