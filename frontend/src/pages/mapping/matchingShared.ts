/** Shared helper for the Mapping workspace. */

/** Server message from an API error (``detail`` or the first field error), else the fallback. */
export function errorText(err: unknown, fallback: string): string {
    const data = (err as { response?: { data?: unknown } })?.response?.data;
    if (data && typeof data === "object") {
        const record = data as Record<string, unknown>;
        if (typeof record.detail === "string") return record.detail;
        const first = Object.values(record).find((v) => typeof v === "string");
        if (typeof first === "string") return first;
    }
    return fallback;
}
