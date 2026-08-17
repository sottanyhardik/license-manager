import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchPlanningNorm, planNorm } from "../../services/api/licenseApi";
import NormRowPlanner from "./NormRowPlanner";
import { toast } from "sonner";

vi.mock("../../services/api/licenseApi", () => ({ planNorm: vi.fn(), fetchPlanningNorm: vi.fn() }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const mockedPlanNorm = vi.mocked(planNorm);
const mockedSnapshot = vi.mocked(fetchPlanningNorm);
const norms = [
    { id: 11, norm_class: "E1", description: "Sugar preparation", import_norm: [{ hsn_code: { hs_code: "1701" }, description: "Refined sugar" }] },
    { id: 22, norm_class: "E5", description: "Milk product", import_norm: [{ hsn_code: { hs_code: "0402" }, description: "Milk powder" }] },
];
const licenses = [{ id: 101, number: "LIC-101" }, { id: 202, number: "LIC-202" }];

describe("NormRowPlanner", () => {
    beforeEach(() => { vi.clearAllMocks(); mockedPlanNorm.mockResolvedValue({}); mockedSnapshot.mockResolvedValue({ available_qty: "800.000", planned_qty: "700.000", status: "FEASIBLE" }); });

    it("disables row actions until at least one license is selected", () => {
        render(<NormRowPlanner norms={norms} licenses={licenses} />);
        expect(screen.getAllByRole("button", { name: /^Plan / })).toHaveLength(2);
        screen.getAllByRole("button", { name: /^Plan / }).forEach((button) => expect(button).toBeDisabled());
    });

    it("sends multiple selected licenses with exactly one scalar sion_id", async () => {
        render(<NormRowPlanner norms={norms} licenses={licenses} />);
        fireEvent.keyDown(screen.getByLabelText("Planning licenses"), { key: "ArrowDown" });
        fireEvent.click(screen.getByText("LIC-101"));
        expect(await screen.findAllByText("800.000")).not.toHaveLength(0);
        fireEvent.keyDown(screen.getByLabelText("Planning licenses"), { key: "ArrowDown" });
        fireEvent.click(screen.getByText("LIC-202"));
        fireEvent.click(screen.getByRole("button", { name: "Plan E5" }));
        await waitFor(() => expect(mockedPlanNorm).toHaveBeenCalledWith([101, 202], 22));
        expect(mockedPlanNorm).toHaveBeenCalledTimes(1);
    });

    it("supports HSN/product AND-OR and direct SION filters", () => {
        render(<NormRowPlanner norms={norms} licenses={licenses} />);
        fireEvent.change(screen.getByLabelText("Filter SION by HSN"), { target: { value: "1701" } });
        fireEvent.change(screen.getByLabelText("Filter SION by product"), { target: { value: "milk" } });
        expect(screen.queryByRole("button", { name: "Plan E1" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Plan E5" })).not.toBeInTheDocument();
        fireEvent.keyDown(screen.getByLabelText("HSN and product match operator"), { key: "ArrowDown" });
        fireEvent.click(screen.getByRole("option", { name: "OR" }));
        expect(screen.getByRole("button", { name: "Plan E1" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Plan E5" })).toBeInTheDocument();
        fireEvent.keyDown(screen.getByLabelText("Direct SION filter"), { key: "ArrowDown" });
        fireEvent.click(screen.getByRole("option", { name: "E5" }));
        expect(screen.queryByRole("button", { name: "Plan E1" })).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Plan E5" })).toBeInTheDocument();
    });

    it("keeps saving state row-local and reports the selected-license count", async () => {
        let resolvePlan!: (value: unknown) => void;
        mockedPlanNorm.mockReturnValue(new Promise((resolve) => { resolvePlan = resolve; }));
        render(<NormRowPlanner norms={norms} licenses={licenses} initialSelectedLicenseIds={[101, 202]} embeddedSnapshots />);

        fireEvent.click(screen.getByRole("button", { name: "Plan E1" }));
        expect(screen.getByRole("button", { name: "Plan E1" })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Plan E5" })).toBeEnabled();
        resolvePlan({ created: 1, updated: 1, unchanged: 0, blocked: 0 });

        await waitFor(() => expect(screen.getByRole("button", { name: "Plan E1" })).toBeEnabled());
        expect(toast.success).toHaveBeenCalledWith("E1 planned for 2 licenses: 1 created, 1 updated, 0 already existed.");
    });

    it("recovers the row action after a failed plan and exposes the API error", async () => {
        mockedPlanNorm.mockRejectedValueOnce({ response: { data: { message: "Selected SION is not applicable." } } });
        render(<NormRowPlanner norms={norms} licenses={licenses} initialSelectedLicenseIds={[101]} embeddedSnapshots />);

        fireEvent.click(screen.getByRole("button", { name: "Plan E5" }));
        await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Selected SION is not applicable."));
        expect(screen.getByRole("button", { name: "Plan E5" })).toBeEnabled();
    });
});
