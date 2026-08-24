import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PlanningEditor from "./PlanningEditor";
import { autoPlanLicense, type AutoPlanResponse } from "../../services/api/planningRuleApi";

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
        split_percentage: "40.00",
        percentage_theoretical_quantity: "256911.188",
        percentage_theoretical_cif: "462440.14",
        remaining_entitlement_qty: "256911.188",
        effective_planned_cif: "462440.14",
        effective_unit_price: "1.80",
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
        split_percentage: "60.00",
        percentage_theoretical_quantity: "385366.782",
        percentage_theoretical_cif: "1610678.05",
        remaining_entitlement_qty: "307368.942",
        effective_planned_cif: "1284678.47",
        effective_unit_price: "4.179597527",
    }]),
    bulkUpsertItemPlans: vi.fn(),
    deleteItemPlan: vi.fn(),
}));

vi.mock("../../services/api/planningRuleApi", () => ({
    autoPlanLicense: vi.fn(),
    planLicense: vi.fn(),
}));

describe("PlanningEditor reconciliation", () => {
    it("shows only approved percentage-split business fields", async () => {
        render(<PlanningEditor licenseId={1} licenseNumber="LEVEL2" canWrite />);

        expect(await screen.findByText("PALM KERNEL OIL - E126")).toBeInTheDocument();
        expect(screen.getByText("OLIVE OIL - E126")).toBeInTheDocument();
        expect(screen.getByText("PARTIALLY UTILIZED")).toBeInTheDocument();
        expect(screen.getAllByText("Percentage Target Qty")).toHaveLength(2);
        expect(screen.getAllByText("Percentage Target CIF")).toHaveLength(2);
        expect(screen.getAllByText("BOE Used Qty")).toHaveLength(1);
        expect(screen.getAllByText("BOE Used CIF")).toHaveLength(1);
        expect(screen.getAllByText("Unlinked Allotment Qty")).toHaveLength(1);
        expect(screen.getAllByText("Unlinked Allotment CIF")).toHaveLength(1);
        expect(screen.getAllByText("Remaining Qty")).toHaveLength(2);
        expect(screen.getAllByText("Unit Price")).toHaveLength(3); // plus table header
        expect(screen.getAllByText("Remaining CIF")).toHaveLength(2);
        expect(screen.getByText("385,366.782")).toBeInTheDocument();
        expect(screen.getByText("$1,610,678.05")).toBeInTheDocument();
        expect(screen.getByText("307,368.942")).toBeInTheDocument();
        expect(screen.getByText("$1,284,678.47")).toBeInTheDocument();
        for (const hidden of [
            "Candidate Planned CIF", "CIF Cap Adjustment", "Effective Planned CIF",
            "Unfilled Target Qty", "Unfilled Target CIF", "Excess Qty", "Excess CIF",
        ]) expect(screen.queryByText(hidden)).not.toBeInTheDocument();

        const parentRow = screen.getByText("Fats and oils").closest("tr");
        expect(parentRow).not.toBeNull();
        const parent = within(parentRow!);
        // The parent reconciliation shows total eligible, live available and
        // effective available quantity.  With no quantity cap all three are
        // intentionally equal; asserting all three prevents a duplicate or a
        // missing live-balance field from being hidden by the coincidence.
        expect(parent.getAllByText("642,277.000")).toHaveLength(3);
        expect(parent.getByText("$1,747,118.61")).toBeInTheDocument();
        expect(parent.getByText("77,997.840")).toBeInTheDocument();
        expect(parent.queryByText("Over Planned")).not.toBeInTheDocument();
        expect(parent.getByText("Planned")).toBeInTheDocument();

    });

    it("keeps Auto Plan disabled until the synchronous forced request completes", async () => {
        let resolvePlan!: (value: AutoPlanResponse) => void;
        vi.mocked(autoPlanLicense).mockReturnValueOnce(new Promise((resolve) => {
            resolvePlan = resolve;
        }) as ReturnType<typeof autoPlanLicense>);

        render(<PlanningEditor licenseId={430} licenseNumber="SYNC" canWrite />);
        const button = await screen.findByRole("button", { name: "Auto Plan" });
        fireEvent.click(button);

        expect(autoPlanLicense).toHaveBeenCalledTimes(1);
        expect(autoPlanLicense).toHaveBeenCalledWith(430);
        expect(button).toBeDisabled();
        expect(screen.getByRole("button", { name: "Planning…" })).toBeDisabled();

        // A second click during the in-flight transaction is ignored.
        fireEvent.click(button);
        expect(autoPlanLicense).toHaveBeenCalledTimes(1);

        resolvePlan({
            license_id: 430,
            license_number: "SYNC",
            planning_state: "CURRENT",
            message: "Auto Plan completed.",
            result: {},
        });
        expect(await screen.findByRole("button", { name: "Auto Plan" })).toBeEnabled();
    });

    it("recovers the Auto Plan action after a synchronous failure", async () => {
        vi.mocked(autoPlanLicense).mockRejectedValueOnce({
            response: { data: { detail: "Planning transaction failed" } },
        });
        render(<PlanningEditor licenseId={431} licenseNumber="SYNC-ERROR" canWrite />);

        const button = await screen.findByRole("button", { name: "Auto Plan" });
        fireEvent.click(button);

        expect(await screen.findByRole("button", { name: "Auto Plan" })).toBeEnabled();
        expect(autoPlanLicense).toHaveBeenCalledWith(431);
    });
});
