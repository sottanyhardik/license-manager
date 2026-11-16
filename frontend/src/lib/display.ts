/** Shows a received value verbatim; only null/undefined/"" become an em dash. Booleans read Yes/No. */
export function displayValue(value: unknown): string {
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    return String(value);
}

/** Token overrides so the light-only `outline` Button variant respects dark mode. */
export const OUTLINE_TOKENS = "border-border bg-card text-foreground hover:bg-muted hover:border-border";
