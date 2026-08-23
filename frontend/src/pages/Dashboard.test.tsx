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

describe("Dashboard command centre", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("keeps canonical KPI values, operational queues, and correctly formatted recent dates", async () => {
        vi.mocked(api.get).mockResolvedValueOnce({ data: dashboardData } as never);
        renderDashboard();

        expect(await screen.findByRole("heading", { name: "Licence health" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /total licences/i })).toHaveTextContent("12");
        expect(screen.getByRole("button", { name: /pending invoices/i })).toHaveTextContent("2");
        expect(screen.getByText("LIC-1")).toBeInTheDocument();
        expect(screen.getAllByText("22-08-2026")).toHaveLength(2);
        expect(screen.getByRole("tab", { name: /missing dgft/i })).toBeInTheDocument();
    });

    it("refreshes only through the existing dashboard endpoint and keeps attention queues operable", async () => {
        const get = vi.mocked(api.get);
        get.mockResolvedValue({ data: dashboardData } as never);
        renderDashboard();
        await screen.findByText("Recent allotments");

        fireEvent.click(screen.getByRole("tab", { name: /pending invoices/i }));
        expect(screen.getByText(/2 pending invoices/i)).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: /refresh dashboard data/i }));
        await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
        expect(get).toHaveBeenLastCalledWith("dashboard/");
    });
});
