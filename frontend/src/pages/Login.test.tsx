import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "../context/AuthContext";
import { getSafeRedirect } from "../utils/authRedirect";
import Login from "./Login";

vi.mock("../api/axios", () => ({
    default: {
        post: vi.fn(),
    },
}));

const authValue = {
    user: null,
    loading: false,
    loginSuccess: vi.fn(),
    logout: vi.fn(),
    hasRole: vi.fn(() => false),
    hasAnyRole: vi.fn(() => false),
    isSuperAdmin: vi.fn(() => false),
    canManageUsers: vi.fn(() => false),
};

describe("Login", () => {
    it("only accepts internal redirect paths", () => {
        expect(getSafeRedirect("/dashboard")).toBe("/dashboard");
        expect(getSafeRedirect("/licenses?tab=open")).toBe("/licenses?tab=open");
        expect(getSafeRedirect("https://example.com")).toBeNull();
        expect(getSafeRedirect("//example.com/path")).toBeNull();
        expect(getSafeRedirect(null)).toBeNull();
    });

    it("links to the password reset page", () => {
        render(
            <MemoryRouter>
                <AuthContext.Provider value={authValue as never}>
                    <Login />
                </AuthContext.Provider>
            </MemoryRouter>,
        );

        expect(screen.getByRole("link", { name: /forgot password/i })).toHaveAttribute(
            "href",
            "/forgot-password",
        );
    });
});
