/**
 * Fixtures for the licence workspace tests. Built on the licence-balance
 * fixtures, so item 101 and its ledger line up with `licence-balances/testData`.
 * Shapes follow `types.ts` and `workspace/types.ts`. Amounts are decimal strings.
 */
import { licenceDetail, itemLedger } from "@/pages/licence-balances/testData";
import type { ItemRow, LicenceDetail } from "@/pages/licence-balances/types";
import type { InvoiceLedger, LedgerRow, LicenceHeader, LicenceTransactions, SourceReconciliation } from "./types";

export const WORKSPACE_LICENCE_ID = 7;
export const WORKSPACE_LICENCE_NUMBER = "0310835341";

/** Over-utilised item with a negative CIF and quantity available. */
const overUtilisedItem: ItemRow = {
  item_id: 102,
  sr: "2",
  description: "Wool blend",
  hs_code: "5101",
  unit: "KGS",
  unit_raw: "kgs",
  unit_status: "VERIFIED",
  cif: {
    original: "500.00",
    debited: "520.00",
    allotted: "0.00",
    invoiced: "0.00",
    invoiced_boe_covered: "0.00",
    available: "-20.00",
    is_over_utilised: true,
    status: "OVER-UTILISED",
  },
  qty: {
    original: "50.000",
    debited: "55.000",
    allotted: "0.000",
    invoiced: "0.000",
    available: "-5.000",
    is_over_utilised: true,
    unit: "KGS",
    status: "OVER-UTILISED",
  },
  status: "OVER-UTILISED",
  flags: ["OVER_UTILISED"],
  previous_owner_debit_cif: "0.00",
  previous_owner_debit_qty: "0.000",
  customers: [],
};

/** Unmapped item whose unit was not verified, so its quantity is withheld. */
const unitItem: ItemRow = {
  item_id: 201,
  sr: "3",
  description: "Mixed chemicals",
  hs_code: null,
  unit: null,
  unit_raw: "mts",
  unit_status: "UNIT_UNVERIFIED",
  cif: {
    original: "0.00",
    debited: "0.00",
    allotted: "0.00",
    invoiced: "0.00",
    invoiced_boe_covered: "0.00",
    available: "0.00",
    is_over_utilised: false,
    status: "UNMAPPED ITEM",
  },
  qty: { status: "UNIT_UNVERIFIED", note: "Unit recorded as 'mts' could not be matched.", unresolved_items: 1 },
  status: "UNMAPPED ITEM",
  flags: ["UNMAPPED_AMOUNT", "UNIT_UNVERIFIED"],
  previous_owner_debit_cif: "0.00",
  previous_owner_debit_qty: "0.000",
  customers: [],
};

export const workspaceDetail: LicenceDetail = {
  ...licenceDetail,
  licence_number: WORKSPACE_LICENCE_NUMBER,
  licence_id: WORKSPACE_LICENCE_ID,
  legacy_status: "MISMATCH",
  legacy_balance_cif: "260.00",
  status: "OVER-UTILISED",
  flags: ["OVER_UTILISED", "LEGACY_BALANCE_DIFFERS"],
  cif: {
    original: "1000.00",
    debited: "1020.00",
    allotted: "0.00",
    invoiced: "0.00",
    invoiced_boe_covered: "0.00",
    available: "-20.00",
    is_over_utilised: true,
    status: "OVER-UTILISED",
  },
  qty: {
    original: "100.000",
    debited: "40.000",
    allotted: "10.000",
    invoiced: "25.000",
    available: "25.000",
    is_over_utilised: false,
    unit: "KGS",
    status: "RECONCILED",
  },
  unverified_qty_items: [{ item_id: 201, sr: "3", unit_raw: "mts", status: "UNIT_UNVERIFIED" }],
  items: [licenceDetail.items[0], overUtilisedItem, unitItem],
};

export const workspaceHeader: LicenceHeader = {
  id: WORKSPACE_LICENCE_ID,
  license_number: WORKSPACE_LICENCE_NUMBER,
  license_date: "01-01-2026",
  license_expiry_date: "31-03-2027",
  ledger_date: "05-01-2026",
  port_name: "INNSA1 Nhava Sheva",
  exporter_name: "ACME Exports",
  exporter_iec: "0300000001",
  get_norm_class: "E5",
  purchase_status_code: "GE",
  purchase_status_label: "General",
  is_expired: false,
};

export const workspaceTransactions: LicenceTransactions = {
  license_id: WORKSPACE_LICENCE_ID,
  boes: [
    {
      item_id: 101,
      sr: "1",
      boe_number: "BOE-1001",
      boe_date: "2026-03-01",
      port: "INNSA1",
      customer: "BUYER LTD",
      cif_fc: "400.00",
      cif_inr: "35000.50",
      qty: "40.000",
      linked_sale_trade_ids: [11, 12],
      linked_sale_invoices: ["LGL/2026-27/0010", "LGL/2026-27/0011"],
      covered_cif: "200.00",
      covered_qty: "20.000",
      uncovered_cif: "200.00",
      uncovered_qty: "20.000",
      previous_owner: false,
      status: "RECONCILED",
      source: { type: "bill_of_entry", id: "1" },
    },
    {
      item_id: 101,
      sr: "1",
      boe_number: "BOE-0999",
      boe_date: "2025-06-10",
      port: "INMAA1",
      customer: null,
      cif_fc: "50.00",
      cif_inr: "4400.00",
      qty: "0.000",
      linked_sale_trade_ids: [],
      linked_sale_invoices: [],
      covered_cif: "0.00",
      covered_qty: "0.000",
      uncovered_cif: "50.00",
      uncovered_qty: "50.000",
      previous_owner: true,
      status: "PREVIOUS OWNER — DEDUCTED",
      source: { type: "bill_of_entry", id: "9" },
    },
  ],
  allotments: [
    {
      item_id: 101,
      sr: "1",
      allotment_id: 55,
      allotment_date: "2026-04-02",
      customer: "BUYER LTD",
      cif_fc: "100.00",
      qty: "10.000",
      boe_covered_cif: "60.00",
      outstanding_cif: "-40.00",
      outstanding_qty: "0.000",
      status: "Allotted",
      source: { type: "allotment", id: "55" },
    },
  ],
  invoices: [
    {
      item_id: 101,
      sr: "1",
      invoice_number: "INV-77",
      invoice_date: "2026-05-01",
      customer: "BUYER LTD",
      cif_fc: "300.00",
      cif_inr: "26000.00",
      qty: "30.000",
      covered_by_boe: "200.00",
      uncovered: "100.00",
      over_linked: false,
      status: "Partial",
      source: { type: "sale", id: "77" },
    },
    {
      item_id: 102,
      sr: "2",
      invoice_number: "INV-78",
      invoice_date: "2026-05-03",
      customer: "OTHER CO",
      cif_fc: "120.00",
      cif_inr: "10400.00",
      qty: "12.000",
      covered_by_boe: "150.00",
      uncovered: "-30.00",
      over_linked: true,
      status: "Over-linked",
      source: { type: "sale", id: "78" },
    },
  ],
};

export { itemLedger };

/** A row of the purchase and sale ledger, with every field defaulted, so fixtures only name what differs. */
export function ledgerRow(overrides: Partial<LedgerRow> & Pick<LedgerRow, "line_id" | "trade_id" | "type" | "invoice">): LedgerRow {
  return {
    date: "2026-05-02",
    particulars: "ABHISHEK TRADELINKS",
    items: "SWP",
    holder_company: "LABDHI GLOBAL LLP",
    sale_cif: null,
    purchase_cif: null,
    sale_bill_inr: null,
    purchase_bill_inr: null,
    cif_inr: null,
    exchange_rate: null,
    effect: "Adds to sale",
    matched_original: null,
    status: "OK",
    counts_in_summary: true,
    related_boes: [],
    source: { type: "trade", id: overrides.trade_id ?? 0, line_id: overrides.line_id, currency: "USD" },
    ...overrides,
  };
}

/**
 * LABDHI has a purchase, two sales, a credit note against the first sale and an
 * unmatched debit note. The second company has no rows. The totals are fixture
 * strings, not computed here.
 */
export const workspaceInvoiceLedger: InvoiceLedger = {
  summary: {
    currency: "USD",
    gross_purchase_cif: "92128.06",
    gross_sale_cif: "63254.58",
    purchase_adjustments_cif: "0.00",
    sale_adjustments_cif: "-1000.00",
    net_purchase_cif: "92128.06",
    net_sale_cif: "62254.58",
    current_balance_cif: "29873.48",
    purchase_bill_inr_gross: "1238942.00",
    sale_bill_inr_gross: "1182594.00",
    purchase_bill_inr_adjustments: "0.00",
    sale_bill_inr_adjustments: "-84000.00",
    net_purchase_bill_inr: "1238942.00",
    net_sale_bill_inr: "1098594.00",
    net_bill_difference_inr: "140348.00",
    unmatched_notes: 1,
    unmatched_note_cif: "500.00",
    canonical_sale_cif: "63254.58",
    canonical_vs_net_sale_difference: "1000.00",
    canonical_gross_check: "0.00",
  },
  companies: [
    {
      company: "LABDHI GLOBAL LLP",
      balance_cif: "29873.48",
      rows: [
        ledgerRow({
          line_id: 1,
          trade_id: 10,
          date: "2025-02-25",
          particulars: "JASH MERCANTILE LLP",
          invoice: "JASH/2025-26/115",
          type: "PURCHASE",
          items: "WHEAT GLUTEN",
          purchase_cif: "92128.06",
          purchase_bill_inr: "1238942.00",
          cif_inr: "7698371.31",
          exchange_rate: "83.5600",
          effect: "Adds to purchase",
          related_boes: ["BOE-1001"],
        }),
        ledgerRow({
          line_id: 2,
          trade_id: 20,
          date: "2026-05-02",
          invoice: "LGL/2026-27/0010",
          type: "SALE",
          sale_cif: "35645.04",
          sale_bill_inr: "463372.00",
          cif_inr: "2978000.00",
          exchange_rate: "83.5500",
        }),
        ledgerRow({
          line_id: 3,
          trade_id: 21,
          date: "2026-05-04",
          particulars: "GOLDEN AGRI RESOURCES (INDIA) PRIVATE LIMITED",
          invoice: "LGL/2026-27/0011",
          type: "SALE",
          items: "RBD PALMOLEIN OIL",
          sale_cif: "27609.54",
          sale_bill_inr: "719222.00",
          cif_inr: "2305000.00",
          exchange_rate: "83.4700",
          related_boes: ["BOE-1002"],
        }),
        ledgerRow({
          line_id: 4,
          trade_id: 30,
          date: "2026-06-08",
          invoice: "CREDIT NOTE LGL/2026-27/0010",
          type: "CREDIT NOTE",
          sale_cif: "-1000.00",
          sale_bill_inr: "-84000.00",
          effect: "Reduces sale (credit note)",
          matched_original: { trade_id: 20, line_id: 2, invoice: "LGL/2026-27/0010", side: "SALE" },
          status: "MATCHED TO ORIGINAL",
        }),
        ledgerRow({
          line_id: 5,
          trade_id: 31,
          date: "2026-06-10",
          particulars: "ZETA TRADERS",
          invoice: "DEBIT NOTE ZTR/2026-27/0003",
          type: "DEBIT NOTE",
          items: "WHEAT",
          purchase_cif: "500.00",
          purchase_bill_inr: "42000.00",
          effect: "Not netted (review)",
          status: "UNMATCHED NOTE: no original invoice found",
          counts_in_summary: false,
        }),
      ],
    },
    {
      company: "NORTHSTAR AGRO LLP",
      balance_cif: "0.00",
      rows: [],
    },
  ],
};

/** Source-level reconciliation: SR 1 has a CIF difference and a BOE needing review; SR 3 has a unit withheld. */
export const workspaceSourceReconciliation: SourceReconciliation = {
  license_id: WORKSPACE_LICENCE_ID,
  items_not_reconciled: 1,
  issue_count: 1,
  items: [
    {
      item_id: 101,
      sr: "1",
      description: "Cotton yarn",
      canonical_status: "REVIEW REQUIRED",
      reconciliation: {
        status: "MISMATCH",
        cif: [
          { field: "debited", status: "MISMATCH", drill: "400.00", item_table: "390.00", difference: "10.00" },
          { field: "allotted", status: "RECONCILED", drill: "100.00", item_table: "100.00", difference: "0.00" },
          { field: "invoiced", status: "RECONCILED", drill: "250.00", item_table: "250.00", difference: "0.00" },
          { field: "available", status: "RECONCILED", drill: "600.00", item_table: "600.00", difference: "0.00" },
        ],
        qty: [
          { field: "debited", status: "RECONCILED", drill: "40.000", item_table: "40.000", difference: "0.000" },
          { field: "allotted", status: "RECONCILED", drill: "10.000", item_table: "10.000", difference: "0.000" },
          { field: "invoiced", status: "RECONCILED", drill: "25.000", item_table: "25.000", difference: "0.000" },
          { field: "available", status: "RECONCILED", drill: "60.000", item_table: "60.000", difference: "0.000" },
        ],
      },
      issues: [
        {
          kind: "BOE",
          reference: "BOE-0999",
          source: { type: "bill_of_entry", id: "9" },
          status: "LINKED TO AN OVER-LINKED SALE (excess counted on the invoice)",
          flags: ["OVER_LINKED_MIXED_OWNERSHIP: excess ownership not determined (review)"],
          amount: { qty: "0.000", cif: "50.00" },
        },
      ],
    },
    {
      item_id: 201,
      sr: "3",
      description: "Mixed chemicals",
      canonical_status: "UNMAPPED ITEM",
      reconciliation: {
        status: "RECONCILED",
        cif: [
          { field: "debited", status: "RECONCILED", drill: "0.00", item_table: "0.00", difference: "0.00" },
          { field: "allotted", status: "RECONCILED", drill: "0.00", item_table: "0.00", difference: "0.00" },
          { field: "invoiced", status: "RECONCILED", drill: "0.00", item_table: "0.00", difference: "0.00" },
          { field: "available", status: "RECONCILED", drill: "0.00", item_table: "0.00", difference: "0.00" },
        ],
        qty: [
          { field: "debited", status: "UNIT_UNVERIFIED" },
          { field: "allotted", status: "UNIT_UNVERIFIED" },
          { field: "invoiced", status: "UNIT_UNVERIFIED" },
          { field: "available", status: "UNIT_UNVERIFIED" },
        ],
      },
      issues: [],
    },
  ],
};
