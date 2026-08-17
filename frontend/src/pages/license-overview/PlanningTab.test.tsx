import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PlanningTab from "./PlanningTab";
import { useLicenseOverviewPlanning } from "./useLicenseOverviewPlanning";

vi.mock("./useLicenseOverviewPlanning", () => ({ useLicenseOverviewPlanning: vi.fn() }));

const mockedPlanning = vi.mocked(useLicenseOverviewPlanning);

const baseRow = {
    group_id: 1,
    description: "Refined Sugar",
    hs_code: "1701",
    has_plan: true,
    original_quantity: 1_000,
    original_cif_fc: 20_000,
    remaining_quantity: 700,
    remaining_cif_fc: 14_000,
    used_quantity: 300,
    used_cif_fc: 6_000,
    available_qty: 800,
    planned_qty: 1_000,
    allocated_qty: 300,
    consumed_qty: 300,
    remaining_qty: 700,
    shortage_qty: 0,
    excess_qty: 100,
    feasible: true,
    status: "FEASIBLE" as const,
};

describe("PlanningTab canonical quantities", () => {
    beforeEach(() => vi.clearAllMocks());

    it("renders backend quantities without comparing original plan to current availability", () => {
        mockedPlanning.mockReturnValue({ data: { norm: "E5", rows: [baseRow] }, isLoading: false, isError: false } as ReturnType<typeof useLicenseOverviewPlanning>);
        render(<PlanningTab licenseId={1} isActive />);

        const row = screen.getByText("Refined Sugar").closest("tr")!;
        expect(row).toHaveAttribute("data-planning-status", "FEASIBLE");
        expect(within(row).getByText("1,000.00")).toBeInTheDocument();
        expect(within(row).getByText("800.00")).toBeInTheDocument();
        expect(within(row).getByText("700.00")).toBeInTheDocument();
        expect(within(row).getByText("Feasible")).toBeInTheDocument();
        expect(within(row).queryByText(/Short by/)).not.toBeInTheDocument();
    });

    it("shows an accessible textual shortage from the canonical response", () => {
        const shortRow = { ...baseRow, available_qty: 500, shortage_qty: 200, excess_qty: 0, feasible: false, status: "SHORT" as const };
        mockedPlanning.mockReturnValue({ data: { norm: "E5", rows: [shortRow] }, isLoading: false, isError: false } as ReturnType<typeof useLicenseOverviewPlanning>);
        render(<PlanningTab licenseId={1} isActive />);

        const row = screen.getByText("Refined Sugar").closest("tr")!;
        expect(row).toHaveAttribute("data-planning-status", "SHORT");
        expect(within(row).getByText("Short by 200.00")).toBeInTheDocument();
    });

    it("does not present mixed-unit groups as feasible", () => {
        const blocked = { ...baseRow, feasible: false, status: "BLOCKED_UNIT_MISMATCH" as const };
        mockedPlanning.mockReturnValue({ data: { norm: "E5", rows: [blocked] }, isLoading: false, isError: false } as ReturnType<typeof useLicenseOverviewPlanning>);
        render(<PlanningTab licenseId={1} isActive />);
        expect(screen.getByText("Blocked: unit mismatch")).toBeInTheDocument();
    });

    it("renders loading, error, and empty states from the query contract", () => {
        mockedPlanning.mockReturnValueOnce({ data: undefined, isLoading: true, isError: false } as ReturnType<typeof useLicenseOverviewPlanning>);
        const { rerender } = render(<PlanningTab licenseId={1} isActive />);
        expect(screen.getByText("Loading plan utilization…")).toBeInTheDocument();

        mockedPlanning.mockReturnValueOnce({ data: undefined, isLoading: false, isError: true, error: new Error("denied") } as ReturnType<typeof useLicenseOverviewPlanning>);
        rerender(<PlanningTab licenseId={1} isActive />);
        expect(screen.getByRole("alert")).toHaveTextContent("denied");

        mockedPlanning.mockReturnValueOnce({ data: { norm: null, rows: [] }, isLoading: false, isError: false } as ReturnType<typeof useLicenseOverviewPlanning>);
        rerender(<PlanningTab licenseId={1} isActive />);
        expect(screen.getByText("No export product groups on this licence.")).toBeInTheDocument();
    });
});
