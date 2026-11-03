/** Shared fixtures for the licence balance tests. Shapes follow the API contract in types.ts. */
import type { BalanceListResponse, ItemLedger, LicenceDetail, LicenceSummary, Movement } from "./types";

export const reconciledSummary: LicenceSummary = {
  licence_id: 7,
  licence_number: "0310835341",
  importer: "ACME Exports",
  expiry_date: "2027-03-31",
  cif: {
    original: "1000.00",
    debited: "400.00",
    allotted: "100.00",
    invoiced: "250.00",
    invoiced_boe_covered: "250.00",
    available: "250.00",
    is_over_utilised: false,
    status: "RECONCILED",
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
  previous_owner_debit_cif: "0.00",
  previous_owner_debit_qty: "0.000",
  legacy_balance_cif: "250.00",
  legacy_status: "RECONCILED",
  status: "RECONCILED",
  flags: [],
  unverified_qty_items: [],
};

/** Over-utilised CIF (negative available) with an unverified quantity unit. */
export const overUtilisedSummary: LicenceSummary = {
  licence_id: 9,
  licence_number: "0310835999",
  importer: "Beta Trading",
  expiry_date: "2025-01-15",
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
    status: "UNIT_UNVERIFIED",
    note: "Unit recorded as 'mts' could not be matched to a unit of measure.",
    unresolved_items: 1,
  },
  previous_owner_debit_cif: "0.00",
  previous_owner_debit_qty: "0.000",
  legacy_balance_cif: null,
  legacy_status: "",
  status: "OVER-UTILISED",
  flags: ["OVER_UTILISED", "UNIT_UNVERIFIED"],
  unverified_qty_items: [{ item_id: 201, sr: "3", unit_raw: "mts", status: "UNIT_UNVERIFIED" }],
};

export function listResponse(overrides: Partial<BalanceListResponse> = {}): BalanceListResponse {
  return {
    count: 2,
    page: 1,
    page_size: 25,
    total_pages: 1,
    has_next: false,
    has_previous: false,
    results: [reconciledSummary, overUtilisedSummary],
    ...overrides,
  };
}

/** Licence detail with one item, a memo-bearing legacy mismatch and a customer sale. */
export const licenceDetail: LicenceDetail = {
  ...reconciledSummary,
  previous_owner_debit_cif: "50.00",
  previous_owner_debit_qty: "50.000",
  legacy_balance_cif: "260.00",
  legacy_status: "MISMATCH",
  items: [
    {
      item_id: 101,
      sr: "1",
      description: "Cotton yarn",
      hs_code: null,
      unit: "MTS",
      unit_raw: "mts",
      unit_status: "VERIFIED",
      cif: {
        original: "1000.00",
        debited: "400.00",
        allotted: "100.00",
        invoiced: "250.00",
        invoiced_boe_covered: "250.00",
        available: "600.00",
        is_over_utilised: false,
        status: "RECONCILED",
      },
      qty: {
        original: "100.000",
        debited: "40.000",
        allotted: "10.000",
        invoiced: "25.000",
        available: "60.000",
        is_over_utilised: false,
        unit: "MTS",
        status: "RECONCILED",
      },
      status: "REVIEW REQUIRED",
      flags: ["OVER_LINKED_MIXED_OWNERSHIP"],
      previous_owner_debit_cif: "50.00",
      previous_owner_debit_qty: "50.000",
      customers: [
        {
          customer: "BUYER LTD",
          invoice: "INV-1",
          sold: "300.00",
          sold_qty: "30.000",
          covered_by_boe: "200.00",
          remaining_entitlement: "100.00",
        },
      ],
    },
  ],
};

function movement(overrides: Partial<Movement>): Movement {
  return {
    kind: "ORIGINAL",
    date: null,
    reference: "",
    customer: "",
    sr: "1",
    debit: null,
    credit: null,
    running_balance: null,
    link_status: "",
    source: { type: "licence", id: "7" },
    memo: false,
    previous_owner: false,
    ...overrides,
  };
}

/** Item 101 ledger. The last balance-changing row (600.00) matches the item's CIF available. */
export const itemLedger: ItemLedger = {
  ...licenceDetail.items[0],
  cif_movements: [
    movement({ kind: "ORIGINAL", date: "2026-01-10", reference: "AUTH-1", running_balance: "1000.00" }),
    movement({
      kind: "BOE_DEBIT",
      date: "2026-02-01",
      reference: "BOE-9",
      debit: "400.00",
      running_balance: "600.00",
      link_status: "UNCOVERED",
      source: { type: "bill_of_entry", id: "9" },
    }),
    movement({
      kind: "SALE_COVERED_BOE",
      date: "2026-03-01",
      reference: "BOE-9",
      customer: "BUYER LTD",
      debit: "200.00",
      running_balance: "600.00",
      link_status: "COVERED BY SALE",
      memo: true,
    }),
  ],
  qty_movements: [
    movement({ kind: "ORIGINAL", date: "2026-01-10", reference: "AUTH-1", running_balance: "100.000" }),
    movement({
      kind: "BOE_DEBIT",
      date: "2026-02-01",
      reference: "BOE-9",
      debit: "40.000",
      running_balance: "60.000",
      source: { type: "bill_of_entry", id: "9" },
    }),
  ],
};
