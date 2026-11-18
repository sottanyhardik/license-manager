import api from "@/api/axios";
import { openAuthedFile } from "@/utils/documentDownload";

/** Decimal values arrive as strings and are never re-computed on the client. */
export type Money = string;

export type EntitlementOpeningRow = {
    group: string; group_label: string; entitlement: string; label: string; products: string[];
    percentage: string; valuation: "RATE" | "RESIDUAL"; quantity: Money; max_unit_price: Money;
    unit_price: Money | null; planned_cif: Money; cif_available: Money;
};
export type EntitlementGroupRow = {
    group: string; label: string; quantity: Money; source_records: number; split_quantity: Money; reconciles: boolean;
    split: { entitlement: string; label: string; percentage: string }[];
};
export type DebitRow = { kind: "BOE" | "ALLOTMENT"; reference: string; quantity: Money; cif: Money; rate: Money | null; [key: string]: unknown };
export type QtyRateCif = { quantity: Money; rate: Money | null; cif: Money };
export type EntitlementAfterRow = {
    group: string; group_label: string; entitlement: string; label: string; products: string[];
    valuation: "RATE" | "RESIDUAL"; percentage: string; opening: QtyRateCif;
    boe_debited: QtyRateCif & { rows: DebitRow[] }; allotted: QtyRateCif & { rows: DebitRow[] };
    components: { code: string; cif: Money }[]; balance: QtyRateCif;
};
export type EntitlementIssue = { code: string; blocking: boolean; group: string | null; entitlement: string | null; message: string; reference?: string };
export type EntitlementPlan = {
    licence_id: number; licence_number: string; sion: string; read_only: true; can_confirm: boolean;
    opening: { total_cif: Money; total_quantity: Money; rows: EntitlementOpeningRow[]; groups: EntitlementGroupRow[]; total_planned_cif: Money; unplanned_cif: Money };
    after: { entitlements: EntitlementAfterRow[]; total_balance_cif: Money; remaining_licence_cif: Money };
    totals: { boe_debit_quantity: Money; boe_debit_cif: Money; allotment_quantity: Money; allotment_cif: Money };
    reconciliation: { status: "RECONCILED" | "ATTENTION"; authority_difference: Money; computed_remaining_cif: Money; authoritative_remaining_cif: Money; adjustments: { code: string; cif: Money; references: string[] }[] };
    issues: EntitlementIssue[];
    group_config: { group: string; label: string; split_action?: string | null; source_rule?: string | null; products: { name: string; entitlement: string }[] }[];
};

const PATH = "entitlement-plan/";

export async function fetchEntitlementPlan(licenseNumber: string, sion: string): Promise<EntitlementPlan> {
    return (await api.get(PATH, { params: { license_number: licenseNumber, sion } })).data;
}

export function downloadEntitlementPlanXlsx(licenseNumber: string, sion: string): Promise<void> {
    return openAuthedFile(`/${PATH}`, `planning_${licenseNumber}_${sion}.xlsx`, { license_number: licenseNumber, sion, export: "xlsx" });
}
