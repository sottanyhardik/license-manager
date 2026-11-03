import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/api/axios";
import ItemDrilldownDrawer from "./ItemDrilldownDrawer";
import { itemDrilldown, unverifiedUnitDrilldown } from "./drilldownTestData";
import type { DrilldownBoeRow, DrilldownGroup, ItemDrilldown } from "./types";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn() } }));

const get = vi.mocked(api.get);
const DRILLDOWN_URL = "licence-balances/2583/items/101/drilldown/";

function renderDrawer({
  group = "boes",
  payload = itemDrilldown,
  onClose = vi.fn(),
}: { group?: DrilldownGroup; payload?: ItemDrilldown; onClose?: () => void } = {}) {
  get.mockImplementation(((url: string) => {
    if (url === DRILLDOWN_URL) return Promise.resolve({ data: payload });
    return Promise.reject(new Error(`unexpected ${url}`));
  }) as never);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ItemDrilldownDrawer licenceId={2583} itemId={101} group={group} onClose={onClose} />
    </QueryClientProvider>,
  );
  return { onClose };
}

/** Text of each cell in a row, in DOM order. Body rows start with the expand control; totals rows start with the label. */
function cellsOf(row: Element) {
  return Array.from(row.querySelectorAll("th, td")).map((cell) => cell.textContent?.trim() ?? "");
}

/** Body rows of the table (not the expanded detail rows). */
function bodyRows(tableEl: HTMLElement) {
  return Array.from(tableEl.querySelectorAll<HTMLElement>("tbody > tr")).filter(
    (row) => row.querySelectorAll("td").length > 0 && !row.classList.contains("bg-muted/20"),
  );
}

/** The body row whose BOE number cell matches. */
function boeRow(tableEl: HTMLElement, number: string) {
  const row = bodyRows(tableEl).find((candidate) => cellsOf(candidate)[1] === number);
  if (!row) throw new Error(`no row for BOE ${number}`);
  return row;
}

async function table() {
  return screen.findByTestId("drilldown-table");
}

function readBytes(blob: Blob): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(blob);
  });
}

/** Stubs the object-URL API (jsdom lacks it) and records each exported blob. */
function captureExports() {
  const created: Blob[] = [];
  URL.createObjectURL = vi.fn((blob: Blob | MediaSource) => {
    created.push(blob as Blob);
    return "blob:drilldown";
  });
  URL.revokeObjectURL = vi.fn();
  return created;
}

/** A BOE debit row. Override only the fields a case cares about. */
function makeBoeRow(overrides: Partial<DrilldownBoeRow>): DrilldownBoeRow {
  return {
    kind: "BOE",
    row_id: 9000,
    boe_number: "9000",
    boe_date: null,
    port: "",
    importer: "",
    sr: "1",
    hs_code: "1234",
    currency: "USD",
    invoice_number: null,
    boe_cif: "0.00",
    boe_qty: "0.000",
    cif_inr: "0.00",
    covered_cif: "0.00",
    covered_qty: "0.000",
    debited_cif: "0.00",
    debited_qty: "0.000",
    previous_owner: false,
    sale_links: [],
    allotment_ids: [],
    status: "UNCOVERED",
    flags: [],
    source: { type: "bill_of_entry", id: 9000 },
    ...overrides,
  };
}

/** A copy of the fixture with extra BOE rows and the totals the caller provides. */
function withBoeRows(extra: DrilldownBoeRow[], totals: Partial<ItemDrilldown["boes"]["totals"]> = {}) {
  const copy = structuredClone(itemDrilldown);
  copy.boes.rows = [...copy.boes.rows, ...extra];
  copy.boes.totals = { ...copy.boes.totals, ...totals };
  return copy;
}

beforeEach(() => {
  get.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ItemDrilldownDrawer: BOE debits show Quantity and CIF together", () => {
  it("opens with the spec title and totals that list Quantity before CIF", async () => {
    renderDrawer();

    expect(await screen.findByRole("dialog", { name: "BOE Debit Details — SR 1 — Item one" })).toBeInTheDocument();
    const totals = screen.getByRole("table", { name: "Totals for BOE debits" });
    expect(cellsOf(within(totals).getByRole("row", { name: /Debited \(Item Figure\)/ }))).toEqual([
      "Debited (Item Figure)",
      "300.000 kg",
      "300.00",
    ]);
    expect(cellsOf(within(totals).getByRole("row", { name: /Covered by Sale/ }))).toEqual(["Covered by Sale", "100.000 kg", "100.00"]);
    expect(screen.getByLabelText("Totals")).toHaveTextContent("2 counted · 0 previous-owner");
    expect(await table()).toBeInTheDocument();
  });

  it("lists the summary metrics in the spec's order", async () => {
    renderDrawer();
    const totals = await screen.findByRole("table", { name: "Totals for BOE debits" });
    const labels = within(totals)
      .getAllByRole("row")
      .slice(1)
      .map((row) => row.querySelector("th")?.textContent);
    expect(labels).toEqual([
      "Covered by Sale",
      "Uncovered BOE Debit (current owner)",
      "Over-linked Excess",
      "Debited (Item Figure)",
      "Previous-owner BOE Debit",
    ]);
  });

  it("has no CIF / Quantity toggle", async () => {
    renderDrawer();
    await table();
    expect(screen.queryByRole("group", { name: "Figure" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "CIF (USD)" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Quantity \(kg\)$/ })).not.toBeInTheDocument();
  });

  it("puts Quantity before CIF in every pair, under the spec's group headings", async () => {
    renderDrawer();
    const tableEl = await table();
    const [groupRow, subRow] = Array.from(tableEl.querySelectorAll("thead tr"));

    const groups = Array.from(groupRow.querySelectorAll("th[scope='colgroup']")).map((th) => th.textContent);
    expect(groups).toEqual(["BOE", "Covered by Sale", "Debited"]);
    expect(Array.from(subRow.querySelectorAll("button")).map((button) => button.getAttribute("aria-label"))).toEqual([
      "Sort by BOE Quantity (kg)",
      "Sort by BOE CIF (USD)",
      "Sort by Covered by Sale — Quantity (kg)",
      "Sort by Covered by Sale — CIF (USD)",
      "Sort by Debited — Quantity (kg)",
      "Sort by Debited — CIF (USD)",
    ]);
    expect(Array.from(groupRow.querySelectorAll("th button")).map((button) => button.getAttribute("aria-label"))).toEqual([
      "Sort by BOE No.",
      "Sort by BOE Date",
      "Sort by Port",
      "Sort by Importer",
      "Sort by Sale / Invoice",
      "Sort by Allotment",
      "Sort by Status",
    ]);
  });

  it("partly sale-covered BOE: BOE, coverage and debit, each as quantity then CIF", async () => {
    renderDrawer();
    const cells = cellsOf(boeRow(await table(), "4001"));
    expect(cells.slice(1, 5)).toEqual(["4001", expect.any(String), "Mundra", "Customer One"]);
    expect(cells.slice(5, 11)).toEqual(["300.000 kg", "300.00", "100.000 kg", "100.00", "200.000 kg", "200.00"]);
    expect(cells[11]).toBe("INV-1");
    expect(cells[13]).toBe("PARTIALLY COVERED");
  });

  it("uncovered BOE: no coverage, full debit, both measures", async () => {
    renderDrawer();
    const cells = cellsOf(boeRow(await table(), "4002"));
    expect(cells.slice(5, 11)).toEqual(["100.000 kg", "100.00", "0.000 kg", "0.00", "100.000 kg", "100.00"]);
    expect(cells[13]).toBe("UNCOVERED");
  });

  it("expanded BOE: linked sales show Linked quantity before Linked CIF for each allocation", async () => {
    const user = userEvent.setup();
    renderDrawer();
    await table();

    await user.click(screen.getByRole("button", { name: "Show details for BOE 4001" }));
    const sales = screen.getByRole("table", { name: "Linked sales" });
    expect(within(sales).getAllByRole("columnheader").map((th) => th.textContent)).toEqual([
      "Sale / invoice",
      "Linked quantity (kg)",
      "Linked CIF (USD)",
      "Allocation basis",
    ]);
    expect(cellsOf(within(sales).getByRole("row", { name: /INV-1/ }))).toEqual(["INV-1", "100.000 kg", "100.00", "ALLOCATION"]);

    const figures = screen.getByRole("table", { name: "Figures for BOE 4001" });
    expect(cellsOf(within(figures).getByRole("row", { name: /Debited \(counted/ }))).toEqual([
      "Debited (counted in the item figure)",
      "200.000 kg",
      "200.00",
    ]);
  });

  it("over-linked BOE: its excess is a separate debit row with its own quantity and CIF", async () => {
    const user = userEvent.setup();
    const payload = withBoeRows(
      [
        makeBoeRow({
          kind: "OVER_LINKED_EXCESS",
          row_id: null,
          boe_number: "",
          invoice_number: "INV-1",
          debited_cif: "50.00",
          debited_qty: "50.000",
          status: "OVER-LINKED EXCESS (counted as debit)",
          source: { type: "trade", id: 1 },
          flags: ["OVER_LINKED_MIXED_OWNERSHIP: excess ownership not determined (review)"],
        }),
      ],
      { over_linked_cif: "50.00", over_linked_qty: "50.000", debited_cif: "350.00", debited_qty: "350.000" },
    );
    renderDrawer({ payload });
    const tableEl = await table();

    const excess = cellsOf(boeRow(tableEl, "Excess on INV-1"));
    expect(excess.slice(5, 11)).toEqual(["—", "—", "—", "—", "50.000 kg", "50.00"]);
    expect(
      cellsOf(within(screen.getByRole("table", { name: "Totals for BOE debits" })).getByRole("row", { name: /Over-linked Excess/ })),
    ).toEqual(["Over-linked Excess", "50.000 kg", "50.00"]);

    await user.click(screen.getByRole("button", { name: "Show details for excess on INV-1" }));
    expect(screen.getByRole("table", { name: "Over-linked excess figures" })).toHaveTextContent("50.000 kg");
    expect(screen.getByText(/OVER_LINKED_MIXED_OWNERSHIP/)).toBeInTheDocument();
  });

  it("previous-owner BOE: deducted, shown with quantity and CIF, in the item debit breakdown and the Previous-owner metric", async () => {
    const user = userEvent.setup();
    const payload = withBoeRows(
      [
        makeBoeRow({
          row_id: 9003,
          boe_number: "7238066",
          boe_date: "2026-02-20",
          port: "Kandla",
          importer: "Previous Owner Ltd",
          boe_cif: "200.00",
          boe_qty: "200.000",
          debited_cif: "200.00",
          debited_qty: "200.000",
          previous_owner: true,
          status: "PREVIOUS OWNER — DEDUCTED",
          source: { type: "bill_of_entry", id: 7238066 },
        }),
      ],
      {
        boe_rows: 3,
        previous_owner_rows: 1,
        boe_cif: "600.00",
        boe_qty: "600.000",
        previous_owner_debit_cif: "200.00",
        previous_owner_debit_qty: "200.000",
        debited_cif: "500.00",
        debited_qty: "500.000",
      },
    );
    renderDrawer({ payload });
    const tableEl = await table();

    const cells = cellsOf(boeRow(tableEl, "7238066"));
    expect(cells.slice(5, 11)).toEqual(["200.000 kg", "200.00", "0.000 kg", "0.00", "200.000 kg", "200.00"]);
    expect(cells[13]).toBe("PREVIOUS OWNER — DEDUCTED");

    const totals = screen.getByRole("table", { name: "Totals for BOE debits" });
    expect(cellsOf(within(totals).getByRole("row", { name: /Previous-owner BOE Debit/ }))).toEqual(["Previous-owner BOE Debit", "200.000 kg", "200.00"]);
    expect(cellsOf(within(totals).getByRole("row", { name: /Debited \(Item Figure\)/ }))).toEqual(["Debited (Item Figure)", "500.000 kg", "500.00"]);
    expect(screen.getByLabelText("Totals")).toHaveTextContent("3 counted · 1 previous-owner");

    await user.click(screen.getByRole("button", { name: "Show details for BOE 7238066" }));
    const figures = screen.getByRole("table", { name: "Figures for BOE 7238066" });
    expect(cellsOf(within(figures).getByRole("row", { name: /Debited: previous-owner BOE/ }))).toEqual([
      "Debited: previous-owner BOE (deducted)",
      "200.000 kg",
      "200.00",
    ]);
    expect(screen.getByText(/Previous-owner BOE: deducted from Available CIF and quantity/)).toBeInTheDocument();
  });

  it("several BOEs linked to one sale: each row shows the sale, and its own quantity then CIF", async () => {
    const user = userEvent.setup();
    const payload = withBoeRows([
      makeBoeRow({
        row_id: 9004,
        boe_number: "4003",
        boe_date: "2026-05-01",
        boe_cif: "50.00",
        boe_qty: "50.000",
        covered_cif: "50.00",
        covered_qty: "50.000",
        sale_links: [{ trade_id: 1, invoice_number: "INV-1", cif: "50.00", qty: "50.000", basis: "ALLOCATION" }],
        status: "COVERED BY SALE",
        source: { type: "bill_of_entry", id: 4003 },
      }),
    ]);
    renderDrawer({ payload });
    const tableEl = await table();

    const linked = bodyRows(tableEl).filter((row) => cellsOf(row).includes("INV-1"));
    expect(linked.map((row) => cellsOf(row)[1])).toEqual(["4001", "4003"]);
    expect(cellsOf(boeRow(tableEl, "4003")).slice(5, 11)).toEqual(["50.000 kg", "50.00", "50.000 kg", "50.00", "0.000 kg", "0.00"]);

    await user.click(screen.getByRole("button", { name: "Show details for BOE 4003" }));
    expect(cellsOf(within(screen.getByRole("table", { name: "Linked sales" })).getByRole("row", { name: /INV-1/ }))).toEqual([
      "INV-1",
      "50.000 kg",
      "50.00",
      "ALLOCATION",
    ]);
  });

  it("unverified quantity unit: quantities are words, CIF stays a figure, the unit is labelled as recorded", async () => {
    renderDrawer({ payload: unverifiedUnitDrilldown });
    const tableEl = await table();

    const row = boeRow(tableEl, "4001");
    expect(cellsOf(row).slice(5, 11)).toEqual(["Unit unverified", "300.00", "Unit unverified", "100.00", "Unit unverified", "200.00"]);
    expect(cellsOf(row).some((cell) => /kg|mts/.test(cell))).toBe(false);
    expect(screen.getByRole("button", { name: "Sort by BOE Quantity (mts, unit not verified)" })).toBeInTheDocument();
    expect(screen.getByText("Quantities are withheld: the unit is not verified.")).toBeInTheDocument();
    expect(screen.getByText("Quantity not reconciled: unit not verified")).toBeInTheDocument();
  });

  it("filters by search text across BOE, port, importer and status", async () => {
    const user = userEvent.setup();
    renderDrawer();
    const tableEl = await table();

    await user.type(screen.getByLabelText("Search rows"), "nhava");
    expect(bodyRows(tableEl)).toHaveLength(1);
    expect(cellsOf(bodyRows(tableEl)[0])[1]).toBe("4002");
    expect(screen.getByText("Showing 1 of 2 rows")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Search rows"));
    await user.type(screen.getByLabelText("Search rows"), "no such thing");
    expect(screen.getByText("No rows match the search or dates.")).toBeInTheDocument();
  });

  it("filters by BOE date range, inclusive of both ends", async () => {
    const user = userEvent.setup();
    renderDrawer();
    const tableEl = await table();

    await user.type(screen.getByLabelText("From"), "2026-04-01");
    expect(bodyRows(tableEl)).toHaveLength(1);
    expect(cellsOf(bodyRows(tableEl)[0])[1]).toBe("4002");
  });

  it("sorts by a BOE figure ascending, descending, then back to source order", async () => {
    const user = userEvent.setup();
    renderDrawer();
    const tableEl = await table();
    const button = screen.getByRole("button", { name: "Sort by BOE CIF (USD)" });
    const header = button.closest("th");

    await user.click(button);
    expect(header).toHaveAttribute("aria-sort", "ascending");
    expect(cellsOf(bodyRows(tableEl)[0])[1]).toBe("4002");

    await user.click(button);
    expect(header).toHaveAttribute("aria-sort", "descending");
    expect(cellsOf(bodyRows(tableEl)[0])[1]).toBe("4001");

    await user.click(button);
    expect(header).toHaveAttribute("aria-sort", "none");
    expect(cellsOf(bodyRows(tableEl)[0])[1]).toBe("4001");
  });

  it("links each BOE to its record, which opens in a new tab", async () => {
    const user = userEvent.setup();
    renderDrawer();
    await table();

    await user.click(screen.getByRole("button", { name: "Show details for BOE 4001" }));
    const link = screen.getByRole("link", { name: /Open BOE 4001/ });
    expect(link).toHaveAttribute("href", "/bill-of-entries/4001/edit");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("reconciles both quantity and CIF to the item table", async () => {
    renderDrawer();
    await table();
    expect(screen.getByText("Quantity reconciles to the item table")).toBeInTheDocument();
    expect(screen.getByText("CIF reconciles to the item table")).toBeInTheDocument();
    const lines = screen.getAllByTestId("reconciliation-lines");
    expect(lines).toHaveLength(2);
    lines.forEach((line) => expect(line).toHaveTextContent("Matches"));
  });

  it("exports the rows shown, with the spec column order and Quantity before CIF in every pair", async () => {
    const user = userEvent.setup();
    const created = captureExports();
    renderDrawer();
    await table();

    await user.type(screen.getByLabelText("Search rows"), "mundra");
    await user.click(screen.getByRole("button", { name: "Export CSV" }));

    expect(created).toHaveLength(1);
    const bytes = await readBytes(created[0]);
    // The UTF-8 byte-order mark is kept (ignoreBOM), so spreadsheets read the file as UTF-8.
    expect(Array.from(bytes.slice(0, 3))).toEqual([0xef, 0xbb, 0xbf]);
    const text = new TextDecoder("utf-8", { ignoreBOM: true }).decode(bytes);
    const [header, ...body] = text.slice(1).split("\r\n");
    expect(header).toBe(
      [
        "BOE No.",
        "BOE Date",
        "Port",
        "Importer",
        "BOE Quantity (kg)",
        "BOE CIF (USD)",
        "Covered by Sale — Quantity (kg)",
        "Covered by Sale — CIF (USD)",
        "Debited — Quantity (kg)",
        "Debited — CIF (USD)",
        "Sale / Invoice",
        "Allotment",
        "Status",
      ].join(","),
    );
    expect(body).toHaveLength(1);
    expect(body[0]).toContain("4001");
    expect(body[0]).toContain("300.000,300.00,100.000,100.00,200.000,200.00");
  });

  it("closes through the Escape key", async () => {
    const user = userEvent.setup();
    const { onClose } = renderDrawer();
    await table();

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("ItemDrilldownDrawer: customer allotments", () => {
  it("lists each allotment, shows invoice-linked as not recorded, and states the outstanding total as Quantity then CIF", async () => {
    renderDrawer({ group: "allotments" });

    expect(await screen.findByRole("dialog", { name: "Customer Allotment Details — SR 1 — Item one" })).toBeInTheDocument();
    const tableEl = await table();
    expect(within(tableEl).getByText("ALLOT-7")).toBeInTheDocument();
    expect(within(tableEl).getByText("UNLINKED")).toBeInTheDocument();
    expect(within(tableEl).getAllByText("Not recorded").length).toBeGreaterThan(0);
    const totals = screen.getByRole("table", { name: "Totals for customer allotments" });
    expect(cellsOf(within(totals).getByRole("row", { name: /Outstanding/ }))).toEqual(["Outstanding (Allotted Figure)", "40.000 kg", "40.00"]);
  });

  it("has no toggle, and every figure lists Quantity before CIF", async () => {
    renderDrawer({ group: "allotments" });
    const tableEl = await table();
    expect(screen.queryByRole("group", { name: "Figure" })).not.toBeInTheDocument();
    const subRow = tableEl.querySelectorAll("thead tr")[1];
    expect(Array.from(subRow.querySelectorAll("button")).map((button) => button.getAttribute("aria-label"))).toEqual([
      "Sort by Original Quantity (kg)",
      "Sort by Original CIF (USD)",
      "Sort by BOE-linked Quantity (kg)",
      "Sort by BOE-linked CIF (USD)",
      "Sort by Invoice-linked Quantity (kg)",
      "Sort by Invoice-linked CIF (USD)",
      "Sort by Outstanding Quantity (kg)",
      "Sort by Outstanding CIF (USD)",
    ]);
  });

  it("shows the BOE-linked BOEs beneath an allotment, marking previous-owner BOEs as deducted", async () => {
    const withBoe = structuredClone(itemDrilldown);
    withBoe.allotments.rows[0] = {
      ...withBoe.allotments.rows[0],
      status: "LINKED",
      boe_linked_cif: "40.00",
      outstanding_cif: "0.00",
      linked_boes: [
        { boe_id: 4001, boe_number: "4001", boe_date: "2026-03-10", on_this_item: true, previous_owner: false, debit_on_item_cif: "300.00", debit_on_item_qty: "300.000", row_ids: [9001] },
        { boe_id: 7238066, boe_number: "7238066", boe_date: "2026-02-20", on_this_item: true, previous_owner: true, debit_on_item_cif: "200.00", debit_on_item_qty: "200.000", row_ids: [9003] },
      ],
    };
    const user = userEvent.setup();
    renderDrawer({ group: "allotments", payload: withBoe });
    await table();

    await user.click(screen.getByRole("button", { name: "Show details for ALLOT-7" }));
    const linked = screen.getByRole("table", { name: "BOEs linked to this allotment" });
    expect(within(linked).getByText("Debits this item")).toBeInTheDocument();
    expect(within(linked).getByText("Previous owner (deducted)")).toBeInTheDocument();
    expect(cellsOf(within(linked).getByRole("row", { name: /7238066/ }))).toEqual([
      "7238066",
      "20 Feb 2026",
      "200.000 kg",
      "200.00",
      "Previous owner (deducted)",
    ]);
  });
});

describe("ItemDrilldownDrawer: invoices", () => {
  it("lists every invoice with its type, flags a note that is not netted, and shows the sold total as Quantity then CIF", async () => {
    const user = userEvent.setup();
    renderDrawer({ group: "invoices" });

    expect(await screen.findByRole("dialog", { name: "Invoice Details — SR 1 — Item one" })).toBeInTheDocument();
    const tableEl = await table();
    expect(bodyRows(tableEl)).toHaveLength(2);
    expect(within(tableEl).getByText("CREDIT NOTE")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show details for invoice CREDIT NOTE CN-9" }));
    expect(screen.getByText(/NOTE NOT NETTED/)).toBeInTheDocument();

    const totals = screen.getByRole("table", { name: "Totals for invoices" });
    expect(cellsOf(within(totals).getByRole("row", { name: /Gross external sales/ }))).toEqual(["Gross external sales", "500.000 kg", "500.00"]);
  });

  it("shows INTERNAL invoices on their own, labelled, and keeps them out of the external figures", async () => {
    const user = userEvent.setup();
    const base = itemDrilldown.invoices.rows[0];
    const internalRow = {
      ...base,
      trade_id: 900,
      invoice_number: "GST/26-27/021",
      customer: "Sambhav Corporation",
      counts_in_current_balance: false,
      classification: "INTERNAL" as const,
      classification_reason: "Group-company sale",
      classification_authorised_by: "hardik",
      classification_authorised_on: "2026-11-03T10:00:00Z",
      status: "INTERNAL TRADE: not external utilisation",
    };
    const payload: ItemDrilldown = {
      ...itemDrilldown,
      invoices: {
        ...itemDrilldown.invoices,
        totals: {
          ...itemDrilldown.invoices.totals,
          internal_invoice_rows: 1,
          internal_sold_cif: "169492.39",
          internal_sold_qty: "0.000",
          gross_sold_cif: "169492.39",
        },
        rows: [...itemDrilldown.invoices.rows, internalRow],
      },
    };
    renderDrawer({ group: "invoices", payload });

    const tableEl = await table();
    expect(bodyRows(tableEl)).toHaveLength(3);
    expect(within(tableEl).getByText("GST/26-27/021 · INTERNAL TRADE")).toBeInTheDocument();

    const totals = screen.getByRole("table", { name: "Totals for invoices" });
    expect(cellsOf(within(totals).getByRole("row", { name: /Gross internal sales/ }))[2]).toBe("1,69,492.39");
    expect(cellsOf(within(totals).getByRole("row", { name: /Amount contributing to external utilisation/ }))).toHaveLength(3);

    await user.click(screen.getByRole("button", { name: "Show details for invoice GST/26-27/021" }));
    expect(screen.getByText("INTERNAL TRADE")).toBeInTheDocument();
    expect(screen.getByText("Reason: Group-company sale")).toBeInTheDocument();
    expect(screen.getByText(/Authorised by hardik/)).toBeInTheDocument();
    expect(screen.getByText("Not in the external balance. Internal trades do not reduce the licence.")).toBeInTheDocument();
  });

  it("has no toggle, and the invoice figures list Quantity before CIF", async () => {
    renderDrawer({ group: "invoices" });
    const tableEl = await table();
    expect(screen.queryByRole("group", { name: "Figure" })).not.toBeInTheDocument();
    const subRow = tableEl.querySelectorAll("thead tr")[1];
    expect(subRow.querySelectorAll("button")[0].getAttribute("aria-label")).toBe("Sort by Sold Quantity (kg)");
    expect(subRow.querySelectorAll("button")[1].getAttribute("aria-label")).toBe("Sort by Sold CIF (USD)");
  });

  it("lists the BOEs linked to an invoice with their allocation basis", async () => {
    const user = userEvent.setup();
    renderDrawer({ group: "invoices" });
    await table();

    await user.click(screen.getByRole("button", { name: "Show details for invoice INV-1" }));
    const linked = screen.getByRole("table", { name: "BOEs linked to this invoice" });
    expect(within(linked).getByText("4001")).toBeInTheDocument();
    expect(within(linked).getByText("ALLOCATION")).toBeInTheDocument();
    expect(cellsOf(within(linked).getByRole("row", { name: /4001/ }))).toEqual([
      "4001",
      "10 Mar 2026",
      "Customer One",
      "100.000 kg",
      "100.00",
      "ALLOCATION",
    ]);
  });
});

describe("ItemDrilldownDrawer: failure", () => {
  it("shows a retryable error when the source records cannot be loaded", async () => {
    get.mockReset();
    get.mockRejectedValue(new Error("network down"));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <ItemDrilldownDrawer licenceId={2583} itemId={101} group="boes" onClose={vi.fn()} />
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("The source records could not be loaded.");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
