import { describe, expect, it } from "vitest";

import { BALANCE_METRIC_SOURCE_AUDIT, selectBalanceItemMetricSource } from "./balanceMetricContract";

describe("Balance item metric source contract", () => {
    it("selects each canonical source field without combining BOE, allotment, or plan values", () => {
        const source = {
            quantity: "1000.000",
            debited_quantity: "125.125",
            allotted_quantity: "75.250",
            planned_quantity: "300.500",
            available_quantity: "800.625",
            remaining_planned_quantity: "225.375",
            cif_fc: "104205.70",
            debited_value: "13000.11",
            allotted_value: "9000.22",
            original_planned_cif_fc: "45000.33",
            remaining_planned_cif_fc: "12000.44",
            balance_cif_fc: "82105.37",
            available_value: "82000.12",
            has_plan: true,
        };

        expect(selectBalanceItemMetricSource(source)).toEqual({
            quantity: {
                totalQuantity: "1000.000",
                boeDebitedQuantity: "125.125",
                allottedQuantity: "75.250",
                plannedQuantity: "300.500",
                actualAvailableQuantity: "800.625",
                planRemainingQuantity: "225.375",
            },
            cif: {
                totalOpeningCif: "104205.70",
                boeDebitedCif: "13000.11",
                allottedCif: "9000.22",
                plannedCif: "45000.33",
                actualBalanceCif: "82105.37",
                operationalAvailableCif: "82000.12",
                planRemainingCif: "12000.44",
            },
        });
    });

    it("keeps a missing plan unavailable instead of turning the serializer's zero fallback into a planned value", () => {
        const metrics = selectBalanceItemMetricSource({
            planned_quantity: 0,
            original_planned_cif_fc: 0,
            remaining_planned_quantity: 0,
            remaining_planned_cif_fc: 0,
            has_plan: false,
        });

        expect(metrics.quantity.plannedQuantity).toBeNull();
        expect(metrics.quantity.planRemainingQuantity).toBeNull();
        expect(metrics.cif.plannedCif).toBeNull();
        expect(metrics.cif.planRemainingCif).toBeNull();
    });

    it("preserves explicit zero values for an active plan and never changes decimal precision", () => {
        const metrics = selectBalanceItemMetricSource({
            planned_quantity: "0.000",
            original_planned_cif_fc: "0.00",
            remaining_planned_quantity: "0.000",
            remaining_planned_cif_fc: "0.00",
            available_quantity: "0.000",
            available_value: "0.00",
            has_plan: true,
        });

        expect(metrics.quantity).toMatchObject({
            plannedQuantity: "0.000",
            planRemainingQuantity: "0.000",
            actualAvailableQuantity: "0.000",
        });
        expect(metrics.cif).toMatchObject({
            plannedCif: "0.00",
            planRemainingCif: "0.00",
            operationalAvailableCif: "0.00",
        });
    });

    it("keeps unknown values unavailable and documents every quantity and CIF metric", () => {
        const metrics = selectBalanceItemMetricSource({ has_plan: true });
        expect(metrics.quantity.totalQuantity).toBeUndefined();
        expect(metrics.quantity.planRemainingQuantity).toBeUndefined();
        expect(metrics.cif.actualBalanceCif).toBeUndefined();
        expect(BALANCE_METRIC_SOURCE_AUDIT).toHaveLength(13);
        expect(BALANCE_METRIC_SOURCE_AUDIT.map(([label]) => label)).toEqual(expect.arrayContaining([
            "Total Quantity",
            "Actual Available Quantity",
            "Plan Remaining Quantity",
            "Total/Opening CIF",
            "Operational Available CIF",
            "Plan Remaining CIF",
        ]));
    });
});
