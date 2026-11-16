import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route, useLocation, useNavigate, type NavigateFunction } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext } from "../../context/AuthContext";

/**
 * B0/B1/B2 request-count characterisation for MasterList.  Each interaction
 * must cost exactly one list GET, and the page size must survive paging.
 * Counts recorded before the fix are noted next to each case.
 */
const FILTER_CONFIG = {
  scheme_code: { type: "exact", label: "Scheme Code" },
  exporter: { type: "fk", label: "Exporter", fk_endpoint: "masters/companies/" },
};
const makeMeta = (defaultFilters: Record<string, unknown> = {}) => ({
  count: 120,
  results: [{ id: 1, license_number: "0310835340", exporter: { id: 1, name: "ACME" }, license_date: "2024-01-01", license_expiry_date: "2026-01-01", balance_cif: "100.00", is_active: true }],
  list_display: ["license_number"], form_fields: [], search_fields: ["license_number"],
  filter_fields: [], filter_config: FILTER_CONFIG, ordering_fields: [], nested_field_defs: {}, nested_list_display: {},
  field_meta: {}, default_filters: defaultFilters, inline_editable: [], current_page: 1, total_pages: 5, page_size: 25,
  has_next: true, has_previous: false,
});

vi.mock("../../api/axios", () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock("../../api", () => ({
  boeApi: { fetchBOEList: vi.fn(() => Promise.resolve({ results: [] })) },
  masterApi: {}, licenseApi: {}, allotmentApi: {},
}));
// Stand-in multi-select: emits the same array shape the real component emits.
vi.mock("../../components/DebouncedAsyncSelect", () => ({
  default: ({ onChange }: { onChange: (v: string[]) => void }) => (
    <button type="button" onClick={() => onChange(["1", "2"])}>pick-fk</button>
  ),
}));

import MasterList from "./MasterList";
import api from "../../api/axios";

const getMock = api.get as unknown as ReturnType<typeof vi.fn>;
const authValue = {
  user: { id: 1, username: "t", is_superuser: true, roles: [] }, loading: false, loginSuccess: vi.fn(), logout: vi.fn(),
  hasRole: () => true, hasAnyRole: () => true, isSuperAdmin: () => true, canManageUsers: () => true,
};

let lastSearch = "";
let nav: NavigateFunction;
function LocationProbe() { lastSearch = useLocation().search; nav = useNavigate(); return null; }

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

const listCalls = (url: string) => getMock.mock.calls.filter(([u]) => u === url).map(([, cfg]) => cfg?.params);
const lastOf = <T,>(a: T[]): T => a[a.length - 1];
const settle = () => act(() => new Promise<void>((r) => setTimeout(r, 700)));

async function loaded(url: string) {
  await waitFor(() => expect(screen.getByRole("navigation", { name: "Pagination" })).toBeInTheDocument());
  await settle();
  expect(listCalls(url).length).toBeGreaterThan(0);
}

describe("MasterList request counts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    getMock.mockImplementation(() => Promise.resolve({ data: makeMeta() }));
  });

  it("cold load costs exactly 1 list GET", async () => {
    renderAt("/licenses");
    await loaded("licenses/");
    expect(listCalls("licenses/")).toHaveLength(1);
  });

  it("page change costs exactly 1 GET and stays on that page", async () => {
    renderAt("/licenses");
    await loaded("licenses/");
    fireEvent.click(screen.getByRole("button", { name: "Page 2" }));
    await settle();
    const calls = listCalls("licenses/");
    expect(calls).toHaveLength(2); // before fix: 3 (page 2, then reset to page 1)
    expect(calls[1].page).toBe(2);
    expect(new URLSearchParams(lastSearch).get("page")).toBe("2");
  });

  it("page size change then page change: 1 GET each, size kept", async () => {
    renderAt("/licenses");
    await loaded("licenses/");
    fireEvent.change(screen.getByLabelText("Rows per page"), { target: { value: "50" } });
    await settle();
    expect(listCalls("licenses/")).toHaveLength(2);
    expect(listCalls("licenses/")[1]).toMatchObject({ page: 1, page_size: 50 });
    fireEvent.click(screen.getByRole("button", { name: "Page 2" }));
    await settle();
    const calls = listCalls("licenses/");
    expect(calls).toHaveLength(3); // before fix: 4+ and the last one reverted to page_size 25
    expect(calls[2]).toMatchObject({ page: 2, page_size: 50 });
  });

  it("multi-select FK change costs exactly 1 GET carrying the comma form", async () => {
    renderAt("/licenses");
    await loaded("licenses/");
    const toggle = screen.queryByRole("button", { name: /^Filters/ });
    if (toggle && toggle.getAttribute("aria-expanded") === "false") fireEvent.click(toggle);
    fireEvent.click(screen.getByRole("button", { name: "pick-fk" }));
    await settle();
    const calls = listCalls("licenses/");
    expect(calls).toHaveLength(2); // before fix: 3 (array form, then "1,2")
    expect(calls[1].exporter).toBe("1,2");
    expect(new URLSearchParams(lastSearch).get("exporter")).toBe("1,2");
  });

  it("deep link with filters costs exactly 1 GET and applies them", async () => {
    renderAt("/licenses?scheme_code=26&exporter=1%2C2&page=2");
    await loaded("licenses/");
    const calls = listCalls("licenses/");
    expect(calls).toHaveLength(1);
    expect(calls[0]).toMatchObject({ scheme_code: "26", exporter: "1,2", page: 2, page_size: 25 });
  });

  it("deep link ?page=2 with no filters stays on page 2 (F2)", async () => {
    renderAt("/masters/companies?page=2");
    await loaded("masters/companies/");
    const calls = listCalls("masters/companies/");
    expect(calls[calls.length - 1].page).toBe(2);
    expect(calls).toHaveLength(1);
  });

  it("cold load with typed backend defaults costs at most 2 GETs, the last with string values", async () => {
    getMock.mockImplementation(() => Promise.resolve({ data: makeMeta({ is_active: true, status: ["A", "B"] }) }));
    renderAt("/masters/companies");
    await loaded("masters/companies/");
    const calls = listCalls("masters/companies/");
    expect(calls).toHaveLength(2); // before fix: 3 (unfiltered, typed, stringified)
    expect(calls[1]).toMatchObject({ is_active: "true", status: "A,B" });
  });

  it("entity switch with an identical literal search re-initialises (no stale pageSize/filters)", async () => {
    renderAt("/masters/companies");
    await loaded("masters/companies/");
    fireEvent.change(screen.getByLabelText("Rows per page"), { target: { value: "50" } });
    await settle();
    expect(lastOf(listCalls("masters/companies/"))).toMatchObject({ page_size: 50 });
    act(() => { nav("/masters/vendors?page=1"); });
    await settle();
    const calls = listCalls("masters/vendors/");
    // The first render after the switch still holds the old state (pre-existing,
    // one transient request); the effect must then settle on defaults.
    expect(calls.length).toBeLessThanOrEqual(2);
    expect(lastOf(calls)).toMatchObject({ page: 1, page_size: 25 });
  });

  it("an external push landing on the last own-written string is not swallowed", async () => {
    renderAt("/licenses");
    await loaded("licenses/");
    fireEvent.change(screen.getByLabelText("Rows per page"), { target: { value: "50" } });
    await settle();
    fireEvent.click(screen.getByRole("button", { name: "Page 2" })); // own write: ?page=2
    await settle();
    expect(lastOf(listCalls("licenses/"))).toMatchObject({ page: 2, page_size: 50 });
    act(() => { nav("/licenses?page=2&scheme_code=26"); });
    await settle();
    act(() => { nav("/licenses?page=2"); });
    await settle();
    // Re-initialised from the URL: page size is back to the default, not kept.
    expect(lastOf(listCalls("licenses/"))).toMatchObject({ page: 2, page_size: 25 });
    expect(lastOf(listCalls("licenses/")).scheme_code).toBeUndefined();
  });

  it("back navigation re-initialises state from the URL", async () => {
    renderAt("/licenses?scheme_code=26&page=1");
    await loaded("licenses/");
    act(() => { nav("/licenses?scheme_code=27&page=1"); });
    await settle();
    expect(lastOf(listCalls("licenses/"))).toMatchObject({ scheme_code: "27" });
    act(() => { nav(-1); });
    await settle();
    expect(lastOf(listCalls("licenses/"))).toMatchObject({ scheme_code: "26", page: 1 });
    act(() => { nav(1); });
    await settle();
    expect(lastOf(listCalls("licenses/"))).toMatchObject({ scheme_code: "27" });
  });

  it("unset (null/undefined) filter values are omitted from the request, not sent as empty", async () => {
    getMock.mockImplementation(() => Promise.resolve({ data: makeMeta({ is_active: true, owner: null }) }));
    renderAt("/masters/companies");
    await loaded("masters/companies/");
    const last = lastOf(listCalls("masters/companies/"));
    expect(last).toMatchObject({ is_active: "true" });
    expect("owner" in last).toBe(false);
  });
});
