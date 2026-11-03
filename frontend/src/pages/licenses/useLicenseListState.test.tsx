import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useEffect } from "react";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useNavigationType,
  type NavigateFunction,
} from "react-router-dom";
import { toast } from "sonner";
import { useLicenseListState, SEARCH_COMMIT_DELAY_MS, type LicenseListUrlState } from "./useLicenseListState";

vi.mock("sonner", () => ({ toast: { message: vi.fn() } }));

interface Snapshot {
  url: LicenseListUrlState;
  search: string;
  navigate: NavigateFunction;
}

let latest: Snapshot | null = null;
let renderCount = 0;
/** One entry per distinct history entry the router has created, with how it was created. */
let entries: Array<{ key: string; type: string; search: string }> = [];

function Probe() {
  renderCount += 1;
  const url = useLicenseListState();
  const location = useLocation();
  const navigationType = useNavigationType();
  const navigate = useNavigate();
  latest = { url, search: location.search, navigate };

  useEffect(() => {
    if (!entries.some((entry) => entry.key === location.key)) {
      entries = [...entries, { key: location.key, type: navigationType, search: location.search }];
    }
  }, [location.key, location.search, navigationType]);
  return null;
}

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/licenses" element={<Probe />} />
      </Routes>
    </MemoryRouter>,
  );
}

function current(): Snapshot {
  if (!latest) throw new Error("Probe has not rendered");
  return latest;
}

function pushCount(): number {
  return entries.filter((entry) => entry.type === "PUSH").length;
}

describe("useLicenseListState", () => {
  beforeEach(() => {
    latest = null;
    renderCount = 0;
    entries = [];
    vi.mocked(toast.message).mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("initialises the state from the URL", () => {
    renderAt("/licenses?exporter=3,1&purchase_status=11&page=2&page_size=50&is_expired=True");
    const { state } = current().url;
    expect(state.filters.exporter).toEqual([1, 3]);
    expect(state.filters.purchase_status).toEqual([11]);
    expect(state.filters.is_expired).toBe("True");
    expect(state.page).toBe(2);
    expect(state.pageSize).toBe(50);
  });

  it("normalises a malformed URL with REPLACE, not PUSH, and keeps valid values", () => {
    renderAt("/licenses?page=abc&page_size=17&license_date_from=2026-01-01");
    expect(entries[entries.length - 1].type).toBe("REPLACE");
    const search = current().search;
    expect(search).toContain("license_date__gte=2026-01-01");
    expect(search).not.toContain("license_date_from");
    expect(search).toContain("page=1");
    expect(search).toContain("page_size=25");
    expect(search).toContain("is_expired=False");
    expect(pushCount()).toBe(0);
    expect(toast.message).toHaveBeenCalledTimes(1);
  });

  it("a committed filter change pushes one history entry, and Back restores the previous filters", async () => {
    renderAt("/licenses");
    const before = entries.length;
    act(() => current().url.setFilters({ exporter: [7] }));
    expect(entries.length).toBe(before + 1);
    expect(entries[entries.length - 1].type).toBe("PUSH");
    expect(current().search).toContain("exporter=7");

    await act(async () => {
      current().navigate(-1);
    });
    expect(current().url.state.filters.exporter).toEqual([]);
    expect(current().search).not.toContain("exporter=");
  });

  it("page changes keep the filters and push a history entry", () => {
    renderAt("/licenses?port=4&page=1");
    act(() => current().url.setPage(3));
    expect(pushCount()).toBe(1);
    expect(current().url.state.filters.port).toEqual([4]);
    expect(current().url.state.page).toBe(3);
  });

  it("a filter change resets the page to 1", () => {
    renderAt("/licenses?page=4");
    act(() => current().url.setFilters({ port: [1] }));
    expect(current().url.state.page).toBe(1);
    expect(current().url.state.filters.port).toEqual([1]);
  });

  it("a page size change keeps filters and resets the page to 1", () => {
    renderAt("/licenses?exporter=2&page=5");
    act(() => current().url.setPageSize(100));
    const { state } = current().url;
    expect(state.pageSize).toBe(100);
    expect(state.page).toBe(1);
    expect(state.filters.exporter).toEqual([2]);
  });

  it("does not push when a commit leaves the canonical URL unchanged", () => {
    renderAt("/licenses");
    act(() => current().url.setFilters({ is_expired: "False" }));
    expect(pushCount()).toBe(0);
  });

  it("does not push a history entry per keystroke and commits the search once after the pause", () => {
    vi.useFakeTimers();
    renderAt("/licenses");

    act(() => current().url.setSearchDraft("a"));
    act(() => vi.advanceTimersByTime(100));
    act(() => current().url.setSearchDraft("ac"));
    act(() => vi.advanceTimersByTime(100));
    act(() => current().url.setSearchDraft("acm"));
    expect(pushCount()).toBe(0);
    expect(current().search).not.toContain("search=");

    act(() => vi.advanceTimersByTime(SEARCH_COMMIT_DELAY_MS));
    expect(pushCount()).toBe(1);
    expect(current().search).toContain("search=acm");
    expect(current().url.state.page).toBe(1);
  });

  it("follows the URL when the search changes from outside (Back) and does not re-commit", async () => {
    vi.useFakeTimers();
    renderAt("/licenses?search=first");
    act(() => current().url.setFilters({ search: "second" }));
    expect(current().url.searchDraft).toBe("second");

    await act(async () => {
      current().navigate(-1);
    });
    act(() => vi.advanceTimersByTime(SEARCH_COMMIT_DELAY_MS * 2));
    expect(current().url.searchDraft).toBe("first");
    expect(current().search).toContain("search=first");
    expect(pushCount()).toBe(1);
  });

  it("keeps the open licence out of the URL: a filter or page write does not add workspace keys", () => {
    renderAt("/licenses?licence=7&tab=invoices&item=101");
    act(() => current().url.setFilters({ exporter: [4] }));
    const afterFilter = new URLSearchParams(current().search);
    expect(afterFilter.get("exporter")).toBe("4");
    expect(afterFilter.has("licence")).toBe(false);
    expect(afterFilter.has("tab")).toBe(false);
    expect(afterFilter.has("item")).toBe(false);

    act(() => current().url.setPage(2));
    expect(new URLSearchParams(current().search).get("page")).toBe("2");
    expect(new URLSearchParams(current().search).has("licence")).toBe(false);
  });

  it("keeps the render count bounded: no URL-sync loop", () => {
    renderAt("/licenses?page=bad&exporter=5,1,x");
    act(() => current().url.setFilters({ port: [2] }));
    act(() => current().url.setPage(2));
    expect(renderCount).toBeLessThan(15);
  });

  it("drops a workspace key from a legacy link, with REPLACE, and keeps the list state", () => {
    renderAt("/licenses?licence=9&page=abc");
    expect(entries[entries.length - 1].type).toBe("REPLACE");
    const params = new URLSearchParams(current().search);
    expect(params.has("licence")).toBe(false);
    expect(params.get("page")).toBe("1");
  });
});
