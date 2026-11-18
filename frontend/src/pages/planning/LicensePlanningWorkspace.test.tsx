import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import LicensePlanningWorkspace from "./LicensePlanningWorkspace";
import { planningPath } from "./planningPath";
import * as rulesApi from "@/api/planningRuleApi";
import { AuthContext } from "@/context/AuthContext";
import type { AuthContextValue } from "@/types";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn().mockResolvedValue({ data: [] }) } }));
vi.mock("@/api/planningRuleApi", () => ({ fetchSionPlanningRules: vi.fn(), createSionPlanningRule: vi.fn(), updateSionPlanningRule: vi.fn(), deleteSionPlanningRule: vi.fn(), searchSionImportItems: vi.fn(), fetchSionImportItem: vi.fn(), testSionPlanningRule: vi.fn(), previewSavedSionRules: vi.fn(), planSavedSionRules: vi.fn(), reorderSionPlanningRules: vi.fn(), previewScopedSionPlan: vi.fn(), saveScopedSionPlan: vi.fn(), fetchSionNormSummaries: vi.fn(), fetchSionNormConfiguration: vi.fn() }));

const summary = (id: number, norm_class: string, extra: Partial<rulesApi.SionNormSummary> = {}): rulesApi.SionNormSummary => ({ id, norm_class, description: `${norm_class} norm`, is_active: true, active_rule_count: 0, split_rule_count: 0, rule_version_count: 0, max_rule_version: null, last_updated: null, profile_version: null, profile_action_count: 0, registry_rule_count: 0, registry_action_count: 0, registry_split_count: 0, has_entitlement_profile: false, ...extra });
const norms = [summary(6, "E1"), summary(7, "E5", { active_rule_count: 1, max_rule_version: 1 }), summary(5, "E126", { is_active: false, registry_rule_count: 4, registry_action_count: 7, registry_split_count: 1, has_entitlement_profile: true })];
const emptyConfig = (id: number, norm_class: string): rulesApi.SionNormConfiguration => ({ sion: { id, norm_class, is_active: true }, rule_versions: [], profiles: [], registry: null, entitlement_profile: null, audit: [] });
const e126Config: rulesApi.SionNormConfiguration = {
  sion: { id: 5, norm_class: "E126", description: "Pickles in oil", is_active: false },
  rule_versions: [], profiles: [], audit: [],
  registry: {
    source: "registry",
    rules: [
      { stable_key: "E126:RULE:002:PKO_OLIVE_SPLIT", name: "Palm Kernel / Olive Oil split", priority: 2, expression: { operator: "AND", conditions: [{ field: "HSN", comparator: "STARTS_WITH", value: "1513" }] }, max_unit_price: "5.00", unit: "KG", output_key: "PKO_OLIVE_SPLIT" },
      { stable_key: "E126:RULE:003:PKO", name: "Palm Kernel Oil", priority: 3, expression: { field: "HSN", comparator: "STARTS_WITH", value: "1513" }, max_unit_price: "1.80", unit: "KG", output_key: "PKO" },
    ],
    actions: [{ stable_key: "E126:ACTION:002:SPLIT", priority: 2, action_type: "SPLIT", config: { source_output: "PKO_OLIVE_SPLIT", basis: "RECORD_AVAILABLE_QUANTITY", targets: { PKO: "0.5", OLIVE: "0.5" } } }],
    mappings: [{ stable_key: "E126:OUTPUT:002:PKO", priority: 2, source_key: "PKO", output_name: "PALM KERNEL OIL - E126", rate: "1.80", conversion_factor: "1", unit: "KG" }],
  },
  entitlement_profile: {
    source: "profiles",
    groups: [{ key: "VEGETABLE_OIL", label: "Vegetable Oil", entitlement_items: ["PALM KERNEL OIL", "OLIVE OIL"], source_rule: "E126:RULE:002:PKO_OLIVE_SPLIT", split_action: "E126:ACTION:002:SPLIT", products: [{ name: "Sunflower Oil", entitlement: "OLIVE OIL", aliases: ["SUNFLOWER"] }, { name: "Olive Oil", entitlement: "OLIVE OIL", aliases: ["OLIVE"] }, { name: "PKO", entitlement: "PALM KERNEL OIL", aliases: ["PKO"] }] }],
    entitlements: [{ item: "PALM KERNEL OIL", label: "PKO", split_target: "PKO", valuation: "RATE", sequence: 1 }, { item: "OLIVE OIL", label: "Olive Oil + Sunflower Oil", split_target: "OLIVE", valuation: "RESIDUAL", sequence: 2 }],
  },
};

const rule = { id: 4, sion: 7, name: "Sugar rule", stable_key: "E5:RULE:001", expression: { operator: "AND" as const, conditions: [{ field: "HSN" as const, comparator: "CONTAINS" as const, value: "1701" }] }, max_unit_price: "2.70", unit: "KG", priority: 10, is_active: true, strategy: "STANDARD" as const, import_item: 101, standard_item_name: "Sugar - E5", unit_value_rows: [], percentage_rows: [], version: 1 };
const preview = { sion: "E5", mode: "NEW" as const, rules_processed: 1, summary: { licenses_matched: 1, licenses_new: 0, licenses_changed: 1, licenses_unchanged: 0, licenses_shortage: 0, rules_processed: 1 }, licenses: [{ license_id: 42, license_number: "LIC-42", sion: "E5", matched_item_count: 1, matched_rule_count: 1, matched_rule_priorities: [1], existing_plan_summary: "10 KG", proposed_plan_summary: "12 KG", existing_plan: {}, proposed_plan: {}, change_status: "CHANGE" as const, has_shortage: false, status: "FEASIBLE", items: [{ item_id: 1, rule_priority: 1, rule_name: "Sugar rule", item_name: "Sugar", hsn_code: "1701", unit: "KG", available_qty: "10.000", existing_planned_qty: "8.000", proposed_planned_qty: "10.000", max_unit_price: "2.70" }] }], conflicts: [] };

const auth = (roles: string[]): AuthContextValue => ({ user: null, loading: false, loginSuccess: () => {}, updateUser: () => {}, logout: async () => {}, hasRole: (r: string) => roles.includes(r), hasAnyRole: (rs: readonly string[]) => rs.some((r) => roles.includes(r)), isSuperAdmin: () => false, canManageUsers: () => false });
function Where() { const l = useLocation(); return <output data-testid="where">{l.search}</output>; }
const wrap = (children: ReactNode, roles = ["LICENSE_MANAGER"]) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}><AuthContext.Provider value={auth(roles)}>{children}</AuthContext.Provider></QueryClientProvider>;
};
const renderWorkspace = (entry = "/planning?sion=E5&view=rules", roles?: string[]) =>
  render(wrap(<MemoryRouter initialEntries={[entry]}><LicensePlanningWorkspace /><Where /></MemoryRouter>, roles));
const ready = () => screen.findByRole("button", { name: "Select rule Sugar rule" });
const openEdit = async () => { await ready(); await userEvent.click(screen.getByRole("button", { name: "Edit Rule" })); return screen.findByLabelText("Rule editor"); };

describe("SION planning workspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(rulesApi.fetchSionNormSummaries).mockResolvedValue(norms);
    vi.mocked(rulesApi.fetchSionNormConfiguration).mockImplementation(async (id) => id === 5 ? e126Config : emptyConfig(id, id === 7 ? "E5" : "E1"));
    vi.mocked(rulesApi.fetchSionPlanningRules).mockImplementation(async (id) => id === 7 ? [rule] : []);
    vi.mocked(rulesApi.searchSionImportItems).mockResolvedValue({ items: [], nextPage: null });
    vi.mocked(rulesApi.fetchSionImportItem).mockResolvedValue({ id: 101, name: "Sugar - E5" });
    vi.mocked(rulesApi.updateSionPlanningRule).mockResolvedValue(rule);
    vi.mocked(rulesApi.testSionPlanningRule).mockResolvedValue(preview);
    vi.mocked(rulesApi.previewSavedSionRules).mockResolvedValue(preview);
  });
  it("preserves optional license context in the route", () => expect(planningPath(42, "/licenses")).toBe("/planning?license_id=42&origin=%2Flicenses"));

  it("lists norms as collapsed accordion rows without an empty panel", async () => {
    renderWorkspace("/planning");
    const list = await screen.findByRole("list", { name: "SION norms" });
    expect(within(list).getAllByRole("article")).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Expand SION norm E126" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Select a SION norm")).not.toBeInTheDocument();
    expect(screen.getByText("4 rules (registry)")).toBeInTheDocument();
    expect(screen.getByText("3 SION norms")).toBeInTheDocument();
  });

  it("expands a norm inline, pushes ?sion= and collapses again", async () => {
    renderWorkspace("/planning");
    await userEvent.click(await screen.findByRole("button", { name: "Expand SION norm E5" }));
    expect(await screen.findByRole("region", { name: "SION norm E5 workspace" })).toBeInTheDocument();
    expect(screen.getByTestId("where").textContent).toContain("sion=E5");
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    await userEvent.click(screen.getByRole("tab", { name: /Rules/ }));
    expect(await ready()).toHaveAttribute("aria-current", "true");
    expect(screen.getByText("Single Item — Sugar - E5")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Close E5 workspace" }));
    expect(screen.queryByRole("region", { name: "SION norm E5 workspace" })).not.toBeInTheDocument();
    expect(screen.getByTestId("where").textContent).not.toContain("sion=");
  });

  it("shows E126 split configuration from the actual registry and entitlement profile", async () => {
    renderWorkspace("/planning?sion=E126&view=split");
    const table = await screen.findByRole("table", { name: "Split entitlements" });
    expect(within(table).getAllByText("50%")).toHaveLength(2);
    expect(within(table).getByText("Sunflower Oil → Olive Oil + Sunflower Oil")).toBeInTheDocument();
    expect(within(table).getByText("Olive Oil → Olive Oil + Sunflower Oil")).toBeInTheDocument();
    expect(within(table).getByText("PKO → PKO")).toBeInTheDocument();
    expect(screen.getByText("Total 100%")).toBeInTheDocument();
    // Tabs are configuration-driven: E126 has split + mapping, no DB history.
    const tabs = screen.getAllByRole("tab").map((t) => t.textContent);
    expect(tabs).toEqual(["Overview", "Rules (0)", "Split Configuration", "Product Mapping", "Validation"]);
  });

  it("hides the split tab for a norm without split configuration", async () => {
    renderWorkspace("/planning?sion=E1");
    await screen.findByRole("region", { name: "SION norm E1 workspace" });
    expect(screen.queryByRole("tab", { name: "Split Configuration" })).not.toBeInTheDocument();
  });

  it("searches norms and keeps the query in the URL", async () => {
    renderWorkspace("/planning");
    await screen.findByRole("list", { name: "SION norms" });
    fireEvent.change(screen.getByLabelText("Search SION norms"), { target: { value: "e12" } });
    expect(screen.getAllByRole("article")).toHaveLength(1);
    expect(screen.getByTestId("where").textContent).toContain("q=e12");
  });

  it("filters the rule worklist without changing the selected server rule", async () => {
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
    render(wrap(<MemoryRouter initialEntries={["/planning?sion=E5"]}><Routes><Route path="/planning" element={<LicensePlanningWorkspace />} /><Route path="/licenses/:id/overview" element={<p>Canonical license plan</p>} /></Routes></MemoryRouter>));
    const previewButton = await screen.findByRole("button", { name: "Preview Impact" }); await waitFor(() => expect(previewButton).toBeEnabled()); await userEvent.click(previewButton);
    await waitFor(() => expect(rulesApi.previewSavedSionRules).toHaveBeenCalledWith(7, "NEW")); expect(rulesApi.planSavedSionRules).not.toHaveBeenCalled(); await userEvent.click(await screen.findByRole("button", { name: "View Plan" })); expect(await screen.findByText("Canonical license plan")).toBeInTheDocument();
  });
  it("disables planning actions without an active saved rule", async () => {
    vi.mocked(rulesApi.fetchSionPlanningRules).mockResolvedValue([{ ...rule, is_active: false }]); renderWorkspace();
    await screen.findByRole("button", { name: "Select rule Sugar rule" });
    expect(screen.getByRole("button", { name: "Preview Impact" })).toBeDisabled(); await userEvent.click(screen.getByRole("button", { name: "More planning actions" })); expect(await screen.findByRole("menuitem", { name: "Re-plan all eligible licences" })).toHaveAttribute("data-disabled");
  });
  it("confirms Force All and submits ALL mode", async () => {
    vi.mocked(rulesApi.planSavedSionRules).mockResolvedValue({ status: "COMPLETED" }); renderWorkspace(); await ready();
    await userEvent.click(screen.getByRole("button", { name: "More planning actions" })); await userEvent.click(await screen.findByRole("menuitem", { name: "Re-plan all eligible licences" })); expect(screen.getByRole("alertdialog", { name: "Force re-plan E5?" })).toBeInTheDocument(); await userEvent.click(screen.getByRole("button", { name: "Force All" })); await waitFor(() => expect(rulesApi.planSavedSionRules).toHaveBeenCalledWith(7, "ALL")); expect(rulesApi.previewSavedSionRules).toHaveBeenCalledWith(7, "ALL");
  });
  it("keeps invalid new drafts unsaved", async () => {
    renderWorkspace(); await ready(); await userEvent.click(screen.getByRole("button", { name: "New Rule" })); expect(await screen.findByLabelText("Rule editor")).toBeInTheDocument(); expect(screen.getByLabelText("Maximum unit price")).toHaveAttribute("aria-invalid", "true"); expect(screen.getByRole("button", { name: "Save Changes" })).toBeDisabled();
  });
  it("saves a changed draft with the current allocation contract", async () => {
    renderWorkspace(); await openEdit(); fireEvent.change(screen.getByLabelText("Rule name"), { target: { value: "Updated sugar rule" } }); await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));
    await waitFor(() => expect(rulesApi.updateSionPlanningRule).toHaveBeenCalledWith(4, expect.objectContaining({ name: "Updated sugar rule", strategy: "STANDARD", import_item: 101 })));
    expect(vi.mocked(rulesApi.updateSionPlanningRule).mock.calls[0][1]).not.toHaveProperty("stable_key");
    expect(screen.getByLabelText("Rule detail")).toBeInTheDocument();
    await waitFor(() => expect(rulesApi.fetchSionNormSummaries).toHaveBeenCalledTimes(2));
  });
  it("keeps a rejected draft open and shows backend validation", async () => {
    vi.mocked(rulesApi.updateSionPlanningRule).mockRejectedValue({ response: { data: { unit_value_rows: ["Price ranges overlap."] } } }); renderWorkspace(); await openEdit(); fireEvent.change(screen.getByLabelText("Rule name"), { target: { value: "Rejected rule" } }); await userEvent.click(screen.getByRole("button", { name: "Save Changes" })); expect(await screen.findByRole("alert")).toHaveTextContent("Price ranges overlap."); expect(screen.getByLabelText("Rule editor")).toBeInTheDocument(); expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });
  it("protects unsaved edits while switching norms", async () => {
    renderWorkspace(); await openEdit(); fireEvent.change(screen.getByLabelText("Rule name"), { target: { value: "Unsaved E5 edit" } }); await userEvent.click(screen.getByRole("button", { name: "Expand SION norm E1" })); const dialog = await screen.findByRole("alertdialog", { name: "Unsaved changes" }); expect(within(dialog).getByText(/Save or discard/)).toBeInTheDocument(); await userEvent.click(within(dialog).getByRole("button", { name: "Discard and switch" })); expect(await screen.findByText("No rules match this search.")).toBeInTheDocument(); expect(screen.queryByDisplayValue("Unsaved E5 edit")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "SION norm E1 workspace" })).toBeInTheDocument();
  });
  it("fetches the norm list once across tab, rule and norm changes", async () => {
    renderWorkspace();
    await ready();
    await userEvent.click(screen.getByRole("button", { name: "Select rule Sugar rule" }));
    await userEvent.click(screen.getByRole("button", { name: "Expand SION norm E1" }));
    await userEvent.click(screen.getByRole("button", { name: "Expand SION norm E5" }));
    await ready();
    expect(rulesApi.fetchSionNormSummaries).toHaveBeenCalledTimes(1);
  });
  it("hides write actions from read-only users", async () => {
    renderWorkspace("/planning?sion=E5&view=rules", ["LICENSE_VIEWER"]); await ready();
    expect(screen.queryByRole("button", { name: "New Rule" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit Rule" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview Impact" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "More planning actions" }));
    expect(screen.queryByRole("menuitem", { name: "Re-plan all eligible licences" })).not.toBeInTheDocument();
  });
  it("maps legacy ?view=versions to Version History", async () => {
    vi.mocked(rulesApi.fetchSionNormConfiguration).mockResolvedValue({ ...emptyConfig(7, "E5"), rule_versions: [{ id: 4, stable_key: "E5:RULE:001", name: "Sugar rule", version: 1, priority: 10, is_active: true, created_on: null, created_by_username: null, modified_on: "2026-08-20T15:39:50Z", modified_by_username: "owner" }] });
    renderWorkspace("/planning?sion=E5&view=versions");
    expect(await screen.findByRole("tab", { name: "Version History" })).toHaveAttribute("aria-selected", "true");
    expect(within(screen.getByRole("region", { name: "Rule versions" })).getByText("owner")).toBeInTheDocument();
  });
});
