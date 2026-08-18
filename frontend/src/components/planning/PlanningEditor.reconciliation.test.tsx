import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PlanningEditor from "./PlanningEditor";

vi.mock("../../services/api/licenseApi", () => ({
    fetchLicense: vi.fn().mockResolvedValue({
        balance_cif: "2772554.16",
        total_cif: "2772554.16",
        export_license: [{ cif_fc: "2772554.16" }],
        plan_utilization: [{
            group_id: 10,
            description: "Fats and oils",
            serials: [1],
            member_ids: [10],
            item_names: [{ id: 126, name: "PALM KERNEL OIL - E126" }],
            available_quantity: "642277",
            // Quantity remains operationally available; CIF exhaustion alone
            // must still make the planner complete.
            effective_available_quantity: "642277.000",
            license_balance_cif: "499.99",
            effective_license_balance_cif: "0.00",
            total_quantity: "642277",
            balance_cif_fc: "2183743.40",
            has_plan: true,
            original_quantity: "321138",
            used_quantity: "25000",
            remaining_quantity: "296138",
            original_cif_fc: "578048.40",
            used_cif_fc: "50000",
            remaining_cif_fc: "528048.40",
            status: "FEASIBLE",
        }],
    }),
    fetchItemPlans: vi.fn().mockResolvedValue([{
        id: 99,
        import_item: 10,
        item_name: 126,
        planning_item_name: "PALM KERNEL OIL - E126",
        planned_quantity: "321138.000",
        unit_price: "1.80",
        planned_cif_fc: "578048.40",
        boe_used_quantity: "0.000",
        boe_used_cif: "0.00",
        unlinked_allotment_quantity: "0.000",
        unlinked_allotment_cif: "0.00",
        effective_used_quantity: "0.000",
        effective_used_cif: "0.00",
        reconciled_planned_quantity: "321138.000",
        reconciled_planned_cif: "578048.40",
        remaining_quantity: "321138.000",
        remaining_cif: "578048.40",
        excess_quantity: "0.000",
        excess_cif: "0.00",
        reconciliation_status: "NOT_USED",
    }, {
        id: 100,
        import_item: 10,
        item_name: 127,
        planning_item_name: "OLIVE OIL - E126",
        planned_quantity: "321139.000",
        unit_price: "5.00",
        planned_cif_fc: "1605695.00",
        boe_used_quantity: "51286.840",
        boe_used_cif: "284982.98",
        unlinked_allotment_quantity: "26711.000",
        unlinked_allotment_cif: "130033.87",
        effective_used_quantity: "77997.840",
        effective_used_cif: "415016.85",
        reconciled_planned_quantity: "321139.000",
        reconciled_planned_cif: "1605695.00",
        remaining_quantity: "243141.160",
        remaining_cif: "1190678.15",
        excess_quantity: "0.000",
        excess_cif: "0.00",
        reconciliation_status: "PARTIALLY_UTILIZED",
    }]),
    bulkUpsertItemPlans: vi.fn(),
    deleteItemPlan: vi.fn(),
}));

vi.mock("../../services/api/planningRuleApi", () => ({
    autoPlanLicense: vi.fn(),
    planLicense: vi.fn(),
}));

describe("PlanningEditor reconciliation", () => {
    it("shows theoretical, BOE, unlinked-allotment, remaining, and excess values per item", async () => {
        render(<PlanningEditor licenseId={1} licenseNumber="LEVEL2" canWrite />);

        expect(await screen.findByText("PALM KERNEL OIL - E126")).toBeInTheDocument();
        expect(screen.getByText("OLIVE OIL - E126")).toBeInTheDocument();
        expect(screen.getByText("PARTIALLY UTILIZED")).toBeInTheDocument();
        for (const label of [
            "Theoretical Qty", "Theoretical CIF", "BOE Used Qty", "BOE Used CIF",
            "Unlinked Allotment Qty", "Unlinked Allotment CIF", "Remaining Qty",
            "Remaining CIF", "Excess Qty", "Excess CIF",
        ]) expect(screen.getAllByText(label)).toHaveLength(2);
        expect(screen.getAllByText("243,141.160").length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText("$1,190,678.15").length).toBeGreaterThanOrEqual(1);

        const parentRow = screen.getByText("Fats and oils").closest("tr");
        expect(parentRow).not.toBeNull();
        const parent = within(parentRow!);
        expect(parent.getAllByText("642,277.000")).toHaveLength(2);
        expect(parent.getByText("$2,183,743.40")).toBeInTheDocument();
        expect(parent.getByText("77,997.840")).toBeInTheDocument();
        expect(parent.queryByText("Over Planned")).not.toBeInTheDocument();
        expect(parent.getByText("Planned")).toBeInTheDocument();

        expect(screen.getAllByText("Reconciled Planned CIF")).toHaveLength(3);
        expect(screen.getAllByText("$2,183,743.40").length).toBeGreaterThanOrEqual(2);
    });
});
