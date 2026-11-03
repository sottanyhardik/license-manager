/**
 * Column definitions and the persisted column-visibility choice for the
 * Invoices & Sales ledger. Only the hidden columns are stored, so a column
 * added later shows by default. Storage failures fall back to in-memory state.
 */
import { useCallback, useEffect, useState } from "react";

export type LedgerColumnId =
  | "date"
  | "particulars"
  | "invoice"
  | "type"
  | "items"
  | "sale"
  | "purchase"
  | "saleBill"
  | "purchaseBill";

export const LEDGER_COLUMN_IDS: readonly LedgerColumnId[] = [
  "date",
  "particulars",
  "invoice",
  "type",
  "items",
  "sale",
  "purchase",
  "saleBill",
  "purchaseBill",
];

/** These columns identify the row and can never be hidden. */
const LOCKED_COLUMN_IDS: ReadonlySet<LedgerColumnId> = new Set(["particulars", "invoice", "type"]);

export const COLUMN_STORAGE_KEY = "licence-invoices-columns";

export interface LedgerColumn {
  id: LedgerColumnId;
  label: string;
  numeric: boolean;
  locked: boolean;
}

/** The nine columns in display order. CIF labels carry the ledger's currency code. */
export function ledgerColumns(currency: string): LedgerColumn[] {
  return [
    { id: "date", label: "Date", numeric: false, locked: false },
    { id: "particulars", label: "Particulars", numeric: false, locked: true },
    { id: "invoice", label: "Invoice", numeric: false, locked: true },
    { id: "type", label: "Type", numeric: false, locked: true },
    { id: "items", label: "Items", numeric: false, locked: false },
    { id: "sale", label: `Sale (${currency})`, numeric: true, locked: false },
    { id: "purchase", label: `Purchase (${currency})`, numeric: true, locked: false },
    { id: "saleBill", label: "Sale Bill (₹)", numeric: true, locked: false },
    { id: "purchaseBill", label: "Purchase Bill (₹)", numeric: true, locked: false },
  ];
}

const KNOWN_IDS: ReadonlySet<string> = new Set(LEDGER_COLUMN_IDS);

/** Parses the stored list of hidden column ids. Unknown and locked ids are dropped. */
export function parseHiddenColumns(raw: string | null): Set<LedgerColumnId> {
  if (!raw) return new Set();
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();
    return new Set(
      parsed.filter(
        (id): id is LedgerColumnId => typeof id === "string" && KNOWN_IDS.has(id) && !LOCKED_COLUMN_IDS.has(id as LedgerColumnId),
      ),
    );
  } catch {
    return new Set();
  }
}

function readStoredHidden(): Set<LedgerColumnId> {
  try {
    return parseHiddenColumns(window.localStorage.getItem(COLUMN_STORAGE_KEY));
  } catch {
    return new Set();
  }
}

export function isLockedColumn(id: LedgerColumnId): boolean {
  return LOCKED_COLUMN_IDS.has(id);
}

export function useInvoiceColumns() {
  const [hidden, setHidden] = useState<Set<LedgerColumnId>>(readStoredHidden);

  useEffect(() => {
    try {
      window.localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify([...hidden]));
    } catch {
      // Persistence is best effort; the in-memory choice still applies.
    }
  }, [hidden]);

  const setColumnVisible = useCallback((id: LedgerColumnId, visible: boolean) => {
    if (LOCKED_COLUMN_IDS.has(id)) return;
    setHidden((current) => {
      if (current.has(id) === !visible) return current;
      const next = new Set(current);
      if (visible) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  return { hidden, setColumnVisible };
}
