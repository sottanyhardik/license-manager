import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import Dashboard from "./Dashboard";
import { dashboardApiContract } from "./dashboardContract";

vi.mock("../api/axios", () => ({ default: { get: vi.fn() } }));

const permissions = {
    user: null,
    loading: false,
    hasRole: vi.fn(() => true),
    hasAnyRole: vi.fn(() => true),
    isSuperAdmin: vi.fn(() => true),
    canManageUsers: vi.fn(() => true),
};

const responseFixture = {
    license_stats: { total: 12, active: 9, expired: 2, null_dfia: 1, expiring_soon: 3 },
    allotment_stats: { total: 7, recent: [] },
    boe_stats: { total: 5, pending_invoices: 2, recent: [] },
    expiring_licenses: [],
    boe_monthly_trend: [],
};

describe("Dashboard API contract", () => {
    it("freezes the single dashboard request path, verb, parameters, and response shape", async () => {
        const get = vi.mocked(api.get);
        get.mockResolvedValueOnce({ data: responseFixture } as never);

        render(
            <MemoryRouter>
                <AuthContext.Provider value={permissions as never}>
                    <Dashboard />
                </AuthContext.Provider>
            </MemoryRouter>,
        );

        await waitFor(() => expect(get).toHaveBeenCalledTimes(1));
        expect(get).toHaveBeenCalledWith(dashboardApiContract.endpoint);
        expect(dashboardApiContract.method).toBe("GET");
        expect(dashboardApiContract.queryParameters).toEqual([]);
        expect(Object.keys(responseFixture)).toEqual(Object.keys(dashboardApiContract.response));
        expect(Object.keys(responseFixture.license_stats)).toEqual(dashboardApiContract.response.license_stats);
        expect(Object.keys(responseFixture.allotment_stats)).toEqual(dashboardApiContract.response.allotment_stats);
        expect(Object.keys(responseFixture.boe_stats)).toEqual(dashboardApiContract.response.boe_stats);
    });
});
