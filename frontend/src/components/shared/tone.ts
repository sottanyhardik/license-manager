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
        soft: "border-transparent bg-success/10 text-success",
        solid: "border-transparent bg-success text-white",
        outline: "border-success/40 bg-transparent text-success",
        dot: "bg-success",
    },
    warning: {
        soft: "border-transparent bg-warning/10 text-warning",
        solid: "border-transparent bg-warning text-white",
        outline: "border-warning/40 bg-transparent text-warning",
        dot: "bg-warning",
    },
    danger: {
        soft: "border-transparent bg-destructive/10 text-destructive",
        solid: "border-transparent bg-destructive text-white",
        outline: "border-destructive/40 bg-transparent text-destructive",
        dot: "bg-destructive",
    },
    info: {
        soft: "border-transparent bg-info/10 text-info",
        solid: "border-transparent bg-info text-white",
        outline: "border-info/40 bg-transparent text-info",
        dot: "bg-info",
    },
    neutral: {
        soft: "border-transparent bg-muted text-muted-foreground",
        solid: "border-transparent bg-foreground text-background",
        outline: "border-border bg-transparent text-muted-foreground",
        dot: "bg-muted-foreground",
    },
};
