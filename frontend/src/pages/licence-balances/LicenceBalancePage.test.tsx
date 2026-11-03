import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import api from "@/api/axios";
import LicenceBalanceRoutes from "./LicenceBalanceRoutes";
import { COLUMN_STORAGE_KEY } from "./columns";
import { SEARCH_DEBOUNCE_MS } from "./listParams";
import { listResponse, overUtilisedSummary, reconciledSummary } from "./testData";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn() } }));

const get = vi.mocked(api.get);

function listCalls() {
  return get.mock.calls.filter(([url]) => url === "licence-balances/");
}

function lastListParams() {
  const calls = listCalls();
  return calls[calls.length - 1]?.[1] as { params?: Record<string, unknown> } | undefined;
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location-search">{location.search}</output>;
}

function renderPage(url = "/licence-balances") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/licence-balances/*" element={<LicenceBalanceRoutes />} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function rowFor(licenceNumber: string) {
  const row = (await screen.findByRole("rowheader", { name: licenceNumber })).closest("tr");
  if (!row) throw new Error(`No row for ${licenceNumber}`);
  return row;
}

beforeEach(() => {
  get.mockReset();
  window.localStorage.clear();
  get.mockResolvedValue({ data: listResponse() } as never);
});

describe("LicenceBalancePage: table", () => {
  it("renders one row per licence from the fixture response, with the record count", async () => {
    renderPage();

    const table = await screen.findByTestId("balance-table");
    expect(within(table).getByRole("rowheader", { name: reconciledSummary.licence_number })).toBeInTheDocument();
    expect(within(table).getByRole("rowheader", { name: overUtilisedSummary.licence_number })).toBeInTheDocument();
    expect(screen.getByText("2 licences")).toBeInTheDocument();
    expect(screen.getByText("Showing 1–2 of 2")).toBeInTheDocument();
  });

  it("shows the compact default columns and hides optional ones", async () => {
    renderPage();
    await screen.findByTestId("balance-table");

    expect(screen.getByRole("columnheader", { name: /Available CIF/ })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Available qty/ })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /Original qty/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /Legacy balance/ })).not.toBeInTheDocument();
  });

  it("formats CIF with 2 decimals and quantity with its unit", async () => {
    renderPage();
    const row = await rowFor(reconciledSummary.licence_number);

    expect(within(row).getByText("1,000.00")).toBeInTheDocument();
    expect(within(row).getByText("25.000 KGS")).toBeInTheDocument();
  });

  it("shows a negative value in red with its sign and an over-utilised badge", async () => {
    renderPage();
    const row = await rowFor(overUtilisedSummary.licence_number);

    const negative = within(row).getByText("-20.00");
    expect(negative.closest("[class*='text-destructive']")).not.toBeNull();
    expect(within(row).getAllByText("Over-utilised").length).toBeGreaterThan(0);
  });

  it("shows 'Unit unverified' text, not a number, for an unverified quantity", async () => {
    renderPage();
    const row = await rowFor(overUtilisedSummary.licence_number);

    expect(within(row).getAllByText("Unit unverified").length).toBeGreaterThan(0);
    expect(within(row).queryByText(/^0\.000/)).not.toBeInTheDocument();
    expect(within(row).queryByText(/^-?\d+\.\d{3}/)).not.toBeInTheDocument();
  });

  it("links each row to its detail page with a real Open link", async () => {
    renderPage();
    const open = await screen.findByRole("link", { name: `Open ${reconciledSummary.licence_number}` });

    expect(open).toHaveAttribute("href", `/licence-balances/${reconciledSummary.licence_id}`);
    expect(open).toHaveTextContent("Open");
  });

  it("opens the reasons dialog from the status button and lists the flags in plain language", async () => {
    const user = userEvent.setup();
    renderPage();
    const row = await rowFor(overUtilisedSummary.licence_number);

    await user.click(within(row).getByRole("button", { name: /Over-utilised: show reasons/ }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Available is negative")).toBeInTheDocument();
    expect(within(dialog).getByText("Quantity unit is not verified")).toBeInTheDocument();
  });
});

describe("LicenceBalancePage: column visibility", () => {
  it("reveals a hidden column from the menu and persists the choice to localStorage", async () => {
    const user = userEvent.setup();
    const { unmount } = renderPage();
    await screen.findByTestId("balance-table");

    await user.click(screen.getByTestId("column-toggle"));
    await user.click(await screen.findByRole("menuitemcheckbox", { name: "Original qty" }));
    // The menu stays open for multi-select; close it so the table is accessible again.
    await user.keyboard("{Escape}");

    expect(await screen.findByRole("columnheader", { name: /Original qty/ })).toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem(COLUMN_STORAGE_KEY) ?? "[]")).toEqual(["qtyOriginal"]);

    unmount();
    renderPage();
    await screen.findByTestId("balance-table");
    expect(screen.getByRole("columnheader", { name: /Original qty/ })).toBeInTheDocument();
  });
});

describe("LicenceBalancePage: filters and URL", () => {
  it("resets the page to 1 and issues exactly one request when the expiry filter changes", async () => {
    const user = userEvent.setup();
    get.mockResolvedValue({ data: listResponse({ count: 120, page: 2, total_pages: 5, has_previous: true, has_next: true }) } as never);
    renderPage("/licence-balances?page=2");
    await screen.findByTestId("balance-table");
    const before = listCalls().length;

    await user.click(screen.getByRole("button", { name: "Expiry: Expired" }));

    await waitFor(() => expect(listCalls().length).toBe(before + 1));
    expect(lastListParams()?.params).toMatchObject({ page: 1, expiry: "expired" });
    expect(screen.getByTestId("location-search")).toHaveTextContent("expiry=expired");
    expect(screen.getByTestId("location-search").textContent).not.toContain("page=2");
  });

  it("commits a typed search once, after the debounce, and resets the page", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("balance-table");
    const before = listCalls().length;

    await user.type(screen.getByRole("searchbox", { name: "Search by licence number or importer" }), "acme");
    expect(listCalls().length).toBe(before);

    await waitFor(() => expect(listCalls().length).toBe(before + 1), { timeout: SEARCH_DEBOUNCE_MS + 1000 });
    expect(lastListParams()?.params).toMatchObject({ search: "acme", page: 1 });
  });

  it("disables Previous on the first page and Next on the last page", async () => {
    renderPage();
    await screen.findByTestId("balance-table");

    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });
});

describe("LicenceBalancePage: states", () => {
  it("shows a loading status while the first request is in flight", () => {
    get.mockReturnValue(new Promise(() => {}) as never);
    renderPage();

    expect(screen.getByRole("status", { name: "Loading licence balances" })).toBeInTheDocument();
  });

  it("shows the empty state text when no licence matches", async () => {
    get.mockResolvedValue({ data: listResponse({ count: 0, total_pages: 1, results: [] }) } as never);
    renderPage();

    expect(await screen.findByText("No licences match these filters")).toBeInTheDocument();
  });

  it("shows an alert with Retry on failure, and Retry reloads the data", async () => {
    const user = userEvent.setup();
    const failure = Object.assign(new Error("Server error"), { isAxiosError: true, response: { status: 500 } });
    get.mockRejectedValueOnce(failure);
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Licence balances could not be loaded.")).toBeInTheDocument();

    await user.click(within(alert).getByRole("button", { name: "Retry" }));

    expect(await screen.findByTestId("balance-table")).toBeInTheDocument();
    expect(listCalls().length).toBe(2);
  });
});
