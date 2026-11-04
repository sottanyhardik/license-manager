import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { itemDrilldown } from "@/pages/licence-balances/drilldownTestData";
import type { AuthContextValue } from "@/types";
import LicenseListPage from "../LicenseListPage";
import {
  WORKSPACE_LICENCE_ID,
  WORKSPACE_LICENCE_NUMBER,
  itemLedger,
  workspaceDetail,
  workspaceHeader,
  workspaceInvoiceLedger,
  workspaceSourceReconciliation,
  workspaceTransactions,
} from "./testData";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), message: vi.fn(), warning: vi.fn(), info: vi.fn() } }));

const get = vi.mocked(api.get);
const ID = WORKSPACE_LICENCE_ID;
const TRANSACTIONS_URL = `licence-balances/${ID}/transactions/`;
const INVOICE_LEDGER_URL = `licence-balances/${ID}/invoice-ledger/`;
const SOURCE_URL = `licence-balances/${ID}/source-reconciliation/`;
const DETAIL_URL = `licence-balances/${ID}/`;
const HEADER_URL = `licenses/${ID}/`;
const LEDGER_URL = `licence-balances/${ID}/items/101/`;
const DRILLDOWN_URL = `licence-balances/${ID}/items/101/drilldown/`;

/** Latest router search string, so assertions can read the URL the user would see. */
const location = { search: "" };
function LocationProbe() {
  location.search = useLocation().search;
  return null;
}

const listRow = {
  id: ID,
  license_number: WORKSPACE_LICENCE_NUMBER,
  license_date: "01-01-2026",
  license_expiry_date: "31-03-2027",
  ledger_date: "05-10-2026",
  port_name: null,
  exporter_name: "ACME Exports",
  exporter_iec: null,
  get_norm_class: "PP",
  get_balance_cif: "250.00",
  current_owner_name: "NEW OWNER LTD",
  licence_status_code: "ACTIVE",
  licence_status_label: "Active",
  available_cif: "1234.56",
  latest_transfer: null,
  purchase_status_label: null,
  purchase_status_code: null,
  is_manually_planned: false,
  has_tl: false,
  has_copy: false,
  has_condition_sheet: false,
};

const listPage = {
  count: 1,
  next: null,
  previous: null,
  total_pages: 1,
  current_page: 1,
  page_size: 25,
  has_next: false,
  has_previous: false,
  results: [listRow],
};

function httpError(status: number) {
  return Object.assign(new Error(`Request failed with status ${status}`), {
    isAxiosError: true,
    response: { status, data: {} },
  });
}

/** Routes each URL to its fixture. Tests can override one URL with an error or other data. */
function installApi(overrides: Record<string, unknown> = {}) {
  const defaults: Record<string, unknown> = {
    "licenses/": listPage,
    [DETAIL_URL]: workspaceDetail,
    [HEADER_URL]: workspaceHeader,
    [TRANSACTIONS_URL]: workspaceTransactions,
    [INVOICE_LEDGER_URL]: workspaceInvoiceLedger,
    [SOURCE_URL]: workspaceSourceReconciliation,
    [LEDGER_URL]: itemLedger,
    [DRILLDOWN_URL]: itemDrilldown,
  };
  get.mockReset();
  get.mockImplementation(((url: string) => {
    const value = url in overrides ? overrides[url] : url in defaults ? defaults[url] : { results: [] };
    if (value instanceof Error) return Promise.reject(value);
    return Promise.resolve({ data: value });
  }) as never);
}

function callsTo(url: string) {
  return get.mock.calls.filter(([called]) => called === url);
}

const writer = {
  user: null,
  loading: false,
  loginSuccess: () => {},
  updateUser: () => {},
  logout: async () => {},
  hasRole: () => false,
  hasAnyRole: (roles: string[]) => roles.includes("LICENSE_MANAGER"),
  isSuperAdmin: () => false,
  canManageUsers: () => false,
} as unknown as AuthContextValue;

function renderList(url: string, auth?: AuthContextValue) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const page = (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/licenses" element={<LicenseListPage />} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return render(auth ? <AuthContext.Provider value={auth}>{page}</AuthContext.Provider> : page);
}

/** Cells of a table row as text, in DOM order. */
function cellsOf(row: Element) {
  return Array.from(row.querySelectorAll("th, td")).map((cell) => cell.textContent?.trim() ?? "");
}

const TAB_NAME = {
  overview: "Overview",
  items: "Items & Balance",
  invoices: "Invoices & Sales",
  reconciliation: "Reconciliation",
} as const;

/**
 * Renders the list, opens the licence from its row, and selects `tab` when given.
 * The workspace is page state, so nothing is passed through the URL.
 */
async function renderOpen(options: { tab?: keyof typeof TAB_NAME; auth?: AuthContextValue; url?: string } = {}) {
  const user = userEvent.setup();
  const rendered = renderList(options.url ?? "/licenses", options.auth);
  const row = await screen.findByRole("article", { name: `License ${WORKSPACE_LICENCE_NUMBER}` });
  await user.click(within(row).getByRole("button", { expanded: false }));
  await screen.findByTestId("licence-workspace");
  if (options.tab) await user.click(screen.getByRole("tab", { name: TAB_NAME[options.tab] }));
  return { ...rendered, user, row };
}

/** Page 1 holds the licence. Page 2 holds a different one. */
function installTwoPages() {
  const second = { ...listRow, id: ID + 1, license_number: "0310835999" };
  const pageOne = { ...listPage, count: 26, total_pages: 2, current_page: 1, has_next: true, results: [listRow] };
  const pageTwo = { ...listPage, count: 26, total_pages: 2, current_page: 2, has_previous: true, results: [second] };
  installApi();
  const fallback = get.getMockImplementation();
  get.mockImplementation(((url: string, config?: { params?: Record<string, unknown> }) => {
    if (url === "licenses/") {
      return Promise.resolve({ data: Number(config?.params?.page ?? 1) === 2 ? pageTwo : pageOne });
    }
    return fallback?.(url, config);
  }) as never);
}

beforeEach(() => {
  location.search = "";
  installApi();
});

describe("licence workspace: opening and closing", () => {
  it("renders the workspace inside the open licence's row and loads only the header and detail", async () => {
    await renderOpen();

    expect(await screen.findByRole("heading", { name: "Licence workspace" })).toBeInTheDocument();
    const row = screen.getByRole("article", { name: `License ${WORKSPACE_LICENCE_NUMBER}` });
    expect(row).toHaveAttribute("data-expanded", "true");
    expect(within(row).getByRole("region", { name: `Workspace for licence ${WORKSPACE_LICENCE_NUMBER}` })).toContainElement(
      within(row).getByTestId("licence-workspace"),
    );
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    await waitFor(() => expect(callsTo(DETAIL_URL)).toHaveLength(1));
    expect(callsTo(HEADER_URL)).toHaveLength(1);
    // Tab data is fetched only when its tab is selected.
    expect(callsTo(TRANSACTIONS_URL)).toHaveLength(0);
    expect(callsTo(SOURCE_URL)).toHaveLength(0);
    expect(callsTo(LEDGER_URL)).toHaveLength(0);
  });

  it("expands the row inline without changing the list filters, and collapses it on a second click", async () => {
    const user = userEvent.setup();
    renderList("/licenses?search=acme&is_expired=True");

    const row = await screen.findByRole("article", { name: `License ${WORKSPACE_LICENCE_NUMBER}` });
    expect(row).not.toHaveAttribute("data-expanded");
    await user.click(within(row).getByRole("button", { expanded: false }));
    expect(await within(row).findByTestId("licence-workspace")).toBeInTheDocument();
    expect(row).toHaveAttribute("data-expanded", "true");
    expect(new URLSearchParams(location.search).get("search")).toBe("acme");
    expect(new URLSearchParams(location.search).get("is_expired")).toBe("True");

    await user.click(within(row).getByRole("button", { expanded: true }));
    await waitFor(() => expect(screen.queryByTestId("licence-workspace")).not.toBeInTheDocument());
    expect(row).not.toHaveAttribute("data-expanded");
  });

  it("closes with Close, collapses the row, and keeps the list filters", async () => {
    const { user, row } = await renderOpen({ url: "/licenses?search=acme&is_expired=True" });

    await user.click(screen.getByRole("button", { name: "Close" }));

    await waitFor(() => expect(screen.queryByTestId("licence-workspace")).not.toBeInTheDocument());
    expect(row).not.toHaveAttribute("data-expanded");
    expect(new URLSearchParams(location.search).get("search")).toBe("acme");
  });

  it("keeps one licence expanded: opening another row collapses the first and starts the new one on Overview", async () => {
    const user = userEvent.setup();
    const second = { ...listRow, id: ID + 1, license_number: "0310835999" };
    installApi({ "licenses/": { ...listPage, count: 2, results: [listRow, second] } });
    renderList("/licenses");

    const [firstRow, secondRow] = await screen.findAllByRole("article");
    await user.click(within(firstRow).getByRole("button", { expanded: false }));
    expect(await within(firstRow).findByTestId("licence-workspace")).toBeInTheDocument();
    await user.click(within(firstRow).getByRole("tab", { name: "Items & Balance" }));

    await user.click(within(secondRow).getByRole("button", { expanded: false }));

    await waitFor(() => expect(firstRow).not.toHaveAttribute("data-expanded"));
    expect(screen.getAllByTestId("licence-workspace")).toHaveLength(1);
    expect(within(secondRow).getByTestId("licence-workspace")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
  });

  it("shows Edit only to licence managers", async () => {
    const first = await renderOpen({ auth: writer });
    expect(await screen.findByRole("link", { name: "Edit" })).toHaveAttribute("href", `/licenses/${ID}/edit`);
    first.unmount();

    await renderOpen();
    expect(screen.queryByRole("link", { name: "Edit" })).not.toBeInTheDocument();
  });
});

describe("licence workspace: page state", () => {
  it("a licence number in the URL does not open the workspace on load", async () => {
    renderList(`/licenses?licence=${ID}`);

    await screen.findByRole("article", { name: `License ${WORKSPACE_LICENCE_NUMBER}` });
    expect(screen.queryByTestId("licence-workspace")).not.toBeInTheDocument();
  });

  it("reloading the page starts with no licence open", async () => {
    const first = await renderOpen({ tab: "items" });
    first.unmount();

    renderList("/licenses");
    await screen.findByRole("article", { name: `License ${WORKSPACE_LICENCE_NUMBER}` });
    expect(screen.queryByTestId("licence-workspace")).not.toBeInTheDocument();
  });

  it("stays open when the page changes, shows the notice while the licence is off the page, and returns to its row", async () => {
    installTwoPages();
    const { user, row } = await renderOpen();

    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("The open licence is not on this page of results. Its workspace stays open here until you close it.")).toBeInTheDocument();
    expect(screen.getByTestId("licence-workspace")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");

    await user.click(screen.getByRole("button", { name: "Previous page" }));
    await waitFor(() => expect(row).toHaveAttribute("data-expanded", "true"));
    expect(screen.queryByText(/not on this page of results/)).not.toBeInTheDocument();
    expect(screen.getAllByTestId("licence-workspace")).toHaveLength(1);
  });

  it("a filter change closes the workspace", async () => {
    const { user, row } = await renderOpen();

    await user.click(screen.getByRole("radio", { name: "Expired" }));

    await waitFor(() => expect(screen.queryByTestId("licence-workspace")).not.toBeInTheDocument());
    expect(row).not.toHaveAttribute("data-expanded");
  });

  it("a search change closes the workspace", async () => {
    const { user } = await renderOpen();

    await user.type(screen.getByRole("searchbox", { name: "Search licences" }), "acme{Enter}");

    await waitFor(() => expect(screen.queryByTestId("licence-workspace")).not.toBeInTheDocument());
  });

  it("Refresh keeps the workspace open and the selected tab", async () => {
    const { user } = await renderOpen({ tab: "invoices" });

    await user.click(screen.getByRole("button", { name: "Refresh" }));

    expect(screen.getByTestId("licence-workspace")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Invoices & Sales" })).toHaveAttribute("aria-selected", "true");
  });
});

describe("licence workspace: navigation", () => {
  it("shows Overview, Planning, Items & Balance, Invoices & Sales and Reconciliation, in that order", async () => {
    await renderOpen();
    await screen.findByRole("heading", { name: "Licence workspace" });

    const tabs = screen.getAllByRole("tab").map((tab) => tab.textContent);
    expect(tabs).toEqual(["Overview", "Planning", "Items & Balance", "Invoices & Sales", "Reconciliation"]);
    expect(screen.queryByRole("tab", { name: "BOEs" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Allotments" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Ledger" })).not.toBeInTheDocument();
  });

  it("moves between tabs with the arrow keys and keeps the licence open", async () => {
    const { user } = await renderOpen();

    screen.getByRole("tab", { name: "Overview" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(await screen.findByRole("tab", { name: "Planning" })).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{ArrowRight}");
    expect(await screen.findByRole("tab", { name: "Items & Balance" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("licence-workspace")).toBeInTheDocument();
  });

  it("opens the movement ledger for an item from Items & Balance", async () => {
    const { user } = await renderOpen({ tab: "items" });

    await user.click(await screen.findByRole("button", { name: "Show sources for SR 1" }));
    await user.click(await screen.findByRole("button", { name: "Open movement ledger" }));

    expect(await screen.findByRole("heading", { name: /Movement ledger: SR 1/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Items & Balance" })).toHaveAttribute("aria-selected", "true");
  });

  it("shows the Not yet available card in the Overview footer", async () => {
    await renderOpen();

    expect(await screen.findByText("Not yet available in this build")).toBeInTheDocument();
    expect(screen.getByText("Financial ledger")).toBeInTheDocument();
    expect(screen.getAllByText("Planning").length).toBeGreaterThan(0);
  });
});

describe("licence workspace: header", () => {
  it("shows the fields the accordion row does not, and the available quantity, with their status", async () => {
    await renderOpen();
    const workspace = await screen.findByTestId("licence-workspace");
    const header = within(workspace);
    // Only the header's definition list: the Overview panels have their own terms.
    const fields = workspace.querySelector("header dl") as HTMLElement;

    expect(within(fields).getAllByRole("term").map((term) => term.textContent)).toEqual([
      "Importer", "IEC", "Port", "Purchase status",
    ]);
    expect(await header.findByText("0300000001")).toBeInTheDocument();
    expect(header.getByText("Available quantity")).toBeInTheDocument();
    expect(header.getAllByText("Over-utilised").length).toBeGreaterThan(0);
  });

  it("does not repeat the licence number, status, owner, dates, exporter, norm class or available CIF", async () => {
    await renderOpen();
    const workspace = within(await screen.findByTestId("licence-workspace"));
    await workspace.findByRole("heading", { name: "Licence workspace" });

    expect(workspace.queryByRole("heading", { name: WORKSPACE_LICENCE_NUMBER })).not.toBeInTheDocument();
    expect(workspace.queryByText("NEW OWNER LTD")).not.toBeInTheDocument();
    expect(workspace.queryByText("Current owner")).not.toBeInTheDocument();
    for (const label of ["Licence date", "Expiry date", "Ledger date", "Exporter", "Norm class", "Active"]) {
      expect(workspace.queryByText(label, { exact: true }), label).not.toBeInTheDocument();
    }
    expect(workspace.queryByText("Available CIF (USD)")).not.toBeInTheDocument();
  });

  it("the reconciliation tab does not repeat the available CIF", async () => {
    await renderOpen({ tab: "reconciliation" });
    const workspace = within(await screen.findByTestId("licence-workspace"));
    await workspace.findByRole("heading", { name: "Licence balance" });

    expect(workspace.queryByText("Reconciled available (CIF, USD)")).not.toBeInTheDocument();
    expect(workspace.queryByText("Available CIF (USD)")).not.toBeInTheDocument();
  });
});

describe("licence workspace: accordion summary", () => {
  it("shows the nine summary fields in the collapsed header, with Ledger Date once", async () => {
    renderList("/licenses?search=acme");
    const row = await screen.findByRole("article", { name: `License ${WORKSPACE_LICENCE_NUMBER}` });

    expect(within(row).getByText(WORKSPACE_LICENCE_NUMBER)).toBeInTheDocument();
    expect(within(row).getByText("Active")).toBeInTheDocument();
    expect(within(row).getByText("01-01-2026")).toBeInTheDocument();
    expect(within(row).getByText("31-03-2027")).toBeInTheDocument();
    expect(within(row).getAllByText("Ledger date")).toHaveLength(1);
    expect(within(row).getByText("05-10-2026")).toBeInTheDocument();
    expect(within(row).getByText("1,234.56")).toBeInTheDocument();
    expect(within(row).getByText("NEW OWNER LTD")).toBeInTheDocument();
    expect(within(row).getByText("ACME Exports")).toBeInTheDocument();
    expect(within(row).getByText("PP")).toBeInTheDocument();
  });

  it("keeps the same summary header when the licence is expanded, and the workspace does not repeat it", async () => {
    const user = userEvent.setup();
    renderList("/licenses?search=acme");
    const row = await screen.findByRole("article", { name: `License ${WORKSPACE_LICENCE_NUMBER}` });
    await user.click(within(row).getByRole("button", { expanded: false }));

    const workspace = within(await within(row).findByTestId("licence-workspace"));
    expect(within(row).getByText("1,234.56")).toBeInTheDocument();
    expect(within(row).getByText("NEW OWNER LTD")).toBeInTheDocument();
    expect(within(row).getAllByText("Ledger date")).toHaveLength(1);
    expect(workspace.queryByText("1,234.56")).not.toBeInTheDocument();
  });

  it("shows an expired licence as Expired from the server, with the label the server sends", async () => {
    installApi({
      "licenses/": {
        ...listPage,
        results: [{ ...listRow, licence_status_code: "EXPIRED", licence_status_label: "Expired" }],
      },
    });
    renderList("/licenses?search=acme");
    const row = await screen.findByRole("article", { name: `License ${WORKSPACE_LICENCE_NUMBER}` });

    expect(within(row).getByText("Expired")).toBeInTheDocument();
    expect(within(row).queryByText("Active")).not.toBeInTheDocument();
  });

  it("shows a status code this screen does not know, with the server's label", async () => {
    installApi({
      "licenses/": {
        ...listPage,
        results: [{ ...listRow, licence_status_code: "CANCELLED", licence_status_label: "Cancelled" }],
      },
    });
    renderList("/licenses?search=acme");
    const row = await screen.findByRole("article", { name: `License ${WORKSPACE_LICENCE_NUMBER}` });

    expect(within(row).getByText("Cancelled")).toBeInTheDocument();
  });

  it("shows a dash for an owner or CIF that is not recorded, and does not invent one", async () => {
    installApi({
      "licenses/": { ...listPage, results: [{ ...listRow, current_owner_name: null, available_cif: null }] },
    });
    renderList("/licenses?search=acme");
    const row = await screen.findByRole("article", { name: `License ${WORKSPACE_LICENCE_NUMBER}` });

    expect(within(row).queryByText("NEW OWNER LTD")).not.toBeInTheDocument();
    expect(within(row).getByText("Current owner").nextElementSibling).toHaveTextContent("—");
    expect(within(row).getByText("Available balance CIF (USD)").nextElementSibling).toHaveTextContent("—");
  });
});

describe("licence workspace: operations", () => {
  it("shows the balance downloads and, for a licence manager, the write actions in the Actions menu", async () => {
    const user = userEvent.setup();
    await renderOpen({ auth: writer });
    await screen.findByTestId("licence-workspace");

    await user.click(screen.getByRole("button", { name: "Licence actions" }));

    expect(await screen.findByRole("menuitem", { name: "Balance PDF" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Balance Excel" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Auto plan" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Fetch from DGFT" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Delete licence" })).toBeInTheDocument();
  });

  it("hides the write actions from a viewer, who keeps the balance downloads", async () => {
    const user = userEvent.setup();
    await renderOpen();
    await screen.findByTestId("licence-workspace");

    await user.click(screen.getByRole("button", { name: "Licence actions" }));

    expect(await screen.findByRole("menuitem", { name: "Balance PDF" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Delete licence" })).not.toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Auto plan" })).not.toBeInTheDocument();
  });
});

describe("licence workspace: overview and items", () => {
  it("shows the review flags in plain words and the previous-owner BOE debit, quantity first", async () => {
    await renderOpen();

    expect(await screen.findByText("Legacy balance engine disagrees with the reconciled figure — review")).toBeInTheDocument();
    expect(screen.getByText("Available is negative")).toBeInTheDocument();
    expect(screen.getAllByText("Of which previous-owner BOEs (deducted)")).toHaveLength(2);
    expect(screen.getByTestId("legacy-note")).toHaveTextContent("Legacy balance engine shows 260.00 USD");
  });

  it("renders one row per item on the Items & Balance tab", async () => {
    await renderOpen({ tab: "items" });

    const table = await screen.findByTestId("item-table");
    const rows = within(table).getAllByRole("row").slice(2);
    expect(rows).toHaveLength(3);
    expect(within(table).getByText("Cotton yarn")).toBeInTheDocument();
    expect(within(table).getByText("Wool blend")).toBeInTheDocument();
    expect(within(table).getByText("Mixed chemicals")).toBeInTheDocument();
  });

  it("opens the BOE debit details from the Debited figure on Items & Balance", async () => {
    const user = userEvent.setup();
    await renderOpen({ tab: "items" });

    await user.click(await screen.findByRole("button", { name: "Open BOE debit details for SR 1, quantity" }));
    expect(await screen.findByRole("dialog", { name: /BOE Debit Details/ })).toBeInTheDocument();
  });
});

describe("licence workspace: invoices and sales", () => {
  it("fetches the purchase and sale ledger only when Invoices & Sales opens", async () => {
    const user = userEvent.setup();
    await renderOpen();
    await screen.findByRole("heading", { name: "Licence workspace" });
    expect(callsTo(INVOICE_LEDGER_URL)).toHaveLength(0);

    await user.click(screen.getByRole("tab", { name: "Invoices & Sales" }));
    expect(await screen.findByRole("button", { name: "LGL/2026-27/0010" })).toBeInTheDocument();
    expect(callsTo(INVOICE_LEDGER_URL)).toHaveLength(1);
    expect(callsTo(TRANSACTIONS_URL)).toHaveLength(0);
  });

  it("keeps negative amounts with their sign and colour on Invoices & Sales", async () => {
    const user = userEvent.setup();
    await renderOpen({ tab: "invoices" });

    const creditNoteRow = (await screen.findByRole("button", { name: "CREDIT NOTE LGL/2026-27/0010" })).closest("tr") as HTMLElement;
    expect(within(creditNoteRow).getByText("-1,000.00")).toHaveClass("text-destructive");
    await user.click(screen.getByRole("tab", { name: "Reconciliation" }));
    expect(await screen.findByRole("heading", { name: "Source-level reconciliation" })).toBeInTheDocument();
  });
});

describe("licence workspace: reconciliation", () => {
  it("shows the source-level difference with quantity first, and the summary of items that reconcile", async () => {
    await renderOpen({ tab: "reconciliation" });

    expect(await screen.findByText("1 of 2 items reconcile to their source records.")).toBeInTheDocument();
    const differences = screen.getByRole("table", { name: /Figures where the source records and the item figures differ/ });
    const debited = within(differences).getByRole("row", { name: /debited/i });
    expect(cellsOf(debited)).toEqual(["1", "debited", "40.000", "40.000", "400.00", "390.00", "MISMATCH", "Show in Items & Balance"]);
    const headers = within(differences).getAllByRole("columnheader").map((th) => th.textContent);
    expect(headers.indexOf("Quantity (source)")).toBeLessThan(headers.indexOf("CIF (USD, source)"));
  });

  it("lists allocation records that need review, with quantity and CIF and the reason in plain words", async () => {
    await renderOpen({ tab: "reconciliation" });

    const issues = await screen.findByRole("table", { name: /Allocation records that need review/ });
    const row = within(issues).getByRole("row", { name: /BOE-0999/ });
    expect(cellsOf(row).slice(0, 6)).toEqual([
      "1",
      "Bill of entry",
      "BOE-0999",
      "LINKED TO AN OVER-LINKED SALE (excess counted on the invoice)",
      "0.000 MTS",
      "50.00",
    ]);
    expect(within(row).getByText(/OVER_LINKED_MIXED_OWNERSHIP/)).toBeInTheDocument();
  });

  it("shows the bills of entry behind the balance with quantity before CIF, and badges a previous-owner BOE", async () => {
    await renderOpen({ tab: "reconciliation" });

    const boes = await screen.findByRole("table", { name: /Bills of entry behind this licence's balance/ });
    const headers = within(boes).getAllByRole("columnheader").map((th) => th.textContent);
    expect(headers.slice(4, 10)).toEqual([
      "BOE Quantity",
      "BOE CIF (USD)",
      "Covered by Sale — Quantity",
      "Covered by Sale — CIF (USD)",
      "Uncovered — Quantity",
      "Uncovered — CIF (USD)",
    ]);
    const bo1001 = within(boes).getByRole("row", { name: /BOE-1001/ });
    expect(cellsOf(bo1001).slice(4, 10)).toEqual(["40.000 MTS", "400.00", "20.000 MTS", "200.00", "20.000 MTS", "200.00"]);
    const previousOwner = within(boes).getByRole("row", { name: /BOE-0999/ });
    expect(within(previousOwner).getByText("Previous owner")).toBeInTheDocument();
    expect(bo1001).not.toHaveAttribute("data-previous-owner");
  });

  it("sends an item from the reconciliation list to Items & Balance, with its ledger open", async () => {
    const user = userEvent.setup();
    await renderOpen({ tab: "reconciliation" });

    const [button] = await screen.findAllByRole("button", { name: "Show SR 1 in Items & Balance" });
    await user.click(button);

    expect(await screen.findByRole("tab", { name: "Items & Balance" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByRole("heading", { name: /Movement ledger: SR 1/ })).toBeInTheDocument();
  });

  it("lists every item that is not reconciled and its flags", async () => {
    await renderOpen({ tab: "reconciliation" });

    const section = await screen.findByRole("heading", { name: /Items not reconciled \(\d+\)/ });
    const region = section.closest("section") as HTMLElement;
    expect(within(region).getByText("Cotton yarn")).toBeInTheDocument();
    expect(
      within(region).getByText(
        "Over-linked excess whose sale has both previous-owner and current-owner BOEs; the excess owner is not determined — review",
      ),
    ).toBeInTheDocument();
  });

  it("lists negative balances with quantity before CIF, and the unit issue for SR 3", async () => {
    await renderOpen({ tab: "reconciliation" });

    const negativeHeading = await screen.findByRole("heading", { name: "Negative balances (1)" });
    const negativeRegion = negativeHeading.closest("section") as HTMLElement;
    const text = negativeRegion.textContent ?? "";
    expect(text.indexOf("-5.000 KGS")).toBeLessThan(text.indexOf("-20.00"));
    expect(within(negativeRegion).getByText("-20.00")).toBeInTheDocument();
    expect(within(negativeRegion).getByText("-5.000 KGS")).toBeInTheDocument();

    const unitHeading = screen.getByRole("heading", { name: "Unit issues (1)" });
    expect(within(unitHeading.closest("section") as HTMLElement).getByText(/Unit recorded as mts/)).toBeInTheDocument();
  });

  it("explains a legacy mismatch and shows both figures", async () => {
    await renderOpen({ tab: "reconciliation" });

    expect(await screen.findByText(/The legacy balance engine and the reconciled item calculation disagree/)).toBeInTheDocument();
    expect(screen.getByText("260.00")).toBeInTheDocument();
  });
});

describe("licence workspace: loading and error states", () => {
  it("shows an alert with Retry when the bills of entry are forbidden, and the page stays usable", async () => {
    installApi({ [TRANSACTIONS_URL]: httpError(403) });
    await renderOpen({ tab: "reconciliation" });

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("You do not have permission to view licence balances.")).toBeInTheDocument();
    expect(within(alert).getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Licence workspace" })).toBeInTheDocument();
  });

  it("explains an expired session on the Overview tab without crashing", async () => {
    installApi({ [DETAIL_URL]: httpError(401) });
    await renderOpen();

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Your session has expired. Sign in again to continue.")).toBeInTheDocument();
    // The header still loads from the legacy endpoint, so the licence number stays visible.
    expect(screen.getByRole("heading", { name: "Licence workspace" })).toBeInTheDocument();
  });

  it("retries a failed bills-of-entry load", async () => {
    const user = userEvent.setup();
    let failures = 1;
    installApi();
    get.mockImplementation(((url: string) => {
      if (url === TRANSACTIONS_URL && failures > 0) {
        failures -= 1;
        // 403 is not retried automatically, so the first failure is shown and Retry is the only way forward.
        return Promise.reject(httpError(403));
      }
      if (url === TRANSACTIONS_URL) return Promise.resolve({ data: workspaceTransactions });
      if (url === DETAIL_URL) return Promise.resolve({ data: workspaceDetail });
      if (url === HEADER_URL) return Promise.resolve({ data: workspaceHeader });
      if (url === SOURCE_URL) return Promise.resolve({ data: workspaceSourceReconciliation });
      if (url === "licenses/") return Promise.resolve({ data: listPage });
      return Promise.resolve({ data: { results: [] } });
    }) as never);

    await renderOpen({ tab: "reconciliation" });
    const alert = await screen.findByRole("alert");
    await user.click(within(alert).getByRole("button", { name: "Retry" }));

    expect(await screen.findByText("BOE-1001")).toBeInTheDocument();
  });
});
