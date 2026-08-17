import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LicensePlanningWorkspace, { planningPath } from "./LicensePlanningWorkspace";
import * as rulesApi from "@/services/api/planningRuleApi";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn().mockResolvedValue({ data: [{ id: 6, norm_class: "E1" }, { id: 7, norm_class: "E5" }] }) } }));
vi.mock("@/services/api/planningRuleApi", () => ({ fetchSionPlanningRules: vi.fn(), createSionPlanningRule: vi.fn(), updateSionPlanningRule: vi.fn(), testSionPlanningRule: vi.fn(), previewSavedSionRules: vi.fn(), planSavedSionRules: vi.fn(), reorderSionPlanningRules: vi.fn() }));
const existing = { id: 4, sion: 7, name: "Sugar rule", expression: { operator: "AND" as const, conditions: [{ field: "HSN" as const, comparator: "CONTAINS" as const, value: "1701" }] }, max_unit_price: "2.70", unit: "KG", priority: 10, is_active: true };
const groupedPreview = { sion: "E5", mode: "NEW" as const, rules_processed: 2, summary: { licenses_matched: 1, licenses_new: 0, licenses_changed: 1, licenses_unchanged: 0, licenses_shortage: 0, rules_processed: 2 }, licenses: [{ license_id: 42, license_number: "LIC-42", sion: "E5", matched_item_count: 2, matched_rule_count: 2, matched_rule_priorities: [1, 2], existing_plan_summary: "10 KG", proposed_plan_summary: "12 KG", existing_plan: {}, proposed_plan: {}, change_status: "CHANGE" as const, has_shortage: false, status: "FEASIBLE", items: [{ item_id: 1, rule_priority: 1, rule_name: "Sugar rule", item_name: "Sugar", hsn_code: "1701", unit: "KG", available_qty: "10.000", existing_planned_qty: "8.000", proposed_planned_qty: "10.000", max_unit_price: "2.70", status: "FEASIBLE" }, { item_id: 2, rule_priority: 2, rule_name: "WPC rule", item_name: "WPC", hsn_code: "3502", available_qty: "2.000", existing_planned_qty: "2.000", proposed_planned_qty: "2.000", max_unit_price: "25.00" }] }], conflicts: [] };

describe("SION-first planning workspace", () => {
    beforeEach(() => { vi.clearAllMocks(); vi.mocked(rulesApi.fetchSionPlanningRules).mockResolvedValue([existing]); vi.mocked(rulesApi.updateSionPlanningRule).mockResolvedValue(existing); vi.mocked(rulesApi.testSionPlanningRule).mockResolvedValue(groupedPreview); vi.mocked(rulesApi.previewSavedSionRules).mockResolvedValue(groupedPreview); });
    it("preserves optional license context in the route", () => expect(planningPath(42, "/licenses")).toBe("/planning?license_id=42&origin=%2Flicenses"));
    it("is SION-first and loads existing rules after selection", async () => {
        render(<MemoryRouter initialEntries={["/planning?license_id=42"]}><LicensePlanningWorkspace /></MemoryRouter>);
        expect(screen.getByText(/Select a SION norm/)).toBeInTheDocument();
        fireEvent.keyDown(screen.getByLabelText("SION Norm"), { key: "ArrowDown" }); fireEvent.click(await screen.findByText("E5"));
        fireEvent.click(await screen.findByRole("button", { name: /Edit/ }));
        expect(await screen.findByDisplayValue("Sugar rule")).toBeInTheDocument();
        expect(screen.getByDisplayValue("2.70")).toBeInTheDocument();
        expect(screen.getByLabelText("Rule logic")).toHaveValue("AND");
    });
    it("tests through the backend and renders its authoritative preview", async () => {
        render(<MemoryRouter initialEntries={["/planning?license_id=42"]}><LicensePlanningWorkspace /></MemoryRouter>);
        fireEvent.keyDown(screen.getByLabelText("SION Norm"), { key: "ArrowDown" }); fireEvent.click(await screen.findByText("E5"));
        fireEvent.click(await screen.findByRole("button", { name: /Edit/ }));
        fireEvent.click(await screen.findByRole("button", { name: /Test Saved Rule/ }));
        await waitFor(() => expect(rulesApi.testSionPlanningRule).toHaveBeenCalledWith(4));
        fireEvent.click(await screen.findByRole("button", { name: "View items for LIC-42" }));
        expect(await screen.findByText("#1 Sugar rule")).toBeInTheDocument();
        expect(screen.getByText(/HSN: 1701/)).toBeInTheDocument();
        expect(screen.getByText(/Available: 10.000/)).toBeInTheDocument();
    });
    it("renders one license row with backend counts and preserves child items", async () => {
        render(<MemoryRouter initialEntries={["/planning?sion=E5"]}><LicensePlanningWorkspace /></MemoryRouter>);
        const previewButton = await screen.findByRole("button", { name: /Preview E5 Plan/ });
        await waitFor(() => expect(previewButton).toBeEnabled());
        fireEvent.click(previewButton);
        expect(await screen.findByText(/Matched Licenses:/)).toBeInTheDocument();
        expect(screen.getAllByText("LIC-42")).toHaveLength(1);
        expect(screen.getByText("CHANGE")).toBeInTheDocument();
        expect(screen.getByText("10 KG")).toBeInTheDocument();
        expect(screen.getByText("12 KG")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "View items for LIC-42" }));
        expect(screen.getByText("#1 Sugar rule")).toBeInTheDocument();
        expect(screen.getByText("#2 WPC rule")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Hide items for LIC-42" })).toHaveAttribute("aria-expanded", "true");
    });
    it("opens the established canonical license planning route", async () => {
        render(<MemoryRouter initialEntries={["/planning?sion=E5"]}><Routes><Route path="/planning" element={<LicensePlanningWorkspace />} /><Route path="/licenses/:id/overview" element={<p>Canonical license plan</p>} /></Routes></MemoryRouter>);
        const previewButton = await screen.findByRole("button", { name: /Preview E5 Plan/ });
        await waitFor(() => expect(previewButton).toBeEnabled());
        fireEvent.click(previewButton);
        fireEvent.click(await screen.findByRole("button", { name: "View Plan" }));
        expect(await screen.findByText("Canonical license plan")).toBeInTheDocument();
    });
    it("plans by SION id using saved database rules only", async () => {
        vi.mocked(rulesApi.planSavedSionRules).mockResolvedValue({ rules_executed: [{ id: 4, priority: 10 }] });
        render(<MemoryRouter initialEntries={["/planning?license_id=42"]}><LicensePlanningWorkspace /></MemoryRouter>);
        fireEvent.keyDown(screen.getByLabelText("SION Norm"), { key: "ArrowDown" }); fireEvent.click(await screen.findByText("E5"));
        fireEvent.click(await screen.findByRole("button", { name: "New Only" }));
        await waitFor(() => expect(rulesApi.planSavedSionRules).toHaveBeenCalledWith(7, "NEW"));
        expect(rulesApi.previewSavedSionRules).toHaveBeenCalledWith(7, "NEW");
    });
    it("does not enable preview or PLAN when only inactive rules are returned", async () => {
        vi.mocked(rulesApi.fetchSionPlanningRules).mockResolvedValue([{ ...existing, is_active: false }]);
        render(<MemoryRouter initialEntries={["/planning?sion=E5"]}><LicensePlanningWorkspace /></MemoryRouter>);
        const planButton = await screen.findByRole("button", { name: "New Only" });
        await waitFor(() => expect(screen.getByText(/Activate and save at least one rule/)).toBeInTheDocument());
        expect(planButton).toBeDisabled();
        expect(screen.getByRole("button", { name: /Preview E5 Plan/ })).toBeDisabled();
        fireEvent.click(planButton);
        expect(rulesApi.planSavedSionRules).not.toHaveBeenCalled();
    });
    it("supports nested ALL/ANY groups and accessible condition fields", async () => {
        render(<MemoryRouter initialEntries={["/planning"]}><LicensePlanningWorkspace /></MemoryRouter>);
        fireEvent.keyDown(screen.getByLabelText("SION Norm"), { key: "ArrowDown" }); fireEvent.click(await screen.findByText("E5"));
        fireEvent.click(await screen.findByRole("button", { name: /Edit/ }));
        fireEvent.click(await screen.findByRole("button", { name: "Group" }));
        expect(screen.getByLabelText("Nested group logic")).toBeInTheDocument();
        expect(screen.getAllByLabelText(/Condition 1 field/).length).toBeGreaterThan(1);
    });
    it("removes all match rules only after destructive confirmation and marks the draft dirty", async () => {
        render(<MemoryRouter initialEntries={["/planning?sion=E5"]}><LicensePlanningWorkspace /></MemoryRouter>);
        fireEvent.click(await screen.findByRole("button", { name: /Edit/ }));
        fireEvent.click(screen.getByRole("button", { name: "Remove All Match Rules" }));
        expect(screen.getByText("Remove all match rules?")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
        expect(screen.getByLabelText("Condition 1 field")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Remove All Match Rules" }));
        fireEvent.click(screen.getByRole("button", { name: "Remove All" }));
        expect(screen.queryByLabelText("Condition 1 field")).not.toBeInTheDocument();
        expect(screen.getByText("No match rules configured. Add a condition or group.")).toBeInTheDocument();
        expect(screen.getByText(/Unsaved changes/)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Remove All Match Rules" })).not.toBeInTheDocument();
    });
    it("removes a populated nested group only after confirmation while retaining condition removal", async () => {
        render(<MemoryRouter initialEntries={["/planning?sion=E5"]}><LicensePlanningWorkspace /></MemoryRouter>);
        fireEvent.click(await screen.findByRole("button", { name: /Edit/ }));
        fireEvent.click(screen.getByRole("button", { name: "Group" }));
        fireEvent.click(screen.getByRole("button", { name: "Remove Group" }));
        const dialog = screen.getByRole("alertdialog");
        expect(within(dialog).getByText("Remove populated group?")).toBeInTheDocument();
        fireEvent.click(within(dialog).getByRole("button", { name: "Remove Group" }));
        expect(screen.queryByLabelText("Nested group logic")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
    });
    it("removes an empty nested group immediately without confirmation and never offers root removal", async () => {
        render(<MemoryRouter initialEntries={["/planning?sion=E5"]}><LicensePlanningWorkspace /></MemoryRouter>);
        fireEvent.click(await screen.findByRole("button", { name: /Edit/ }));
        fireEvent.click(screen.getByRole("button", { name: "Group" }));
        const removeButtons = screen.getAllByRole("button", { name: "Remove" });
        fireEvent.click(removeButtons[removeButtons.length - 1]);
        expect(screen.getAllByText("No match rules configured. Add a condition or group.")).toHaveLength(1);
        fireEvent.click(screen.getByRole("button", { name: "Remove Group" }));
        expect(screen.queryByText("Remove populated group?")).not.toBeInTheDocument();
        expect(screen.queryByLabelText("Nested group logic")).not.toBeInTheDocument();
        expect(screen.getByText("Match rules")).toBeInTheDocument();
    });
    it("loads SION from the URL and keeps the editor closed until New or Edit", async () => {
        render(<MemoryRouter initialEntries={["/planning?sion=E5"]}><LicensePlanningWorkspace /></MemoryRouter>);
        expect(await screen.findByText("E5 — Planning Rules")).toBeInTheDocument();
        expect(screen.queryByLabelText("Rule editor")).not.toBeInTheDocument();
        expect(rulesApi.fetchSionPlanningRules).toHaveBeenCalledWith(7);
    });
    it("previews the selected SION without invoking PLAN", async () => {
        vi.mocked(rulesApi.previewSavedSionRules).mockResolvedValue({ sion: "E5", rules_processed: 1, licenses: [] });
        render(<MemoryRouter initialEntries={["/planning?sion=E5"]}><LicensePlanningWorkspace /></MemoryRouter>);
        const previewButton = await screen.findByRole("button", { name: /Preview E5 Plan/ });
        await waitFor(() => expect(previewButton).toBeEnabled());
        fireEvent.click(previewButton);
        await waitFor(() => expect(rulesApi.previewSavedSionRules).toHaveBeenCalledWith(7, "NEW"));
        expect(rulesApi.planSavedSionRules).not.toHaveBeenCalled();
    });
    it("confirms Force All and submits ALL mode through the same API", async () => {
        vi.mocked(rulesApi.planSavedSionRules).mockResolvedValue({ status: "COMPLETED" });
        render(<MemoryRouter initialEntries={["/planning?sion=E5"]}><LicensePlanningWorkspace /></MemoryRouter>);
        const forceButton = await screen.findByRole("button", { name: "Force All" });
        await waitFor(() => expect(forceButton).toBeEnabled());
        fireEvent.click(forceButton);
        expect(screen.getByRole("alertdialog", { name: "Force re-plan E5" })).toBeInTheDocument();
        fireEvent.click(screen.getAllByRole("button", { name: "Force All" })[1]);
        await waitFor(() => expect(rulesApi.planSavedSionRules).toHaveBeenCalledWith(7, "ALL"));
        expect(rulesApi.previewSavedSionRules).toHaveBeenCalledWith(7, "ALL");
    });
    it("protects a dirty editor and discards all norm-specific state on switch", async () => {
        vi.mocked(rulesApi.fetchSionPlanningRules).mockImplementation(async (id) => id === 7 ? [existing] : []);
        render(<MemoryRouter initialEntries={["/planning?sion=E5"]}><LicensePlanningWorkspace /></MemoryRouter>);
        fireEvent.click(await screen.findByRole("button", { name: /Edit/ }));
        fireEvent.change(screen.getByLabelText("Rule name"), { target: { value: "Unsaved E5 edit" } });
        fireEvent.keyDown(screen.getByLabelText("SION Norm"), { key: "ArrowDown" });
        fireEvent.click(await screen.findByText("E1"));
        expect(await screen.findByRole("alertdialog", { name: "Unsaved changes" })).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Discard and switch" }));
        expect(await screen.findByText("E1 has no planning rules yet.")).toBeInTheDocument();
        expect(screen.queryByDisplayValue("Unsaved E5 edit")).not.toBeInTheDocument();
    });
});
