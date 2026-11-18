import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext } from "../../context/AuthContext";
import MasterRecordPanel from "./MasterRecordPanel";

const { getSpy } = vi.hoisted(() => ({ getSpy: vi.fn() }));
vi.mock("../../api/axios", () => ({ default: { get: getSpy } }));
vi.mock("@/api/axios", () => ({ default: { get: getSpy } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
// The Edit tab embeds the generic MasterForm (covered by its own tests); a stub exposes its contract here.
const { formProps } = vi.hoisted(() => ({ formProps: vi.fn() }));
vi.mock("./MasterForm", () => ({
    default: (props: { entityName: string; recordId: string; embedded?: boolean; onSuccess?: (id: string) => void; onClose?: () => void }) => {
        formProps(props);
        return (
            <form aria-label="Edit form">
                <button type="button" onClick={() => { props.onSuccess?.(props.recordId); props.onClose?.(); }}>Update</button>
                <button type="button" onClick={() => props.onClose?.()}>Cancel</button>
            </form>
        );
    },
}));

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

function renderPanel(
    entity: string,
    lookup: string,
    { value = auth({ superuser: true }), initialTab, canWrite = false }: { value?: ReturnType<typeof auth>; initialTab?: string; canWrite?: boolean } = {},
) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={client}>
            <AuthContext.Provider value={value}>
                <MasterRecordPanel entity={entity} lookup={lookup} label={`${entity} ${lookup}`} initialTab={initialTab} canWrite={canWrite} />
            </AuthContext.Provider>
        </QueryClientProvider>,
    );
}

describe("MasterRecordPanel (inline record of any master)", () => {
    beforeEach(() => {
        getSpy.mockReset();
        sessionStorage.clear();
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

    it("opens on Overview with the list identifiers; Details shows accordion sections with fields and audit", async () => {
        const user = userEvent.setup();
        renderPanel("ports", "5");
        expect(await screen.findByRole("tab", { name: "Overview", selected: true })).toBeInTheDocument();
        expect(screen.getByText("INMAA1")).toBeInTheDocument();

        await user.click(screen.getByRole("tab", { name: "Details" }));
        expect(screen.getByRole("button", { name: "General information", expanded: true })).toBeInTheDocument();
        expect(screen.getByText("Port code")).toBeInTheDocument();
        expect(screen.getByText("Chennai")).toBeInTheDocument();
        const audit = screen.getByRole("button", { name: "Audit information", expanded: false });
        await user.click(audit);
        expect(audit).toHaveAttribute("aria-expanded", "true");
        expect(screen.getByText("Last updated")).toBeInTheDocument();
        // Ports have no child collections or documents.
        expect(screen.queryByRole("tab", { name: /Related records/ })).not.toBeInTheDocument();
        expect(screen.queryByRole("tab", { name: "Document" })).not.toBeInTheDocument();
    });

    it("honours an initial tab (old ?tab=details links)", async () => {
        renderPanel("ports", "5", { initialTab: "details" });
        expect(await screen.findByRole("tab", { name: "Details", selected: true })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "General information" })).toBeInTheDocument();
    });

    it("addresses slash codes with an encoded API path and omits absent audit fields", async () => {
        renderPanel("notification-numbers", "025/2023", { initialTab: "details" });
        expect(await screen.findByRole("button", { name: "General information" })).toBeInTheDocument();
        expect(getSpy).toHaveBeenCalledWith("masters/notification-numbers/025%2F2023/", expect.anything());
        expect(screen.queryByRole("button", { name: "Audit information" })).not.toBeInTheDocument();
    });

    it("shows real change history to user managers", async () => {
        const user = userEvent.setup();
        renderPanel("notification-numbers", "025/2023", { value: auth({ roles: ["USER_MANAGER"] }) });
        await user.click(await screen.findByRole("tab", { name: "History" }));
        expect(await screen.findByText("Updated")).toBeInTheDocument();
        expect(screen.getByText(/asha/)).toBeInTheDocument();
        expect(getSpy).toHaveBeenCalledWith("masters/activity-logs/", expect.objectContaining({
            params: { endpoint: "/api/masters/notification-numbers/025/2023/", changes_only: 1, limit: 100 },
        }));
    });

    it("has no history tab for readers and never calls the audit log", async () => {
        renderPanel("ports", "5", { value: auth({ roles: ["LICENSE_VIEWER"] }) });
        expect(await screen.findByRole("tab", { name: "Overview" })).toBeInTheDocument();
        expect(screen.queryByRole("tab", { name: "History" })).not.toBeInTheDocument();
        expect(getSpy).not.toHaveBeenCalledWith("masters/activity-logs/", expect.anything());
    });

    it("Edit tab (writers): the generic form embedded for this record; save and cancel stay in the row", async () => {
        const user = userEvent.setup();
        renderPanel("notification-numbers", "025/2023", { canWrite: true, initialTab: "edit" });
        // Opened by the old /edit URL: Edit is selected.
        expect(await screen.findByRole("tab", { name: "Edit", selected: true })).toBeInTheDocument();
        expect(formProps).toHaveBeenLastCalledWith(expect.objectContaining({ entityName: "notification-numbers", recordId: "025/2023", embedded: true }));

        await user.click(screen.getByRole("button", { name: "Update" }));
        expect(await screen.findByRole("tab", { name: "Overview", selected: true })).toBeInTheDocument();

        await user.click(screen.getByRole("tab", { name: "Edit" }));
        await user.click(screen.getByRole("button", { name: "Cancel" }));
        expect(screen.getByRole("tab", { name: "Overview", selected: true })).toBeInTheDocument();
    });

    it("no Edit tab without write access, even from an /edit link", async () => {
        renderPanel("ports", "5", { value: auth({ roles: ["LICENSE_VIEWER"] }), initialTab: "edit" });
        expect(await screen.findByRole("tab", { name: "Overview", selected: true })).toBeInTheDocument();
        expect(screen.queryByRole("tab", { name: "Edit" })).not.toBeInTheDocument();
        expect(screen.queryByRole("form", { name: "Edit form" })).not.toBeInTheDocument();
    });

    it("explains a missing record inline", async () => {
        renderPanel("ports", "999");
        expect(await screen.findByText("Record not found")).toBeInTheDocument();
    });

    it("shows an inline error with retry when the record cannot be loaded", async () => {
        const user = userEvent.setup();
        let calls = 0;
        getSpy.mockImplementation((url: string) => {
            if (url === "masters/ports/") return Promise.resolve({ data: META });
            if (url === "masters/ports/5/") return ++calls === 1 ? Promise.reject({ response: { status: 500 } }) : Promise.resolve({ data: PORT });
            return Promise.reject({ response: { status: 404 } });
        });
        renderPanel("ports", "5");
        expect(await screen.findByText("Could not load this record")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: /retry/i }));
        expect(await screen.findByRole("tab", { name: "Overview" })).toBeInTheDocument();
        expect(screen.getByText("INMAA1")).toBeInTheDocument();
    });
});
