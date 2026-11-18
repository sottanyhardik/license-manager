import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }));
vi.mock("@/pages/AllotmentAction", () => ({ default: ({ allotmentId }: { allotmentId: number }) => <p>Allocation workflow {allotmentId}</p> }));
vi.mock("@/utils/pdfPreview", () => ({ openPdfPreview: vi.fn() }));
vi.mock("@/pages/masters/MasterForm", () => ({
    default: ({ recordId, onSuccess, onClose }: { recordId: number; onSuccess: (id: number) => void; onClose: () => void }) => (
        <div aria-label="Allotment form">
            <p>Editing {recordId}</p>
            <button type="button" onClick={() => onSuccess(recordId)}>Save</button>
            <button type="button" onClick={onClose}>Cancel</button>
        </div>
    ),
}));

import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import type { AuthContextValue } from "@/types";
import AllotmentsTable from "@/pages/masters/tables/AllotmentsTable";
import { ALLOTMENT_FIXTURES } from "./fixtures";

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const del = api.delete as unknown as ReturnType<typeof vi.fn>;
const navigate = vi.fn();
const onDelete = vi.fn();

const auth = (roles: string[]): AuthContextValue => ({
    user: null, loading: false, loginSuccess: () => {}, updateUser: () => {}, logout: async () => {},
    hasRole: (r: string) => roles.includes(r), hasAnyRole: (rs: readonly string[]) => rs.some((r) => roles.includes(r)),
    isSuperAdmin: () => false, canManageUsers: () => false,
});

function setup({ canWrite = true, roles = ["ALLOTMENT_MANAGER"] }: { canWrite?: boolean; roles?: string[] } = {}) {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
        <QueryClientProvider client={qc}>
            <AuthContext.Provider value={auth(roles)}>
                <MemoryRouter>
                    <AllotmentsTable
                        loading={false} data={ALLOTMENT_FIXTURES} canWrite={canWrite} entityName="allotments"
                        filterParams={{}} currentPage={1} pageSize={25} navigate={navigate} onDelete={onDelete}
                    />
                </MemoryRouter>
            </AuthContext.Provider>
        </QueryClientProvider>,
    );
    return userEvent.setup();
}

const row = (id: number) => screen.getByRole("article", { name: `Allotment #${id}` });
const urls = () => get.mock.calls.map((c) => c[0]);

beforeEach(() => {
    vi.clearAllMocks();
    get.mockImplementation((url: string, config?: { params?: Record<string, unknown> }) => {
        const id = Number(url.match(/^allotments\/(\d+)\/$/)?.[1]);
        const record = ALLOTMENT_FIXTURES.find((r) => r.id === id);
        if (record) return Promise.resolve({ data: { ...record, alloted_quantity: `ALLOTTED-${id}`, contact_person: `Contact-${id}` } });
        if (url === "licenses/") {
            const number = String(config?.params?.license_number);
            return Promise.resolve({ data: { results: [{ id: 11, license_number: number, get_norm_class: `SION-${number.slice(-2)}`, get_balance_cif: "1234.5" }] } });
        }
        const ledger = url.match(/^licenses\/(\d+)\/overview-allotments\/$/);
        if (ledger) return Promise.resolve({ data: [
            { allotment_number: "ALT-999", quantity: "1", cif_fc: "1", outstanding_cif_fc: "1", status: "Pending" },
            { allotment_number: "ALT-101", quantity: "10000", cif_fc: "12000.50", outstanding_cif_fc: `${ledger[1]}00.25`, status: "Approved" },
        ] });
        if (url === "masters/activity-logs/") {
            const prefix = String(config?.params?.endpoint_prefix);
            return Promise.resolve({ data: prefix.startsWith("/api/allotment-actions/")
                ? [{ id: 2, username: "ops", action: "CREATE", method: "POST", endpoint: "/api/allotment-actions/101/allocate-items/", timestamp: "2026-11-02T10:00:00Z", status_code: 201 }]
                : [{ id: 1, username: "lead", action: "UPDATE", method: "PATCH", endpoint: "/api/allotments/101/", timestamp: "2026-11-01T10:00:00Z", status_code: 200 }] });
        }
        if (url === "bill-of-entries/") return Promise.resolve({ data: { results: [{ id: 9, bill_of_entry_number: "BOE-77", total_inr: "5000", invoice_status_label: "Invoiced" }] } });
        return Promise.resolve({ data: new Blob() });
    });
});

describe("Allotment register rows", () => {
    it("renders compact rows with backend figures and opens one row at a time", async () => {
        const user = setup();
        expect(screen.getByRole("list", { name: "Allotments" }).children).toHaveLength(4);
        const a = row(101);
        expect(within(a).getByText("INV-101")).toBeInTheDocument();
        expect(within(a).getByText("0310001111 +1")).toHaveAttribute("title", "0310001111, 0310002222");
        expect(within(a).getByText("Acme Foods")).toBeInTheDocument();
        expect(within(row(102)).getByText("BOE linked")).toBeInTheDocument();
        expect(within(row(102)).getByText("No invoice")).toBeInTheDocument();
        expect(within(row(103)).getByText("-5")).toBeInTheDocument();
        expect(get).not.toHaveBeenCalled();

        await user.click(within(a).getByRole("button", { name: "Expand allotment #101" }));
        expect(within(a).getByRole("region", { name: "Allotment #101 details" })).toBeInTheDocument();
        await user.click(within(row(103)).getByRole("button", { name: "Expand allotment #103" }));
        expect(screen.getAllByRole("tablist")).toHaveLength(1);
        expect(within(row(101)).queryByRole("region")).toBeNull();
        await user.click(within(row(103)).getByRole("button", { name: "Collapse allotment #103" }));
        expect(screen.queryByRole("tablist")).toBeNull();
    });

    it("lazy-loads each tab from its existing endpoint and hides tabs without data", async () => {
        const user = setup({ roles: ["ALLOTMENT_MANAGER", "BOE_VIEWER"] });
        await user.click(within(row(101)).getByRole("button", { name: "Expand allotment #101" }));
        const a = row(101);
        const tabs = within(a).getAllByRole("tab").map((t) => t.textContent);
        // 101 is not BOE-linked → no BOE tab; History needs USER_MANAGER.
        expect(tabs).toEqual(["Overview", "Allotted Licences (2)", "Allocation", "Allocate Licence", "Documents", "Edit"]);
        await user.click(await within(a).findByRole("button", { name: "Shipment & contact" }));
        expect(within(a).getByText("Contact-101")).toBeInTheDocument();
        expect(urls()).toEqual(["allotments/101/"]);

        await user.click(within(a).getByRole("tab", { name: "Allocation" }));
        expect(await within(a).findByText("ALLOTTED-101")).toBeInTheDocument();
        expect(within(a).getByText("Palm Oil RBD")).toBeInTheDocument();
        expect(urls()).toEqual(["allotments/101/"]);

        await user.click(within(a).getByRole("tab", { name: /Allotted Licences/ }));
        const table = await within(a).findByRole("table", { name: "Allotted licences" });
        expect(await within(table).findByText("SION-11")).toBeInTheDocument();
        expect(within(table).getAllByText("$1,234.50")).toHaveLength(2);
        // Outstanding + status come from each licence's own ledger row for ALT-101 (never another allotment's).
        expect(await within(table).findByText("$1,100.25")).toBeInTheDocument();
        expect(within(table).getByText("$2,200.25")).toBeInTheDocument();
        expect(within(table).getAllByText("Approved")).toHaveLength(2);
        expect(within(table).queryByText("Pending")).toBeNull();
        expect(within(table).getByRole("link", { name: "0310001111" })).toHaveAttribute("href", "/licenses/11");
        expect(urls().filter((u) => u === "licenses/")).toHaveLength(2);
        expect(urls()).toContain("licenses/11/overview-allotments/");
    });

    it("shows the BOE tab only for BOE-linked allotments and BOE readers", async () => {
        let user = setup({ roles: ["ALLOTMENT_MANAGER", "BOE_VIEWER"] });
        await user.click(within(row(102)).getByRole("button", { name: "Expand allotment #102" }));
        await user.click(within(row(102)).getByRole("tab", { name: "BOE" }));
        expect(await within(row(102)).findByText("BOE-77")).toBeInTheDocument();
        expect(get).toHaveBeenCalledWith("bill-of-entries/", expect.objectContaining({ params: { allotment: 102, page_size: 100 } }));

        document.body.innerHTML = "";
        user = setup({ roles: ["ALLOTMENT_MANAGER"] });
        await user.click(within(row(102)).getByRole("button", { name: "Expand allotment #102" }));
        expect(within(row(102)).queryByRole("tab", { name: "BOE" })).toBeNull();
    });

    it("edits inline and returns to Overview on save or cancel", async () => {
        const user = setup();
        await user.click(within(row(101)).getByRole("button", { name: "Expand allotment #101" }));
        await user.click(within(row(101)).getByRole("button", { name: "Actions for allotment #101" }));
        await user.click(await screen.findByRole("menuitem", { name: "Edit" }));
        expect(await within(row(101)).findByText("Editing 101")).toBeInTheDocument();
        expect(navigate).not.toHaveBeenCalled();
        await user.click(within(row(101)).getByRole("button", { name: "Cancel" }));
        expect(within(row(101)).getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
        await user.click(within(row(101)).getByRole("tab", { name: "Edit" }));
        await user.click(await within(row(101)).findByRole("button", { name: "Save" }));
        expect(within(row(101)).getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    });

    it("keeps every existing action in the row menu, gated by role", async () => {
        let user = setup({ canWrite: true });
        await user.click(within(row(101)).getByRole("button", { name: "Expand allotment #101" }));
        await user.click(within(row(101)).getByRole("button", { name: "Actions for allotment #101" }));
        expect((await screen.findAllByRole("menuitem")).map((m) => m.textContent)).toEqual(["Edit", "Copy", "Allocate", "Preview PDF", "Download", "Delete"]);
        await user.click(screen.getByRole("menuitem", { name: "Allocate" }));
        // Allocate opens the inline Allocate Licence tab (same workflow), no navigation.
        expect(await within(row(101)).findByText("Allocation workflow 101")).toBeInTheDocument();
        expect(navigate).not.toHaveBeenCalled();
        await user.click(within(row(101)).getByRole("button", { name: "Actions for allotment #101" }));
        await user.click(await screen.findByRole("menuitem", { name: "Delete" }));
        expect(onDelete).toHaveBeenCalledWith(expect.objectContaining({ id: 101 }));

        document.body.innerHTML = "";
        user = setup({ canWrite: false, roles: ["ALLOTMENT_VIEWER"] });
        await user.click(within(row(101)).getByRole("button", { name: "Expand allotment #101" }));
        expect(within(row(101)).queryByRole("tab", { name: "Edit" })).toBeNull();
        expect(within(row(101)).queryByRole("tab", { name: "Allocate Licence" })).toBeNull();
        await user.click(within(row(101)).getByRole("button", { name: "Actions for allotment #101" }));
        expect((await screen.findAllByRole("menuitem")).map((m) => m.textContent)).toEqual(["Preview PDF", "Download"]);
    });

    it("documents tab requests nothing until a document action is pressed", async () => {
        const user = setup();
        await user.click(within(row(101)).getByRole("button", { name: "Expand allotment #101" }));
        await user.click(within(row(101)).getByRole("tab", { name: "Documents" }));
        await user.click(within(row(101)).getByRole("button", { name: "Open License Copy PDF for 0310002222" }));
        await waitFor(() => expect(urls()).toContain("licenses/22/merged-documents/"));
        await user.click(within(within(row(101)).getByRole("region", { name: "Allotment PDF" })).getByRole("button", { name: "Preview PDF" }));
        await waitFor(() => expect(urls()).toContain("allotment-actions/101/generate-pdf/"));
    });

    it("shows the three allocation stages from backend fields without mixing them", async () => {
        const user = setup();
        await user.click(within(row(101)).getByRole("button", { name: "Expand allotment #101" }));
        const allot = within(row(101)).getByRole("region", { name: "Allotment (customer)" });
        expect(within(allot).getByText("12,500.5")).toBeInTheDocument();
        expect(within(allot).getByText("$1,520,000.75")).toBeInTheDocument();
        const allocated = within(row(101)).getByRole("region", { name: "Allocated to licences" });
        expect(within(allocated).getByText("$1,420,000.75")).toBeInTheDocument();
        expect(within(allocated).getByText("$100,000.00")).toBeInTheDocument();
        expect(within(allocated).getByText("250")).toBeInTheDocument();
        expect(within(row(101)).getByRole("region", { name: "BOE utilisation" })).toHaveTextContent("Not linked");
    });

    it("releases an allocation only after confirmation, through the existing endpoint", async () => {
        del.mockResolvedValue({ data: { message: "Successfully removed allocation of 2250.5 from 0310002222" } });
        const user = setup();
        await user.click(within(row(101)).getByRole("button", { name: "Expand allotment #101" }));
        await user.click(within(row(101)).getByRole("tab", { name: /Allotted Licences/ }));
        await user.click(await within(row(101)).findByRole("button", { name: "Release allocation 0310002222 Sl# 1" }));
        const dialog = await screen.findByRole("alertdialog", { name: "Release allocation?" });
        expect(del).not.toHaveBeenCalled();
        await user.click(within(dialog).getByRole("button", { name: "Release" }));
        await waitFor(() => expect(del).toHaveBeenCalledWith("allotment-actions/101/delete-item/2/"));
    });

    it("read-only users see allocations without release or allocate actions", async () => {
        const user = setup({ canWrite: false, roles: ["ALLOTMENT_VIEWER"] });
        await user.click(within(row(101)).getByRole("button", { name: "Expand allotment #101" }));
        await user.click(within(row(101)).getByRole("tab", { name: /Allotted Licences/ }));
        await within(row(101)).findByRole("table", { name: "Allotted licences" });
        expect(within(row(101)).queryByRole("button", { name: /Release allocation/ })).toBeNull();
        expect(within(row(101)).queryByRole("button", { name: "Allocate Licence" })).toBeNull();
    });

    it("history merges record edits and allocation actions for user managers", async () => {
        const user = setup({ roles: ["ALLOTMENT_MANAGER", "USER_MANAGER"] });
        await user.click(within(row(101)).getByRole("button", { name: "Expand allotment #101" }));
        await user.click(within(row(101)).getByRole("tab", { name: "History" }));
        expect(await within(row(101)).findByText("Allocated to licence")).toBeInTheDocument();
        expect(within(row(101)).getByText("Edited")).toBeInTheDocument();
        expect(get).toHaveBeenCalledWith("masters/activity-logs/", expect.objectContaining({ params: expect.objectContaining({ endpoint_prefix: "/api/allotment-actions/101/", changes_only: 1 }) }));
    });
});
