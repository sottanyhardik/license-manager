import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext } from "../../context/AuthContext";

/** Deep link from the Mapping workspace: the Licence List opens with its standard filters and then the clicked licence's
 *  existing workspace (by real id) — on the loaded page, via the exact licence-number lookup, or with a notice. */
vi.mock("../../api/axios", () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } }));
vi.mock("../../api", () => ({ boeApi: { fetchBOEList: vi.fn(() => Promise.resolve({ results: [] })) }, masterApi: {}, licenseApi: {}, allotmentApi: {} }));

import MasterList from "./MasterList";
import api from "../../api/axios";
import { LICENCE_LIST_URL, requestOpenLicence } from "@/features/licenses/openLicenceTarget";

const getMock = api.get as unknown as ReturnType<typeof vi.fn>;
const authValue = { user: { id: 1, username: "t", is_superuser: true, roles: [] }, loading: false, loginSuccess: vi.fn(), logout: vi.fn(),
    hasRole: () => true, hasAnyRole: () => true, isSuperAdmin: () => true, canManageUsers: () => true };
const lic = (id: number, n: string) => ({ id, license_number: n, exporter: { id: 1, name: "ACME" }, license_date: "2024-01-01", license_expiry_date: "2027-01-01", balance_cif: "100.00", is_active: true });
const page1 = [lic(1, "0310835340"), lic(2, "0310835341")];
let filterConfig: Record<string, unknown> = {};
const meta = (results: unknown[]) => ({ count: results.length, results, list_display: ["license_number"], form_fields: [], search_fields: ["license_number"], filter_fields: [],
    filter_config: filterConfig, ordering_fields: [], nested_field_defs: {}, nested_list_display: {}, field_meta: {}, default_filters: {}, inline_editable: [],
    current_page: 1, total_pages: 1, page_size: 25, has_next: false, has_previous: false });

let lastSearch = "";
function LocationProbe() { lastSearch = useLocation().search; return null; }
function renderAt(path: string) {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(<QueryClientProvider client={qc}><AuthContext.Provider value={authValue as never}><MemoryRouter initialEntries={[path]}>
        <LocationProbe /><Routes><Route path="/licenses" element={<MasterList />} /></Routes></MemoryRouter></AuthContext.Provider></QueryClientProvider>);
}
const listParams = () => getMock.mock.calls.filter(([url]) => url === "licenses/").map(([, cfg]) => cfg?.params ?? {});
const expandedButton = (n: string) => screen.findByRole("button", { name: `Collapse license ${n}` });

describe("Licence List opens a licence handed over by a Mapping licence chip", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        sessionStorage.clear();
        filterConfig = {};
        getMock.mockImplementation((url: string, cfg?: { params?: Record<string, unknown> }) => {
            if (url !== "licenses/") return Promise.resolve({ data: null }); // workspace endpoints: not under test here
            const p = cfg?.params ?? {};
            if (p.license_number === "0210118391") return Promise.resolve({ data: meta(p.is_expired === "False" && p.flags__is_null === "False" && p.purchase_status ? [lic(77, "0210118391")] : []) });
            if (p.license_number === "0999999999") return Promise.resolve({ data: meta(p.is_expired ? [] : [lic(99, "0999999999")]) });
            return Promise.resolve({ data: meta(page1) });
        });
    });

    it("opens the licence on the loaded page with the standard filters (one workspace)", async () => {
        requestOpenLicence({ id: 2, license_number: "0310835341" });
        renderAt(LICENCE_LIST_URL);
        expect(await expandedButton("0310835341")).toHaveAttribute("aria-expanded", "true");
        expect(screen.getByRole("button", { name: "Expand license 0310835340" })).toHaveAttribute("aria-expanded", "false");
        const p = new URLSearchParams(lastSearch);
        expect([p.get("flags__is_null"), p.get("is_expired"), p.get("purchase_status")]).toEqual(["False", "False", "11,10,1,2,4,5,7"]);
        expect(sessionStorage.length).toBe(0); // taken once
    });

    it("finds a licence that is not on the first page through the exact licence-number lookup, keeping the filters", async () => {
        requestOpenLicence({ id: 77, license_number: "0210118391" });
        renderAt(LICENCE_LIST_URL);
        expect(await expandedButton("0210118391")).toHaveAttribute("aria-expanded", "true");
        const last = listParams().slice(-1)[0];
        expect(last.license_number).toBe("0210118391");
        expect([last.is_expired, last.flags__is_null, last.purchase_status]).toEqual(["False", "False", "11,10,1,2,4,5,7"]);
        // the card's existing workspace (with its Overview tab) is what opens; its contents are covered by the Licence List suites
    });

    it("explains when the filters exclude the licence and can show it without filters", async () => {
        requestOpenLicence({ id: 99, license_number: "0999999999" });
        renderAt(LICENCE_LIST_URL);
        const notice = await screen.findByText(/Licence 0999999999 is not in the current filters/);
        await userEvent.setup().click(within(notice.parentElement as HTMLElement).getByRole("button", { name: "Show it without filters" }));
        expect(await expandedButton("0999999999")).toHaveAttribute("aria-expanded", "true");
        expect(listParams().slice(-1)[0]).toMatchObject({ license_number: "0999999999" });
        expect(listParams().slice(-1)[0]?.is_expired).toBeUndefined();
    });

    it("ignores a stale or malformed hand-off (plain list, nothing opened)", async () => {
        sessionStorage.setItem("licence-list-open-target", JSON.stringify({ id: 2, license_number: "0310835341", at: Date.now() - 60 * 60 * 1000 }));
        renderAt(LICENCE_LIST_URL);
        expect(await screen.findByRole("button", { name: "Expand license 0310835341" })).toHaveAttribute("aria-expanded", "false");
    });

    it("a pending target is dropped when the first load fails (no surprise later)", async () => {
        requestOpenLicence({ id: 2, license_number: "0310835341" });
        getMock.mockImplementationOnce(() => Promise.reject(new Error("network")));
        renderAt(LICENCE_LIST_URL);
        await new Promise((r) => setTimeout(r, 400)); // failed load settles; the target is dropped
        expect(screen.queryByRole("button", { name: "Collapse license 0310835341" })).toBeNull();
        expect(listParams().every((p) => p.license_number === undefined)).toBe(true); // no lookup was attempted
    });

    it("still opens the target with a real filter panel (its config-driven re-sync is not a user change)", async () => {
        filterConfig = {
            is_expired: { type: "exact", label: "Is Expired" }, flags__is_null: { type: "exact", label: "Flags" },
            purchase_status: { type: "choice", label: "Purchase Status", choices: [["11", "A"], ["10", "B"], ["1", "C"]] },
            license_date: { type: "date_range", label: "Licence Date" },
        };
        requestOpenLicence({ id: 77, license_number: "0210118391" });
        renderAt(LICENCE_LIST_URL);
        expect(await expandedButton("0210118391")).toHaveAttribute("aria-expanded", "true");
        await new Promise((r) => setTimeout(r, 700)); // past the panel's 400 ms auto-apply window
        expect(screen.getByRole("button", { name: "Collapse license 0210118391" })).toHaveAttribute("aria-expanded", "true");
    });
});

