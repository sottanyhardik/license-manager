/**
 * The workspace tabs, in display order. Planning sits directly after Overview. BOEs, Allotments and
 * Ledger are not tabs. Their information is in Items & Balance and Reconciliation.
 */
export const WORKSPACE_TABS = ["overview", "planning", "items", "invoices", "reconciliation"] as const;

export type WorkspaceTab = (typeof WORKSPACE_TABS)[number];

export const DEFAULT_WORKSPACE_TAB: WorkspaceTab = "overview";

export const WORKSPACE_TAB_LABELS: Record<WorkspaceTab, string> = {
  overview: "Overview",
  planning: "Planning",
  items: "Items & Balance",
  invoices: "Invoices & Sales",
  reconciliation: "Reconciliation",
};

/** A tab value from the UI. Anything unknown falls back to Overview. */
export function asWorkspaceTab(value: string): WorkspaceTab {
  return (WORKSPACE_TABS as readonly string[]).includes(value) ? (value as WorkspaceTab) : DEFAULT_WORKSPACE_TAB;
}
