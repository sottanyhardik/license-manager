/**
 * Inline record opening on the generic master list: `/masters/:entity/:id` is the list with that record
 * expanded in its row (licence register pattern), never a separate page.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route, useLocation, useNavigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext } from "../../context/AuthContext";

const { getSpy, deleteSpy, toastError } = vi.hoisted(() => ({ getSpy: vi.fn(), deleteSpy: vi.fn(), toastError: vi.fn() }));
vi.mock("../../api/axios", () => ({ default: { get: getSpy, post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: deleteSpy } }));
vi.mock("@/api/axios", () => ({ default: { get: getSpy, post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: deleteSpy } }));
vi.mock("../../api", () => ({ boeApi: {}, masterApi: {}, licenseApi: {}, allotmentApi: {} }));
vi.mock("react-toastify", () => ({ toast: { success: vi.fn(), error: toastError, warning: vi.fn(), info: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: toastError, warning: vi.fn(), info: vi.fn() } }));
vi.mock("../../hooks/useConfirmDialog.jsx", async (importOriginal) => {
    const actual = await importOriginal<typeof import("../../hooks/useConfirmDialog")>();
    return { ...actual, useConfirmDialog: () => ({ ...actual.useConfirmDialog(), confirmDelete: () => Promise.resolve(true) }) };
});

// The Edit tab embeds the generic MasterForm (own tests); a stub keeps this file about routing.
vi.mock("./MasterForm", () => ({
    default: ({ recordId }: { recordId: string }) => <form aria-label={`Edit ${recordId}`} />,
}));

import MasterList from "./MasterList";

const RATES = [
    { id: 1, date: "01-11-2026", usd: "84.1234", euro: "91.20", pound_sterling: "107.00", chinese_yuan: "11.60" },
    { id: 2, date: "02-11-2026", usd: "84.2000", euro: "91.30", pound_sterling: "107.10", chinese_yuan: "11.70" },
];
const LIST_META = {
    list_display: ["date", "usd"], form_fields: ["date", "usd", "euro"], search_fields: ["date"], filter_fields: [], filter_config: {},
    ordering_fields: [], nested_field_defs: [], nested_list_display: {}, field_meta: {}, default_filters: {}, inline_editable: [],
    current_page: 1, total_pages: 1, page_size: 25, has_next: false, has_previous: false, count: 2,
};

const authValue = {
    user: { id: 1, username: "t", is_superuser: true, roles: [] }, loading: false,
    hasRole: () => true, hasAnyRole: () => true, isSuperAdmin: () => true, canManageUsers: () => true,
};

let locationRef: ReturnType<typeof useLocation> | null = null;
let navigateRef: ReturnType<typeof useNavigate> | null = null;
function Probe() {
    locationRef = useLocation();
    navigateRef = useNavigate();
    return null;
}

function renderAt(path: string) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={client}>
            <AuthContext.Provider value={authValue as never}>
                <MemoryRouter initialEntries={[path]}>
                    <Probe />
                    <Routes>
                        <Route path="/masters/:entity/:id?" element={<MasterList />} />
                        <Route path="/masters/:entity/:id/edit" element={<MasterList />} />
                    </Routes>
                </MemoryRouter>
            </AuthContext.Provider>
        </QueryClientProvider>,
    );
}

const listCalls = () => getSpy.mock.calls.filter(([url, cfg]) => url === "masters/exchange-rates/" && cfg?.params?.page_size !== 1);

describe("MasterList: records open inline", () => {
    beforeEach(() => {
        getSpy.mockReset();
        deleteSpy.mockReset();
        toastError.mockReset();
        sessionStorage.clear();
        getSpy.mockImplementation((url: string) => {
            if (url === "masters/exchange-rates/") return Promise.resolve({ data: { ...LIST_META, results: RATES } });
            if (url === "masters/exchange-rates/1/") return Promise.resolve({ data: RATES[0] });
            if (url === "masters/exchange-rates/2/") return Promise.resolve({ data: RATES[1] });
            if (url === "masters/activity-logs/") return Promise.resolve({ data: [] });
            return Promise.reject({ response: { status: 404 } });
        });
    });

    it("Open record expands the row in place: URL becomes the record URL, list query kept, no list refetch", async () => {
        const user = userEvent.setup();
        renderAt("/masters/exchange-rates?search=11-2026&page=1");
        const list = await screen.findByRole("list", { name: "Exchange Rates" });
        await waitFor(() => expect(listCalls().length).toBeGreaterThan(0));
        const before = listCalls().length;

        await user.click(within(list).getByRole("link", { name: "01-11-2026" }));
        const region = await screen.findByRole("region", { name: "01-11-2026 details" });
        expect(await within(region).findByRole("tab", { name: "Overview", selected: true })).toBeInTheDocument();
        expect(locationRef!.pathname).toBe("/masters/exchange-rates/1");
        expect(new URLSearchParams(locationRef!.search).get("search")).toBe("11-2026");
        // Same list, still on screen; the list was not fetched again.
        expect(screen.getByRole("list", { name: "Exchange Rates" })).toBe(list);
        expect(listCalls().length).toBe(before);

        // Collapse: back to the compact list URL, query intact.
        await user.click(screen.getByRole("button", { name: "Collapse 01-11-2026" }));
        expect(locationRef!.pathname).toBe("/masters/exchange-rates");
        expect(new URLSearchParams(locationRef!.search).get("search")).toBe("11-2026");
        expect(screen.queryByRole("region", { name: "01-11-2026 details" })).not.toBeInTheDocument();
    });

    it("a direct record URL renders the list with that record expanded; ?tab= picks its tab and is not a list filter", async () => {
        renderAt("/masters/exchange-rates/2?tab=details");
        const list = await screen.findByRole("list", { name: "Exchange Rates" });
        expect(within(list).getAllByRole("listitem")).toHaveLength(2);
        const region = await screen.findByRole("region", { name: "02-11-2026 details" });
        expect(await within(region).findByRole("tab", { name: "Details", selected: true })).toBeInTheDocument();
        expect(within(region).getByRole("button", { name: "General information" })).toBeInTheDocument();
        await waitFor(() => expect(listCalls().length).toBeGreaterThan(0));
        for (const [, cfg] of listCalls()) expect(cfg.params).not.toHaveProperty("tab");
    });

    it("an old /edit URL opens the list with the record expanded on its Edit tab (no edit page)", async () => {
        renderAt("/masters/exchange-rates/1/edit?page=1");
        const region = await screen.findByRole("region", { name: "01-11-2026 details" });
        expect(await within(region).findByRole("tab", { name: "Edit", selected: true })).toBeInTheDocument();
        expect(within(region).getByRole("form", { name: "Edit 1" })).toBeInTheDocument();
        expect(screen.getByRole("list", { name: "Exchange Rates" })).toBeInTheDocument();
        await waitFor(() => expect(locationRef!.pathname).toBe("/masters/exchange-rates/1"));
    });

    it("browser back closes the record and forward reopens it without losing the list", async () => {
        const user = userEvent.setup();
        renderAt("/masters/exchange-rates?page=1");
        const list = await screen.findByRole("list", { name: "Exchange Rates" });
        await user.click(within(list).getByRole("button", { name: "Actions for 02-11-2026" }));
        await user.click(screen.getByRole("menuitem", { name: "Open record" }));
        expect(await screen.findByRole("region", { name: "02-11-2026 details" })).toBeInTheDocument();
        expect(locationRef!.pathname).toBe("/masters/exchange-rates/2");

        navigateRef!(-1);
        await waitFor(() => expect(screen.queryByRole("region", { name: "02-11-2026 details" })).not.toBeInTheDocument());
        expect(locationRef!.pathname).toBe("/masters/exchange-rates");
        navigateRef!(1);
        expect(await screen.findByRole("region", { name: "02-11-2026 details" })).toBeInTheDocument();
        expect(screen.getByRole("list", { name: "Exchange Rates" })).toBe(list);
    });

    it("deleting the open record shows the server's refusal reason; a successful delete closes it", async () => {
        const user = userEvent.setup();
        deleteSpy.mockRejectedValueOnce({ response: { status: 400, data: ["Cannot delete: referenced by 2 licences."] } });
        renderAt("/masters/exchange-rates/1");
        await screen.findByRole("region", { name: "01-11-2026 details" });
        await user.click(screen.getByRole("button", { name: "Actions for 01-11-2026" }));
        await user.click(screen.getByRole("menuitem", { name: /Delete/ }));
        await waitFor(() => expect(toastError).toHaveBeenCalledWith("Cannot delete: referenced by 2 licences."));
        expect(locationRef!.pathname).toBe("/masters/exchange-rates/1");

        deleteSpy.mockResolvedValueOnce({});
        await user.click(screen.getByRole("button", { name: "Actions for 01-11-2026" }));
        await user.click(screen.getByRole("menuitem", { name: /Delete/ }));
        await waitFor(() => expect(locationRef!.pathname).toBe("/masters/exchange-rates"));
        expect(deleteSpy).toHaveBeenLastCalledWith("masters/exchange-rates/1/");
    });
});
