/**
 * Shared relative-date-range presets for filter panels (`<DateRangeFilter>`
 * and any bespoke From/To filter block that wants the same shortcuts).
 * Every function returns `yyyy-MM-dd` strings — the exact shape a native
 * `<input type="date">` needs, no conversion required by callers.
 */

export interface DateRange {
    from: string;
    to: string;
}

function toIsoDate(date: Date): string {
    return date.toISOString().slice(0, 10);
}

/**
 * Financial year (Apr 1 → Mar 31) containing `date`, or `offset` years
 * before/after it (`offset: -1` = previous FY). Moved here from
 * `LicenseLedger.tsx` (still re-exported there for backward compatibility —
 * `LicenseLedger.test.tsx` imports it from that path) since every other
 * preset builder below lives here too.
 */
export function getFinancialYearRange(date = new Date(), offset = 0): { fyStart: string; fyEnd: string } {
    const currentYear = date.getFullYear();
    const currentMonth = date.getMonth();
    const currentFyStartYear = currentMonth <= 2 ? currentYear - 1 : currentYear;
    const fyStartYear = currentFyStartYear + offset;
    return {
        fyStart: `${fyStartYear}-04-01`,
        fyEnd: `${fyStartYear + 1}-03-31`,
    };
}

export function getCurrentFinancialYearRange(date = new Date()): DateRange {
    const { fyStart, fyEnd } = getFinancialYearRange(date, 0);
    return { from: fyStart, to: fyEnd };
}

export function getPreviousFinancialYearRange(date = new Date()): DateRange {
    const { fyStart, fyEnd } = getFinancialYearRange(date, -1);
    return { from: fyStart, to: fyEnd };
}

export function getTodayRange(date = new Date()): DateRange {
    const today = toIsoDate(date);
    return { from: today, to: today };
}

export function getLastNDaysRange(n: number, date = new Date()): DateRange {
    const to = toIsoDate(date);
    const from = new Date(date);
    from.setDate(from.getDate() - (n - 1));
    return { from: toIsoDate(from), to };
}

export function getThisMonthRange(date = new Date()): DateRange {
    const from = new Date(date.getFullYear(), date.getMonth(), 1);
    const to = new Date(date.getFullYear(), date.getMonth() + 1, 0);
    return { from: toIsoDate(from), to: toIsoDate(to) };
}
