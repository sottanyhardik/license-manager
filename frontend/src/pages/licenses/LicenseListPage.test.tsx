import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import api from "@/api/axios";
import LicenseListPage from "./LicenseListPage";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }));

const get = vi.mocked(api.get);

/** A resolved axios-like response. The shape is all the page reads. */
function response(data: unknown) {
  return { data } as never;
}

function licenseRow(id: number) {
  return {
    id,
    license_number: `031083534${id}`,
    license_date: "2026-01-01",
    license_expiry_date: "2030-01-01",
    ledger_date: null,
    port_name: null,
    exporter_name: "ACME",
    exporter_iec: null,
    get_norm_class: null,
    get_balance_cif: 1000,
    latest_transfer: null,
    purchase_status_label: null,
    purchase_status_code: null,
    is_manually_planned: false,
    has_tl: false,
    has_copy: false,
    has_condition_sheet: false,
  };
}

function listPage(count: number, rowIds: number[]) {
  return {
    count,
    next: null,
    previous: null,
    total_pages: Math.max(1, Math.ceil(count / 25)),
    current_page: 1,
    page_size: 25,
    has_next: false,
    has_previous: false,
    results: rowIds.map(licenseRow),
  };
}

function licenseCalls() {
  return get.mock.calls.filter(([url]) => url === "licenses/");
}

function renderPage(url: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/licenses" element={<LicenseListPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LicenseListPage request behaviour", () => {
  beforeEach(() => {
    get.mockReset();
    get.mockImplementation((url: string) => {
      if (url === "licenses/") return Promise.resolve(response(listPage(5, [1, 2])));
      return Promise.resolve(response({ results: [] }));
    });
  });

  it("issues exactly one list request for one committed change", async () => {
    const user = userEvent.setup();
    renderPage("/licenses");
    await waitFor(() => expect(licenseCalls()).toHaveLength(1));
    await screen.findByTestId("licence-result-count");

    get.mockClear();
    get.mockImplementation((url: string) => {
      if (url === "licenses/") return Promise.resolve(response(listPage(2, [1])));
      return Promise.resolve(response({ results: [] }));
    });
    await user.click(screen.getByRole("radio", { name: "Expired" }));
    await waitFor(() => expect(licenseCalls()).toHaveLength(1));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });
    expect(licenseCalls()).toHaveLength(1);
    expect(licenseCalls()[0][1]).toMatchObject({ params: expect.objectContaining({ is_expired: "True" }) });
  });

  it("issues no list request while the search is being typed, then one after the pause", async () => {
    const user = userEvent.setup();
    renderPage("/licenses");
    await waitFor(() => expect(licenseCalls()).toHaveLength(1));
    get.mockClear();

    await user.type(screen.getByRole("searchbox", { name: "Search licences" }), "acme");
    expect(licenseCalls()).toHaveLength(0);

    await waitFor(() => expect(licenseCalls()).toHaveLength(1), { timeout: 1500 });
    expect(licenseCalls()[0][1]).toMatchObject({ params: expect.objectContaining({ search: "acme" }) });
  });

  it("shows the result of the newest request even when an older response arrives last", async () => {
    const user = userEvent.setup();
    const pending: Array<{ params: Record<string, unknown>; resolve: (data: unknown) => void }> = [];
    get.mockImplementation((url: string, config?: { params?: Record<string, unknown> }) => {
      if (url === "licenses/") {
        return new Promise((resolve) => {
          pending.push({
            params: config?.params ?? {},
            resolve: (data) => resolve(response(data)),
          });
        });
      }
      return Promise.resolve(response({ results: [] }));
    });

    renderPage("/licenses");
    await waitFor(() => expect(pending).toHaveLength(1));
    await act(async () => pending[0].resolve(listPage(5, [1, 2])));
    await screen.findByText(/of 5 licences/);

    await user.click(screen.getByRole("radio", { name: "Expired" }));
    await waitFor(() => expect(pending).toHaveLength(2));
    await user.click(screen.getByRole("radio", { name: "Not expired" }));
    await waitFor(() => expect(pending).toHaveLength(3));

    expect(pending[1].params).toMatchObject({ is_expired: "True" });
    expect(pending[2].params).toMatchObject({ is_expired: "False" });

    await act(async () => pending[2].resolve(listPage(3, [1, 2, 3])));
    await screen.findByText(/of 3 licences/);

    await act(async () => pending[1].resolve(listPage(9, [1, 2, 3, 4, 5, 6, 7, 8, 9])));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    const count = screen.getByTestId("licence-result-count");
    expect(count).toHaveTextContent("Showing 1–3 of 3 licences");
    expect(within(screen.getByTestId("licence-results")).queryByText(/of 9 licences/)).toBeNull();
  });
});
