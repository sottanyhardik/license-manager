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
