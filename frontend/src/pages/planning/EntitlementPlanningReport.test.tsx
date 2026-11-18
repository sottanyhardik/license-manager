import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EntitlementPlanningReport, PlanView } from "./EntitlementPlanningReport";
import * as planApi from "@/api/entitlementPlanApi";
import type { EntitlementPlan } from "@/api/entitlementPlanApi";

vi.mock("@/api/entitlementPlanApi", () => ({ fetchEntitlementPlan: vi.fn(), downloadEntitlementPlanXlsx: vi.fn() }));

const part = (quantity: string, rate: string | null, cif: string) => ({ quantity, rate, cif });
const plan: EntitlementPlan = {
    licence_id: 2510, licence_number: "3411008089", sion: "E126", read_only: true, can_confirm: true,
    opening: {
        total_cif: "3724889.95", total_quantity: "1151390.580", total_planned_cif: "3724889.95", unplanned_cif: "0.00",
        rows: [
            { group: "FOOD_FLAVOUR", group_label: "Food Flavour", entitlement: "FOOD FLAVOUR", label: "Food Flavour", products: [], percentage: "100", valuation: "RATE", quantity: "299770.320", max_unit_price: "2.70", unit_price: "2.7000", planned_cif: "809379.86", cif_available: "2915510.09" },
            { group: "VEGETABLE_OIL", group_label: "Vegetable Oil", entitlement: "PALM KERNEL OIL", label: "PKO", products: [], percentage: "50", valuation: "RATE", quantity: "425810.130", max_unit_price: "1.80", unit_price: "1.8000", planned_cif: "766458.23", cif_available: "2149051.85" },
            { group: "VEGETABLE_OIL", group_label: "Vegetable Oil", entitlement: "OLIVE OIL", label: "Olive Oil + Sunflower Oil", products: [], percentage: "50", valuation: "RESIDUAL", quantity: "425810.130", max_unit_price: "5.50", unit_price: "5.0470", planned_cif: "2149051.85", cif_available: "0.00" },
        ],
        groups: [
            { group: "FOOD_FLAVOUR", label: "Food Flavour", quantity: "299770.320", source_records: 4, split_quantity: "299770.320", reconciles: true, split: [{ entitlement: "FOOD FLAVOUR", label: "Food Flavour", percentage: "100" }] },
            { group: "VEGETABLE_OIL", label: "Vegetable Oil", quantity: "851620.260", source_records: 4, split_quantity: "851620.260", reconciles: true, split: [{ entitlement: "PALM KERNEL OIL", label: "PKO", percentage: "50" }, { entitlement: "OLIVE OIL", label: "Olive Oil + Sunflower Oil", percentage: "50" }] },
        ],
    },
    after: {
        total_balance_cif: "1714276.98", remaining_licence_cif: "1714276.98",
        entitlements: [
            { group: "VEGETABLE_OIL", group_label: "Vegetable Oil", entitlement: "PALM KERNEL OIL", label: "PKO", products: [], valuation: "RATE", percentage: "50",
              opening: part("425810.130", "1.8000", "766458.23"),
              boe_debited: { ...part("211771.000", "1.7856", "378141.62"), rows: [{ kind: "BOE", reference: "3631938", quantity: "211771.000", cif: "378141.62", rate: "1.7856", product: "PALM KERNEL OIL" }] },
              allotted: { ...part("200000.000", "1.8000", "360000.00"), rows: [] },
              components: [{ code: "RELEASED_TO_RESIDUAL", cif: "-3046.18" }], balance: part("14039.130", "1.8000", "25270.43") },
            { group: "VEGETABLE_OIL", group_label: "Vegetable Oil", entitlement: "OLIVE OIL", label: "Olive Oil + Sunflower Oil", products: ["Olive Oil", "Sunflower Oil"], valuation: "RESIDUAL", percentage: "50",
              opening: part("425810.130", "5.0470", "2149051.85"), boe_debited: { ...part("244421.640", "4.9643", "1213378.55"), rows: [] },
              allotted: { ...part("12311.000", "4.8000", "59092.80"), rows: [] },
              components: [{ code: "RECEIVED_FROM_OTHER_ENTITLEMENTS", cif: "3046.18" }], balance: part("169077.490", "5.2025", "879626.68") },
        ],
    },
    totals: { boe_debit_quantity: "456192.640", boe_debit_cif: "1591520.17", allotment_quantity: "212311.000", allotment_cif: "419092.80" },
    reconciliation: { status: "RECONCILED", authority_difference: "0.00", computed_remaining_cif: "1714276.98", authoritative_remaining_cif: "1714276.98", adjustments: [] },
    issues: [], group_config: [],
};

describe("EntitlementPlanningReport", () => {
    beforeEach(() => vi.clearAllMocks());

    it("renders the spreadsheet sections with Indian formatting", () => {
        render(<PlanView plan={plan} />);
        expect(screen.getByText("OPENING PLANNING")).toBeInTheDocument();
        expect(screen.getByText("AFTER BOE DEBITS AND ALLOTTED")).toBeInTheDocument();
        expect(screen.getAllByText("21,49,051.85").length).toBeGreaterThan(0);
        expect(screen.getByText("8,79,626.68", { selector: "td" })).toBeInTheDocument();
        expect(screen.getByText("25,270.43", { selector: "td" })).toBeInTheDocument();
        expect(screen.getByText("Received from other entitlements")).toBeInTheDocument();
        expect(screen.getByRole("img", { name: /PKO 50%, Olive Oil \+ Sunflower Oil 50%/ })).toBeInTheDocument();
        expect(screen.getByText("Reconciled")).toBeInTheDocument();
    });

    it("summary links point to the detailed entitlement rows", () => {
        const { container } = render(<PlanView plan={plan} />);
        const summary = screen.getByRole("list", { name: "Entitlement balances" });
        const link = within(summary).getByRole("link", { name: /PKO/ });
        expect(container.querySelector(link.getAttribute("href")!)).not.toBeNull();
    });

    it("expands BOE detail rows", async () => {
        render(<PlanView plan={plan} />);
        await userEvent.click(screen.getByRole("button", { name: /BOE Debited/ }));
        expect(screen.getByText(/BOE 3631938/)).toBeInTheDocument();
    });

    it("shows blocking warnings and negative balances", () => {
        const bad = { ...plan, can_confirm: false, reconciliation: { ...plan.reconciliation, status: "ATTENTION" as const },
            issues: [{ code: "POSSIBLE_DUPLICATE_UTILISATION", blocking: true, group: null, entitlement: null, message: "BOE 5051922 is not linked" }],
            after: { ...plan.after, entitlements: [{ ...plan.after.entitlements[0], balance: part("-10.000", "1.8000", "-18.00") }] } };
        render(<PlanView plan={bad} />);
        expect(screen.getByRole("alert")).toHaveTextContent("Confirmation blocked");
        expect(screen.getByText("Needs attention")).toBeInTheDocument();
        expect(screen.getByText("-18.00", { selector: "td" })).toHaveClass("text-destructive");
    });

    it("loads the plan for the exact licence and SION and exports", async () => {
        vi.mocked(planApi.fetchEntitlementPlan).mockResolvedValue(plan);
        render(<EntitlementPlanningReport licenseNumber="3411008089" sion="E126" />);
        expect(await screen.findByText("OPENING PLANNING")).toBeInTheDocument();
        expect(planApi.fetchEntitlementPlan).toHaveBeenCalledWith("3411008089", "E126");
        await userEvent.click(screen.getByRole("button", { name: /Excel/ }));
        expect(planApi.downloadEntitlementPlanXlsx).toHaveBeenCalledWith("3411008089", "E126");
    });

    it("shows an error instead of crashing on a bad response", async () => {
        vi.mocked(planApi.fetchEntitlementPlan).mockResolvedValue([] as unknown as EntitlementPlan);
        render(<EntitlementPlanningReport licenseNumber="X" sion="E126" />);
        await waitFor(() => expect(screen.getByText("Licence planning unavailable")).toBeInTheDocument());
    });
});
