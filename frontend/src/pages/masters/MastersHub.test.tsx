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

    it("edits code-keyed masters by their encoded code", async () => {
        const user = userEvent.setup();
        const navigate = vi.fn();
        render(<GenericMasterCards {...props} navigate={navigate} onDelete={vi.fn()} />);
        await user.click(screen.getByRole("button", { name: /Edit/ }));
        expect(navigate).toHaveBeenCalledWith("/masters/notification-numbers/025%2F2023/edit");
    });

    it("hides edit and delete when the user cannot write", () => {
        render(<GenericMasterCards {...props} navigate={vi.fn()} onDelete={vi.fn()} canWrite={false} />);
        expect(screen.getByText("025/2023")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Edit/ })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    });
});
