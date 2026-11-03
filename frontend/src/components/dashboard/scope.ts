/** Global date-range presets. `all` sends no date parameters. */
export const RANGE_PRESETS = [
    { value: "last30", label: "Last 30 days" },
    { value: "last90", label: "Last 90 days" },
    { value: "ytd", label: "Year to date" },
    { value: "all", label: "All time" },
] as const;

export type RangePreset = (typeof RANGE_PRESETS)[number]["value"];

export type DashboardScope = {
    companyId: number | null;
    preset: RangePreset;
};

/** Local calendar date as `YYYY-MM-DD`. Uses the local clock, not UTC. */
export function toIsoDate(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

/**
 * Maps a preset to the API's `date_from` / `date_to`. "Last 30 days" is the
 * 30 calendar days ending today, inclusive.
 */
export function presetToDates(preset: RangePreset, today: Date): { date_from?: string; date_to?: string } {
    if (preset === "all") return {};
    const to = toIsoDate(today);
    if (preset === "ytd") return { date_from: `${today.getFullYear()}-01-01`, date_to: to };
    const days = preset === "last90" ? 89 : 29;
    const from = new Date(today.getFullYear(), today.getMonth(), today.getDate() - days);
    return { date_from: toIsoDate(from), date_to: to };
}
