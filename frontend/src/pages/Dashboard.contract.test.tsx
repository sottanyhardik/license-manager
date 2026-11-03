import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import { v3Fixture } from "@/components/dashboard/fixtures";
import Dashboard from "./Dashboard";
import { dashboardApiContract, DASHBOARD_SECTION_ROLES } from "./dashboardContract";

vi.mock("../api/axios", () => ({ default: { get: vi.fn() } }));
vi.mock("recharts", async () => {
    const React = await import("react");
    const Container = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>;
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

const permissions = {
    user: null,
    loading: false,
    hasRole: vi.fn(() => true),
    hasAnyRole: vi.fn(() => true),
    isSuperAdmin: vi.fn(() => true),
    canManageUsers: vi.fn(() => true),
};

describe("Dashboard API contract v3", () => {
    it("freezes the endpoint, verb, query parameters and section keys", () => {
        expect(dashboardApiContract.version).toBe(3);
        expect(dashboardApiContract.endpoint).toBe("dashboard/");
        expect(dashboardApiContract.method).toBe("GET");
        expect(dashboardApiContract.queryParameters).toEqual(["company_id", "date_from", "date_to", "refresh"]);
        expect([...dashboardApiContract.sections].sort()).toEqual(Object.keys(v3Fixture).sort());
    });

    it("requests the endpoint with no parameters on first load", async () => {
        const get = vi.mocked(api.get);
        get.mockImplementation(async (url: string) =>
            (url === "masters/companies/" ? { data: { results: [] } } : { data: v3Fixture }) as never,
        );

        render(
            <MemoryRouter>
                <AuthContext.Provider value={permissions as never}>
                    <Dashboard />
                </AuthContext.Provider>
            </MemoryRouter>,
        );

        await waitFor(() => expect(get).toHaveBeenCalledWith(dashboardApiContract.endpoint, { params: undefined }));
    });

    it("keeps role gates aligned with the backend role lists", () => {
        expect(DASHBOARD_SECTION_ROLES.licence).toEqual(["LICENSE_MANAGER", "LICENSE_VIEWER", "REPORT_VIEWER"]);
        expect(DASHBOARD_SECTION_ROLES.allotment).toEqual(["ALLOTMENT_MANAGER", "ALLOTMENT_VIEWER", "REPORT_VIEWER"]);
        expect(DASHBOARD_SECTION_ROLES.boe).toEqual(["BOE_MANAGER", "BOE_VIEWER", "ACCOUNT_ACCESS", "REPORT_VIEWER"]);
        expect(DASHBOARD_SECTION_ROLES.invoice).toEqual(["TRADE_MANAGER", "TRADE_VIEWER", "ACCOUNT_ACCESS", "REPORT_VIEWER"]);
    });
});
