import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "../context/AuthContext";
import { ThemeContext } from "../context/ThemeContext";
import TopNav from "./TopNav";

vi.mock("./CommandPalette", () => ({
    default: () => null,
}));

const authValue = {
    user: {
        id: 1,
        username: "viewer",
        email: "viewer@example.com",
        first_name: "",
        last_name: "",
        is_superuser: false,
        is_staff: false,
        roles: ["LICENSE_VIEWER", "REPORT_VIEWER"],
    },
    loading: false,
    loginSuccess: vi.fn(),
    logout: vi.fn(),
    hasRole: vi.fn((role: string) => ["LICENSE_VIEWER", "REPORT_VIEWER"].includes(role)),
    hasAnyRole: vi.fn((roles: string[]) => roles.some(r => ["LICENSE_VIEWER", "REPORT_VIEWER"].includes(r))),
    isSuperAdmin: vi.fn(() => false),
    canManageUsers: vi.fn(() => false),
};

describe("TopNav authorization visibility", () => {
    it("shows Reports when the user has a report-route role", () => {
        render(
            <MemoryRouter>
                <ThemeContext.Provider value={{ theme: "light", toggleTheme: vi.fn() }}>
                    <AuthContext.Provider value={authValue as never}>
                        <TopNav />
                    </AuthContext.Provider>
                </ThemeContext.Provider>
            </MemoryRouter>,
        );

        expect(screen.getByRole("button", { name: /reports/i })).toBeInTheDocument();
    });

    it("provides an accessible mobile drawer without changing the available destinations", () => {
        render(
            <MemoryRouter>
                <ThemeContext.Provider value={{ theme: "light", toggleTheme: vi.fn() }}>
                    <AuthContext.Provider value={authValue as never}>
                        <TopNav />
                    </AuthContext.Provider>
                </ThemeContext.Provider>
            </MemoryRouter>,
        );

        const trigger = screen.getByTestId("mobile-nav-toggle");
        fireEvent.click(trigger);
        expect(screen.getByTestId("mobile-nav-drawer")).toBeInTheDocument();
        expect(screen.getAllByRole("link", { name: /licenses/i }).length).toBeGreaterThan(0);

        fireEvent.keyDown(document, { key: "Escape" });
        expect(screen.queryByTestId("mobile-nav-drawer")).not.toBeInTheDocument();
    });
});

function renderWithRoles(roles: string[]) {
    const value = {
        ...authValue,
        user: { ...authValue.user, roles },
        hasRole: vi.fn((role: string) => roles.includes(role)),
        hasAnyRole: vi.fn((required: string[]) => required.some(r => roles.includes(r))),
    };
    render(
        <MemoryRouter>
            <ThemeContext.Provider value={{ theme: "light", toggleTheme: vi.fn() }}>
                <AuthContext.Provider value={value as never}>
                    <TopNav />
                </AuthContext.Provider>
            </ThemeContext.Provider>
        </MemoryRouter>,
    );
    fireEvent.click(screen.getByTestId("mobile-nav-toggle"));
    return within(screen.getByTestId("mobile-nav-drawer"));
}

const EXTRA_REPORT_HREFS = [
    "/reports/expiring-licenses", "/reports/active-licenses", "/reports/download-license",
    "/reports/parle/sion-e1", "/reports/parle/sion-e5", "/reports/parle/sion-e126", "/reports/parle/sion-e132",
];

describe("TopNav previously unlinked routes", () => {
    const hrefs = (drawer: ReturnType<typeof within>) => drawer.queryAllByRole("link").map(a => a.getAttribute("href"));

    it("links the extra report routes for a REPORT_VIEWER", () => {
        const found = hrefs(renderWithRoles(["REPORT_VIEWER"]));
        EXTRA_REPORT_HREFS.forEach(h => expect(found).toContain(h));
        expect(found).not.toContain("/reconciliation-issues");
    });

    it("hides the extra report routes without a report role", () => {
        const found = hrefs(renderWithRoles(["LICENSE_VIEWER"]));
        EXTRA_REPORT_HREFS.forEach(h => expect(found).not.toContain(h));
    });

    it("links reconciliation issues for read roles only (same gate as the route)", () => {
        expect(hrefs(renderWithRoles(["TRADE_VIEWER"]))).toContain("/reconciliation-issues");
    });

    it("does not link reconciliation issues for a licence viewer", () => {
        expect(hrefs(renderWithRoles(["LICENSE_VIEWER"]))).not.toContain("/reconciliation-issues");
    });
});
