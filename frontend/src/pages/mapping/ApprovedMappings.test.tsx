import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ toastSuccess: vi.fn(), toastError: vi.fn() }));
vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: h.toastSuccess, error: h.toastError, warning: vi.fn() } }));
vi.mock("@/components/item-async-select", () => ({
    ItemNameAsyncSelect: ({ onChange, ariaLabel, disabled }: { onChange: (id: number | null, label?: string | null) => void; ariaLabel?: string; disabled?: boolean }) => (
        <div><input aria-label={ariaLabel} disabled={disabled} /><button onClick={() => onChange(9, "Steel")}>pick-steel</button></div>
    ),
}));
import api from "@/api/axios";
import ApprovedMappings from "./ApprovedMappings";
import MappingWorkspace from "./MappingWorkspace";

const BASE = "item-pivot/matching/item-name-mapping/import/approvals/";
const rows = [
    { id: 1, description: "STEEL SHEETS", hsn_code: "7208", status: "USER_APPROVED", item: { id: 4, name: "Zinc" }, version: 2, records: 37, licences: 12, overridden: 2, updated_by: "ann", updated_on: "2026-11-20" },
    { id: 2, description: "COPPER WIRE", hsn_code: null, status: "USER_APPROVED_CLEAR", item: null, version: 1, records: 5, licences: 3, overridden: 0, updated_by: null, updated_on: null },
];
let lastParams: unknown;

function setup(canApply = true) {
    vi.mocked(api.get).mockImplementation(async (url: string, cfg?: { params?: Record<string, unknown> }) => {
        if (url === BASE) {
            lastParams = cfg?.params;
            const status = cfg?.params?.status;
            const list = status ? rows.filter((r) => r.status === status) : rows;
            return { data: { rows: list, total: list.length, counts: { approved: 1, cleared: 1 }, can_apply: canApply } };
        }
        if (url === `${BASE}1/history/`) {
            return { data: { events: [{ version: 2, action: "REVISE", item: { id: 4, name: "Zinc" }, previous_item: null, status: "USER_APPROVED", previous_status: "USER_APPROVED_CLEAR", records: 37, licences: 12, user: "ann", time: "2026-11-20T10:00:00+00:00", id: 1, mapping_change: null, detail: {} }] } };
        }
        return { data: {} };
    });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ApprovedMappings /></QueryClientProvider>);
    return userEvent.setup();
}

beforeEach(() => { vi.clearAllMocks(); lastParams = undefined; });

describe("Approved (Description + HSN)", () => {
    it("lists approvals with counts, Cleared and backend figures", async () => {
        setup();
        const table = await screen.findByRole("table", { name: "Approved Description + HSN combinations" });
        const steel = within(table).getByText("STEEL SHEETS").closest("tr")!;
        expect(within(steel).getByText("Zinc")).toBeInTheDocument();
        expect(within(steel).getByText("37")).toBeInTheDocument();
        expect(within(steel).getByText("v2")).toBeInTheDocument();
        expect(within(steel).getByText("ann")).toBeInTheDocument();
        const copper = within(table).getByText("COPPER WIRE").closest("tr")!;
        expect(within(copper).getByText("Cleared")).toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent("1 approved · 1 cleared");
    });

    it("filters by status and shows an empty state", async () => {
        const user = setup();
        await screen.findByText("STEEL SHEETS");
        await user.selectOptions(screen.getByLabelText("Filter approvals by status"), "USER_APPROVED_CLEAR");
        await waitFor(() => expect(screen.queryByText("STEEL SHEETS")).toBeNull());
        expect(lastParams).toMatchObject({ status: "USER_APPROVED_CLEAR" });
        expect(screen.getByText("COPPER WIRE")).toBeInTheDocument();
    });

    it("shows an error with retry when loading fails", async () => {
        vi.mocked(api.get).mockRejectedValue(new Error("boom"));
        render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ApprovedMappings /></QueryClientProvider>);
        expect(await screen.findByText("Could not load approved combinations")).toBeInTheDocument();
    });

    it("revises with expected_version and reports the propagation", async () => {
        const user = setup();
        await user.click(await screen.findByRole("button", { name: "Revise approval for STEEL SHEETS" }));
        const dialog = await screen.findByRole("dialog");
        expect(within(dialog).getByRole("button", { name: "Save revision" })).toBeDisabled();
        await user.click(within(dialog).getByText("pick-steel"));
        vi.mocked(api.post).mockResolvedValue({ data: { records: 40, licences: 12, applied: 37, unchanged: 0, overridden: 2, conflicts: 0, conflict_licences: [] } });
        await user.click(within(dialog).getByRole("button", { name: "Save revision" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith(`${BASE}save/`, { description: "STEEL SHEETS", hsn_code: "7208", item_id: 9, expected_version: 2 }));
        await waitFor(() => expect(h.toastSuccess).toHaveBeenCalledWith("Applied to 37 records on 12 licences; 2 overridden"));
    });

    it("revise with Clear posts item_id null; 409 keeps the dialog with a Reload action", async () => {
        const user = setup();
        await user.click(await screen.findByRole("button", { name: "Revise approval for STEEL SHEETS" }));
        const dialog = await screen.findByRole("dialog");
        const clear = within(dialog).getByRole("button", { name: /Clear \(deliberately/ });
        expect(clear).toHaveAttribute("aria-pressed", "false");
        await user.click(clear);
        expect(clear).toHaveAttribute("aria-pressed", "true");
        vi.mocked(api.post).mockRejectedValue({ response: { status: 409, data: { detail: "Approval changed by someone else" } } });
        await user.click(within(dialog).getByRole("button", { name: "Save revision" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith(`${BASE}save/`, { description: "STEEL SHEETS", hsn_code: "7208", item_id: null, expected_version: 2 }));
        expect(await within(dialog).findByText("Approval changed by someone else")).toBeInTheDocument();
        expect(within(dialog).getByRole("button", { name: "Reload" })).toBeInTheDocument();
    });

    it("revokes only after confirmation", async () => {
        const user = setup();
        await user.click(await screen.findByRole("button", { name: "Revoke approval for STEEL SHEETS" }));
        const dialog = await screen.findByRole("alertdialog");
        expect(api.post).not.toHaveBeenCalled();
        vi.mocked(api.post).mockResolvedValue({ data: {} });
        await user.click(within(dialog).getByRole("button", { name: "Revoke" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith(`${BASE}1/revoke/`, {}));
    });

    it("opens history", async () => {
        const user = setup();
        await user.click(await screen.findByRole("button", { name: "History for STEEL SHEETS" }));
        const dialog = await screen.findByRole("dialog");
        expect(await within(dialog).findByText("v2 · REVISE")).toBeInTheDocument();
        expect(within(dialog).getByText("Cleared → Zinc")).toBeInTheDocument();
    });

    it("hides Revise and Revoke without permission", async () => {
        setup(false);
        await screen.findByText("STEEL SHEETS");
        expect(screen.queryByRole("button", { name: /Revise approval/ })).toBeNull();
        expect(screen.getAllByRole("button", { name: /History for/ })).toHaveLength(2);
    });

    it("is reachable from the Licence Import Item tab without adding a primary tab", async () => {
        vi.mocked(api.get).mockImplementation(async (url: string) => {
            if (url === BASE) return { data: { rows, total: 2, counts: { approved: 1, cleared: 1 }, can_apply: true } };
            if (url.includes("counts")) return { data: { import: { records: 1, descriptions: 1 }, boe: { records: 1, descriptions: 1 }, allotment: { records: 1, descriptions: 1 } } };
            if (url.includes("import/descriptions")) return { data: { rows: [], total: 0, total_records: 0, summary: {}, offset: 0, limit: 50, can_apply: true } };
            return { data: { masters: [], changes: [] } };
        });
        const { MemoryRouter } = await import("react-router-dom");
        render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><MappingWorkspace /></MemoryRouter></QueryClientProvider>);
        const user = userEvent.setup();
        const toggle = await screen.findByRole("button", { name: "Approved (Description + HSN)" });
        expect(toggle).toHaveAttribute("aria-pressed", "false");
        await user.click(toggle);
        expect(toggle).toHaveAttribute("aria-pressed", "true");
        expect(await screen.findByRole("table", { name: "Approved Description + HSN combinations" })).toBeInTheDocument();
        expect(within(screen.getByRole("tablist", { name: "Mapping sources" })).getAllByRole("tab")).toHaveLength(3);
    });
});
