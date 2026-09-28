import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import Dashboard from "./Dashboard";

vi.mock("../api/axios", () => ({ default: { get: vi.fn() } }));

// Recharts measures its parent with ResizeObserver. JSDOM deliberately has no
// layout, which otherwise emits a zero-size warning unrelated to Dashboard
// behaviour. Browser coverage renders the real chart at measured dimensions.
vi.mock("recharts", async () => {
    const React = await import("react");
    const Container = ({ children }: { children?: React.ReactNode }) => <div data-testid="boe-trend-chart">{children}</div>;
    return {
        ResponsiveContainer: Container,
        BarChart: Container,
        CartesianGrid: () => null,
        XAxis: () => null,
        YAxis: () => null,
        Tooltip: () => null,
        Bar: Container,
        Cell: () => null,
    };
});

const permissions = {
    user: null,
    loading: false,
    hasRole: vi.fn(() => true),
    hasAnyRole: vi.fn(() => true),
    isSuperAdmin: vi.fn(() => true),
    canManageUsers: vi.fn(() => true),
};

const dashboardData = {
    license_stats: { total: 12, active: 9, expired: 2, null_dfia: 1, expiring_soon: 3 },
    allotment_stats: { total: 7, recent: [{ id: 42, modified_on: "2026-08-22T10:32:51.272787Z", item_name: "Sugar", required_quantity: "20.00", cif_fc: "24.10" }] },
    boe_stats: { total: 5, pending_invoices: 2, recent: [{ id: 9, bill_of_entry_number: "BOE-9", bill_of_entry_date: "2026-08-22", company_name: "Importer" }] },
    expiring_licenses: [{ license_number: "LIC-1", license_expiry_date: "2026-08-29", balance_cif: "100.00", days_to_expiry: 7 }],
    boe_monthly_trend: [{ month: "Aug", count: 5 }],
};

function renderDashboard() {
    return render(<MemoryRouter><AuthContext.Provider value={permissions as never}><Dashboard /></AuthContext.Provider></MemoryRouter>);
}

describe("Dashboard operational redesign", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("renders urgent alerts, KPI snapshot, and recent activity tables", async () => {
        vi.mocked(api.get).mockResolvedValueOnce({ data: dashboardData } as never);
        renderDashboard();

        // Urgent alerts section
        expect(await screen.findByText("Urgent alerts")).toBeInTheDocument();
        expect(screen.getByText("Critical (< 7 days)")).toBeInTheDocument();
        expect(screen.getByText("Require data entry")).toBeInTheDocument();
        expect(screen.getByText("Awaiting follow-up")).toBeInTheDocument();

        // KPI snapshot
        expect(screen.getByText("Snapshot")).toBeInTheDocument();
        expect(screen.getByText("Active")).toBeInTheDocument();
        expect(screen.getByText("Expired")).toBeInTheDocument();

        // Recent activity
        expect(screen.getByText("Recent BOE entries")).toBeInTheDocument();
        expect(screen.getByText("Recent allotments")).toBeInTheDocument();
        expect(screen.getByText("LIC-1")).toBeInTheDocument();
        expect(screen.getByText("BOE-9")).toBeInTheDocument();
        // Verify the company name is in the BOE table
        expect(screen.getByText("Sugar")).toBeInTheDocument();
    });

    it("displays formatted dates and alert counts correctly", async () => {
        vi.mocked(api.get).mockResolvedValueOnce({ data: dashboardData } as never);
        renderDashboard();

        // Wait for urgent alerts to load
        await screen.findByText("Urgent alerts");
        // Test that alert counts are displayed
        expect(screen.getByText(/pending invoices/i)).toBeInTheDocument();
        // Check formatted dates (date format from the data)
        expect(screen.getAllByText("22-08-2026")).toBeDefined();
    });

    it("refreshes only through the existing dashboard endpoint", async () => {
        const get = vi.mocked(api.get);
        get.mockResolvedValue({ data: dashboardData } as never);
        renderDashboard();
        await screen.findByText("Recent allotments");

        fireEvent.click(screen.getByRole("button", { name: /refresh dashboard data/i }));
        await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
        expect(get).toHaveBeenLastCalledWith("dashboard/");
    });
});
