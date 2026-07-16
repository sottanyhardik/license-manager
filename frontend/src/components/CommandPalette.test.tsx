import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext } from "../context/AuthContext";
import CommandPalette from "./CommandPalette";

vi.mock("@/components/Icon", () => ({
    default: ({ name }: { name: string }) => <span data-testid={`icon-${name}`} />,
}));

const authValue = (roles: string[] = [], isSuperuser = false) => ({
    user: {
        id: 1,
        username: "viewer",
        email: "viewer@example.com",
        first_name: "",
        last_name: "",
        is_superuser: isSuperuser,
        is_staff: false,
        is_active: true,
        roles,
        date_joined: "2026-01-01T00:00:00Z",
    },
    loading: false,
    loginSuccess: vi.fn(),
    logout: vi.fn(),
    hasRole: vi.fn((role: string) => isSuperuser || roles.includes(role)),
    hasAnyRole: vi.fn((allowedRoles: string[]) => (
        isSuperuser || allowedRoles.some((role) => roles.includes(role))
    )),
    isSuperAdmin: vi.fn(() => isSuperuser),
    canManageUsers: vi.fn(() => isSuperuser || roles.includes("USER_MANAGER")),
});

function renderPalette(roles: string[] = [], isSuperuser = false) {
    render(
        <MemoryRouter>
            <AuthContext.Provider value={authValue(roles, isSuperuser) as never}>
                <CommandPalette open onClose={vi.fn()} />
            </AuthContext.Provider>
        </MemoryRouter>,
    );
}

describe("CommandPalette authorization visibility", () => {
    it("hides role-protected commands from users without matching roles", () => {
        renderPalette();

        expect(screen.getByRole("option", { name: /dashboard/i })).toBeInTheDocument();
        expect(screen.getByRole("option", { name: /profile/i })).toBeInTheDocument();
        expect(screen.queryByRole("option", { name: /licenses/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("option", { name: /new license/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("option", { name: /item report/i })).not.toBeInTheDocument();
    });

    it("shows read/report commands but hides write commands for a license viewer", () => {
        renderPalette(["LICENSE_VIEWER"]);

        expect(screen.getByRole("option", { name: /^licenses$/i })).toBeInTheDocument();
        expect(screen.getByRole("option", { name: /item report/i })).toBeInTheDocument();
        expect(screen.queryByRole("option", { name: /new license/i })).not.toBeInTheDocument();
    });

    it("shows every command for a superuser", () => {
        renderPalette([], true);

        expect(screen.getByRole("option", { name: /new license/i })).toBeInTheDocument();
        expect(screen.getByRole("option", { name: /users & roles/i })).toBeInTheDocument();
        expect(screen.getByRole("option", { name: /activity log/i })).toBeInTheDocument();
    });
});
