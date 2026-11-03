/**
 * Wire types the licence workspace reads beyond `licence-balances/types.ts`.
 *
 * Money and quantity are decimal STRINGS. Nothing here converts or sums them.
 */
import type { Decimal } from "@/pages/licence-balances/types";

/** Legacy header fields from `GET licenses/{id}/` (LicenseDetailsSerializer). Only the fields the workspace shows. */
export interface LicenceHeader {
  id: number;
  license_number: string | null;
  /** Indian display format, DD-MM-YYYY. */
  license_date: string | null;
  license_expiry_date: string | null;
  ledger_date: string | null;
  port_name: string | null;
  /** The exporter FK. For an import licence this is the licence holder's name. */
  exporter_name: string | null;
  exporter_iec: string | null;
  get_norm_class: string | null;
  purchase_status_code: string | null;
  purchase_status_label: string | null;
  is_expired?: boolean | null;
  /** Null and false both mean the licence-level CIF calculation. Only true changes it. */
  individual_item_cif_override?: boolean | null;
}

export interface SourceRef {
  type: string;
  id: string;
}

export interface BoeRow {
  item_id: number;
  sr: string;
  boe_number: string;
  boe_date: string | null;
  port: string | null;
  customer: string | null;
  cif_fc: Decimal;
  cif_inr: Decimal;
  qty: Decimal;
  linked_sale_trade_ids: number[];
  /** Invoice numbers of the sales this BOE is linked to, in the same order as the trade ids. */
  linked_sale_invoices: string[];
  covered_cif: Decimal;
  covered_qty: Decimal;
  uncovered_cif: Decimal;
  uncovered_qty: Decimal;
  /** True for a previous owner's BOE. Its debit is deducted like any other BOE. */
  previous_owner: boolean;
  status: string;
  source: SourceRef;
}

export interface AllotmentRow {
  item_id: number;
  sr: string;
  allotment_id: number;
  allotment_date: string | null;
  customer: string | null;
  cif_fc: Decimal;
  qty: Decimal;
  boe_covered_cif: Decimal;
  outstanding_cif: Decimal;
  outstanding_qty: Decimal;
  status: string;
  source: SourceRef;
}

export interface InvoiceRow {
  item_id: number;
  sr: string;
  invoice_number: string;
  invoice_date: string | null;
  customer: string | null;
  cif_fc: Decimal;
  cif_inr: Decimal;
  qty: Decimal;
  covered_by_boe: Decimal;
  uncovered: Decimal;
  over_linked: boolean;
  status: string;
  source: SourceRef;
}

/** `GET licence-balances/{id}/transactions/`. */
export interface LicenceTransactions {
  license_id: number;
  boes: BoeRow[];
  allotments: AllotmentRow[];
  invoices: InvoiceRow[];
}

export type LedgerRowType = "PURCHASE" | "SALE" | "CREDIT NOTE" | "DEBIT NOTE";

export interface LedgerMatchedOriginal {
  trade_id: number;
  line_id: number;
  invoice: string;
  side: "PURCHASE" | "SALE";
}

/** One purchase, sale, credit note or debit note. Signed amounts: a credit note is negative in its column. */
export interface LedgerRow {
  line_id: number;
  trade_id: number;
  /** ISO `YYYY-MM-DD`, or null when the trade has no date. */
  date: string | null;
  /** The counterparty. */
  particulars: string;
  /** Invoice text as stored. A note may read "CREDIT NOTE ...". */
  invoice: string;
  type: LedgerRowType;
  items: string;
  holder_company: string;
  classification?: "EXTERNAL" | "INTERNAL";
  classification_reason?: string;
  sale_cif: Decimal;
  purchase_cif: Decimal;
  sale_bill_inr: Decimal;
  purchase_bill_inr: Decimal;
  cif_inr: Decimal;
  exchange_rate: Decimal;
  effect: string;
  matched_original: LedgerMatchedOriginal | null;
  /** "OK", "MATCHED TO ORIGINAL", or "UNMATCHED NOTE: ..." and similar. */
  status: string;
  counts_in_summary: boolean;
  /** BOE numbers linked to this invoice. */
  related_boes: string[];
  source: { type: string; id: number; line_id: number; currency: string };
}

/** Licence-level totals. Every amount is a decimal string produced by the backend. */
export interface InvoiceLedgerSummary {
  currency: string;
  gross_purchase_cif: Decimal;
  gross_sale_cif: Decimal;
  purchase_adjustments_cif: Decimal;
  sale_adjustments_cif: Decimal;
  net_purchase_cif: Decimal;
  net_sale_cif: Decimal;
  current_balance_cif: Decimal;
  purchase_bill_inr_gross: Decimal;
  sale_bill_inr_gross: Decimal;
  purchase_bill_inr_adjustments: Decimal;
  sale_bill_inr_adjustments: Decimal;
  net_purchase_bill_inr: Decimal;
  net_sale_bill_inr: Decimal;
  net_bill_difference_inr: Decimal;
  unmatched_notes: number;
  unmatched_note_cif: Decimal;
  canonical_sale_cif?: Decimal;
  canonical_vs_net_sale_difference?: Decimal;
  canonical_gross_check?: Decimal;
  gross_internal_sale_cif?: Decimal;
  gross_sale_all_cif?: Decimal;
  internal_sale_bill_inr?: Decimal;
  internal_row_count?: number;
}

export interface InvoiceLedgerCompany {
  company: string;
  balance_cif: Decimal;
  internal_cif?: Decimal;
  rows: LedgerRow[];
}

/** `GET licence-balances/{id}/invoice-ledger/`. */
export interface InvoiceLedger {
  summary: InvoiceLedgerSummary;
  companies: InvoiceLedgerCompany[];
}

/** Quantity and CIF of one source record, quantity first. Both are null when the quantity is withheld. */
export interface IssueAmount {
  qty: Decimal;
  cif: Decimal;
}

/** A source record that needs review: a BOE, an invoice or an allotment, with its amount. */
export interface AllocationIssue {
  kind: "BOE" | "INVOICE" | "ALLOTMENT";
  reference: string;
  source: SourceRef;
  status: string;
  flags: string[];
  amount: IssueAmount;
}

/** One figure compared with the item table. Amounts are absent when the figure is withheld. */
export interface SourceReconciliationLine {
  field: "debited" | "allotted" | "invoiced" | "available";
  status: string;
  drill?: Decimal;
  item_table?: Decimal;
  difference?: Decimal;
}

export interface SourceReconciliationItem {
  item_id: number;
  sr: string;
  description: string;
  canonical_status: string;
  reconciliation: {
    status: string;
    cif: SourceReconciliationLine[];
    qty: SourceReconciliationLine[];
  };
  issues: AllocationIssue[];
}

/** Source-level reconciliation for a licence, from the same per-item drill-downs as Items & Balance. */
export interface SourceReconciliation {
  license_id: number;
  items: SourceReconciliationItem[];
  items_not_reconciled: number;
  issue_count: number;
}
