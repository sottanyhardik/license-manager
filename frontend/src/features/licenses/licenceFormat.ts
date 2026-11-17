import type { Tone } from "@/components/shared";

import type { LicenseListItem } from "./types";

/**
 * The register card's CIF formatter (owner decision: used for every CIF value
 * inside the card and its financial summary). Unchanged from the original
 * `"$" + Number(v || 0).toLocaleString("en-US", 2dp)`, so null renders "$0.00"
 * and a negative renders "$-250.75". Display only, never used for arithmetic.
 */
export function formatCifUsd(value: unknown): string {
    return `$${Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** True when a value received from the backend is a negative number (danger styling only). */
export function isNegativeValue(value: unknown): boolean {
    return Number(value) < 0;
}

/** `DD-MM-YYYY` (list endpoint format) to a local Date. */
export function parseIndianDate(s: string | null | undefined): Date | null {
    if (!s) return null;
    const p = s.split("-");
    if (p.length !== 3) return null;
    return new Date(Number(p[2]), Number(p[1]) - 1, Number(p[0]));
}

export function isLicenceExpired(item: Pick<LicenseListItem, "license_expiry_date">): boolean {
    return !!(item.license_expiry_date && parseIndianDate(item.license_expiry_date)! < new Date());
}

export type LicenceStatusLabel = "Expired" | "Exhausted" | "Planned" | "Active";

/**
 * Display status, unchanged from the original `deriveStatus` (escalated as D4 in
 * 06; kept exactly): Expired if expiry < client clock, else Exhausted if
 * `Number(get_balance_cif) <= 0`, else Planned if `is_manually_planned`, else Active.
 * Only the visual tone is new.
 */
export function deriveStatus(item: LicenseListItem): { label: LicenceStatusLabel; tone: Tone } {
    const balance = Number(item.get_balance_cif ?? 0);
    if (isLicenceExpired(item)) return { label: "Expired", tone: "danger" };
    if (balance <= 0) return { label: "Exhausted", tone: "neutral" };
    if (item.is_manually_planned) return { label: "Planned", tone: "info" };
    return { label: "Active", tone: "success" };
}
