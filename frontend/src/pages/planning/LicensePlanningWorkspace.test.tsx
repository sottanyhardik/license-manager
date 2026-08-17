import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LicensePlanningWorkspace, { planningPath } from "./LicensePlanningWorkspace";
import * as rulesApi from "@/services/api/planningRuleApi";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn().mockResolvedValue({ data: [{ id: 7, norm_class: "E5" }] }) } }));
vi.mock("@/services/api/planningRuleApi", () => ({ fetchSionPlanningRules: vi.fn(), createSionPlanningRule: vi.fn(), updateSionPlanningRule: vi.fn(), testSionPlanningRule: vi.fn(), planSavedSionRules: vi.fn(), reorderSionPlanningRules: vi.fn() }));
const existing = { id: 4, sion: 7, name: "Sugar rule", expression: { operator: "AND" as const, conditions: [{ field: "HSN" as const, comparator: "CONTAINS" as const, value: "1701" }] }, max_unit_price: "2.70", unit: "KG", priority: 10, is_active: true };

describe("SION-first planning workspace", () => {
    beforeEach(() => { vi.clearAllMocks(); vi.mocked(rulesApi.fetchSionPlanningRules).mockResolvedValue([existing]); vi.mocked(rulesApi.updateSionPlanningRule).mockResolvedValue(existing); vi.mocked(rulesApi.testSionPlanningRule).mockResolvedValue({ licenses_requested: 1, results: [{ license_id: 42, license_number: "LIC-42", matched_lines: [{ id: 1, item_name: "Sugar", hsn_code: "1701", unit: "KG", available_qty: "10.000", status: "FEASIBLE" }] }], conflicts: [] }); });
    it("preserves optional license context in the route", () => expect(planningPath(42, "/licenses")).toBe("/planning?license_id=42&origin=%2Flicenses"));
    it("is SION-first and loads existing rules after selection", async () => {
        render(<MemoryRouter initialEntries={["/planning?license_id=42"]}><LicensePlanningWorkspace /></MemoryRouter>);
        expect(screen.getByText(/Select a SION norm/)).toBeInTheDocument();
        fireEvent.keyDown(screen.getByLabelText("SION Norm"), { key: "ArrowDown" }); fireEvent.click(await screen.findByText("E5"));
        expect(await screen.findByDisplayValue("Sugar rule")).toBeInTheDocument();
        expect(screen.getByDisplayValue("2.70")).toBeInTheDocument();
        expect(screen.getByLabelText("Rule logic")).toHaveValue("AND");
    });
    it("tests through the backend and renders its authoritative preview", async () => {
        render(<MemoryRouter initialEntries={["/planning?license_id=42"]}><LicensePlanningWorkspace /></MemoryRouter>);
        fireEvent.keyDown(screen.getByLabelText("SION Norm"), { key: "ArrowDown" }); fireEvent.click(await screen.findByText("E5"));
        fireEvent.click(await screen.findByRole("button", { name: /Test Saved Rule/ }));
        await waitFor(() => expect(rulesApi.testSionPlanningRule).toHaveBeenCalledWith(4, [42]));
        expect(await screen.findByText("Sugar")).toBeInTheDocument();
        expect(screen.getByText("1701")).toBeInTheDocument();
        expect(screen.getByText("10.000")).toBeInTheDocument();
    });
    it("plans by SION id using saved database rules only", async () => {
        vi.mocked(rulesApi.planSavedSionRules).mockResolvedValue({ rules_executed: [{ id: 4, priority: 10 }] });
        render(<MemoryRouter initialEntries={["/planning?license_id=42"]}><LicensePlanningWorkspace /></MemoryRouter>);
        fireEvent.keyDown(screen.getByLabelText("SION Norm"), { key: "ArrowDown" }); fireEvent.click(await screen.findByText("E5"));
        fireEvent.click(await screen.findByRole("button", { name: /Plan Saved SION Rules/ }));
        await waitFor(() => expect(rulesApi.planSavedSionRules).toHaveBeenCalledWith(7, [42]));
    });
    it("supports nested ALL/ANY groups and accessible condition fields", async () => {
        render(<MemoryRouter initialEntries={["/planning"]}><LicensePlanningWorkspace /></MemoryRouter>);
        fireEvent.keyDown(screen.getByLabelText("SION Norm"), { key: "ArrowDown" }); fireEvent.click(await screen.findByText("E5"));
        fireEvent.click(await screen.findByRole("button", { name: "Group" }));
        expect(screen.getByLabelText("Nested group logic")).toBeInTheDocument();
        expect(screen.getAllByLabelText(/Condition 1 field/).length).toBeGreaterThan(1);
    });
});
