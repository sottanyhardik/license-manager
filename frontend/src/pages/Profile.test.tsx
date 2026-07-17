import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import type { AuthContextValue, AuthUser } from "../types";
import Profile, {
    buildProfilePayload,
    getProfileErrorMessage,
    normalizeProfileRoles,
} from "./Profile";

vi.mock("../api/axios", () => ({
    default: {
        patch: vi.fn(),
    },
}));

const mockedPatch = vi.mocked(api.patch);

const baseUser: AuthUser = {
    id: 1,
    username: "ada",
    first_name: "Ada",
    last_name: "Lovelace",
    email: "ada@example.com",
    is_superuser: false,
    is_staff: false,
    is_active: true,
    roles: ["DOC_VIEWER", "DOC_VIEWER", " DOC_EDITOR ", ""],
    date_joined: "2024-01-01T00:00:00Z",
};

function renderProfile(
    user: AuthUser | null,
    overrides: Partial<AuthContextValue> = {},
) {
    const authValue: AuthContextValue = {
        user,
        loading: false,
        loginSuccess: vi.fn(),
        updateUser: vi.fn(),
        logout: vi.fn(),
        hasRole: vi.fn(() => false),
        hasAnyRole: vi.fn(() => false),
        isSuperAdmin: vi.fn(() => false),
        canManageUsers: vi.fn(() => false),
        ...overrides,
    };

    return {
        ...render(
            <AuthContext.Provider value={authValue}>
                <Profile />
            </AuthContext.Provider>,
        ),
        authValue,
    };
}

describe("Profile helpers", () => {
    it("trims profile payload fields and sends blank email as null", () => {
        expect(buildProfilePayload({
            first_name: " Ada ",
            last_name: " Lovelace ",
            email: "   ",
        })).toEqual({
            first_name: "Ada",
            last_name: "Lovelace",
            email: null,
        });
    });

    it("extracts useful profile update errors", () => {
        expect(getProfileErrorMessage({ response: { data: { first_name: ["Too long"] } } })).toBe("Too long");
        expect(getProfileErrorMessage({ response: { data: { detail: "Denied" } } })).toBe("Denied");
        expect(getProfileErrorMessage(new Error("Network down"))).toBe("Network down");
        expect(getProfileErrorMessage({})).toBe("Failed to update profile.");
    });

    it("normalizes duplicate and malformed role values", () => {
        expect(normalizeProfileRoles([" ADMIN ", "ADMIN", "", null, "USER"])).toEqual(["ADMIN", "USER"]);
    });
});

describe("Profile", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        localStorage.clear();
    });

    it("syncs editable form data after the authenticated user hydrates", async () => {
        const { rerender, authValue } = renderProfile(null);

        expect(screen.getByText("Loading…")).toBeInTheDocument();

        rerender(
            <AuthContext.Provider value={{ ...authValue, user: baseUser }}>
                <Profile />
            </AuthContext.Provider>,
        );

        await userEvent.click(screen.getByRole("button", { name: /edit profile/i }));

        expect(screen.getByLabelText(/first name/i)).toHaveValue("Ada");
        expect(screen.getByLabelText(/last name/i)).toHaveValue("Lovelace");
        expect(screen.getByLabelText(/email address/i)).toHaveValue("ada@example.com");
    });

    it("saves normalized profile data without rewriting auth tokens", async () => {
        localStorage.setItem("access", "existing-access");
        localStorage.setItem("refresh", "existing-refresh");
        const updateUser = vi.fn();
        const updatedUser = {
            ...baseUser,
            first_name: "Grace",
            last_name: "Hopper",
            email: "",
        };
        mockedPatch.mockResolvedValue({ data: updatedUser });

        renderProfile(baseUser, { updateUser });

        await userEvent.click(screen.getByRole("button", { name: /edit profile/i }));
        fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: " Grace " } });
        fireEvent.change(screen.getByLabelText(/last name/i), { target: { value: " Hopper " } });
        fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "   " } });
        await userEvent.click(screen.getByRole("button", { name: /save changes/i }));

        await waitFor(() => {
            expect(mockedPatch).toHaveBeenCalledWith("/auth/me/", {
                first_name: "Grace",
                last_name: "Hopper",
                email: null,
            });
        });
        expect(updateUser).toHaveBeenCalledWith(updatedUser);
        expect(localStorage.getItem("access")).toBe("existing-access");
        expect(localStorage.getItem("refresh")).toBe("existing-refresh");
        expect(await screen.findByText("Profile updated successfully.")).toBeInTheDocument();
    });

    it("renders normalized assigned roles once", () => {
        renderProfile(baseUser);

        expect(screen.getAllByText("DOC_VIEWER")).toHaveLength(1);
        expect(screen.getByText("DOC_EDITOR")).toBeInTheDocument();
    });

    it("shows field-level API errors", async () => {
        mockedPatch.mockRejectedValue({ response: { data: { email: ["Enter a valid email address."] } } });
        renderProfile(baseUser);

        await userEvent.click(screen.getByRole("button", { name: /edit profile/i }));
        await userEvent.click(screen.getByRole("button", { name: /save changes/i }));

        expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    });
});
