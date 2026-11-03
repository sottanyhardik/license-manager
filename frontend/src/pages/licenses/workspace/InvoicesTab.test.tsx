import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/api/axios";
import InvoicesTab from "./InvoicesTab";
import { COLUMN_STORAGE_KEY } from "./invoiceLedgerColumns";
import { WORKSPACE_LICENCE_ID, WORKSPACE_LICENCE_NUMBER, ledgerRow, workspaceInvoiceLedger } from "./testData";
import type { InvoiceLedger } from "./types";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }));

const get = vi.mocked(api.get);
const ID = WORKSPACE_LICENCE_ID;
const LEDGER_URL = `licence-balances/${ID}/invoice-ledger/`;
const EMPTY_TEXT = "–";
const LABDHI = "LABDHI GLOBAL LLP";
const NORTHSTAR = "NORTHSTAR AGRO LLP";

function labdhiTable() {
  return screen.getByRole("table", { name: `Purchase and sale rows for ${LABDHI}` });
}

function totalsRegion() {
  return screen.getByRole("region", { name: "Licence totals" });
}

/** Renders the tab with a mocked response. An Error is returned as a failed request. */
function renderTab(response: InvoiceLedger | Error = workspaceInvoiceLedger) {
  get.mockReset();
  get.mockImplementation(((url: string) => {
    if (url !== LEDGER_URL) return Promise.resolve({ data: { results: [] } });
    return response instanceof Error ? Promise.reject(response) : Promise.resolve({ data: response });
  }) as never);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <InvoicesTab licenceId={ID} licenceNumber={WORKSPACE_LICENCE_NUMBER} />
    </QueryClientProvider>,
  );
}

function httpError(status: number) {
  return Object.assign(new Error(`Request failed with status ${status}`), {
    isAxiosError: true,
    response: { status, data: {} },
  });
}

/** Ledger with the given rows in one company, using the fixture's totals. */
function ledgerWithRows(rows: ReturnType<typeof ledgerRow>[], company = LABDHI): InvoiceLedger {
  return {
    summary: workspaceInvoiceLedger.summary,
    companies: [{ company, balance_cif: "0.00", rows }],
  };
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  Reflect.deleteProperty(URL, "createObjectURL");
  Reflect.deleteProperty(URL, "revokeObjectURL");
});

/** jsdom has no object URLs. The test supplies them and records what the component passes in. */
function mockObjectUrls(createObjectURL: (blob: Blob) => string) {
  Object.defineProperty(URL, "createObjectURL", { value: createObjectURL, configurable: true, writable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), configurable: true, writable: true });
}

describe("Invoices & Sales: internal trades", () => {
  it("marks an INTERNAL trade, and shows the internal total apart from the external sale", async () => {
    const internal = ledgerRow({
      line_id: 777, trade_id: 777, invoice: "SC/2026-27/0001", type: "SALE", sale_cif: "169492.39",
      classification: "INTERNAL", classification_reason: "Group-company sale",
    });
    const ledger = ledgerWithRows([...workspaceInvoiceLedger.companies[0].rows, internal]);
    renderTab({
      ...ledger,
      summary: { ...ledger.summary, gross_internal_sale_cif: "169492.39", internal_row_count: 1 },
    });

    expect(await screen.findByText("INTERNAL TRADE")).toBeInTheDocument();
    expect(screen.getByText(/Internal trades, not external: 169,492\.39/)).toBeInTheDocument();
  });
});

describe("Invoices & Sales: summary cards", () => {
  it("shows the four totals from the API strings, with the currency and the bill values in rupees", async () => {
    renderTab();
    const cards = within(await screen.findByRole("region", { name: "Licence totals" }));

    expect(cards.getByText("92,128.06")).toBeInTheDocument();
    expect(cards.getByText("62,254.58")).toBeInTheDocument();
    expect(cards.getByText("29,873.48")).toBeInTheDocument();
    expect(cards.getByText("1,40,348.00")).toBeInTheDocument();
    expect(cards.getByText("Bill ₹ 12,38,942.00")).toBeInTheDocument();
    expect(cards.getByText("Bill ₹ 10,98,594.00")).toBeInTheDocument();
    expect(cards.getByText("Gross 92,128.06 · adjustments 0.00")).toBeInTheDocument();
    expect(cards.getByText("Gross 63,254.58 · credit/debit notes -1,000.00")).toBeInTheDocument();
    expect(cards.getByText("Net purchase − net sale (external trades only)")).toBeInTheDocument();
    expect(cards.getByText("Net purchase bill − net sale bill")).toBeInTheDocument();
  });

  it("never labels the net bill difference as a loss", async () => {
    renderTab();
    const cards = await screen.findByRole("region", { name: "Licence totals" });

    expect(cards.textContent ?? "").toContain("Net bill difference");
    expect(cards.textContent ?? "").not.toMatch(/loss/i);
  });
});

describe("Invoices & Sales: reconciliation notes", () => {
  it("shows the amber note when the balance engine and the net sale differ", async () => {
    renderTab();

    const note = await screen.findByTestId("reconciliation-difference");
    expect(note).toHaveTextContent("The balance engine counts 63,254.58 as sale; the net sale here is 62,254.58.");
    expect(note).toHaveTextContent("The difference of 1,000.00 is credit notes the engine does not yet net.");
  });

  it("does not show the amber note when the difference is 0.00", async () => {
    renderTab({
      ...workspaceInvoiceLedger,
      summary: { ...workspaceInvoiceLedger.summary, canonical_vs_net_sale_difference: "0.00" },
    });

    await screen.findByRole("region", { name: "Licence totals" });
    expect(screen.queryByTestId("reconciliation-difference")).not.toBeInTheDocument();
  });

  it("shows the red note with the count and the unmatched CIF", async () => {
    renderTab();

    expect(await screen.findByTestId("reconciliation-unmatched")).toHaveTextContent(
      "1 credit or debit note has no matching original invoice and is not netted. Unmatched CIF: 500.00.",
    );
  });
});

describe("Invoices & Sales: company sections and table", () => {
  it("shows one section per company, each with its balance in the header bar", async () => {
    renderTab();

    const header = await screen.findByRole("button", { name: new RegExp(LABDHI), expanded: true });
    expect(header).toHaveAttribute("aria-expanded", "true");
    expect(header).toHaveTextContent("Balance: 29,873.48 USD");
    expect(screen.getByRole("button", { name: new RegExp(NORTHSTAR), expanded: true })).toHaveTextContent("Balance: 0.00 USD");
  });

  it("collapses a company so its rows disappear, and expands it to restore them", async () => {
    const user = userEvent.setup();
    renderTab();
    const header = await screen.findByRole("button", { name: new RegExp(LABDHI), expanded: true });
    expect(screen.getByRole("button", { name: "JASH/2025-26/115" })).toBeInTheDocument();

    await user.click(header);
    expect(header).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "JASH/2025-26/115" })).not.toBeInTheDocument();

    await user.click(header);
    expect(header).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "JASH/2025-26/115" })).toBeInTheDocument();
  });

  it("shows the nine columns in the specified order, with the CIF currency from the rows", async () => {
    renderTab();

    const headers = within(await waitFor(labdhiTable)).getAllByRole("columnheader");
    expect(headers.map((header) => header.textContent)).toEqual([
      "Date",
      "Particulars",
      "Invoice",
      "Type",
      "Items",
      "Sale (USD)",
      "Purchase (USD)",
      "Sale Bill (₹)",
      "Purchase Bill (₹)",
    ]);
  });

  it("shows an en dash for an empty amount, red sale values, green purchase values, and keeps credit signs", async () => {
    renderTab();

    const creditRow = (await screen.findByRole("button", { name: "CREDIT NOTE LGL/2026-27/0010" })).closest("tr") as HTMLElement;
    expect(within(creditRow).getByText("-1,000.00")).toHaveClass("text-destructive");
    expect(within(creditRow).getByText("-84,000.00")).toHaveClass("text-destructive");

    const purchaseRow = screen.getByRole("button", { name: "JASH/2025-26/115" }).closest("tr") as HTMLElement;
    expect(within(purchaseRow).getByText("92,128.06")).toHaveClass("text-success");
    expect(within(purchaseRow).getAllByText(EMPTY_TEXT)).toHaveLength(2);
    expect(within(purchaseRow).getAllByText(EMPTY_TEXT)[0]).toHaveClass("text-muted-foreground");
  });

  it("shows the type as a pill, and a note with its effect and a distinct style", async () => {
    renderTab();

    const noteRow = (await screen.findByRole("button", { name: "DEBIT NOTE ZTR/2026-27/0003" })).closest("tr") as HTMLElement;
    expect(within(noteRow).getByText("DEBIT NOTE")).toHaveClass("border-dashed");
    expect(within(noteRow).getByText("Not netted (review)")).toBeInTheDocument();
    const saleRow = screen.getByRole("button", { name: "LGL/2026-27/0010" }).closest("tr") as HTMLElement;
    expect(within(saleRow).getByText("SALE")).not.toHaveClass("border-dashed");
  });

  it("shows the warning status text for an unmatched note, not only a colour", async () => {
    renderTab();

    const row = (await screen.findByText("UNMATCHED NOTE: no original invoice found")).closest("tr") as HTMLElement;
    expect(row).toHaveAttribute("data-needs-review", "true");
    expect(within(row).getByText("UNMATCHED NOTE: no original invoice found")).toBeInTheDocument();
  });

  it("shows the empty-state message when the licence has no purchase or sale rows", async () => {
    renderTab({ summary: workspaceInvoiceLedger.summary, companies: [] });

    expect(await screen.findByText("No purchase or sale transactions on this licence")).toBeInTheDocument();
  });
});

describe("Invoices & Sales: invoice detail panel", () => {
  it("opens the panel for an invoice link, shows its related BOEs, and says when there are none", async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(await screen.findByRole("button", { name: "LGL/2026-27/0011" }));
    const panel = screen.getByRole("region", { name: "LGL/2026-27/0011" });
    expect(within(panel).getByText("BOE-1002")).toBeInTheDocument();
    expect(within(panel).getByText("Not recorded for trades")).toBeInTheDocument();
    expect(within(panel).getByText("Not yet available")).toBeInTheDocument();
    expect(within(panel).getAllByText("None", { selector: "p" })).toHaveLength(2);
  });

  it("shows the matched original of a note and opens that original in the same panel", async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(await screen.findByRole("button", { name: "CREDIT NOTE LGL/2026-27/0010" }));
    const note = screen.getByRole("region", { name: "CREDIT NOTE LGL/2026-27/0010" });
    expect(within(note).getByText("LGL/2026-27/0010 (sale)")).toBeInTheDocument();

    await user.click(within(note).getByRole("button", { name: "Open original" }));
    const original = await screen.findByRole("region", { name: "LGL/2026-27/0010" });
    expect(within(original).getByText("SALE")).toBeInTheDocument();
    expect(within(original).getByText("None linked")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "CREDIT NOTE LGL/2026-27/0010" })).not.toBeInTheDocument();
  });

  it("lists the credit and debit notes that point at an invoice", async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(await screen.findByRole("button", { name: "LGL/2026-27/0010" }));
    const panel = screen.getByRole("region", { name: "LGL/2026-27/0010" });
    expect(within(panel).getByRole("button", { name: "CREDIT NOTE LGL/2026-27/0010" })).toBeInTheDocument();
  });

  it("moves focus into the panel on open and back to the invoice link on close", async () => {
    const user = userEvent.setup();
    renderTab();

    const link = await screen.findByRole("button", { name: "LGL/2026-27/0011" });
    await user.click(link);
    const panel = screen.getByRole("region", { name: "LGL/2026-27/0011" });
    expect(panel).toHaveFocus();

    await user.click(within(panel).getByRole("button", { name: "Close invoice details" }));
    expect(screen.queryByRole("region", { name: "LGL/2026-27/0011" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "LGL/2026-27/0011" })).toHaveFocus();
  });

  it("closes with Escape and returns focus to the link", async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(await screen.findByRole("button", { name: "JASH/2025-26/115" }));
    expect(screen.getByRole("region", { name: "JASH/2025-26/115" })).toHaveFocus();
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("region", { name: "JASH/2025-26/115" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "JASH/2025-26/115" })).toHaveFocus();
  });
});

describe("Invoices & Sales: filters", () => {
  it("reduces the rows when a type is unticked, and says how many rows are shown", async () => {
    const user = userEvent.setup();
    renderTab();
    await screen.findByRole("button", { name: "LGL/2026-27/0010" });

    await user.click(screen.getByRole("checkbox", { name: "Sale" }));

    expect(screen.queryByRole("button", { name: "LGL/2026-27/0010" })).not.toBeInTheDocument();
    expect(screen.getByText("Filtered: 3 of 5 rows")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByRole("button", { name: "LGL/2026-27/0010" })).toBeInTheDocument();
    expect(screen.queryByText(/Filtered:/)).not.toBeInTheDocument();
  });

  it("filters by particulars and leaves the summary cards unchanged", async () => {
    const user = userEvent.setup();
    renderTab();
    await screen.findByRole("button", { name: "LGL/2026-27/0010" });
    const before = totalsRegion().textContent;

    await user.type(screen.getByRole("searchbox", { name: "Particulars" }), "golden");

    expect(screen.getByText("Filtered: 1 of 5 rows")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "JASH/2025-26/115" })).not.toBeInTheDocument();
    expect(totalsRegion().textContent).toBe(before);
  });

  it("shows only invoices with no note when that note filter is chosen", async () => {
    const user = userEvent.setup();
    renderTab();
    await screen.findByRole("button", { name: "LGL/2026-27/0010" });

    await user.selectOptions(screen.getByRole("combobox", { name: "Notes" }), "none");

    expect(screen.queryByRole("button", { name: "LGL/2026-27/0010" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "LGL/2026-27/0011" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "JASH/2025-26/115" })).toBeInTheDocument();
  });

  it("offers a currency filter only when more than one currency occurs", async () => {
    const user = userEvent.setup();
    const { unmount } = renderTab();
    await screen.findByRole("button", { name: "LGL/2026-27/0010" });
    expect(screen.queryByRole("combobox", { name: "Currency" })).not.toBeInTheDocument();
    unmount();

    const eurRow = ledgerRow({
      line_id: 9,
      trade_id: 90,
      invoice: "LGL/EUR/1",
      type: "SALE",
      sale_cif: "10.00",
      source: { type: "trade", id: 90, line_id: 9, currency: "EUR" },
    });
    renderTab(ledgerWithRows([...workspaceInvoiceLedger.companies[0].rows, eurRow]));
    await screen.findByRole("button", { name: "LGL/EUR/1" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Currency" }), "EUR");

    expect(screen.getByText("Filtered: 1 of 6 rows")).toBeInTheDocument();
    // Mixed currencies use a neutral CIF label in the column headers.
    expect(within(labdhiTable()).getAllByRole("columnheader")[5]).toHaveTextContent("Sale (CIF)");
  });
});

describe("Invoices & Sales: sorting and paging", () => {
  it("toggles aria-sort on the sorted column and sorts decimals by value", async () => {
    const user = userEvent.setup();
    renderTab();
    await screen.findByRole("button", { name: "LGL/2026-27/0010" });

    const dateHeader = within(labdhiTable()).getByRole("columnheader", { name: "Date" });
    expect(dateHeader).toHaveAttribute("aria-sort", "ascending");
    await user.click(within(dateHeader).getByRole("button", { name: "Date" }));
    expect(dateHeader).toHaveAttribute("aria-sort", "descending");

    const saleHeader = within(labdhiTable()).getByRole("columnheader", { name: "Sale (USD)" });
    expect(saleHeader).toHaveAttribute("aria-sort", "none");
    await user.click(within(saleHeader).getByRole("button", { name: "Sale (USD)" }));
    expect(saleHeader).toHaveAttribute("aria-sort", "ascending");
    expect(dateHeader).toHaveAttribute("aria-sort", "none");

    // Negative first, then the positive sales, and empty values last.
    const firstRow = labdhiTable().querySelectorAll("tbody tr")[0] as HTMLElement;
    expect(firstRow).toHaveTextContent("CREDIT NOTE LGL/2026-27/0010");
  });

  it("pages a company's rows and shows the range", async () => {
    const user = userEvent.setup();
    const many = Array.from({ length: 12 }, (_, index) =>
      ledgerRow({ line_id: 100 + index, trade_id: 200 + index, invoice: `INV-${index + 1}`, type: "SALE", sale_cif: "1.00" }),
    );
    renderTab(ledgerWithRows(many, "BULK CO"));

    expect(await screen.findByText("Showing 1–10 of 12")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next page for BULK CO" }));
    expect(screen.getByText("Showing 11–12 of 12")).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Rows per page for BULK CO" }), "25");
    expect(screen.getByText("Showing 1–12 of 12")).toBeInTheDocument();
  });
});

describe("Invoices & Sales: column visibility", () => {
  it("hides an optional column, keeps it hidden after a remount, and never hides the locked ones", async () => {
    const user = userEvent.setup();
    const { unmount } = renderTab();
    await screen.findByRole("button", { name: "LGL/2026-27/0010" });

    await user.click(screen.getByRole("button", { name: "Columns" }));
    const menu = await screen.findByRole("menu");
    expect(within(menu).getByRole("menuitemcheckbox", { name: "Particulars" })).toHaveAttribute("aria-disabled", "true");
    expect(within(menu).getByRole("menuitemcheckbox", { name: "Invoice" })).toHaveAttribute("aria-disabled", "true");
    expect(within(menu).getByRole("menuitemcheckbox", { name: "Type" })).toHaveAttribute("aria-disabled", "true");
    await user.click(within(menu).getByRole("menuitemcheckbox", { name: "Items" }));
    await user.keyboard("{Escape}");

    expect(within(labdhiTable()).queryByRole("columnheader", { name: "Items" })).not.toBeInTheDocument();
    expect(window.localStorage.getItem(COLUMN_STORAGE_KEY)).toBe(JSON.stringify(["items"]));
    unmount();

    renderTab();
    await screen.findByRole("button", { name: "LGL/2026-27/0010" });
    expect(within(labdhiTable()).queryByRole("columnheader", { name: "Items" })).not.toBeInTheDocument();
    expect(within(labdhiTable()).getByRole("columnheader", { name: "Invoice" })).toBeInTheDocument();
  });
});

describe("Invoices & Sales: CSV export", () => {
  it("downloads the filtered rows as CSV using the displayed strings", async () => {
    const user = userEvent.setup();
    const createObjectURL = vi.fn((_blob: Blob) => "blob:licence-invoices");
    mockObjectUrls(createObjectURL);
    const clicked: HTMLAnchorElement[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push(this);
    });
    renderTab();
    await screen.findByRole("button", { name: "LGL/2026-27/0010" });

    await user.click(screen.getByRole("button", { name: "Export CSV" }));

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(clicked[0].download).toBe(`licence-${WORKSPACE_LICENCE_NUMBER}-invoices.csv`);
    expect(clicked[0].href).toContain("blob:licence-invoices");
    const text = await readBlob(createObjectURL.mock.calls[0][0]);
    const lines = text.replace(/^\uFEFF/, "").split("\r\n");
    expect(lines).toHaveLength(6);
    expect(lines[0]).toBe(
      "Company,Date,Particulars,Invoice,Type,Items,Sale (USD),Purchase (USD),Sale Bill (₹),Purchase Bill (₹),Status",
    );
    expect(lines[1]).toBe(
      `${LABDHI},25-02-2025,JASH MERCANTILE LLP,JASH/2025-26/115,PURCHASE,WHEAT GLUTEN,–,"92,128.06",–,"12,38,942.00",OK`,
    );
    expect(lines[4]).toContain('"-1,000.00"');
  });

  it("names the file by id when the licence number is not known", async () => {
    const user = userEvent.setup();
    const clicked: HTMLAnchorElement[] = [];
    mockObjectUrls(vi.fn(() => "blob:x"));
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push(this);
    });
    get.mockReset();
    get.mockImplementation((() => Promise.resolve({ data: workspaceInvoiceLedger })) as never);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <InvoicesTab licenceId={ID} />
      </QueryClientProvider>,
    );
    await screen.findByRole("button", { name: "LGL/2026-27/0010" });

    await user.click(screen.getByRole("button", { name: "Export CSV" }));

    expect(clicked[0].download).toBe(`licence-${ID}-invoices.csv`);
  });
});

describe("Invoices & Sales: loading and errors", () => {
  it("shows an alert with Retry when the ledger cannot be loaded", async () => {
    renderTab(httpError(403));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("You do not have permission to view licence balances.")).toBeInTheDocument();
    expect(within(alert).getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

/** Reads a Blob the component passed to createObjectURL. */
function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}
