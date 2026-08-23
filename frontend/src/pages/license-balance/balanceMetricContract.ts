/**
 * Canonical, read-only field contract for the Balance workspace's import-item
 * utilization display.
 *
 * Source: `GET licenses/{id}/` in `LicenseViewSet.retrieve`, serialized by
 * `LicenseImportItemSerializer`. The retrieve action adds the `has_plan` and
 * `*_planned_*` fields only for an active plan. This module intentionally
 * selects fields only: it does not add, subtract, round, or otherwise derive
 * a balance in the browser.
 */

export type BalanceWireNumber = number | string | null | undefined;

/** The additive, documented part of a licence-detail import item response. */
export interface BalanceImportItemWire {
    quantity?: BalanceWireNumber;
    debited_quantity?: BalanceWireNumber;
    allotted_quantity?: BalanceWireNumber;
    planned_quantity?: BalanceWireNumber;
    available_quantity?: BalanceWireNumber;
    remaining_planned_quantity?: BalanceWireNumber;
    cif_fc?: BalanceWireNumber;
    debited_value?: BalanceWireNumber;
    allotted_value?: BalanceWireNumber;
    original_planned_cif_fc?: BalanceWireNumber;
    remaining_planned_cif_fc?: BalanceWireNumber;
    balance_cif_fc?: BalanceWireNumber;
    available_value?: BalanceWireNumber;
    /** Added by the detail retrieve action; false/absent means no active plan. */
    has_plan?: boolean;
}

export interface BalanceQuantityMetricSource {
    totalQuantity: BalanceWireNumber;
    boeDebitedQuantity: BalanceWireNumber;
    allottedQuantity: BalanceWireNumber;
    /** Null means Not planned, which is distinct from a planned quantity of 0. */
    plannedQuantity: BalanceWireNumber;
    actualAvailableQuantity: BalanceWireNumber;
    /** Null means the detail response did not supply an active-plan balance. */
    planRemainingQuantity: BalanceWireNumber;
}

export interface BalanceCifMetricSource {
    totalOpeningCif: BalanceWireNumber;
    boeDebitedCif: BalanceWireNumber;
    allottedCif: BalanceWireNumber;
    /** Null means Not planned, which is distinct from a planned CIF of 0. */
    plannedCif: BalanceWireNumber;
    /** Canonical item-level balance, returned as `balance_cif_fc`. */
    actualBalanceCif: BalanceWireNumber;
    /** Canonical live operational availability, returned as `available_value`. */
    operationalAvailableCif: BalanceWireNumber;
    planRemainingCif: BalanceWireNumber;
}

export interface BalanceItemMetricSource {
    quantity: BalanceQuantityMetricSource;
    cif: BalanceCifMetricSource;
}

/**
 * Select the server-authoritative values for a balance item. There is no
 * arithmetic here because BOE, allotment, and plan dimensions can overlap.
 * `has_plan` guards the server's historical `planned_quantity: 0` fallback,
 * preserving the required distinction between "Not planned" and a real 0.
 */
export function selectBalanceItemMetricSource(item: BalanceImportItemWire): BalanceItemMetricSource {
    const hasActivePlan = item.has_plan === true;

    return {
        quantity: {
            totalQuantity: item.quantity,
            boeDebitedQuantity: item.debited_quantity,
            allottedQuantity: item.allotted_quantity,
            plannedQuantity: hasActivePlan ? item.planned_quantity : null,
            actualAvailableQuantity: item.available_quantity,
            planRemainingQuantity: hasActivePlan ? item.remaining_planned_quantity : null,
        },
        cif: {
            totalOpeningCif: item.cif_fc,
            boeDebitedCif: item.debited_value,
            allottedCif: item.allotted_value,
            plannedCif: hasActivePlan ? item.original_planned_cif_fc : null,
            actualBalanceCif: item.balance_cif_fc,
            operationalAvailableCif: item.available_value,
            planRemainingCif: hasActivePlan ? item.remaining_planned_cif_fc : null,
        },
    };
}

/**
 * UI/source audit table kept adjacent to the mapping so a presentation change
 * cannot silently substitute an inferred field for a canonical one.
 */
export const BALANCE_METRIC_SOURCE_AUDIT = [
    ["Total Quantity", "quantity", "LicenseImportItemSerializer", "item unit", "— when absent", "none"],
    ["BOE Debited Quantity", "debited_quantity", "LicenseImportItemSerializer", "item unit", "— when absent", "may overlap with allotment in domain"],
    ["Allotted Quantity", "allotted_quantity", "LicenseImportItemSerializer", "item unit", "— when absent", "may overlap with BOE in domain"],
    ["Planned Quantity", "planned_quantity + has_plan", "plan_reporting.plan_map_for_import_items", "item unit", "Not planned without active plan", "not an actual debit"],
    ["Actual Available Quantity", "available_quantity", "stored canonical balance field", "item unit", "— when absent", "do not subtract plan in UI"],
    ["Plan Remaining Quantity", "remaining_planned_quantity + has_plan", "plan_enforcement.plan_status_for", "item unit", "— without active plan", "separate planning dimension"],
    ["Total/Opening CIF", "cif_fc", "LicenseImportItemSerializer", "FC", "— when absent", "none"],
    ["BOE Debited CIF", "debited_value", "LicenseImportItemSerializer", "FC", "— when absent", "may overlap with allotment in domain"],
    ["Allotted CIF", "allotted_value", "LicenseImportItemSerializer", "FC", "— when absent", "may overlap with BOE in domain"],
    ["Planned CIF", "original_planned_cif_fc + has_plan", "plan_enforcement.plan_status_for", "FC", "Not planned without active plan", "not an actual debit"],
    ["Actual Balance CIF", "balance_cif_fc", "available_value_calculated", "FC", "— when absent", "canonical item-level balance"],
    ["Operational Available CIF", "available_value", "condition_pool.available_value_bulk_map", "FC", "— when absent", "canonical live availability"],
    ["Plan Remaining CIF", "remaining_planned_cif_fc + has_plan", "plan_enforcement.plan_status_for", "FC", "— without active plan", "separate planning dimension"],
] as const;
