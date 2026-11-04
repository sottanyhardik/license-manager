import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ItemBalanceTable from "./ItemBalanceTable";
import type { BalanceBlock, ItemRow } from "./types";

const EMPTY_CIF: BalanceBlock = { status: "RECONCILED" };

function item(overrides: Partial<ItemRow> & Pick<ItemRow, "item_id" | "sr">): ItemRow {
  return {
    description: `Item ${overrides.sr}`,
    hs_code: "11010000",
    unit: "kg",
    unit_raw: "kg",
    unit_status: "VERIFIED",
    cif: EMPTY_CIF,
    qty: { status: "RECONCILED", original: "100.000", debited: "0.000", allotted: "0.000", invoiced: "0.000", available: "100.000", unit: "kg" },
    status: "RECONCILED",
    flags: [],
    previous_owner_debit_cif: "0.00",
    previous_owner_debit_qty: "0.000",
    customers: [],
    ...overrides,
  };
}

/** Column index in the Items & Balance table (0-based), in the order the spec requires. */
const COL = { SR: 0, AVAILABLE_QTY: 12, AVAILABLE_CIF: 13, CIF_CONTROL: 14, STATUS: 15 } as const;

function bodyRows() {
  const table = screen.getByTestId("item-table");
  // The first two rows are the header rows.
  return within(table).getAllByRole("row").slice(2);
}

function cellText(row: HTMLElement, index: number) {
  return within(row).getAllByRole("cell")[index].textContent ?? "";
}

describe("ItemBalanceTable: licence-level CIF control (Individual Item CIF OFF)", () => {
  // Three rows. Item 1 has a positive item-level CIF, item 2 a negative one. Under licence-level control
  // every row shows the licence's balance, 1,006.98, and that figure is never added across rows.
  const licenceControlled: ItemRow[] = [
    item({
      item_id: 1,
      sr: "1",
      cif: { status: "LICENCE-LEVEL CONTROL", available: "52036.43", cif_control: "LICENCE", is_over_utilised: false },
      qty: { status: "RECONCILED", available: "32885.810", unit: "kg" },
      available_cif_display: "1006.98",
      cif_control: "LICENCE",
    }),
    item({
      item_id: 2,
      sr: "3",
      cif: { status: "LICENCE-LEVEL CONTROL", available: "-14900.36", cif_control: "LICENCE", is_over_utilised: false },
      qty: { status: "REVIEW REQUIRED", available: "0.180", unit: "kg" },
      status: "REVIEW REQUIRED",
      flags: ["ALLOT_AND_SALE_OVERLAP_UNVERIFIED"],
      available_cif_display: "1006.98",
      cif_control: "LICENCE",
    }),
    item({
      item_id: 3,
      sr: "12",
      cif: { status: "LICENCE-LEVEL CONTROL", available: "-36129.09", cif_control: "LICENCE", is_over_utilised: false },
      qty: { status: "RECONCILED", available: "2374.850", unit: "kg" },
      available_cif_display: "1006.98",
      cif_control: "LICENCE",
    }),
  ];

  it("shows the same licence balance in every row's Available CIF, and never a sum", () => {
    render(<ItemBalanceTable licenceId={1} items={licenceControlled} onOpenLedger={() => undefined} />);

    const rows = bodyRows();
    expect(rows).toHaveLength(3);
    for (const row of rows) expect(cellText(row, COL.AVAILABLE_CIF)).toContain("1,006.98");
    // Three rows of 1,006.98 must not appear as 3,020.94 or any other total.
    expect(screen.queryByText("3,020.94")).not.toBeInTheDocument();
  });

  it("labels every row with Licence-level CIF control", () => {
    render(<ItemBalanceTable licenceId={1} items={licenceControlled} onOpenLedger={() => undefined} />);

    for (const row of bodyRows()) {
      expect(cellText(row, COL.CIF_CONTROL)).toBe("Licence-level CIF control");
    }
  });

  it("keeps each item's quantity available independent", () => {
    render(<ItemBalanceTable licenceId={1} items={licenceControlled} onOpenLedger={() => undefined} />);

    const rows = bodyRows();
    expect(cellText(rows[1], COL.AVAILABLE_QTY)).toContain("0.180");
    expect(cellText(rows[2], COL.AVAILABLE_QTY)).toContain("2,374.850");
  });

  it("keeps the item's own review status, not RECONCILED", () => {
    render(<ItemBalanceTable licenceId={1} items={licenceControlled} onOpenLedger={() => undefined} />);

    const row = bodyRows()[1];
    expect(within(row).getByRole("button", { name: /REVIEW REQUIRED|Review required/i })).toBeInTheDocument();
    expect(cellText(row, COL.STATUS)).toMatch(/Review required/);
  });

  it("does not mark an item over-utilised because its informational CIF is negative", () => {
    render(<ItemBalanceTable licenceId={1} items={licenceControlled} onOpenLedger={() => undefined} />);

    const row = bodyRows()[2];
    expect(within(row).queryByText("Over-utilised")).not.toBeInTheDocument();
  });
});

describe("ItemBalanceTable: Individual Item CIF ON", () => {
  const itemControlled: ItemRow[] = [
    item({
      item_id: 1,
      sr: "1",
      cif: { status: "RECONCILED", available: "1000.00", is_over_utilised: false },
      available_cif_display: "1000.00",
      cif_control: "ITEM",
    }),
    item({
      item_id: 2,
      sr: "2",
      cif: { status: "OVER-UTILISED", available: "-200.00", is_over_utilised: true },
      available_cif_display: "-200.00",
      cif_control: "ITEM",
      status: "OVER-UTILISED",
    }),
  ];

  it("shows each row's own available CIF and does not label it licence-level", () => {
    render(<ItemBalanceTable licenceId={2} items={itemControlled} onOpenLedger={() => undefined} />);

    const rows = bodyRows();
    expect(cellText(rows[0], COL.AVAILABLE_CIF)).toContain("1,000.00");
    expect(cellText(rows[1], COL.AVAILABLE_CIF)).toContain("-200.00");
    for (const row of rows) {
      expect(cellText(row, COL.CIF_CONTROL)).toBe("Individual item CIF");
    }
    expect(screen.queryByText("Licence-level CIF control")).not.toBeInTheDocument();
  });

  it("keeps genuine item-level over-utilisation visible", () => {
    render(<ItemBalanceTable licenceId={2} items={itemControlled} onOpenLedger={() => undefined} />);

    // The amount badge and the status pill both say Over-utilised.
    expect(within(bodyRows()[1]).getAllByText("Over-utilised").length).toBeGreaterThan(0);
  });
});

describe("ItemBalanceTable: column structure", () => {
  it("has the spec's columns in order, with quantity before CIF in every group", () => {
    render(
      <ItemBalanceTable
        licenceId={1}
        items={[item({ item_id: 1, sr: "1", cif_control: "LICENCE", available_cif_display: "1006.98" })]}
        onOpenLedger={() => undefined}
      />,
    );

    const table = screen.getByTestId("item-table");
    const [groupRow, subRow] = within(table).getAllByRole("row").slice(0, 2);
    expect(within(groupRow).getAllByRole("columnheader").map((th) => th.textContent)).toEqual([
      "SR",
      "Item",
      "HS Code",
      "Unit",
      "Original",
      "Used through BOEs",
      "Reserved for Customers",
      "Invoiced",
      "Available",
      "CIF Control",
      "Status",
    ]);
    expect(within(subRow).getAllByRole("columnheader").map((th) => th.textContent)).toEqual([
      "Quantity",
      "CIF (USD)",
      "Quantity",
      "CIF (USD)",
      "Quantity",
      "CIF (USD)",
      "Quantity",
      "CIF (USD)",
      "Quantity",
      "CIF (USD)",
    ]);
  });

  it("keeps the expand control in the SR cell, with its accessible name", () => {
    render(
      <ItemBalanceTable
        licenceId={1}
        items={[item({ item_id: 1, sr: "1", cif_control: "LICENCE", available_cif_display: "1006.98" })]}
        onOpenLedger={() => undefined}
      />,
    );

    const row = bodyRows()[0];
    expect(within(row).getByRole("button", { name: "Show sources for SR 1" })).toBeInTheDocument();
    expect(cellText(row, COL.SR)).toBe("1");
  });
});
