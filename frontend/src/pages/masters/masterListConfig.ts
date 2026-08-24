/**
 * Per-entity configuration for the Master list view.
 *
 * First step of decomposing the MasterList god-component (2k LOC): pure,
 * entity-keyed configuration is pulled out here so it can be unit-tested and so
 * the eventual config-driven <EntityTable> has a home for column/action configs.
 */

/** Default list filters applied when a Master entity list first loads. */
export function getDefaultFilters(entityName: string): Record<string, string> {
  switch (entityName) {
    case "allotments":
      // The list contract uses the explicit `all` sentinel to opt out of the
      // server's default allotted-only filter.  This keeps the default list
      // complete while preserving the non-BOE AT scope.
      return { type: "AT", is_boe: "False", is_allotted: "all" };
    case "bill-of-entries":
      return { is_invoice: "False" };
    case "incentive-licenses":
      // Empty string = "All" (shows both sold and unsold).
      return { sold_status: "" };
    default:
      return {};
  }
}
