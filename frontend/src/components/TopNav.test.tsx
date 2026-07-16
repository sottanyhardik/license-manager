import { render, screen } from "@testing-library/react";
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
        roles: ["LICENSE_VIEWER"],
    },
    loading: false,
    loginSuccess: vi.fn(),
    logout: vi.fn(),
    hasRole: vi.fn((role: string) => role === "LICENSE_VIEWER"),
    hasAnyRole: vi.fn((roles: string[]) => roles.includes("LICENSE_VIEWER")),
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
});
