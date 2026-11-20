/** Decimal strings from the backend → display. null/undefined is "missing" ("—"); "0" is a real zero ("0.00"). */
export function formatDecimal(value: string | number | null | undefined): string {
    if (value === null || value === undefined || value === "") return "—";
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    return n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export const isNotAttributed = (itemName: string) => /not\s+attributed/i.test(itemName);
