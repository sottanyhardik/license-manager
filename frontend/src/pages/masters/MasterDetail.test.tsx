import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext } from "../../context/AuthContext";
import { ConfirmProvider } from "@/components/shared/ConfirmDialog";
import MasterDetail from "./MasterDetail";

const { getSpy, deleteSpy } = vi.hoisted(() => ({ getSpy: vi.fn(), deleteSpy: vi.fn() }));
vi.mock("../../api/axios", () => ({ default: { get: getSpy, delete: deleteSpy } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const META = {
    list_display: ["code", "name"],
    form_fields: ["code", "name"],
    field_meta: { code: { label: "Port code" } },
};
const PORT = { id: 5, code: "INMAA1", name: "Chennai", created_on: "2026-01-02T03:04:05Z", modified_on: "2026-02-03T04:05:06Z", created_by: 1, modified_by: 2 };
const NOTIFICATION = { id: 1, code: "025/2023", label: "Advance" };

function auth({ superuser = false, roles = [] as string[] } = {}) {
    return {
        isSuperAdmin: () => superuser,
        hasRole: (role: string) => superuser || roles.includes(role),
        hasAnyRole: (list: readonly string[]) => superuser || list.some(r => roles.includes(r)),
    } as unknown as React.ContextType<typeof AuthContext>;
}

function renderAt(path: string, value = auth({ superuser: true })) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={client}>
            <AuthContext.Provider value={value}>
                <ConfirmProvider>
                    <MemoryRouter initialEntries={[path]}>
                        <Routes>
                            <Route path="/masters/:entity/:id" element={<MasterDetail />} />
                            <Route path="/masters/:entity" element={<div>List page</div>} />
                        </Routes>
                    </MemoryRouter>
                </ConfirmProvider>
            </AuthContext.Provider>
        </QueryClientProvider>,
    );
}

describe("MasterDetail", () => {
    beforeEach(() => {
        getSpy.mockReset();
        deleteSpy.mockReset();
        getSpy.mockImplementation((url: string) => {
            if (url === "masters/ports/") return Promise.resolve({ data: META });
            if (url === "masters/ports/5/") return Promise.resolve({ data: PORT });
            if (url === "masters/notification-numbers/") return Promise.resolve({ data: { list_display: ["code", "label"], form_fields: ["code", "label"] } });
            if (url === "masters/notification-numbers/025%2F2023/") return Promise.resolve({ data: NOTIFICATION });
            if (url === "masters/activity-logs/") {
                return Promise.resolve({ data: [{ id: 9, username: "asha", action: "UPDATE", timestamp: "2026-02-03T04:05:06Z", status_code: 200 }] });
            }
            return Promise.reject({ response: { status: 404 } });
        });
    });

    it("shows the record fields, audit data and breadcrumbs", async () => {
        renderAt("/masters/ports/5");
        expect(await screen.findByRole("heading", { name: "INMAA1", level: 1 })).toBeInTheDocument();
        expect(screen.getByText("Port code")).toBeInTheDocument();
        expect(screen.getByText("Chennai")).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Audit" })).toBeInTheDocument();
        expect(screen.getByText("Last updated")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Masters" })).toHaveAttribute("href", "/masters");
        expect(screen.getByRole("link", { name: "Ports" })).toHaveAttribute("href", "/masters/ports");
        expect(screen.getByRole("link", { name: /Edit/ })).toHaveAttribute("href", "/masters/ports/5/edit");
    });

    it("addresses slash codes with an encoded API path and omits absent audit fields", async () => {
        renderAt("/masters/notification-numbers/025%2F2023");
        expect(await screen.findByRole("heading", { name: "025/2023", level: 1 })).toBeInTheDocument();
        expect(getSpy).toHaveBeenCalledWith("masters/notification-numbers/025%2F2023/", expect.anything());
        expect(screen.queryByRole("heading", { name: "Audit" })).not.toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Edit/ })).toHaveAttribute("href", "/masters/notification-numbers/025%2F2023/edit");
    });

    it("shows real change history to user managers", async () => {
        const user = userEvent.setup();
        renderAt("/masters/notification-numbers/025%2F2023", auth({ roles: ["USER_MANAGER"] }));
        await user.click(await screen.findByRole("tab", { name: "History" }));
        expect(await screen.findByText("Updated")).toBeInTheDocument();
        expect(screen.getByText(/asha/)).toBeInTheDocument();
        expect(getSpy).toHaveBeenCalledWith("masters/activity-logs/", expect.objectContaining({
            params: { endpoint: "/api/masters/notification-numbers/025/2023/", changes_only: 1, limit: 100 },
        }));
    });

    it("is view only for readers: no edit, no delete, no history tab", async () => {
        renderAt("/masters/ports/5", auth({ roles: ["LICENSE_VIEWER"] }));
        expect(await screen.findByRole("heading", { name: "INMAA1", level: 1 })).toBeInTheDocument();
        expect(screen.getByText("View only")).toBeInTheDocument();
        expect(screen.queryByRole("link", { name: /Edit/ })).not.toBeInTheDocument();
        expect(screen.queryByRole("tab", { name: "History" })).not.toBeInTheDocument();
        expect(getSpy).not.toHaveBeenCalledWith("masters/activity-logs/", expect.anything());
    });

    it("titles a record by the same identifier as its list row (companies: IEC, not modified_on)", async () => {
        getSpy.mockImplementation((url: string) => {
            if (url === "masters/companies/") return Promise.resolve({ data: { list_display: ["modified_on", "iec", "name"], form_fields: ["iec", "name"] } });
            if (url === "masters/companies/7/") return Promise.resolve({ data: { id: 7, iec: "0306084341", name: "ABHISHEK TRADE", modified_on: "2026-11-01T10:00:00Z" } });
            return Promise.reject({ response: { status: 404 } });
        });
        renderAt("/masters/companies/7");
        expect(await screen.findByRole("heading", { name: "0306084341", level: 1 })).toBeInTheDocument();
    });

    it("explains a missing record", async () => {
        renderAt("/masters/ports/999");
        expect(await screen.findByText("Record not found")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Back to Ports" })).toHaveAttribute("href", "/masters/ports");
    });

    it("rejects an unregistered master", () => {
        renderAt("/masters/not-a-master/1");
        expect(screen.getByText("Unknown master")).toBeInTheDocument();
        expect(getSpy).not.toHaveBeenCalled();
    });

    it("deletes after confirmation and returns to the list", async () => {
        const user = userEvent.setup();
        deleteSpy.mockResolvedValue({});
        renderAt("/masters/notification-numbers/025%2F2023");
        await screen.findByRole("heading", { name: "025/2023", level: 1 });
        await user.click(screen.getByRole("button", { name: /actions/i }));
        await user.click(screen.getByRole("menuitem", { name: /Delete/ }));
        await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Delete" }));
        expect(deleteSpy).toHaveBeenCalledWith("masters/notification-numbers/025%2F2023/");
        expect(await screen.findByText("List page")).toBeInTheDocument();
    });

    it("shows the server's reason when a delete is refused and stays on the record", async () => {
        const { toast } = await import("sonner");
        const user = userEvent.setup();
        deleteSpy.mockRejectedValue({ response: { status: 400, data: ["Cannot delete: referenced by 2 licences."] } });
        renderAt("/masters/ports/5");
        await screen.findByRole("heading", { name: "INMAA1", level: 1 });
        await user.click(screen.getByRole("button", { name: /actions/i }));
        await user.click(screen.getByRole("menuitem", { name: /Delete/ }));
        await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Delete" }));
        await vi.waitFor(() => expect(toast.error).toHaveBeenCalledWith("Cannot delete: referenced by 2 licences."));
        expect(screen.getByRole("heading", { name: "INMAA1", level: 1 })).toBeInTheDocument();
    });
});
