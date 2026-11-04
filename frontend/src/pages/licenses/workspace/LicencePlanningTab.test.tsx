import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import * as licenseApi from "@/services/api/licenseApi";
import LicencePlanningTab, { PlanningTabLoading } from "./LicencePlanningTab";

// The planning editor reads each licence's own plan lines. The mocks answer per licence ID, so a stale
// response from one licence would show up as the wrong licence's rows.
vi.mock("@/services/api/licenseApi", () => ({
  fetchLicense: vi.fn(),
  fetchItemPlans: vi.fn(),
  bulkUpsertItemPlans: vi.fn(),
  deleteItemPlan: vi.fn(),
}));
vi.mock("@/services/api/planningRuleApi", () => ({ autoPlanLicense: vi.fn() }));

function licenceFixture(id: number) {
  return {
    license_number: `LIC-${id}`,
    balance_cif: "1",
    total_cif: "100",
    export_license: [{ cif_fc: "100" }],
    plan_utilization: [
      {
        group_id: id * 10,
        description: `Group for licence ${id}`,
        serials: [1],
        member_ids: [id * 10 + 1],
        item_names: [{ id: id * 10 + 1, name: `ITEM FOR ${id}` }],
        available_quantity: "1000",
        effective_available_quantity: "1000.000",
        license_balance_cif: "100",
        effective_license_balance_cif: "100.00",
        total_quantity: "1000",
        balance_cif_fc: "100",
        has_plan: true,
        original_quantity: "1000",
        used_quantity: "0",
        remaining_quantity: "1000",
        original_cif_fc: "100",
        used_cif_fc: "0",
        remaining_cif_fc: "100",
        status: "FEASIBLE",
      },
    ],
  };
}

function planFixture(id: number) {
  return [
    {
      id: id * 100,
      import_item: id * 10 + 1,
      item_name: id * 10 + 1,
      planning_item_name: `ITEM FOR ${id}`,
      planned_quantity: "100.000",
      unit_price: "1.00",
      planned_cif_fc: "100.00",
      boe_used_quantity: "0.000",
      boe_used_cif: "0.00",
      unlinked_allotment_quantity: "0.000",
      unlinked_allotment_cif: "0.00",
      effective_used_quantity: "0.000",
      effective_used_cif: "0.00",
      reconciled_planned_quantity: "100.000",
      reconciled_planned_cif: "100.00",
      remaining_quantity: "100.000",
      remaining_cif: "100.00",
      excess_quantity: "0.000",
      excess_cif: "0.00",
      reconciliation_status: "NOT_USED",
      split_percentage: "100.00",
      percentage_theoretical_quantity: "100.000",
      percentage_theoretical_cif: "100.00",
      remaining_entitlement_qty: "100.000",
      effective_planned_cif: "100.00",
      effective_unit_price: "1.00",
    },
  ];
}

describe("LicencePlanningTab", () => {
  beforeEach(() => {
    vi.mocked(licenseApi.fetchLicense).mockImplementation(async (id) => licenceFixture(Number(id)) as never);
    vi.mocked(licenseApi.fetchItemPlans).mockImplementation(async (id) => planFixture(Number(id)) as never);
  });

  it("loads the plan records of the licence it is given", async () => {
    render(<LicencePlanningTab licenceId={7} licenceNumber="LIC-7" canWrite canonicalBalanceCif={1006.98} />);

    expect(await screen.findByText("ITEM FOR 7")).toBeInTheDocument();
    expect(licenseApi.fetchItemPlans).toHaveBeenCalledWith(7);
    expect(licenseApi.fetchLicense).toHaveBeenCalledWith(7);
  });

  it("shows another licence's records after switching, and never the previous licence's", async () => {
    const { rerender } = render(<LicencePlanningTab licenceId={7} licenceNumber="LIC-7" canWrite canonicalBalanceCif={1} />);
    expect(await screen.findByText("ITEM FOR 7")).toBeInTheDocument();

    rerender(<LicencePlanningTab key="8" licenceId={8} licenceNumber="LIC-8" canWrite canonicalBalanceCif={2} />);

    expect(await screen.findByText("ITEM FOR 8")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("ITEM FOR 7")).not.toBeInTheDocument());
  });

  it("states that the user cannot plan, and offers no write action, when the user is read-only", async () => {
    render(<LicencePlanningTab licenceId={7} licenceNumber="LIC-7" canWrite={false} canonicalBalanceCif={1} />);

    expect(await screen.findByText("You don't have permission to plan utilization for this license.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /auto plan/i })).not.toBeInTheDocument();
  });

  it("has a loading region with an accessible name for the editor's load", () => {
    render(<PlanningTabLoading />);

    expect(screen.getByRole("status", { name: "Loading planning" })).toBeInTheDocument();
  });
});
