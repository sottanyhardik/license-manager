/**
 * Hand-off for "open this licence in the Licence List" links (e.g. licence chips in the Mapping workspace).
 *
 * The link navigates to the Licence List with its standard filters; the target (real licence id + licence number) is
 * handed over through sessionStorage because the list rebuilds its own URL from its filter state (router state and
 * unknown query params would be dropped or sent to the API as filters). The list takes the target once.
 */
export type LicenceTarget = { id: number; license_number: string };

/** The Licence List with its standard working filters (owner spec 2026-11-19). */
export const LICENCE_LIST_URL = "/licenses?flags__is_null=False&is_expired=False&page=1&purchase_status=11%2C10%2C1%2C2%2C4%2C5%2C7";

const KEY = "licence-list-open-target";
const MAX_AGE_MS = 5 * 60 * 1000;

export function requestOpenLicence(target: LicenceTarget): void {
    try {
        sessionStorage.setItem(KEY, JSON.stringify({ ...target, at: Date.now() }));
    } catch {
        /* storage unavailable: the list simply opens without a pre-selected licence */
    }
}

/** Read the pending target without clearing it (safe in a React state initialiser, which StrictMode may run twice). */
export function peekLicenceTarget(): LicenceTarget | null {
    try {
        const raw = sessionStorage.getItem(KEY);
        if (!raw) return null;
        const t = JSON.parse(raw) as { id?: unknown; license_number?: unknown; at?: unknown };
        if (typeof t.id !== "number" || !Number.isSafeInteger(t.id) || t.id <= 0 || typeof t.license_number !== "string") return null;
        if (typeof t.at !== "number" || Date.now() - t.at > MAX_AGE_MS) return null;
        return { id: t.id, license_number: t.license_number };
    } catch {
        return null;
    }
}

export function clearLicenceTarget(): void {
    try {
        sessionStorage.removeItem(KEY);
    } catch {
        /* nothing to clear */
    }
}

/** Read and clear the pending target. */
export function takeLicenceTarget(): LicenceTarget | null {
    const target = peekLicenceTarget();
    clearLicenceTarget();
    return target;
}
