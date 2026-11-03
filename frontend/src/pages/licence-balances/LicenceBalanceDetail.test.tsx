import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import api from "@/api/axios";
import LicenceBalanceRoutes from "./LicenceBalanceRoutes";
import { itemDrilldown } from "./drilldownTestData";
import { itemLedger, licenceDetail } from "./testData";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn() } }));

const get = vi.mocked(api.get);
const DETAIL_URL = `licence-balances/${licenceDetail.licence_id}/`;
const LEDGER_URL = `licence-balances/${licenceDetail.licence_id}/items/${licenceDetail.items[0].item_id}/`;
const DRILLDOWN_URL = `licence-balances/${licenceDetail.licence_id}/items/${licenceDetail.items[0].item_id}/drilldown/`;

function callsTo(url: string) {
  return get.mock.calls.filter(([called]) => called === url);
}

function renderDetail(url = `/licence-balances/${licenceDetail.licence_id}`, state?: unknown) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[{ pathname: url, state }]}>
        <Routes>
          <Route path="/licence-balances/*" element={<LicenceBalanceRoutes />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  get.mockImplementation(((url: string) => {
    if (url === DETAIL_URL) return Promise.resolve({ data: licenceDetail });
    if (url === LEDGER_URL) return Promise.resolve({ data: itemLedger });
    if (url === DRILLDOWN_URL) return Promise.resolve({ data: itemDrilldown });
    return Promise.reject(new Error(`unexpected ${url}`));
  }) as never);
});

describe("LicenceBalanceDetail: summary", () => {
  it("shows the licence header, the CIF and quantity panels and the previous-owner BOE debit", async () => {
    renderDetail();

    expect(await screen.findByRole("heading", { name: `Licence ${licenceDetail.licence_number}` })).toBeInTheDocument();
    const summary = screen.getByRole("region", { name: "Balance summary" });
    expect(within(summary).getByText("Original licence value")).toBeInTheDocument();
    // Both panels carry the same row labels (CIF and quantity).
    expect(within(summary).getAllByText("Used through BOEs (debited)")).toHaveLength(2);
    expect(within(summary).getAllByText("Reserved for customers (allotted)")).toHaveLength(2);
    expect(within(summary).getAllByText("Of which previous-owner BOEs (deducted)")).toHaveLength(2);
  });

  it("states the legacy mismatch clearly and does not hide the difference", async () => {
    renderDetail();

    const note = await screen.findByTestId("legacy-note");
    expect(within(note).getByText(/Legacy balance engine shows 260\.00 USD/)).toBeInTheDocument();
    expect(within(note).getByText(/Review required/)).toBeInTheDocument();
  });

  it("links back to the list, keeping the query string the list was opened with", async () => {
    renderDetail(`/licence-balances/${licenceDetail.licence_id}`, { from: "?expiry=expired&page=2" });

    const back = await screen.findByRole("link", { name: /Back to licence balances/ });
    expect(back).toHaveAttribute("href", "/licence-balances?expiry=expired&page=2");
  });

  it("shows a not-found message for an unknown licence", async () => {
    get.mockRejectedValue(Object.assign(new Error("Not found"), { isAxiosError: true, response: { status: 404 } }));
    renderDetail("/licence-balances/999");

    expect(await screen.findByText("Licence not found")).toBeInTheDocument();
  });
});

describe("LicenceBalanceDetail: item rows", () => {
  it("expands a row to show its three source sections and collapses it again", async () => {
    const user = userEvent.setup();
    renderDetail();
    await screen.findByTestId("item-table");

    const toggle = screen.getByRole("button", { name: "Show sources for SR 1" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("heading", { name: "BOE debits" })).not.toBeInTheDocument();

    await user.click(toggle);

    expect(await screen.findByRole("heading", { name: "BOE debits" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Customer allotments" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Invoices" })).toBeInTheDocument();
    expect(await screen.findByText("2 BOEs · debited 300.00 USD · covered 100.00 USD")).toBeInTheDocument();
    const expanded = screen.getByRole("button", { name: "Hide sources for SR 1" });
    expect(expanded).toHaveAttribute("aria-expanded", "true");
    expect(expanded).toHaveAttribute("aria-controls", "item-101-details");

    await user.click(expanded);
    expect(screen.queryByRole("heading", { name: "BOE debits" })).not.toBeInTheDocument();
  });

  it("opens the BOE drawer from the Debited figure and returns focus to that figure on close", async () => {
    const user = userEvent.setup();
    renderDetail();
    await screen.findByTestId("item-table");

    const figure = screen.getByRole("button", { name: "Open BOE debit details for SR 1, CIF (USD)" });
    await user.click(figure);

    expect(await screen.findByRole("dialog", { name: /BOE Debit Details/ })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(figure).toHaveFocus());
  });

  it("opens the allotment and invoice drawers from the Allotted and Invoiced figures", async () => {
    const user = userEvent.setup();
    renderDetail();
    await screen.findByTestId("item-table");

    await user.click(screen.getByRole("button", { name: "Open customer allotment details for SR 1, CIF (USD)" }));
    expect(await screen.findByRole("dialog", { name: /Customer Allotment Details/ })).toBeInTheDocument();
    await user.keyboard("{Escape}");

    await user.click(screen.getByRole("button", { name: "Open invoice details for SR 1, CIF (USD)" }));
    expect(await screen.findByRole("dialog", { name: /Invoice Details/ })).toBeInTheDocument();
  });

  it("makes only the Debited, Allotted and Invoiced figures clickable", async () => {
    renderDetail();
    await screen.findByTestId("item-table");
    const figureButtons = screen.getAllByRole("button", { name: /^Open .* for SR 1, /i });
    expect(figureButtons.map((button) => button.getAttribute("aria-label"))).toEqual([
      "Open BOE debit details for SR 1, quantity",
      "Open BOE debit details for SR 1, CIF (USD)",
      "Open customer allotment details for SR 1, quantity",
      "Open customer allotment details for SR 1, CIF (USD)",
      "Open invoice details for SR 1, quantity",
      "Open invoice details for SR 1, CIF (USD)",
    ]);
  });

  it("lists Quantity before CIF in every figure group of the item table", async () => {
    renderDetail();
    const table = await screen.findByTestId("item-table");
    const subHeadings = Array.from(table.querySelectorAll("thead tr")[1].querySelectorAll("th")).map((th) => th.textContent);
    expect(subHeadings).toEqual(["Quantity", "CIF (USD)", "Quantity", "CIF (USD)", "Quantity", "CIF (USD)", "Quantity", "CIF (USD)", "Quantity", "CIF (USD)"]);
  });

  it("marks an unmapped HS code and a mts unit with a warning", async () => {
    renderDetail();
    const table = await screen.findByTestId("item-table");

    expect(within(table).getByText("Unmapped")).toBeInTheDocument();
    expect(within(table).getByText("Unit not verified")).toBeInTheDocument();
  });
});

describe("LicenceBalanceDetail: movement ledger", () => {
  it("fetches the item endpoint once when opened and renders memo rows in italics", async () => {
    const user = userEvent.setup();
    renderDetail();
    await screen.findByTestId("item-table");

    await user.click(screen.getByRole("button", { name: "Show sources for SR 1" }));
    await user.click(await screen.findByRole("button", { name: "Open movement ledger" }));

    const ledger = await screen.findByTestId("movement-ledger");
    await within(ledger).findByTestId("cif-ledger");
    expect(callsTo(LEDGER_URL)).toHaveLength(1);

    const memoRow = within(ledger).getByText("Sale-covered BOE").closest("tr");
    expect(memoRow).toHaveClass("italic");
    expect(within(ledger).getAllByText("(memo — not deducted)").length).toBeGreaterThan(0);

    // The CIF and quantity ledgers both contain a BOE debit row; check the CIF one.
    const normalRow = within(within(ledger).getByTestId("cif-ledger")).getByText("Bill of entry (used)").closest("tr");
    expect(normalRow).not.toHaveClass("italic");
  });

  it("confirms the ledger's final running balance matches the item's available figure", async () => {
    const user = userEvent.setup();
    renderDetail();
    await screen.findByTestId("item-table");

    await user.click(screen.getByRole("button", { name: "Show sources for SR 1" }));
    await user.click(await screen.findByRole("button", { name: "Open movement ledger" }));

    const check = await screen.findByTestId("cif-ledger-check");
    expect(check).toHaveTextContent("Ledger ends at 600.00 — matches available");
  });

  it("warns when the ledger does not end at the available figure", async () => {
    get.mockImplementation(((url: string) => {
      if (url === DETAIL_URL) return Promise.resolve({ data: licenceDetail });
      if (url === LEDGER_URL) {
        return Promise.resolve({
          data: {
            ...itemLedger,
            cif_movements: itemLedger.cif_movements.map((row) =>
              row.kind === "BOE_DEBIT" ? { ...row, running_balance: "610.00" } : row,
            ),
          },
        });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    }) as never);
    const user = userEvent.setup();
    renderDetail();
    await screen.findByTestId("item-table");

    await user.click(screen.getByRole("button", { name: "Show sources for SR 1" }));
    await user.click(await screen.findByRole("button", { name: "Open movement ledger" }));

    const check = await screen.findByTestId("cif-ledger-check");
    expect(check).toHaveTextContent("Ledger ends at 610.00, but available is 600.00. Review required.");
  });

  it("shows a banner when the item's unit is not verified", async () => {
    get.mockImplementation(((url: string) => {
      if (url === DETAIL_URL) return Promise.resolve({ data: licenceDetail });
      if (url === LEDGER_URL) {
        return Promise.resolve({ data: { ...itemLedger, unit_status: "UNIT_UNVERIFIED" } });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    }) as never);
    const user = userEvent.setup();
    renderDetail();
    await screen.findByTestId("item-table");

    await user.click(screen.getByRole("button", { name: "Show sources for SR 1" }));
    await user.click(await screen.findByRole("button", { name: "Open movement ledger" }));

    expect(await screen.findByText("Quantity unit not verified — figures are shown as recorded.")).toBeInTheDocument();
    await waitFor(() => expect(callsTo(LEDGER_URL)).toHaveLength(1));
  });
});
