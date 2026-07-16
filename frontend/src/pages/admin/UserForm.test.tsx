import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthContext } from "../../context/AuthContext";
import UserForm from "./UserForm";
import { getAvailableRoles, getUser, resetPassword, updateUser } from "../../api/users";

vi.mock("sonner", () => ({
    toast: {
        error: vi.fn(),
        success: vi.fn(),
    },
}));

vi.mock("../../api/users", () => ({
    createUser: vi.fn(),
    getAvailableRoles: vi.fn(),
    getUser: vi.fn(),
    resetPassword: vi.fn(),
    updateUser: vi.fn(),
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

beforeAll(() => {
    if (!globalThis.ResizeObserver) {
        globalThis.ResizeObserver = class ResizeObserver {
            observe() {}
            unobserve() {}
            disconnect() {}
        };
    }
});

function renderEditForm() {
    render(
        <MemoryRouter initialEntries={["/admin/users/2/edit"]}>
            <AuthContext.Provider value={authValue}>
                <Routes>
                    <Route path="/admin/users/:id/edit" element={<UserForm />} />
                </Routes>
            </AuthContext.Provider>
        </MemoryRouter>,
    );
}

describe("UserForm", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(getAvailableRoles).mockResolvedValue({ data: ["USER_MANAGER"] } as never);
        vi.mocked(getUser).mockResolvedValue({
            data: {
                id: 2,
                username: "target",
                email: "target@example.com",
                first_name: "",
                last_name: "",
                is_active: true,
                is_staff: false,
                is_superuser: false,
                roles: ["USER_MANAGER"],
            },
        } as never);
    });

    it("normalizes DRF field errors before rendering them", async () => {
        vi.mocked(updateUser).mockRejectedValue({
            response: {
                data: {
                    email: ["Enter a valid email address."],
                },
            },
        });
        renderEditForm();

        fireEvent.change(await screen.findByLabelText(/email/i), {
            target: { name: "email", value: "duplicate@example.com" },
        });
        fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

        expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    });

    it("shows reset-password validation errors inline", async () => {
        vi.mocked(resetPassword).mockRejectedValue({
            response: {
                data: {
                    password: ["This password is too short."],
                },
            },
        });
        renderEditForm();

        fireEvent.click(await screen.findByRole("button", { name: /^reset password$/i }));
        fireEvent.change(screen.getByPlaceholderText(/new password/i), {
            target: { value: "short" },
        });
        fireEvent.click(screen.getByRole("button", { name: /^set password$/i }));

        await waitFor(() => {
            expect(resetPassword).toHaveBeenCalledWith("2", "short");
        });
        expect(await screen.findByText("This password is too short.")).toBeInTheDocument();
    });
});
