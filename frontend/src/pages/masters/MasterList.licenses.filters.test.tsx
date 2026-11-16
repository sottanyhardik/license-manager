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

async function openFilters() {
  // New collapsible UI: reveal the panel. The legacy UI has no toggle.
  const toggle = screen.queryByRole("button", { name: /^Filters/ });
  if (toggle && toggle.getAttribute("aria-expanded") === "false") fireEvent.click(toggle);
}

async function loaded() {
  await waitFor(() => expect(screen.getByText("Scheme Code")).toBeInTheDocument());
  await openFilters();
}

describe("licence register: request equivalence", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    probeRenders = 0;
    sessionStorage.clear();
    getMock.mockImplementation(() => Promise.resolve({ data: META }));
  });

  it("default load", async () => {
    renderAt("/licenses");
    await loaded();
    expect(listCalls("licenses/")).toMatchSnapshot();
  });

  it("exposes every filter label", async () => {
    renderAt("/licenses");
    await loaded();
    for (const label of ["Port", "Export Licence Norm Class", "Scheme Code", "Licence Date Range", "Expiry Date Range",
      "Balance CIF Range", "Is Null", "Is Planned", "Purchase Status"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("applies each filter type", async () => {
    const { container } = renderAt("/licenses");
    await loaded();
    const seen: unknown[] = [];
    const settle = async (match: (p: Record<string, unknown>) => boolean) => {
      await waitFor(() => { if (!match(lastParams("licenses/"))) throw new Error("no match: " + JSON.stringify(lastParams("licenses/"))); }, { timeout: 3000 });
      seen.push(lastParams("licenses/"));
    };
    // scheme code (text, 400ms debounce)
    fireEvent.change(screen.getByPlaceholderText("Exact scheme code"), { target: { value: "26" } });
    await settle((p) => p.scheme_code === "26");
    // CIF range
    fireEvent.change(screen.getAllByPlaceholderText("Min")[0], { target: { value: "100" } });
    await settle((p) => p.balance_cif__gte === "100" || p.balance_cif_min === "100");
    // dates (immediate)
    const dateInput = (i: number) => container.querySelectorAll('input[type="date"]')[i] as HTMLInputElement;
    fireEvent.change(dateInput(0), { target: { value: "2024-01-01" } });
    await settle((p) => p.license_date__gte === "2024-01-01");
    fireEvent.change(dateInput(3), { target: { value: "2026-12-31" } });
    await settle((p) => p.license_expiry_date__lte === "2026-12-31");
    // flags
    fireEvent.click(screen.getAllByRole("button", { name: "Yes" })[0]);
    await settle((p) => p.is_null === "True");
    fireEvent.click(screen.getAllByRole("button", { name: "No" })[1]);
    await settle((p) => p.is_planned === "False");
    expect(seen).toMatchSnapshot();
    expect(lastSearch).toContain("scheme_code=26");
    expect(lastSearch).toContain("is_null=True");
  });

  it("reset clears filters and page 2 keeps filters", async () => {
    renderAt("/licenses?scheme_code=26");
    await loaded();
    await waitFor(() => expect(lastParams("licenses/")?.scheme_code).toBe("26"));
    const before = listCalls("licenses/").length;
    fireEvent.click(await screen.findByRole("button", { name: "Page 2" }));
    await waitFor(() => expect(lastParams("licenses/")?.page).toBe(2));
    expect(lastParams("licenses/")?.scheme_code).toBe("26");
    expect(lastSearch).toContain("page=2");
    expect(listCalls("licenses/").slice(before - 1)).toMatchSnapshot();
    await openFilters();
    const reset = screen.getAllByRole("button", { name: /Clear Filters|Reset/ }).find((b) => !(b as HTMLButtonElement).disabled)!;
    fireEvent.click(reset);
    await waitFor(() => expect(lastParams("licenses/")?.scheme_code).toBeUndefined());
    expect(lastParams("licenses/")).toMatchSnapshot();
  });

  it("10-digit search is rewritten to license_number; other text stays search", async () => {
    renderAt("/licenses");
    await loaded();
    const input = screen.getByPlaceholderText(/Search by/);
    fireEvent.change(input, { target: { value: "0310835340" } });
    await waitFor(() => expect(lastParams("licenses/")?.license_number).toBe("0310835340"));
    expect(lastParams("licenses/")).not.toHaveProperty("search");
    expect(lastParams("licenses/")).toMatchSnapshot();
    fireEvent.change(input, { target: { value: "abc" } });
    await waitFor(() => expect(lastParams("licenses/")?.search).toBe("abc"));
    expect(lastParams("licenses/")).toMatchSnapshot();
  });

  // NOTE: deep-linking `?page=2` ping-pongs 1<->2 in the existing URL sync (pre-existing, out of scope).
  it("restores filters from the URL", async () => {
    renderAt("/licenses?scheme_code=26&is_null=True&license_date__gte=2024-01-01");
    await loaded();
    await waitFor(() => expect(lastParams("licenses/")?.is_null).toBe("True"));
    expect(lastParams("licenses/")).toMatchSnapshot();
    expect(screen.getByPlaceholderText("Exact scheme code")).toHaveValue("26");
  });
});

describe("other entities: header + filter DOM unchanged", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    getMock.mockImplementation(() => Promise.resolve({ data: { ...META, filter_config: { company: { type: "icontains", label: "Company" }, is_boe: { type: "exact", label: "BOE" } } } }));
  });
  for (const entity of ["allotments", "trades", "incentive-licenses", "companies"]) {
    it(`${entity}`, async () => {
      const { container } = renderAt(`/masters/${entity}`);
      await waitFor(() => expect(screen.getByText("Company")).toBeInTheDocument());
      // Header + filter region only (everything before the table surface).
      const html = container.innerHTML.split('class="surface-card')[0];
      expect(html).toMatchSnapshot();
    });
  }
  it("bill-of-entries", async () => {
    const { boeApi } = await import("../../api");
    (boeApi.fetchBOEList as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ ...META, filter_config: { company: { type: "icontains", label: "Company" } } });
    const { container } = renderAt("/masters/bill-of-entries");
    await waitFor(() => expect(screen.getByText("Company")).toBeInTheDocument());
    expect(container.innerHTML.split('class="surface-card')[0]).toMatchSnapshot();
  });
});
