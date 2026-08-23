import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LicensePlanningWorkspace from "./LicensePlanningWorkspace";
import { planningPath } from "./planningPath";
import * as rulesApi from "@/services/api/planningRuleApi";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn().mockResolvedValue({ data: [{ id: 6, norm_class: "E1" }, { id: 7, norm_class: "E5" }] }) } }));
vi.mock("@/services/api/planningRuleApi", () => ({ fetchSionPlanningRules: vi.fn(), createSionPlanningRule: vi.fn(), updateSionPlanningRule: vi.fn(), searchSionImportItems: vi.fn(), fetchSionImportItem: vi.fn(), testSionPlanningRule: vi.fn(), previewSavedSionRules: vi.fn(), planSavedSionRules: vi.fn(), reorderSionPlanningRules: vi.fn(), previewScopedSionPlan: vi.fn(), saveScopedSionPlan: vi.fn() }));

const rule = { id: 4, sion: 7, name: "Sugar rule", expression: { operator: "AND" as const, conditions: [{ field: "HSN" as const, comparator: "CONTAINS" as const, value: "1701" }] }, max_unit_price: "2.70", unit: "KG", priority: 10, is_active: true, strategy: "STANDARD" as const, import_item: 101, standard_item_name: "Sugar - E5", unit_value_rows: [], percentage_rows: [], version: 1 };
const preview = { sion: "E5", mode: "NEW" as const, rules_processed: 1, summary: { licenses_matched: 1, licenses_new: 0, licenses_changed: 1, licenses_unchanged: 0, licenses_shortage: 0, rules_processed: 1 }, licenses: [{ license_id: 42, license_number: "LIC-42", sion: "E5", matched_item_count: 1, matched_rule_count: 1, matched_rule_priorities: [1], existing_plan_summary: "10 KG", proposed_plan_summary: "12 KG", existing_plan: {}, proposed_plan: {}, change_status: "CHANGE" as const, has_shortage: false, status: "FEASIBLE", items: [{ item_id: 1, rule_priority: 1, rule_name: "Sugar rule", item_name: "Sugar", hsn_code: "1701", unit: "KG", available_qty: "10.000", existing_planned_qty: "8.000", proposed_planned_qty: "10.000", max_unit_price: "2.70" }] }], conflicts: [] };

const renderWorkspace = (entry = "/planning?sion=E5") => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[entry]}><LicensePlanningWorkspace /></MemoryRouter></QueryClientProvider>);
};
const ready = () => screen.findByRole("button", { name: "Select rule Sugar rule" });
const openEdit = async () => { await ready(); await userEvent.click(screen.getByRole("button", { name: "Edit Rule" })); return screen.findByLabelText("Rule editor"); };

describe("SION planning workspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(rulesApi.fetchSionPlanningRules).mockResolvedValue([rule]);
    vi.mocked(rulesApi.searchSionImportItems).mockResolvedValue({ items: [], nextPage: null });
    vi.mocked(rulesApi.fetchSionImportItem).mockResolvedValue({ id: 101, name: "Sugar - E5" });
    vi.mocked(rulesApi.updateSionPlanningRule).mockResolvedValue(rule);
    vi.mocked(rulesApi.testSionPlanningRule).mockResolvedValue(preview);
    vi.mocked(rulesApi.previewSavedSionRules).mockResolvedValue(preview);
  });
  it("preserves optional license context in the route", () => expect(planningPath(42, "/licenses")).toBe("/planning?license_id=42&origin=%2Flicenses"));
  it("uses accessible norm tabs and opens selected detail", async () => {
    renderWorkspace("/planning"); expect(await screen.findByText("Select a SION norm")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /E5/ }));
    expect(await screen.findByLabelText("Rule workspace")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Select rule Sugar rule" })).toHaveAttribute("aria-current", "true");
    expect(screen.getByLabelText("Rule detail")).toHaveTextContent("Sugar rule");
    expect(screen.getByText("Single Item — Sugar - E5")).toBeInTheDocument();
  });
  it("filters the master worklist without changing the selected server rule", async () => {
    renderWorkspace(); await ready();
    fireEvent.change(screen.getByLabelText("Search rules"), { target: { value: "nothing" } }); expect(screen.getByText("No rules match this search.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search rules"), { target: { value: "sugar" } }); expect(screen.getByRole("button", { name: "Select rule Sugar rule" })).toHaveAttribute("aria-current", "true");
  });
  it("validates a saved rule and renders the authoritative backend preview", async () => {
    renderWorkspace(); await ready(); await userEvent.click(screen.getByRole("button", { name: "Validate" }));
    await waitFor(() => expect(rulesApi.testSionPlanningRule).toHaveBeenCalledWith(4)); expect(await screen.findByLabelText("License planning preview")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "View items for LIC-42" })); expect(screen.getByText("#1 Sugar rule")).toBeInTheDocument(); expect(screen.getByText(/HSN: 1701/)).toBeInTheDocument();
  });
  it("previews saved active rules without planning and opens the canonical license plan", async () => {
    render(<MemoryRouter initialEntries={["/planning?sion=E5"]}><Routes><Route path="/planning" element={<LicensePlanningWorkspace />} /><Route path="/licenses/:id/overview" element={<p>Canonical license plan</p>} /></Routes></MemoryRouter>);
    const previewButton = await screen.findByRole("button", { name: "Preview Impact" }); await waitFor(() => expect(previewButton).toBeEnabled()); await userEvent.click(previewButton);
    await waitFor(() => expect(rulesApi.previewSavedSionRules).toHaveBeenCalledWith(7, "NEW")); expect(rulesApi.planSavedSionRules).not.toHaveBeenCalled(); await userEvent.click(await screen.findByRole("button", { name: "View Plan" })); expect(await screen.findByText("Canonical license plan")).toBeInTheDocument();
  });
  it("disables planning actions without an active saved rule", async () => {
    vi.mocked(rulesApi.fetchSionPlanningRules).mockResolvedValue([{ ...rule, is_active: false }]); renderWorkspace();
    expect(await screen.findByRole("button", { name: "Preview Impact" })).toBeDisabled(); await userEvent.click(screen.getByRole("button", { name: "More planning actions" })); expect(await screen.findByRole("menuitem", { name: "Re-plan all eligible licences" })).toHaveAttribute("data-disabled");
  });
  it("confirms Force All and submits ALL mode", async () => {
    vi.mocked(rulesApi.planSavedSionRules).mockResolvedValue({ status: "COMPLETED" }); renderWorkspace(); await ready();
    await userEvent.click(screen.getByRole("button", { name: "More planning actions" })); await userEvent.click(await screen.findByRole("menuitem", { name: "Re-plan all eligible licences" })); expect(screen.getByRole("alertdialog", { name: "Force re-plan E5?" })).toBeInTheDocument(); await userEvent.click(screen.getByRole("button", { name: "Force All" })); await waitFor(() => expect(rulesApi.planSavedSionRules).toHaveBeenCalledWith(7, "ALL")); expect(rulesApi.previewSavedSionRules).toHaveBeenCalledWith(7, "ALL");
  });
  it("keeps invalid new drafts unsaved", async () => {
    renderWorkspace(); await ready(); await userEvent.click(screen.getByRole("button", { name: "New Rule" })); expect(await screen.findByLabelText("Rule editor")).toBeInTheDocument(); expect(screen.getByLabelText("Maximum unit price")).toHaveAttribute("aria-invalid", "true"); expect(screen.getByRole("button", { name: "Save Changes" })).toBeDisabled();
  });
  it("saves a changed draft with the current allocation contract", async () => {
    renderWorkspace(); await openEdit(); fireEvent.change(screen.getByLabelText("Rule name"), { target: { value: "Updated sugar rule" } }); await userEvent.click(screen.getByRole("button", { name: "Save Changes" })); await waitFor(() => expect(rulesApi.updateSionPlanningRule).toHaveBeenCalledWith(4, expect.objectContaining({ name: "Updated sugar rule", strategy: "STANDARD", import_item: 101 }))); expect(screen.getByLabelText("Rule detail")).toBeInTheDocument();
  });
  it("keeps a rejected draft open and shows backend validation", async () => {
    vi.mocked(rulesApi.updateSionPlanningRule).mockRejectedValue({ response: { data: { unit_value_rows: ["Price ranges overlap."] } } }); renderWorkspace(); await openEdit(); fireEvent.change(screen.getByLabelText("Rule name"), { target: { value: "Rejected rule" } }); await userEvent.click(screen.getByRole("button", { name: "Save Changes" })); expect(await screen.findByRole("alert")).toHaveTextContent("Price ranges overlap."); expect(screen.getByLabelText("Rule editor")).toBeInTheDocument(); expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });
  it("protects unsaved edits while switching norms", async () => {
    vi.mocked(rulesApi.fetchSionPlanningRules).mockImplementation(async id => id === 7 ? [rule] : []); renderWorkspace(); await openEdit(); fireEvent.change(screen.getByLabelText("Rule name"), { target: { value: "Unsaved E5 edit" } }); await userEvent.click(screen.getByRole("tab", { name: /E1/ })); const dialog = await screen.findByRole("alertdialog", { name: "Unsaved changes" }); expect(within(dialog).getByText(/Save or discard/)).toBeInTheDocument(); await userEvent.click(within(dialog).getByRole("button", { name: "Discard and switch" })); expect(await screen.findByText("No rules match this search.")).toBeInTheDocument(); expect(screen.queryByDisplayValue("Unsaved E5 edit")).not.toBeInTheDocument();
  });
});
