import { render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "../context/AuthContext";
import type { AuthContextValue } from "../types";
import AppRoutes from "./AppRoutes";

vi.mock("../layout/AdminLayout", () => ({ default: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("../pages/license-overview/LicenseOverviewPage", () => ({ default: () => <div>OVERVIEW PAGE</div> }));
vi.mock("../pages/masters/MasterForm", () => ({ default: () => <div>MASTER FORM</div> }));
vi.mock("../pages/Forbidden", () => ({ default: () => <div>FORBIDDEN</div> }));
vi.mock("../pages/mapping/MappingWorkspace", () => ({ default: () => <div>MAPPING WORKSPACE</div> }));

function Where() {
    const l = useLocation();
    return <div data-testid="where">{l.pathname + l.search + l.hash}</div>;
}

function renderAt(url: string, allowed = true) {
    const ctx: AuthContextValue = {
        user: { id: 1, username: "u" } as AuthContextValue["user"],
        loading: false,
        loginSuccess: () => {},
        updateUser: () => {},
        logout: async () => {},
        hasRole: () => allowed,
        hasAnyRole: () => allowed,
        isSuperAdmin: () => false,
        canManageUsers: () => false,
    };
    return render(
        <AuthContext.Provider value={ctx}>
            <MemoryRouter initialEntries={[url]}>
                <AppRoutes />
                <Where />
            </MemoryRouter>
        </AuthContext.Provider>,
    );
}

describe("/licenses/:id redirect", () => {
    it("redirects to overview preserving query and hash", async () => {
        renderAt("/licenses/5?tab=planning#x");
        expect(await screen.findByText("OVERVIEW PAGE")).toBeTruthy();
        expect(screen.getByTestId("where").textContent).toBe("/licenses/5/overview?tab=planning#x");
    });

    it("does not shadow /licenses/create or /licenses/:id/edit", async () => {
        const a = renderAt("/licenses/create");
        expect(await screen.findByText("MASTER FORM")).toBeTruthy();
        expect(screen.getByTestId("where").textContent).toBe("/licenses/create");
        a.unmount();
        renderAt("/licenses/5/edit");
        expect(await screen.findByText("MASTER FORM")).toBeTruthy();
        expect(screen.getByTestId("where").textContent).toBe("/licenses/5/edit");
    });

    it("gives unauthorised roles the same result as /overview", async () => {
        const a = renderAt("/licenses/5/overview", false);
        expect(await screen.findByText("FORBIDDEN")).toBeTruthy();
        expect(screen.getByTestId("where").textContent).toBe("/403");
        a.unmount();
        renderAt("/licenses/5?tab=planning", false);
        expect(await screen.findByText("FORBIDDEN")).toBeTruthy();
        expect(screen.getByTestId("where").textContent).toBe("/403");
    });

    it("SionNormReport link target (/licenses/:id/overview) resolves", async () => {
        renderAt("/licenses/9/overview");
        expect(await screen.findByText("OVERVIEW PAGE")).toBeTruthy();
    });

    it("keeps the individual licence Overview route after the Mapping / Item Pivot changes (/licenses/312/overview)", async () => {
        renderAt("/licenses/312/overview?tab=transactions");
        expect(await screen.findByText("OVERVIEW PAGE")).toBeTruthy();
        expect(screen.getByTestId("where").textContent).toBe("/licenses/312/overview?tab=transactions"); // no redirect / rename
    });

    it("routes /mapping to the Mapping workspace for report roles only", async () => {
        renderAt("/mapping");
        expect(await screen.findByText("MAPPING WORKSPACE")).toBeTruthy();
    });
});
