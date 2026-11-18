import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import PlanningEditor from "./PlanningEditor";

// Shapes mirror the real API output for licence 3411008089 (E126) after its
// BOEs/allotments were mapped to explicit PKO / OLIVE OIL targets and the
// licence was re-planned.  Every figure is backend-computed; the UI only formats.
vi.mock("../../api/licenseApi", () => ({
    fetchLicense: vi.fn().mockResolvedValue({
        balance_cif: "1715319.19",
        total_cif: "3724889.95",
        export_license: [{ cif_fc: "3724889.95" }],
        plan_utilization: [{
            group_id: 36846,
            description: "RELEVANT FATS AND OILS",
            serials: [1, 5, 9, 17],
            member_ids: [36846, 36849, 36851, 36857],
            item_names: [{ id: 153, name: "OLIVE OIL" }, { id: 159, name: "PALM KERNEL OIL" }],
            available_quantity: "170805.000",
            effective_available_quantity: "170805.000",
            license_balance_cif: "1715319.19",
            effective_license_balance_cif: "1715319.19",
            total_quantity: "851620.260",
            balance_cif_fc: "1715319.19",
            has_plan: true,
            original_quantity: "851620.260",
            used_quantity: "668503.640",
            remaining_quantity: "183116.620",
            original_cif_fc: "2915510.09",
            used_cif_fc: "2009570.76",
            remaining_cif_fc: "902899.41",
            status: "FEASIBLE",
        }],
    }),
    fetchItemPlans: vi.fn().mockResolvedValue([
        {
            id: 36945, import_item: 36846, item_name: 153, planning_item_name: "OLIVE OIL",
            planned_quantity: "169077.490", unit_price: "5.19", planned_cif_fc: "877628.98",
            boe_used_quantity: "256732.640", boe_used_cif: "1271429.14",
            unlinked_allotment_quantity: "0.000", unlinked_allotment_cif: "0.00",
            effective_used_quantity: "256732.640", effective_used_cif: "1271429.14",
            reconciliation_status: "PARTIALLY_UTILIZED", split_percentage: "50.00",
            percentage_theoretical_quantity: "425810.130", percentage_theoretical_cif: "2210248.74",
            remaining_entitlement_qty: "169077.490", effective_planned_cif: "877628.98",
            effective_unit_price: "5.190690848",
        },
        {
            id: 36946, import_item: 36846, item_name: 159, planning_item_name: "PALM KERNEL OIL",
            planned_quantity: "14039.130", unit_price: "1.80", planned_cif_fc: "25270.43",
            boe_used_quantity: "211771.000", boe_used_cif: "378141.62",
            unlinked_allotment_quantity: "200000.000", unlinked_allotment_cif: "360000.00",
            effective_used_quantity: "411771.000", effective_used_cif: "738141.62",
            reconciliation_status: "PARTIALLY_UTILIZED", split_percentage: "50.00",
            percentage_theoretical_quantity: "425810.130", percentage_theoretical_cif: "766458.23",
            remaining_entitlement_qty: "14039.130", effective_planned_cif: "25270.43",
            effective_unit_price: "1.799999715",
        },
    ]),
    bulkUpsertItemPlans: vi.fn(),
    deleteItemPlan: vi.fn(),
}));

vi.mock("../../api/planningRuleApi", () => ({ autoPlanLicense: vi.fn(), planLicense: vi.fn() }));

const renderEditor = () =>
    render(
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
            <PlanningEditor licenseId={2510} licenseNumber="3411008089" canWrite />
        </QueryClientProvider>,
    );

describe("E126 Vegetable Oil entitlement children", () => {
    it("renders exactly two children, PKO and OLIVE OIL, with their own balances", async () => {
        renderEditor();
        expect(await screen.findByText("PALM KERNEL OIL")).toBeInTheDocument();
        expect(screen.getByText("OLIVE OIL")).toBeInTheDocument();
        expect(screen.getAllByText("Percentage Target Qty")).toHaveLength(2);
        expect(screen.getAllByText("425,810.130")).toHaveLength(2);
        expect(screen.getByText("14,039.130")).toBeInTheDocument();
        expect(screen.getByText("169,077.490")).toBeInTheDocument();
        expect(screen.getByText("$25,270.43")).toBeInTheDocument();
        expect(screen.getByText("$877,628.98")).toBeInTheDocument();
    });

    it("shows BOE and outstanding allotment usage per child and never NOT USED", async () => {
        renderEditor();
        await screen.findByText("PALM KERNEL OIL");
        expect(screen.getByText("211,771.000")).toBeInTheDocument();
        expect(screen.getByText("256,732.640")).toBeInTheDocument();
        expect(screen.getByText("200,000.000")).toBeInTheDocument();
        expect(screen.getAllByText("PARTIALLY UTILIZED")).toHaveLength(2);
        expect(screen.queryByText("NOT USED")).not.toBeInTheDocument();
    });
});
