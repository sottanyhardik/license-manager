/**
 * Per-entity configuration for the Master list view.
 *
 * First step of decomposing the MasterList god-component (2k LOC): pure,
 * entity-keyed configuration is pulled out here so it can be unit-tested and so
 * the eventual config-driven <EntityTable> has a home for column/action configs.
 */

/**
 * Masters whose detail route is keyed by a field other than the primary key
 * (`lookup_field` on the backend viewset, `apps/core/views/views.py`).
 * Building their URLs from `id` would 404 — or address another record whose
 * code happens to equal that id.
 */
export const MASTER_LOOKUP_FIELDS: Readonly<Record<string, string>> = {
  "scheme-codes": "code",
  "notification-numbers": "code",
};

/**
 * URL-safe record key for `/masters/<entity>/<key>/` (API) and
 * `/masters/<entity>/<key>/edit` (UI). Codes such as `025/2023` are encoded.
 */
export function getMasterRecordKey(entityName: string, item: { id?: unknown } & Record<string, unknown>): string {
  return encodeURIComponent(getMasterRecordLookup(entityName, item));
}

/** The raw lookup value (`025/2023`, `7`) — what the bulk API takes in `keys`. */
export function getMasterRecordLookup(entityName: string, item: { id?: unknown } & Record<string, unknown>): string {
  const field = MASTER_LOOKUP_FIELDS[entityName] ?? "id";
  const value = item[field];
  if (value === null || value === undefined || value === "") {
    // Never build `masters/<entity>//` — that would address the list endpoint.
    throw new Error(`${entityName} record has no ${field}`);
  }
  return String(value);
}

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
    case "trades":
      // A bill/invoice list is operationally reviewed newest first.  Make the
      // request explicit rather than relying on model/API default ordering,
      // which can be superseded by a persisted filter or a proxy endpoint.
      return { ordering: "-invoice_date" };
    case "incentive-licenses":
      // Empty string = "All" (shows both sold and unsold).
      return { sold_status: "" };
    default:
      return {};
  }
}
