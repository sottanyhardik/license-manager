import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext } from "../../context/AuthContext";

/**
 * Request-equivalence + DOM-stability tests for the licence register header /
 * filter workspace.  The request snapshots were recorded against the pre-change
 * implementation; the redesign must keep them byte-identical.
 */
const FILTER_CONFIG = {
  port: { type: "exact", label: "Port", choices: [["INMUN1", "Mumbai"], ["INNSA1", "Nhava Sheva"]] },
  export_license__norm_class: { type: "exact", label: "Export Licence Norm Class", choices: [["E1", "E1"], ["E5", "E5"]] },
  scheme_code: { type: "exact", label: "Scheme Code" },
  license_date: { type: "date_range", label: "Licence Date" },
  license_expiry_date: { type: "date_range", label: "Expiry Date" },
  balance_cif: { type: "range", label: "Balance CIF", min_field: "balance_cif_min", max_field: "balance_cif_max" },
  is_null: { type: "exact", label: "Is Null" },
  is_planned: { type: "exact", label: "Is Planned" },
  purchase_status: { type: "choice", label: "Purchase Status", choices: [["GE", "GE Purchase"], ["MI", "GE Purchase/Conversion"]] },
};
const META = {
  count: 120, results: [{ id: 1, license_number: "0310835340", exporter: { id: 1, name: "ACME" }, license_date: "2024-01-01", license_expiry_date: "2026-01-01", balance_cif: "100.00", is_active: true }], list_display: ["license_number"], form_fields: [], search_fields: ["license_number"],
  filter_fields: [], filter_config: FILTER_CONFIG, ordering_fields: [], nested_field_defs: {}, nested_list_display: {},
  field_meta: {}, default_filters: {}, inline_editable: [], current_page: 1, total_pages: 3, page_size: 25,
  has_next: true, has_previous: false,
};

vi.mock("../../api/axios", () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock("../../api", () => ({
  boeApi: { fetchBOEList: vi.fn(() => Promise.resolve({ results: [] })) },
  masterApi: {}, licenseApi: {}, allotmentApi: {},
}));

import MasterList from "./MasterList";
import api from "../../api/axios";

const getMock = api.get as unknown as ReturnType<typeof vi.fn>;
const authValue = {
  user: { id: 1, username: "t", is_superuser: true, roles: [] }, loading: false, loginSuccess: vi.fn(), logout: vi.fn(),
  hasRole: () => true, hasAnyRole: () => true, isSuperAdmin: () => true, canManageUsers: () => true,
};

let lastSearch = "";
let probeRenders = 0;
function LocationProbe() { lastSearch = useLocation().search; probeRenders++; if (probeRenders > 300) throw new Error("render loop: " + lastSearch); return null; }

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={authValue as never}>
        <MemoryRouter initialEntries={[path]}>
          <LocationProbe />
          <Routes>
            <Route path="/licenses" element={<MasterList />} />
            <Route path="/masters/:entity" element={<MasterList />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}


const listCalls = (prefix: string) =>
  getMock.mock.calls.filter(([url]) => url === prefix).map(([url, cfg]) => [url, cfg?.params]);
const lastParams = (prefix: string) => {
  const c = listCalls(prefix);
  return c[c.length - 1]?.[1];
};

describe("MasterList deep links and auto-apply", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    probeRenders = 0;
    sessionStorage.clear();
    getMock.mockImplementation(() => Promise.resolve({ data: META }));
  });

  const settleQuiet = () => new Promise((r) => setTimeout(r, 700));

  for (const page of [2, 3]) {
    it(`deep link ?page=${page} stays on page ${page} with exactly one fetch`, async () => {
      renderAt(`/licenses?is_expired=False&scheme_code=26&page=${page}`);
      await waitFor(() => expect(lastParams("licenses/")?.page).toBe(page));
      await settleQuiet();
      expect(lastParams("licenses/")?.page).toBe(page);
      expect(lastParams("licenses/")?.scheme_code).toBe("26");
      expect(new URLSearchParams(lastSearch).get("page")).toBe(String(page));
      expect(listCalls("licenses/").length).toBe(1);
    });
  }

  it("exact target URL with page=1 is stable", async () => {
    renderAt("/licenses?flags__is_null=False&is_expired=False&page=1&purchase_status=1%2C2%2C3%2C4%2C5%2C6%2C7%2C8");
    await waitFor(() => expect(lastParams("licenses/")?.purchase_status).toBe("1,2,3,4,5,6,7,8"));
    await settleQuiet();
    expect(lastParams("licenses/")?.page).toBe(1);
    expect(new URLSearchParams(lastSearch).get("page")).toBe("1");
    expect(listCalls("licenses/").length).toBe(1);
  });

  it("a text edit after an immediate-apply filter is not swallowed", async () => {
    const { container } = renderAt("/licenses");
    await waitFor(() => expect(screen.getByText("Scheme Code")).toBeInTheDocument());
    const toggle = screen.queryByRole("button", { name: /^Filters/ });
    if (toggle && toggle.getAttribute("aria-expanded") === "false") fireEvent.click(toggle);
    fireEvent.change(container.querySelectorAll('input[type="date"]')[0], { target: { value: "2024-01-01" } });
    await waitFor(() => expect(lastParams("licenses/")?.license_date__gte).toBe("2024-01-01"));
    await settleQuiet();
    fireEvent.change(screen.getByPlaceholderText("Exact scheme code"), { target: { value: "26" } });
    await waitFor(() => expect(lastParams("licenses/")?.scheme_code).toBe("26"), { timeout: 3000 });
    expect(lastParams("licenses/")?.license_date__gte).toBe("2024-01-01");
  });

  it("a text edit right after an immediate toggle is applied (not swallowed or clobbered)", async () => {
    renderAt("/licenses");
    await waitFor(() => expect(screen.getByText("Scheme Code")).toBeInTheDocument());
    const toggle = screen.queryByRole("button", { name: /^Filters/ });
    if (toggle && toggle.getAttribute("aria-expanded") === "false") fireEvent.click(toggle);
    fireEvent.click(screen.getAllByRole("button", { name: "Yes" })[0]);
    fireEvent.change(screen.getByPlaceholderText("Exact scheme code"), { target: { value: "26" } });
    await waitFor(() => expect(lastParams("licenses/")?.scheme_code).toBe("26"), { timeout: 3000 });
    await waitFor(() => expect(lastParams("licenses/")?.is_null).toBe("True"));
    await settleQuiet();
    fireEvent.change(screen.getByPlaceholderText(/Search by/), { target: { value: "abc" } });
    await waitFor(() => expect(lastParams("licenses/")?.search).toBe("abc"), { timeout: 3000 });
  });
});
