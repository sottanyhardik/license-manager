import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthContext } from "../../context/AuthContext";
import UserList from "./UserList";
import { listUsers } from "../../api/users";

vi.mock("sonner", () => ({
    toast: {
        error: vi.fn(),
        success: vi.fn(),
    },
}));

vi.mock("../../api/users", () => ({
    deleteUser: vi.fn(),
    listUsers: vi.fn(),
}));

const authValue = {
    user: {
        id: 1,
        username: "admin",
        email: "admin@example.com",
        first_name: "",
        last_name: "",
        is_superuser: true,
        is_staff: true,
        is_active: true,
        roles: [],
        date_joined: "2026-01-01T00:00:00Z",
    },
    loading: false,
    loginSuccess: vi.fn(),
    logout: vi.fn(),
    hasRole: vi.fn(() => true),
    hasAnyRole: vi.fn(() => true),
    isSuperAdmin: vi.fn(() => true),
    canManageUsers: vi.fn(() => true),
};

function renderList() {
    render(
        <MemoryRouter>
            <AuthContext.Provider value={authValue}>
                <UserList />
            </AuthContext.Provider>
        </MemoryRouter>,
    );
}

describe("UserList", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(listUsers).mockResolvedValue({
            data: {
                results: [
                    {
                        id: 1,
                        username: "admin",
                        email: "admin@example.com",
                        first_name: "System",
                        last_name: "Admin",
                        is_active: true,
                        is_superuser: true,
                        roles: ["USER_MANAGER"],
                    },
                    {
                        id: 2,
                        username: "manager",
                        email: "",
                        first_name: "",
                        last_name: "",
                        is_active: false,
                        is_superuser: false,
                        roles: [],
                    },
                ],
            },
        } as never);
    });

    it("renders paginated user results and does not show delete for the current user", async () => {
        renderList();

        expect(await screen.findByText("admin")).toBeInTheDocument();
        expect(screen.getByText("manager")).toBeInTheDocument();
        expect(screen.getByText("No roles")).toBeInTheDocument();
        expect(screen.getByText("Inactive")).toBeInTheDocument();
        expect(screen.getAllByRole("button", { name: "" })).toHaveLength(1);
    });
});
