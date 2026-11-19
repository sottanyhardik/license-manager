/** Types and display-only formatters shared by the Item Pivot intelligence views. */
import type { Tone } from "@/components/shared";

export type Money = string;
export type Status = "CORRECT" | "UNDERUTILIZED" | "WARNING" | "BLOCKED" | "OVERPLANNED";
export interface IntelLicence {
    license_id: number; license_number: string; sion: string | null; company: string | null; expiry_date: string | null; purchase_status: string | null;
    original_cif: Money; boe_cif: Money; allotment_cif: Money; billed_cif: Money; other_adjustments_cif: Money; available_cif: Money;
    is_over_utilised: boolean; components_reconcile: boolean; planning_stale?: boolean; planned_cif: Money; final_balance_cif: Money; utilisation_percent: string | null; products: string[];
}
export interface IntelProduct {
    key: string; status?: Status | null; licences_available_cif?: Money; licences_remaining_cif?: Money; kind: "MAPPED" | "AMBIGUOUS" | "UNMAPPED" | "MULTI_PRODUCT"; item_name_id: number | null; product: string; sion: string | null; mapping_basis: string;
    hsn_codes: string[]; aliases: string[]; hsn_chapters: string[]; mapping_review: string | null; eligible_licences: number; source_record_count: number;
    source_records: { license_id: number; license_number: string; import_item_id: number; serial_number: number; description: string | null; hsn_code: string | null; item_name_ids?: number[]; sion?: string | null }[];
    entitlement_qty: string; allotted_qty: string; debited_qty: string; billed_qty: string; balance_qty: string; max_unit_price: string | null;
    planned_qty: string; planned_cif: Money; utilisation_percent: string | null; status_counts: Partial<Record<Status, number>>;
}
export interface IntelCell {
    license_id: number; license_number: string; company?: string | null; product_key: string; product: string; kind: string; sion: string | null; status: Status; reasons: string[];
    entitlement_qty: string; debited_qty: string; allotted_qty: string; billed_qty: string; balance_qty: string; planned_qty: string; planned_cif: Money;
    max_unit_price: string | null; licence_available_cif: Money; licence_final_balance_cif: Money; planning_eligible: boolean;
    references: { boes: string[]; allotments: string[] };
}
export interface IntelReport {
    overview: Record<string, unknown> & { consolidation: Record<string, number>; status_counts: Partial<Record<Status, number>>; bases: { licence: string; item: string }; integrity?: Integrity };
    licences: IntelLicence[]; products: IntelProduct[]; eligibility: IntelCell[];
}
export type Recommendation = {
    rank: number; license_id: number; license_number: string; expiry_date: string | null; sion: string; item_name_id?: number | null; product: string | null; rule_priority: number | null;
    unit_price: string; recommended_qty: string; recommended_cif: Money; existing_qty: string; existing_cif: Money; additional_qty: string; additional_cif: Money;
    licence_available_cif: Money; remaining_licence_cif_after: Money; cif_status: string | null; reason: string; alternatives: string[];
};

export const STATUS: Record<Status, { tone: Tone; label: string }> = {
    CORRECT: { tone: "success", label: "Correct" },
    UNDERUTILIZED: { tone: "primary", label: "Underutilized" },
    WARNING: { tone: "warning", label: "Warning" },
    BLOCKED: { tone: "danger", label: "Blocked" },
    OVERPLANNED: { tone: "danger", label: "Overplanned" },
};
export const fmt = (v: string | null | undefined, digits = 2) => {
    if (v == null || v === "") return "—";
    const n = Number(v);
    return Number.isFinite(n) ? n.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: digits }) : String(v);
};
/** Display-only: sign before the currency symbol (−$1,234), value from the backend string. */
export const usd = (v: string | null | undefined) => {
    if (v == null || v === "") return "—";
    const text = String(v).trim();
    return text.startsWith("-") ? `−$${fmt(text.slice(1))}` : `$${fmt(text)}`;
};
export const neg = (v: string | null | undefined) => v != null && v.trim().startsWith("-");
export const TH = "sticky top-0 z-[1] bg-muted px-2.5 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-muted-foreground";
export const TD = "px-2.5 py-1.5 align-top";
export const NUM = "text-right tabular-nums whitespace-nowrap";

export type Selection = { product: string | null; licence: number | null; mode: "entitlement" | "planning" };
export type IntegrityField = "entitlement_qty" | "allotted_qty" | "debited_qty" | "billed_qty" | "balance_qty" | "planned_qty" | "planned_cif";
export interface Integrity {
    source_record_count: number; consolidated_source_record_count: number; consolidated_product_count: number; pending_mapping_count: number;
    source_totals: Record<IntegrityField, string>; consolidated_totals: Record<IntegrityField, string>; preserved: boolean;
}
