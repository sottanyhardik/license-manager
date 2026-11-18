/** First readable message from a DRF error body (`detail`, `error`, `non_field_errors`, a list, or a field error). */
export function apiErrorMessage(err: unknown, fallback: string): string {
    const body = (err as { response?: { data?: unknown } })?.response?.data;
    const first = (value: unknown): string | undefined => {
        if (typeof value === "string" && value) return value;
        if (Array.isArray(value)) return value.map(first).find(Boolean);
        if (value && typeof value === "object") {
            const record = value as Record<string, unknown>;
            return first(record.detail) ?? first(record.error) ?? first(record.non_field_errors) ?? Object.values(record).map(first).find(Boolean);
        }
        return undefined;
    };
    return first(body) ?? fallback;
}
