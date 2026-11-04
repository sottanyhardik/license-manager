/**
 * Wire types for `/api/licence-balances/`.
 *
 * Money and quantity arrive as decimal STRINGS. The frontend never converts
 * them to numbers, sums them or compares them arithmetically. It only groups
 * and colours the digits for display (see format.ts).
 */

/** A decimal string such as "1234.50" or "-40.000", or null when the backend withholds it. */
export type Decimal = string | null;

/**
 * One CIF or quantity block. Its shape depends on the situation:
 * - full block: every amount, `is_over_utilised`, `status` and (quantity) `unit`
 * - unit unverified (summary quantity): only `status: "UNIT_UNVERIFIED"`, `note`, `unresolved_items`
 * - not computable (item-level OVER-ALLOCATED): `status` and `error`, amounts absent or null
 * A missing amount field is treated exactly like null.
 */
export interface BalanceBlock {
  original?: Decimal;
  debited?: Decimal;
  allotted?: Decimal;
  invoiced?: Decimal;
  invoiced_boe_covered?: Decimal;
  available?: Decimal;
  is_over_utilised?: boolean;
  status: string;
  /**
   * Item CIF only. "LICENCE" means the licence's pooled CIF decides over-utilisation and this
   * figure is attribution. "ITEM" means the item's own CIF is enforced (Individual Item CIF ON).
   */
  cif_control?: "LICENCE" | "ITEM";
  /** Item CIF only, under licence-level control: the status the item would have under item-level control. */
  raw_status?: string;
  unit?: string | null;
  flags?: string[];
  identity_ok?: boolean;
  error?: string;
  note?: string;
  unresolved_items?: number;
}

export interface UnverifiedQuantityItem {
  item_id: number;
  sr: string;
  unit_raw: string | null;
  status: string;
}

export interface LicenceSummary {
  licence_id: number;
  licence_number: string;
  importer: string;
  expiry_date: string | null;
  cif: BalanceBlock;
  qty: BalanceBlock;
  previous_owner_debit_cif: Decimal;
  previous_owner_debit_qty: Decimal;
  legacy_balance_cif: Decimal;
  legacy_status: "RECONCILED" | "MISMATCH" | "";
  status: string;
  flags: string[];
  unverified_qty_items: UnverifiedQuantityItem[];
  /** "LICENCE" for licence-level CIF control (Individual Item CIF OFF), "ITEM" for item-level control. */
  cif_control?: "LICENCE" | "ITEM";
  /** Licence-level control only: the pooled result with unverified sales as external, and as internal. */
  cif_scenarios?: {
    base_available: Decimal;
    alternative_available: Decimal | null;
    unverified_trade_ids: number[];
  } | null;
}

export interface BalanceListResponse {
  count: number;
  /** The page the backend actually served. It can differ from the requested page (clamped to the last page). */
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
  results: LicenceSummary[];
}

export interface CustomerRow {
  customer: string;
  invoice: string;
  /** CIF (2 decimals). */
  sold: Decimal;
  /** Quantity (3 decimals). */
  sold_qty: Decimal;
  /** CIF (2 decimals). */
  covered_by_boe: Decimal;
  /** CIF (2 decimals). */
  remaining_entitlement: Decimal;
}

export interface ItemRow {
  item_id: number;
  sr: string;
  description: string;
  hs_code: string | null;
  unit: string | null;
  unit_raw: string | null;
  unit_status: "VERIFIED" | "UNIT_UNVERIFIED";
  cif: BalanceBlock;
  qty: BalanceBlock;
  status: string;
  flags: string[];
  previous_owner_debit_cif: Decimal;
  previous_owner_debit_qty: Decimal;
  customers: CustomerRow[];
  /** "LICENCE" (licence-level control) or "ITEM" (Individual Item CIF ON). Decided by the backend. */
  cif_control?: "LICENCE" | "ITEM";
  /**
   * The Available CIF this row shows, from the backend. Under licence-level control it is the licence's
   * balance, identical on every row and never summed. Under item-level control it is the item's own balance.
   */
  available_cif_display?: Decimal;
}

export interface LicenceDetail extends LicenceSummary {
  items: ItemRow[];
}

export type MovementKind =
  | "ORIGINAL"
  | "SALE"
  | "SALE_COVERED_BOE"
  | "BOE_DEBIT"
  | "OVER_LINKED_EXCESS"
  | "ALLOTMENT"
  | "HIDDEN_PREVIOUS_OWNER_BOE";

export interface Movement {
  kind: MovementKind | string;
  date: string | null;
  reference: string;
  customer: string;
  sr: string;
  debit: Decimal;
  credit: Decimal;
  running_balance: Decimal;
  link_status: string;
  source: { type: string; id: string };
  /** Memo rows (SALE_COVERED_BOE, HIDDEN_PREVIOUS_OWNER_BOE) never change the running balance. */
  memo: boolean;
  /** True when the row is a previous owner's BOE. Its debit is deducted, not a memo. */
  previous_owner: boolean;
}

/** `/licence-balances/{licence_id}/items/{item_id}/`. */
export interface ItemLedger extends ItemRow {
  cif_movements: Movement[];
  qty_movements: Movement[];
}

/** The three drill-down groups behind an item's Debited, Allotted and Invoiced figures. */
export type DrilldownGroup = "boes" | "allotments" | "invoices";

/** Which figure the drawer shows: CIF (USD) or quantity. Each is opened on its own. */
export type DrilldownMeasure = "cif" | "qty";

export interface SourceRef {
  type: string;
  id: number | null;
}

export interface SaleLink {
  trade_id: number;
  invoice_number: string;
  cif: Decimal;
  qty: Decimal;
  /** ALLOCATION when an active invoice-BOE allocation record exists, otherwise FULL BOE. */
  basis: string;
}

/** A BOE debit row, or an over-linked excess row (kind OVER_LINKED_EXCESS, no BOE). */
export interface DrilldownBoeRow {
  kind: "BOE" | "OVER_LINKED_EXCESS";
  row_id: number | null;
  boe_number: string;
  boe_date: string | null;
  port: string;
  importer: string;
  sr: string;
  hs_code: string | null;
  currency: string;
  invoice_number: string | null;
  boe_cif: Decimal;
  boe_qty: Decimal;
  cif_inr: Decimal;
  covered_cif: Decimal;
  covered_qty: Decimal;
  debited_cif: Decimal;
  debited_qty: Decimal;
  /** True for a previous owner's BOE. Its debit is deducted like any other, and reported separately. */
  previous_owner: boolean;
  sale_links: SaleLink[];
  allotment_ids: number[];
  status: string;
  flags: string[];
  source: SourceRef;
}

export interface DrilldownAllotmentBoe {
  boe_id: number;
  boe_number: string;
  boe_date: string | null;
  on_this_item: boolean;
  previous_owner: boolean;
  debit_on_item_cif: Decimal;
  debit_on_item_qty: Decimal;
  row_ids: number[];
}

export interface DrilldownAllotmentRow {
  kind: "ALLOTMENT";
  allotment_id: number;
  allotment_item_id: number;
  reference: string;
  allotment_date: string | null;
  customer: string;
  sr: string;
  original_cif: Decimal;
  original_qty: Decimal;
  boe_linked_cif: Decimal;
  boe_linked_qty: Decimal;
  /** Always null: the data model has no allotment-to-invoice link, so this is not recorded. */
  invoice_linked_cif: Decimal;
  invoice_linked_qty: Decimal;
  outstanding_cif: Decimal;
  outstanding_qty: Decimal;
  status: string;
  source_status: string;
  linked_boes: DrilldownAllotmentBoe[];
  flags: string[];
  source: SourceRef;
}

export interface DrilldownInvoiceBoe {
  row_id: number;
  boe_number: string;
  boe_date: string | null;
  port: string;
  importer: string;
  cif: Decimal;
  qty: Decimal;
  basis: string;
  previous_owner: boolean;
}

export interface DrilldownInvoiceRow {
  kind: "INVOICE";
  trade_id: number;
  invoice_number: string;
  document_type: "SALE" | "CREDIT NOTE" | "DEBIT NOTE" | string;
  referenced_invoice: string | null;
  invoice_date: string | null;
  customer: string;
  sr: string;
  currency: string;
  sold_cif: Decimal;
  sold_qty: Decimal;
  sold_cif_inr: Decimal;
  covered_by_boe_cif: Decimal;
  covered_by_boe_qty: Decimal;
  uncovered_cif: Decimal;
  uncovered_qty: Decimal;
  over_linked_cif: Decimal;
  over_linked_qty: Decimal;
  /** The part of this invoice that is in the item's Invoiced figure today. */
  current_balance_cif: Decimal;
  counts_in_current_balance: boolean;
  /** INTERNAL trades are group-company sales. They are listed for audit and are not external utilisation. */
  classification?: "EXTERNAL" | "INTERNAL";
  classification_reason?: string;
  classification_authorised_by?: string | null;
  classification_authorised_on?: string | null;
  linked_boes: DrilldownInvoiceBoe[];
  boes_without_debit_on_item: { boe_id: number; boe_number: string; boe_date: string | null }[];
  status: string;
  flags: string[];
  source: SourceRef;
}

/** One figure compared with the item table. Amounts are absent when the figure is withheld or not computed. */
export interface DrilldownReconciliationLine {
  field: "debited" | "allotted" | "invoiced" | "available";
  status: string;
  drill?: Decimal;
  item_table?: Decimal;
  difference?: Decimal;
}

export interface DrilldownGroupBlock<Row, Totals> {
  totals: Totals;
  rows: Row[];
}

export interface BoeDrilldownTotals {
  /** BOE rows, current and previous owner. */
  boe_rows: number;
  /** Of boe_rows: previous owner's BOEs, deducted. */
  previous_owner_rows: number;
  boe_cif: Decimal;
  covered_cif: Decimal;
  /** Uncovered debit of current-owner BOEs. */
  uncovered_cif: Decimal;
  /** Uncovered debit of previous-owner BOEs, plus over-linked excess attributable to them. */
  previous_owner_debit_cif: Decimal;
  /** Over-linked excess not attributable to previous-owner BOEs. */
  over_linked_cif: Decimal;
  /** uncovered_cif + previous_owner_debit_cif + over_linked_cif: the item's Debited figure. */
  debited_cif: Decimal;
  boe_qty: Decimal;
  covered_qty: Decimal;
  uncovered_qty: Decimal;
  previous_owner_debit_qty: Decimal;
  over_linked_qty: Decimal;
  debited_qty: Decimal;
}

export interface AllotmentDrilldownTotals {
  allotment_rows: number;
  cancelled_rows: number;
  original_cif: Decimal;
  boe_linked_cif: Decimal;
  invoice_linked_cif: Decimal;
  outstanding_cif: Decimal;
  cancelled_cif_excluded: Decimal;
  original_qty: Decimal;
  boe_linked_qty: Decimal;
  outstanding_qty: Decimal;
}

export interface InvoiceDrilldownTotals {
  invoice_rows: number;
  sold_cif: Decimal;
  sold_qty: Decimal;
  covered_by_boe_cif: Decimal;
  covered_by_boe_qty: Decimal;
  uncovered_cif: Decimal;
  uncovered_qty: Decimal;
  over_linked_cif: Decimal;
  over_linked_qty: Decimal;
  current_balance_cif: Decimal;
  /** Gross INTERNAL sales. Listed for audit; never counted as external utilisation. */
  internal_invoice_rows?: number;
  internal_sold_cif?: Decimal;
  internal_sold_qty?: Decimal;
  gross_sold_cif?: Decimal;
}

export interface ItemDrilldown {
  license_id: number;
  item: {
    item_id: number;
    sr: string;
    description: string;
    hs_code: string | null;
    unit: string | null;
    unit_raw: string | null;
    unit_status: "VERIFIED" | "UNIT_UNVERIFIED";
    currency: string;
    original_cif: Decimal;
    original_qty: Decimal;
  };
  canonical: {
    status: string;
    previous_owner_debit_cif: Decimal;
    previous_owner_debit_qty: Decimal;
    cif: Partial<Record<"original" | "debited" | "allotted" | "invoiced" | "available", Decimal>>;
    qty: Partial<Record<"original" | "debited" | "allotted" | "invoiced" | "available", Decimal>>;
  };
  boes: DrilldownGroupBlock<DrilldownBoeRow, BoeDrilldownTotals>;
  allotments: DrilldownGroupBlock<DrilldownAllotmentRow, AllotmentDrilldownTotals>;
  invoices: DrilldownGroupBlock<DrilldownInvoiceRow, InvoiceDrilldownTotals>;
  reconciliation: {
    status: string;
    cif: DrilldownReconciliationLine[];
    qty: DrilldownReconciliationLine[];
  };
}
