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

const ROLES = ["ALLOTMENT_MANAGER", "BOE_MANAGER", "TRADE_MANAGER", "LICENSE_MANAGER"];
const ALLOTMENT_FAILED = "This section could not be loaded. Check the connection, then retry";

function clone<T>(value: T): T {
    return JSON.parse(JSON.stringify(value));
}

type Plan = {
    full: unknown;
    retries?: (unknown | "network-error")[];
};

function mockDashboardApi(plan: Plan) {
    const queue = [...(plan.retries ?? [])];
    vi.mocked(api.get).mockImplementation(async (url: string, config?: { params?: Record<string, string> }) => {
        if (url === "masters/companies/") return { data: { results: [] } } as never;
        if (url !== "dashboard/") throw new Error(`unexpected ${url}`);
        if (!config?.params?.section) return { data: clone(plan.full) } as never;
        const next = queue.shift();
        if (next === undefined || next === "network-error") throw new Error("network");
        return { data: { meta: clone(v3Fixture.meta), allotment_activity: clone(next) } } as never;
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

describe("allotment activity alongside the other sections", () => {
    beforeEach(() => {
        vi.mocked(api.get).mockReset();
    });

    it("loads with the other sections from a single dashboard request", async () => {
        mockDashboardApi({ full: v3Fixture });
        renderPage();

        expect(await screen.findByRole("table", { name: /Recent allotments/ })).toBeInTheDocument();
        expect(screen.getByRole("table", { name: "Bills of entry" })).toBeInTheDocument();
        expect(dashboardCalls()).toHaveLength(1);
    });

    it("an allotment failure leaves BOE and invoice activity working", async () => {
        mockDashboardApi({ full: { ...clone(v3Fixture), allotment_activity: { error: ALLOTMENT_FAILED } } });
        renderPage();

        expect(await screen.findByRole("button", { name: "Retry Allotment activity" })).toBeInTheDocument();
        expect(screen.getByRole("table", { name: "Bills of entry" })).toBeInTheDocument();
        expect(screen.getByRole("table", { name: "Recent invoices with outstanding amounts" })).toBeInTheDocument();
    });

    it("a BOE failure leaves allotment activity working", async () => {
        mockDashboardApi({ full: { ...clone(v3Fixture), boe_activity: { error: "BOE failed" } } });
        renderPage();

        expect(await screen.findByRole("table", { name: /Recent allotments/ })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Retry BOE activity" })).toBeInTheDocument();
    });

    it("retrying allotment activity refetches only that section and recovers it", async () => {
        mockDashboardApi({
            full: { ...clone(v3Fixture), allotment_activity: { error: ALLOTMENT_FAILED } },
            retries: [clone(v3Fixture.allotment_activity)],
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Retry Allotment activity" }));

        const table = await screen.findByRole("table", { name: /Recent allotments/ });
        expect(within(table).getByText("Total, all allotments in scope")).toBeInTheDocument();
        expect(dashboardCalls()).toHaveLength(2);
        expect(dashboardCalls()[1]?.[1]).toEqual({ params: expect.objectContaining({ section: "allotment_activity", refresh: "1" }) });
    });

    it("a failed allotment retry stays in its error state with Retry, never an empty state", async () => {
        mockDashboardApi({
            full: { ...clone(v3Fixture), allotment_activity: { error: ALLOTMENT_FAILED } },
            retries: ["network-error"],
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Retry Allotment activity" }));

        await waitFor(() => expect(screen.getByRole("button", { name: "Retry Allotment activity" })).toBeInTheDocument());
        expect(screen.queryByText("No recent allotments")).not.toBeInTheDocument();
    });
});
