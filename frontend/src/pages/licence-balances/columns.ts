/** Column metadata for the licence balance table. */

export const COLUMN_STORAGE_KEY = "licence-balances.columns";

/** Columns the user can reveal. Everything else is always shown in the compact view. */
export const OPTIONAL_COLUMNS = [
  { id: "qtyOriginal", label: "Original qty" },
  { id: "qtyDebited", label: "Debited qty" },
  { id: "qtyAllotted", label: "Allotted qty" },
  { id: "qtyInvoiced", label: "Invoiced qty" },
  { id: "legacy", label: "Legacy balance" },
] as const;

export type OptionalColumnId = (typeof OPTIONAL_COLUMNS)[number]["id"];
