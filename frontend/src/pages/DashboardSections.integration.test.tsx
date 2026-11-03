import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import { v3Fixture } from "@/components/dashboard/fixtures";
import Dashboard from "./Dashboard";

vi.mock("../api/axios", () => ({ default: { get: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));
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

const COMPANIES = { data: { results: [] } };
const ROLES = ["BOE_MANAGER", "TRADE_MANAGER", "ALLOTMENT_MANAGER", "LICENSE_MANAGER"];

function clone<T>(value: T): T {
    return JSON.parse(JSON.stringify(value));
}

type Plan = {
    /** Full-payload response, or an error to reject with. */
    full: unknown | "network-error";
    /** Responses for single-section retries, in order, keyed by section name. */
    retries?: Partial<Record<"boe_activity" | "invoice_activity", (unknown | "network-error")[]>>;
};

/**
 * Routes `dashboard/` calls by their params: the full payload has no `section`,
 * a section retry has `section` and gets only that section back.
 */
function mockDashboardApi(plan: Plan) {
    const retryQueues = { boe_activity: [...(plan.retries?.boe_activity ?? [])], invoice_activity: [...(plan.retries?.invoice_activity ?? [])] };
    vi.mocked(api.get).mockImplementation(async (url: string, config?: { params?: Record<string, string> }) => {
        if (url === "masters/companies/") return COMPANIES as never;
        if (url !== "dashboard/") throw new Error(`unexpected ${url}`);
        const section = config?.params?.section as keyof typeof retryQueues | undefined;
        if (!section) {
            if (plan.full === "network-error") throw new Error("network");
            return { data: clone(plan.full) } as never;
        }
        const next = retryQueues[section].shift();
        if (next === undefined) throw new Error(`no retry response queued for ${section}`);
        if (next === "network-error") throw new Error("network");
        return { data: { meta: clone(v3Fixture.meta), [section]: clone(next) } } as never;
    });
}

function dashboardCalls() {
    return vi.mocked(api.get).mock.calls.filter(([url]) => url === "dashboard/");
}

function renderPage() {
    const auth = {
        user: null,
        loading: false,
        hasRole: (code: string) => ROLES.includes(code),
        hasAnyRole: (codes: string[]) => codes.some((code) => ROLES.includes(code)),
        isSuperAdmin: () => false,
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

const boeFailure = { error: "This section could not be loaded. Check the connection, then retry" };
const invoiceFailure = { error: "This section could not be loaded. Check the connection, then retry" };

describe("dashboard BOE and invoice sections together", () => {
    beforeEach(() => {
        vi.mocked(api.get).mockReset();
    });

    it("loads both sections from a single dashboard request", async () => {
        mockDashboardApi({ full: v3Fixture });
        renderPage();

        expect(await screen.findByRole("table", { name: "Bills of entry" })).toBeInTheDocument();
        expect(screen.getByRole("table", { name: "Recent invoices with outstanding amounts" })).toBeInTheDocument();
        expect(dashboardCalls()).toHaveLength(1);
    });

    it("a BOE failure leaves Invoice activity working", async () => {
        mockDashboardApi({ full: { ...clone(v3Fixture), boe_activity: boeFailure } });
        renderPage();

        expect(await screen.findByRole("button", { name: "Retry BOE activity" })).toBeInTheDocument();
        expect(screen.getByRole("table", { name: "Recent invoices with outstanding amounts" })).toBeInTheDocument();
    });

    it("an invoice failure leaves BOE activity working", async () => {
        mockDashboardApi({ full: { ...clone(v3Fixture), invoice_activity: invoiceFailure } });
        renderPage();

        expect(await screen.findByRole("button", { name: "Retry Invoice activity" })).toBeInTheDocument();
        expect(screen.getByRole("table", { name: "Bills of entry" })).toBeInTheDocument();
    });

    it("retrying the BOE section recovers it with one section request and no full refetch", async () => {
        mockDashboardApi({
            full: { ...clone(v3Fixture), boe_activity: boeFailure },
            retries: { boe_activity: [clone(v3Fixture.boe_activity)] },
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Retry BOE activity" }));

        const section = await screen.findByRole("table", { name: "Bills of entry" });
        expect(within(section).getAllByRole("row").length).toBeGreaterThan(1);
        expect(dashboardCalls()).toHaveLength(2);
        expect(dashboardCalls()[1]?.[1]).toEqual({ params: expect.objectContaining({ section: "boe_activity", refresh: "1" }) });
        expect(screen.getByRole("table", { name: "Recent invoices with outstanding amounts" })).toBeInTheDocument();
    });

    it("a failed retry keeps the section in its error state with Retry, never an empty state", async () => {
        mockDashboardApi({
            full: { ...clone(v3Fixture), invoice_activity: invoiceFailure },
            retries: { invoice_activity: ["network-error"] },
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Retry Invoice activity" }));

        await waitFor(() => expect(screen.getByRole("button", { name: "Retry Invoice activity" })).toBeInTheDocument());
        expect(screen.queryByText("No recent invoices")).not.toBeInTheDocument();
        expect(screen.getByRole("table", { name: "Bills of entry" })).toBeInTheDocument();
    });

    it("recovers invoice activity after a temporary failure on the second retry", async () => {
        mockDashboardApi({
            full: { ...clone(v3Fixture), invoice_activity: invoiceFailure },
            retries: { invoice_activity: ["network-error", clone(v3Fixture.invoice_activity)] },
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Retry Invoice activity" }));
        await waitFor(() => expect(screen.getByRole("button", { name: "Retry Invoice activity" })).toBeInTheDocument());

        fireEvent.click(screen.getByRole("button", { name: "Retry Invoice activity" }));
        expect(await screen.findByRole("table", { name: "Recent invoices with outstanding amounts" })).toBeInTheDocument();
        expect(dashboardCalls()).toHaveLength(3);
    });
});
