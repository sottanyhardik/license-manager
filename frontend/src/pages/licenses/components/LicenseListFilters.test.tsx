import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { useMemo } from "react";
import api from "@/api/axios";
import { LicenseListFilters } from "./LicenseListFilters";
import { useLicenseListState } from "../useLicenseListState";
import { useLicenseLabelLookup } from "../useLicenseFilterOptions";
import { validateLicenseListFilters } from "../licenseListFilters";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }));

const get = vi.mocked(api.get);

const COMPANIES = [
  { id: 1, name: "ACME" },
  { id: 2, name: "Acorn" },
];

function ok(data: unknown) {
  return Promise.resolve({ data } as never);
}

function Harness() {
  const list = useLicenseListState();
  const labels = useLicenseLabelLookup(list.state.filters);
  const errors = useMemo(() => validateLicenseListFilters(list.state.filters), [list.state.filters]);
  const location = useLocation();
  return (
    <>
      <LicenseListFilters
        state={list.state}
        labels={labels}
        errors={errors}
        searchDraft={list.searchDraft}
        onSearchDraftChange={list.setSearchDraft}
        onSearchSubmit={list.commitSearchNow}
        onFilterChange={list.setFilters}
        onRemoveChip={(chip) => list.commit(chip.remove)}
        onClearAll={list.clearToBaseline}
      />
      <output data-testid="location">{location.search}</output>
    </>
  );
}

function renderFilters(url: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/licenses" element={<Harness />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function location(): string {
  return screen.getByTestId("location").textContent ?? "";
}

describe("LicenseListFilters", () => {
  beforeEach(() => {
    get.mockReset();
    get.mockImplementation((url: string) => {
      if (url === "masters/companies/") return ok({ results: COMPANIES });
      const detail = /^masters\/companies\/(\d+)\/$/.exec(url);
      if (detail) {
        const match = COMPANIES.find((company) => company.id === Number(detail[1]));
        return match ? ok(match) : Promise.reject(Object.assign(new Error("Not found"), { response: { status: 404 } }));
      }
      if (url === "licenses/") return ok({ count: 0, total_pages: 1, current_page: 1, page_size: 25, results: [] });
      return ok({ results: [] });
    });
  });

  it("selects an option in a multi-select with the keyboard", async () => {
    const user = userEvent.setup();
    renderFilters("/licenses");

    const input = screen.getByRole("combobox", { name: "Exporter" });
    await user.click(input);
    await user.type(input, "ac");
    await screen.findByRole("option", { name: "ACME" });
    await user.keyboard("{ArrowDown}{Enter}");

    await waitFor(() => expect(location()).toContain("exporter=2"));
    expect(location()).not.toContain("exporter=1");
  });

  it("blocks an option that is already excluded, and shows the reason", async () => {
    const user = userEvent.setup();
    renderFilters("/licenses?exclude_exporter=1");

    const input = screen.getByRole("combobox", { name: "Exporter" });
    await user.click(input);
    await user.type(input, "ac");
    const acme = await screen.findByRole("option", { name: /ACME/ });

    expect(acme).toHaveAttribute("aria-disabled", "true");
    expect(acme).toHaveTextContent("Already in Exclude exporter");
    await user.click(acme);
    expect(location()).not.toMatch(/[?&]exporter=/);
    expect(location()).toContain("exclude_exporter=1");
  });

  it("shows an error for a date range where from is after to, and does not commit it", async () => {
    const user = userEvent.setup();
    renderFilters("/licenses");
    await user.click(screen.getByRole("button", { name: /More filters/ }));

    fireEvent.change(screen.getByLabelText("Licence date to"), { target: { value: "2026-04-01" } });
    await waitFor(() => expect(location()).toContain("license_date__lte=2026-04-01"));

    fireEvent.change(screen.getByLabelText("Licence date from"), { target: { value: "2026-05-01" } });
    expect(await screen.findByText("From must be on or before To.")).toBeInTheDocument();
    expect(location()).not.toContain("license_date__gte");
  });

  it("shows an error for balance min greater than max and does not commit it", async () => {
    const user = userEvent.setup();
    renderFilters("/licenses");
    await user.click(screen.getByRole("button", { name: /More filters/ }));

    fireEvent.change(screen.getByLabelText("Balance CIF minimum (₹)"), { target: { value: "500" } });
    fireEvent.change(screen.getByLabelText("Balance CIF maximum (₹)"), { target: { value: "100" } });
    expect(await screen.findByText("Minimum must be less than or equal to maximum.")).toBeInTheDocument();

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 600));
    });
    expect(location()).not.toContain("balance__balance_cif_min");
    expect(location()).not.toContain("balance__balance_cif_max");
  });

  it("rejects a decimal with more than 2 places inline", async () => {
    const user = userEvent.setup();
    renderFilters("/licenses");
    await user.click(screen.getByRole("button", { name: /More filters/ }));

    fireEvent.change(screen.getByLabelText("Balance CIF minimum (₹)"), { target: { value: "1.234" } });
    expect(await screen.findByText("Enter an amount with at most 2 decimal places.")).toBeInTheDocument();
  });

  it("Clear all returns to the baseline, not to an empty URL, and resets the page", async () => {
    const user = userEvent.setup();
    renderFilters("/licenses?exporter=1&is_expired=True&page=3");
    expect(screen.getAllByTestId("licence-filter-chip")).toHaveLength(2);

    await user.click(screen.getByTestId("licence-filters-clear"));

    await waitFor(() => expect(location()).toContain("is_expired=False"));
    expect(location()).toContain("flags__is_null=False");
    expect(location()).toContain("page=1");
    expect(location()).not.toMatch(/[?&]exporter=/);
    expect(screen.getByTestId("licence-baseline")).toHaveTextContent("Hiding expired and null-balance licences");
    expect(screen.queryAllByTestId("licence-filter-chip")).toHaveLength(0);
  });

  it("removes one chip value at a time", async () => {
    const user = userEvent.setup();
    renderFilters("/licenses?purchase_status=11,10,1");
    const chips = screen.getAllByTestId("licence-filter-chip");
    expect(chips).toHaveLength(3);

    const removeTen = await screen.findByRole("button", { name: "Remove Purchase status: Unknown #10" });
    await user.click(removeTen);

    // URLSearchParams percent-encodes commas (1%2C11); compare the decoded query.
    await waitFor(() => expect(decodeURIComponent(location())).toContain("purchase_status=1,11"));
    expect(screen.getAllByTestId("licence-filter-chip")).toHaveLength(2);
  });

  it("shows the baseline line only while expired and null-balance licences are hidden", async () => {
    const user = userEvent.setup();
    renderFilters("/licenses");
    expect(screen.getByTestId("licence-baseline")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show all" }));
    await waitFor(() => expect(location()).toContain("is_expired=all"));
    expect(location()).toContain("flags__is_null=all");
    expect(screen.queryByTestId("licence-baseline")).toBeNull();
  });
});
