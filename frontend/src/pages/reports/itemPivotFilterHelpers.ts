export function normalizeMinBalance(value: unknown, fallback = 200): number {
    const parsed = Number.parseInt(String(value), 10);
    return Number.isFinite(parsed) ? parsed : fallback;
}

/**
 * License Numbers filter: split on commas (and newlines / semicolons / tabs from a spreadsheet paste), trim,
 * drop empties and de-duplicate keeping the first occurrence. Exact values — mirrors the backend
 * `parse_license_numbers`.
 */
export function parseLicenseNumbers(raw: unknown): string[] {
    const seen = new Set<string>();
    for (const token of String(raw ?? "").split(/[,;\n\r\t]+/)) {
        const value = token.trim();
        if (value) seen.add(value);
    }
    return [...seen];
}
