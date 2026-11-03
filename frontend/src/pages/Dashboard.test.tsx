import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import { v3Fixture } from "@/components/dashboard/fixtures";
import Dashboard from "./Dashboard";
import type { DashboardResponse } from "./dashboardContract";

vi.mock("../api/axios", () => ({ default: { get: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

// Recharts measures its parent, which JSDOM does not lay out. The chart
// behaviour is covered in the browser; here we only check the surrounding UI.
vi.mock("recharts", async () => {
    const React = await import("react");
    const Container = ({ children }: { children?: React.ReactNode }) => <div data-testid="chart">{children}</div>;
    return {
        ResponsiveContainer: Container,
        BarChart: Container,
        Bar: () => null,
        Cell: () => null,
        CartesianGrid: () => null,
        XAxis: () => null,
        YAxis: () => null,
        Tooltip: () => null,
    };
});

const COMPANIES = { data: { results: [{ id: 7, name: "Importer One" }] } };

function mockApi(payload: unknown) {
    vi.mocked(api.get).mockImplementation(async (url: string) => {
        if (url === "masters/companies/") return COMPANIES as never;
        return { data: payload } as never;
    });
}

function dashboardCalls() {
    return vi.mocked(api.get).mock.calls.filter(([url]) => url === "dashboard/");
}

function renderDashboard(roles: string[], { superuser = false }: { superuser?: boolean } = {}) {
    const auth = {
        user: null,
        loading: false,
        hasRole: (code: string) => superuser || roles.includes(code),
        hasAnyRole: (codes: string[]) => superuser || codes.some((code) => roles.includes(code)),
        isSuperAdmin: () => superuser,
        canManageUsers: () => false,
    };
    return render(
        <MemoryRouter>
            <AuthContext.Provider value={auth as never}>
                <Dashboard />
            </AuthContext.Provider>
        </MemoryRouter>,
    );
}

const ALL_ROLES = ["LICENSE_MANAGER", "ALLOTMENT_MANAGER", "BOE_MANAGER", "TRADE_MANAGER"];

function withoutKeys(payload: DashboardResponse, keys: (keyof DashboardResponse)[]): DashboardResponse {
    const copy = { ...payload };
    for (const key of keys) delete copy[key];
    return copy;
}

describe("Dashboard v3", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("shows the four primary CIF figures with units, context and a list link", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);

        const authorised = await screen.findByRole("link", { name: /Authorised CIF: \$100,000\.00/ });
        expect(authorised).toHaveAttribute("href", "/licenses?is_expired=all");
        expect(within(authorised.closest("div") as HTMLElement).getByText(/42 licences in scope/)).toBeInTheDocument();

        expect(screen.getByRole("link", { name: /Utilised CIF: \$40,000\.00/ })).toHaveAttribute("href", "/bill-of-entries");
        expect(screen.getByRole("link", { name: /Reserved CIF: \$10,000\.00/ })).toHaveAttribute("href", "/allotments");
        expect(screen.getByRole("link", { name: /Available CIF: \$48,000\.00/ })).toHaveAttribute("href", "/licenses?is_expired=false");
    });

    it("never shows a trend, change or percentage comparison", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);
        await screen.findByRole("link", { name: /Authorised CIF/ });

        expect(screen.queryByText(/vs\.? (last|previous)|▲|▼|trend|change from/i)).not.toBeInTheDocument();
    });

    it("shows secondary counts in their own strip", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);

        const total = await screen.findByRole("link", { name: /Total licences/ });
        expect(within(total).getByText("42")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Total allotments/ })).toHaveTextContent("18");
        expect(screen.getByRole("link", { name: /Total BOEs/ })).toHaveTextContent("27");
    });

    it("renders '—' for a failed financial section rather than a zero", async () => {
        mockApi({ ...v3Fixture, financial: { error: "Balance engine failed" } });
        renderDashboard(ALL_ROLES);

        expect(await screen.findByRole("link", { name: /Authorised CIF: —/ })).toBeInTheDocument();
        expect(screen.getAllByText(/Unavailable: Balance engine failed/)).toHaveLength(4);
        expect(screen.getByRole("alert")).toHaveTextContent("Balance engine failed");
    });

    it("does not render sections the caller's roles do not grant", async () => {
        const trade = withoutKeys(v3Fixture, ["licence_portfolio", "financial", "expiring_licences", "c969_link_review", "allotment_activity", "boe_activity"]);
        mockApi(trade);
        renderDashboard(["TRADE_VIEWER"]);

        await waitFor(() => expect(screen.getByText("Invoice activity")).toBeInTheDocument());
        expect(screen.queryByText("Authorised CIF")).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Licence portfolio" })).not.toBeInTheDocument();
        expect(screen.queryByText("Active licences")).not.toBeInTheDocument();
        expect(screen.queryByText("BOE activity")).not.toBeInTheDocument();
        expect(screen.queryByRole("link", { name: /Total BOEs/ })).not.toBeInTheDocument();
    });

    it("shows quick actions only where the route guard allows them", async () => {
        mockApi(v3Fixture);
        renderDashboard(["LICENSE_MANAGER"]);
        await screen.findByRole("link", { name: /Authorised CIF/ });

        expect(screen.getByRole("link", { name: "New Licence" })).toHaveAttribute("href", "/licenses/create");
        expect(screen.queryByRole("link", { name: "New BOE" })).not.toBeInTheDocument();
        expect(screen.queryByRole("link", { name: "New Allotment" })).not.toBeInTheDocument();
    });

    it("isolates a failed section while the rest of the page still renders", async () => {
        mockApi({ ...v3Fixture, expiring_licences: { error: "Expiring list failed" } });
        renderDashboard(ALL_ROLES);

        expect(await screen.findByText("Expiring list failed", { exact: false })).toBeInTheDocument();
        expect(screen.getByText("Attention required")).toBeInTheDocument();
        expect(screen.getByText("Allotment activity")).toBeInTheDocument();
        expect(screen.getByText("Invoice activity")).toBeInTheDocument();
    });

    it("lists only verified attention items and the not-monitored notes", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);

        expect(await screen.findByText("Missing DGFT details")).toBeInTheDocument();
        expect(screen.getByText("Over-utilised licences", { selector: "span" })).toBeInTheDocument();
        expect(screen.queryByText("C969 saved items to review")).not.toBeInTheDocument();
        expect(screen.getByText(/Not monitored on this dashboard/)).toBeInTheDocument();
        expect(screen.getByText(/Use the Reconciliation page/)).toBeInTheDocument();
    });

    it("lists the affected licences inline for the three licence exceptions, each linking to its edit page", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);

        const overUtilised = await screen.findByText("Over-utilised licences", { selector: "span" });
        const row = overUtilised.closest("li") as HTMLElement;
        expect(within(row).getByText(/Show licences \(2 shown\)/)).toBeInTheDocument();
        expect(within(row).getByRole("link", { name: "3011000111" })).toHaveAttribute("href", "/licenses/901/edit");
        expect(within(row).getByRole("link", { name: "3011000222" })).toHaveAttribute("href", "/licenses/902/edit");

        const expired = screen.getByText("Expired licences with balance", { selector: "span" }).closest("li") as HTMLElement;
        expect(within(expired).getByRole("link", { name: "3011000333" })).toHaveAttribute("href", "/licenses/903/edit");
    });

    it("shows the licence list error in its attention row without hiding the count", async () => {
        mockApi({ ...v3Fixture, licence_exceptions: { error: "Exception lookup failed" } });
        renderDashboard(ALL_ROLES);

        expect(await screen.findAllByText(/Licence list unavailable: Exception lookup failed/)).toHaveLength(2);
        expect(screen.getByText("Over-utilised licences", { selector: "span" })).toBeInTheDocument();
    });

    it("builds the Active KPI link from is_active and is_expired", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);

        expect(await screen.findByRole("link", { name: /Active licences/ })).toHaveAttribute(
            "href",
            "/licenses?is_active=true&is_expired=false",
        );
    });

    it("states the two accepted limitations on the page", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);
        await screen.findByRole("link", { name: /Authorised CIF/ });

        expect(screen.getByText(/BOE and invoice links open the unfiltered lists/)).toBeInTheDocument();
        expect(screen.getByText(/local date, while the as-of date is UTC/)).toBeInTheDocument();
    });

    it("says there are no open exceptions when the attention list is empty", async () => {
        mockApi({ ...v3Fixture, attention: [] });
        renderDashboard(ALL_ROLES);

        expect(await screen.findByText("No open exceptions in this scope.")).toBeInTheDocument();
    });

    it("lists the same attention items in the notification panel", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);
        await screen.findByText("Missing DGFT details");

        const bell = screen.getByRole("button", { name: /Notifications: 5 open items/ });
        fireEvent.click(bell);
        expect(bell).toHaveAttribute("aria-expanded", "true");
        expect(screen.getAllByText("Missing DGFT details").length).toBeGreaterThan(1);

        fireEvent.keyDown(document, { key: "Escape" });
        await waitFor(() => expect(bell).toHaveAttribute("aria-expanded", "false"));
    });

    it("shows the licence drill-down with a link to each licence's edit page, and the window chips", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);

        expect(await screen.findByRole("link", { name: "3011009039" })).toHaveAttribute("href", "/licenses/812/edit");
        const chip = screen.getByRole("link", { name: /7 days/ });
        const href = new URL(chip.getAttribute("href") ?? "", "http://x");
        expect(href.searchParams.get("license_expiry_date_from")).toBe("2026-11-02");
        expect(href.searchParams.get("license_expiry_date_to")).toBe("2026-11-09");
        expect(href.searchParams.get("is_expired")).toBe("false");
    });

    it("filters the visible rows with the page search", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);
        await screen.findByRole("link", { name: "3011009040" });

        fireEvent.change(screen.getByRole("searchbox"), { target: { value: "3011009040" } });
        expect(screen.queryByRole("link", { name: "3011009039" })).not.toBeInTheDocument();
        expect(screen.getByRole("link", { name: "3011009040" })).toBeInTheDocument();
    });

    it("switches BOE tabs and filters the pending tab to pending mapping", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);
        await screen.findByRole("link", { name: "8001234" });

        fireEvent.mouseDown(screen.getByRole("tab", { name: "Pending licence mapping" }), { button: 0 });
        expect(await screen.findByText(/Showing up to 1 of 4 BOEs with no licence rows/)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "8001235" })).toBeInTheDocument();
        expect(screen.queryByRole("link", { name: "8001234" })).not.toBeInTheDocument();
    });

    it("sorts the BOE table from its headers and exposes aria-sort", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);
        await screen.findByRole("link", { name: "8001234" });

        const header = screen.getByRole("columnheader", { name: /BOE #/ });
        expect(header).toHaveAttribute("aria-sort", "none");
        fireEvent.click(within(header).getByRole("button"));
        expect(header).toHaveAttribute("aria-sort", "ascending");
        fireEvent.click(within(header).getByRole("button"));
        expect(header).toHaveAttribute("aria-sort", "descending");
    });

    it("refreshes with refresh=1 and shows a refreshing state", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);
        await screen.findByRole("link", { name: /Authorised CIF/ });
        expect(dashboardCalls()[0][1]).toEqual({ params: undefined });

        fireEvent.click(screen.getByRole("button", { name: "Refresh dashboard data" }));
        await waitFor(() => expect(dashboardCalls()).toHaveLength(2));
        expect(dashboardCalls()[1][1]).toEqual({ params: { refresh: "1" } });
    });

    it("re-fetches a company scope without refresh=1", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);
        await screen.findByRole("link", { name: /Authorised CIF/ });

        const select = await screen.findByRole("combobox", { name: "Company" });
        await waitFor(() => expect(within(select).getByRole("option", { name: "Importer One" })).toBeInTheDocument());
        fireEvent.change(select, { target: { value: "7" } });

        await waitFor(() => expect(dashboardCalls()).toHaveLength(2));
        expect(dashboardCalls()[1][1]).toEqual({ params: { company_id: 7 } });
    });

    it("sends the activity date range for a preset and omits it for all time", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);
        await screen.findByRole("link", { name: /Authorised CIF/ });

        fireEvent.change(screen.getByRole("combobox", { name: "Activity date range" }), { target: { value: "last30" } });
        await waitFor(() => expect(dashboardCalls()).toHaveLength(2));
        const params = (dashboardCalls()[1][1] as { params: Record<string, string> }).params;
        expect(params.date_to).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(params.date_from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(params.refresh).toBeUndefined();
    });

    it("shows a retry state when the first load fails", async () => {
        vi.mocked(api.get).mockImplementation(async (url: string) => {
            if (url === "masters/companies/") return COMPANIES as never;
            throw new Error("network");
        });
        renderDashboard(ALL_ROLES);

        expect(await screen.findByText("The dashboard could not be loaded.")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /Retry/ })).toBeInTheDocument();
    });

    it("keeps the last successful figures and says so when a refresh fails", async () => {
        mockApi(v3Fixture);
        renderDashboard(ALL_ROLES);
        await screen.findByRole("link", { name: /Authorised CIF/ });

        vi.mocked(api.get).mockImplementation(async (url: string) => {
            if (url === "masters/companies/") return COMPANIES as never;
            throw new Error("network");
        });
        fireEvent.click(screen.getByRole("button", { name: "Refresh dashboard data" }));

        expect(await screen.findByText(/The last successful result is still shown/)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Authorised CIF: \$100,000\.00/ })).toBeInTheDocument();
    });

    it("does not crash when the BOE payload is missing its pending list; the BOE card shows the contract error", async () => {
        const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
        const malformed = JSON.parse(JSON.stringify(v3Fixture));
        delete malformed.boe_activity.pending_mapping;
        mockApi(malformed);
        renderDashboard(ALL_ROLES);

        expect(await screen.findByRole("link", { name: /Authorised CIF/ })).toBeInTheDocument();
        expect(screen.getByText("BOE activity")).toBeInTheDocument();
        expect(screen.getByText(/did not match the expected format/)).toBeInTheDocument();
        expect(screen.getByText("Attention required")).toBeInTheDocument();
        expect(consoleError).toHaveBeenCalledWith(
            expect.stringContaining("contract v3"),
            [{ section: "boe_activity", problem: "boe_activity.pending_mapping should be an array" }],
        );
        consoleError.mockRestore();
    });
});
