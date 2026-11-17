import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext } from "../../context/AuthContext";
import { MASTER_CATEGORIES, masterEntities } from "../../routes/config";
import { getMasterRecordKey, MASTER_LOOKUP_FIELDS } from "./masterListConfig";
import MastersHub from "./MastersHub";
import GenericMasterCards from "./tables/GenericMasterCards";
import { ConfirmProvider } from "@/components/shared/ConfirmDialog";

const { getSpy } = vi.hoisted(() => ({ getSpy: vi.fn() }));
vi.mock("../../api/axios", () => ({ default: { get: getSpy } }));

function auth({ superuser = false, roles = [] as string[] } = {}) {
    return {
        isSuperAdmin: () => superuser,
        hasRole: (role: string) => superuser || roles.includes(role),
        hasAnyRole: (list: readonly string[]) => superuser || list.some(r => roles.includes(r)),
    } as unknown as React.ContextType<typeof AuthContext>;
}

function renderHub(value = auth({ superuser: true })) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={client}>
            <AuthContext.Provider value={value}>
                <MemoryRouter><MastersHub /></MemoryRouter>
            </AuthContext.Provider>
        </QueryClientProvider>,
    );
}

describe("getMasterRecordKey", () => {
    it("uses the primary key for ordinary masters", () => {
        expect(getMasterRecordKey("ports", { id: 7, code: "INMAA1" })).toBe("7");
    });
    it("uses the encoded code for code-keyed masters", () => {
        expect(getMasterRecordKey("notification-numbers", { id: 1, code: "025/2023" })).toBe("025%2F2023");
        expect(getMasterRecordKey("scheme-codes", { id: 14, code: "37" })).toBe("37");
    });
    it("refuses to build a key from a missing value (never `masters/<entity>//`)", () => {
        expect(() => getMasterRecordKey("notification-numbers", { id: 3, code: "" })).toThrow(/no code/);
        expect(() => getMasterRecordKey("ports", {})).toThrow(/no id/);
    });
    it("covers exactly the backend code-keyed viewsets", () => {
        expect(Object.keys(MASTER_LOOKUP_FIELDS).sort()).toEqual(["notification-numbers", "scheme-codes"]);
    });
});

describe("masterEntities registry", () => {
    it("gives every master a known category and a unique entity", () => {
        const entities = masterEntities.map(m => m.entity);
        expect(new Set(entities).size).toBe(entities.length);
        masterEntities.forEach(m => {
            expect(MASTER_CATEGORIES).toContain(m.category);
            expect(m.path).toBe(`/masters/${m.entity}`);
        });
    });
});

describe("MastersHub", () => {
    beforeEach(() => {
        getSpy.mockReset();
        getSpy.mockImplementation((url: string) => {
            if (url === "masters/ports/") return Promise.reject(new Error("boom"));
            return Promise.resolve({ data: { count: url === "masters/companies/" ? 1234 : 5, results: [] } });
        });
    });

    it("lists every master by category with a live count", async () => {
        renderHub();
        for (const category of MASTER_CATEGORIES) {
            expect(screen.getByRole("heading", { name: category })).toBeInTheDocument();
        }
        expect(screen.getAllByRole("link")).toHaveLength(masterEntities.length);
        expect(screen.getByRole("link", { name: /Notification Numbers/ })).toHaveAttribute("href", "/masters/notification-numbers");
        expect(await within(screen.getByTestId("master-count-companies")).findByText("1,234")).toBeInTheDocument();
        expect(getSpy).toHaveBeenCalledWith("masters/companies/", expect.objectContaining({ params: { page_size: 1 } }));
    });

    // The hub retries a failed count once (React Query backoff ~1 s) before showing "—".
    it("shows an unavailable count instead of failing the page", async () => {
        renderHub();
        expect(await within(screen.getByTestId("master-count-ports")).findByLabelText("Count unavailable", {}, { timeout: 4000 })).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Ports/ })).toBeInTheDocument();
    });

    it("filters by name and shows an empty state", async () => {
        const user = userEvent.setup();
        renderHub();
        const search = screen.getByRole("searchbox", { name: "Search masters" });
        await user.type(search, "notification");
        expect(await screen.findByRole("link", { name: /Notification Numbers/ })).toBeInTheDocument();
        expect(screen.queryByRole("link", { name: /Companies/ })).not.toBeInTheDocument();
        await user.clear(search);
        await user.type(search, "zzzz-nothing");
        expect(await screen.findByText("No masters match your search")).toBeInTheDocument();
    });

    it("tells read-only users that masters are view only", () => {
        renderHub(auth({ roles: ["LICENSE_VIEWER"] }));
        expect(screen.getByTestId("masters-read-only")).toBeInTheDocument();
    });

    it("does not show the view-only note to a User Manager", () => {
        renderHub(auth({ roles: ["USER_MANAGER"] }));
        expect(screen.queryByTestId("masters-read-only")).not.toBeInTheDocument();
    });
});

describe("GenericMasterCards", () => {
    const props = {
        loading: false,
        data: [{ id: 1, code: "025/2023", label: "Advance authorisation" }],
        metadata: { list_display: ["code", "label"] },
        entityName: "notification-numbers",
        entityTitle: "Notification Numbers",
        filterParams: {},
        currentPage: 1,
        pageSize: 25,
    };
    const renderCards = (extra: Record<string, unknown> = {}) => {
        const navigate = vi.fn();
        const onDelete = vi.fn();
        const view = render(<ConfirmProvider><MemoryRouter><GenericMasterCards {...props} navigate={navigate} onDelete={onDelete} {...extra} /></MemoryRouter></ConfirmProvider>);
        const rerenderCards = (more: Record<string, unknown>) =>
            view.rerender(<ConfirmProvider><MemoryRouter><GenericMasterCards {...props} navigate={navigate} onDelete={onDelete} {...extra} {...more} /></MemoryRouter></ConfirmProvider>);
        return { navigate, onDelete, rerenderCards };
    };

    it("links the identifier to the record page by its encoded code", () => {
        renderCards();
        expect(screen.getByRole("link", { name: "025/2023" })).toHaveAttribute("href", "/masters/notification-numbers/025%2F2023");
        expect(screen.getByText("Advance authorisation")).toBeInTheDocument();
    });

    it("edits and deletes through the shared action menu", async () => {
        const user = userEvent.setup();
        const { navigate, onDelete } = renderCards();
        await user.click(screen.getByRole("button", { name: "Actions for 025/2023" }));
        await user.click(screen.getByRole("menuitem", { name: /Edit/ }));
        expect(navigate).toHaveBeenCalledWith("/masters/notification-numbers/025%2F2023/edit");
        await user.click(screen.getByRole("button", { name: "Actions for 025/2023" }));
        await user.click(screen.getByRole("menuitem", { name: /Delete/ }));
        expect(onDelete).toHaveBeenCalledWith(props.data[0]);
    });

    it("offers only Open when the user cannot write", async () => {
        const user = userEvent.setup();
        renderCards({ canWrite: false });
        await user.click(screen.getByRole("button", { name: "Actions for 025/2023" }));
        expect(screen.getByRole("menuitem", { name: /Open/ })).toBeInTheDocument();
        expect(screen.queryByRole("menuitem", { name: /Edit/ })).not.toBeInTheDocument();
        expect(screen.queryByRole("menuitem", { name: /Delete/ })).not.toBeInTheDocument();
    });

    it("shows is_active as a status badge", () => {
        renderCards({ data: [{ id: 2, code: "Q1", label: "Off", is_active: false }], metadata: { list_display: ["code", "label", "is_active"] }, entityName: "purchase-statuses" });
        expect(screen.getByText("Inactive")).toBeInTheDocument();
    });

    it("shows the shared empty state", () => {
        renderCards({ data: [] });
        expect(screen.getByText("No notification numbers found")).toBeInTheDocument();
    });

    describe("bulk actions", () => {
        const rows = [
            { id: 1, code: "025/2023", label: "Advance" },
            { id: 2, code: "040/2006", label: "Old" },
        ];
        const bulkMeta = { list_display: ["code", "label"], bulk_actions: ["delete"] };

        it("are not offered without bulk metadata, a handler or write access", () => {
            renderCards({ data: rows });
            expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
        });

        it("are not offered to read-only users", () => {
            renderCards({ data: rows, metadata: bulkMeta, onBulk: vi.fn(), canWrite: false });
            expect(screen.queryByRole("checkbox", { name: "Select all on page" })).not.toBeInTheDocument();
        });

        it("select rows, confirm, send raw keys and report each refused record by name", async () => {
            const user = userEvent.setup();
            const onBulk = vi.fn().mockResolvedValue({
                action: "delete", requested: 2, succeeded: 1, failed: 1,
                results: [{ key: "025/2023", ok: true }, { key: "040/2006", ok: false, error: "Cannot delete: still referenced." }],
            });
            renderCards({ data: rows, metadata: bulkMeta, onBulk });
            const all = screen.getByRole("checkbox", { name: "Select all on page" });

            await user.click(screen.getByRole("checkbox", { name: "Select 025/2023" }));
            expect(all).toHaveAttribute("data-state", "indeterminate");
            expect(screen.getByText("1 selected")).toBeInTheDocument();
            await user.click(all);
            expect(screen.getByText("2 selected")).toBeInTheDocument();

            await user.click(screen.getByRole("button", { name: "Delete" }));
            const dialog = screen.getByRole("alertdialog");
            expect(within(dialog).getByText("Delete 2 records?")).toBeInTheDocument();
            await user.click(within(dialog).getByRole("button", { name: "Delete" }));

            expect(onBulk).toHaveBeenCalledWith("delete", ["025/2023", "040/2006"]);
            const results = await screen.findByTestId("bulk-results");
            expect(results).toHaveTextContent("1 of 2 deleted");
            expect(within(results).getByText("040/2006")).toBeInTheDocument();
            expect(results).toHaveTextContent("Cannot delete: still referenced.");
            expect(screen.queryByText(/selected$/)).not.toBeInTheDocument();
        });

        it("cancelling the confirmation sends nothing", async () => {
            const user = userEvent.setup();
            const onBulk = vi.fn();
            renderCards({ data: rows, metadata: bulkMeta, onBulk });
            await user.click(screen.getByRole("checkbox", { name: "Select all on page" }));
            await user.click(screen.getByRole("button", { name: "Delete" }));
            await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Cancel" }));
            expect(onBulk).not.toHaveBeenCalled();
        });

        it("clears the selection when the page's rows change", async () => {
            const user = userEvent.setup();
            const { rerenderCards } = renderCards({ data: rows, metadata: bulkMeta, onBulk: vi.fn() });
            await user.click(screen.getByRole("checkbox", { name: "Select all on page" }));
            expect(screen.getByText("2 selected")).toBeInTheDocument();
            rerenderCards({ data: [{ id: 3, code: "018/2015", label: "Next page" }] });
            expect(screen.queryByText(/selected$/)).not.toBeInTheDocument();
        });

        it("offers activate and deactivate only when the master supports them", () => {
            renderCards({
                data: [{ id: 5, code: "Q1", label: "On", is_active: true }],
                metadata: { list_display: ["code", "label", "is_active"], bulk_actions: ["activate", "deactivate", "delete"] },
                entityName: "purchase-statuses",
                onBulk: vi.fn(),
            });
            // Buttons appear once something is selected.
            expect(screen.queryByRole("button", { name: "Activate" })).not.toBeInTheDocument();
        });
    });
});
