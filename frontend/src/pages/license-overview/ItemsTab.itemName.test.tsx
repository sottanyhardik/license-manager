import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ItemsTab from "./ItemsTab";
import type { ImportItemNameRow } from "./types";

const h = vi.hoisted(() => ({
    get: vi.fn(),
    post: vi.fn(),
    toastSuccess: vi.fn(),
}));

vi.mock("@/api/axios", () => ({ default: { get: h.get, post: h.post } }));
vi.mock("sonner", () => ({ toast: { success: h.toastSuccess, error: vi.fn() } }));
vi.mock("@/components/item-async-select", () => ({
    ItemNameAsyncSelect: ({ onChange, ariaLabel }: { onChange: (id: number | null, label?: string | null) => void; ariaLabel?: string }) => (
        <div>
            <input aria-label={ariaLabel} />
            <button onClick={() => onChange(9, "Steel")}>pick-steel</button>
            <button onClick={() => onChange(8, "Copper")}>pick-copper</button>
            <button onClick={() => onChange(null, null)}>pick-clear</button>
        </div>
    ),
}));

const overviewRow = (id: number, description: string) => ({
    id, description, hs_code: "7208", unit: "KG",
    total_qty: 10, total_cif: 100, debited_qty: 0, debited_cif: 0, allotted_qty: 0, allotted_cif: 0,
    balance_qty: 10, balance_cif: 100,
});

const nameRow = (id: number, over: Partial<ImportItemNameRow>): ImportItemNameRow => ({
    import_item_id: id, serial_number: id, description: `Desc ${id}`, hs_code: "7208", unit: "KG", sion: [],
    items: [], status: "NOT_MAPPED", source: null, note: "", overridden: false, override: null, description_mapping: null,
    ...over,
});

let namesPayload: { can_edit: boolean; rows: ImportItemNameRow[] };
let namesFails = false;

function setup() {
    h.get.mockImplementation(async (url: string) => {
        if (url.endsWith("/overview-items/")) {
            return { data: { rows: [overviewRow(1, "Desc 1"), overviewRow(2, "Desc 2"), overviewRow(3, "Desc 3")], footer_totals: { total_cif: 300 } } };
        }
        if (url.endsWith("/import-item-names/")) {
            if (namesFails) throw new Error("boom");
            return { data: namesPayload };
        }
        if (url.endsWith("/history/")) {
            return { data: { events: [{ time: "2026-01-02T10:00:00+00:00", user: "ann", action: "OVERRIDE", previous_items: [], new_items: [{ id: 9, name: "Steel" }], note: "fix" }] } };
        }
        throw new Error(`unexpected GET ${url}`);
    });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={qc}>
            <ItemsTab licenseId={5} isActive />
        </QueryClientProvider>,
    );
}

beforeEach(() => {
    saveResponse = { data: { saved: 1, unchanged: 0, mapping_change: null, rows: [] } };
    h.get.mockReset();
    h.post.mockReset();
    h.toastSuccess.mockReset();
    namesFails = false;
    namesPayload = {
        can_edit: true,
        rows: [
            nameRow(1, { items: [{ id: 1, name: "Zinc" }], status: "MAPPED", source: "DESCRIPTION_MAPPING" }),
            nameRow(2, {}),
            nameRow(3, { items: [{ id: 4, name: "A" }, { id: 5, name: "B" }], status: "MULTIPLE", source: "AUTO" }),
        ],
    };
});

const previewFor = (id: number, over: Record<string, unknown> = {}) => ({
    import_item_id: id, combination: { description: `Desc ${id}`, hsn_code: "7208" }, records: 37, licences: 12, overridden: 2,
    licence_numbers: ["0310000001", "0310000002"], current_item_sets: { Zinc: 30, "": 7 }, ...over,
});

/** Save all → (global drafts) preview dialog → confirm. */
async function saveAllAndConfirm(user: ReturnType<typeof userEvent.setup>, previews: unknown[] = []) {
    h.post.mockImplementation(async (url: string) => {
        if (url.endsWith("/preview/")) return { data: { previews } };
        return saveResponse;
    });
    await user.click(screen.getByRole("button", { name: "Save all" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByLabelText("Affected combinations");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));
}
let saveResponse: { data: unknown };
const saveCalls = () => h.post.mock.calls.filter((c) => String(c[0]).endsWith("/save/"));

const editBtn = (n: number) => screen.getByRole("button", { name: `Edit Item Name for Desc ${n}` });

describe("ItemsTab Item Name column", () => {
    it("shows mapped, Not Mapped and Multiple, and keeps footer colSpan aligned", async () => {
        const { container } = setup();
        expect(await screen.findByText("Zinc")).toBeInTheDocument();
        expect(screen.getByText("Description mapping")).toBeInTheDocument();
        expect(screen.getByText("Not Mapped")).toBeInTheDocument();
        const multi = screen.getByText("Multiple (ambiguous)");
        expect(multi).toHaveAttribute("title", "A, B");
        const headers = container.querySelectorAll("thead th");
        expect(headers[1]).toHaveTextContent("Item Name");
        const footerCell = container.querySelector("tfoot td") as HTMLElement;
        expect(footerCell.getAttribute("colspan")).toBe(String(5));
        expect(headers.length).toBe(12);
        expect(container.querySelector("tfoot td[data-column-id='total-cif']")).toBeInTheDocument();
    });

    it("shows a Conflict with its note", async () => {
        namesPayload.rows[1] = nameRow(2, { status: "CONFLICT", note: "HSN clash" });
        setup();
        const badge = await screen.findByText(/Conflict: HSN clash/);
        expect(badge).toHaveAttribute("title", "HSN clash");
    });

    it("is read-only when can_edit is false", async () => {
        namesPayload.can_edit = false;
        setup();
        await screen.findByText("Zinc");
        expect(screen.queryByRole("button", { name: /Edit Item Name/ })).toBeNull();
    });

    it("shows a dash with retry when the names query fails and keeps numeric table", async () => {
        namesFails = true;
        setup();
        const retry = await screen.findAllByRole("button", { name: "Retry loading item names" });
        expect(retry.length).toBe(3);
        expect(screen.getByText("Desc 1")).toBeInTheDocument();
    });

    it("marks drafts unsaved, discards, and saves several rows in one request", async () => {
        const user = userEvent.setup();
        setup();
        await screen.findByText("Zinc");
        await user.click(editBtn(1));
        await user.click(screen.getByText("pick-steel"));
        await user.click(editBtn(2));
        await user.click(screen.getByText("pick-copper"));
        expect(screen.getAllByText(/● Unsaved/).length).toBe(2);
        expect(screen.getByText("2 unsaved changes")).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Discard" }));
        expect(screen.queryByText("2 unsaved changes")).toBeNull();
        expect(screen.getByText("Zinc")).toBeInTheDocument();

        await user.click(editBtn(1));
        await user.click(screen.getByText("pick-steel"));
        await user.click(editBtn(3));
        await user.click(screen.getByText("pick-clear"));
        saveResponse = { data: { saved: 2, unchanged: 0, mapping_change: null, rows: [] } };
        await saveAllAndConfirm(user, [previewFor(1), previewFor(3)]);
        await waitFor(() => expect(saveCalls()).toHaveLength(1));
        expect(saveCalls()[0][0]).toBe("licenses/5/import-item-names/save/");
        expect(saveCalls()[0][1]).toEqual({
            changes: [
                { import_item_id: 1, item_id: 9, expected_item_ids: [1], scope: "global" },
                { import_item_id: 3, item_id: null, expected_item_ids: [4, 5], scope: "global" },
            ],
        });
        await waitFor(() => expect(h.toastSuccess).toHaveBeenCalled());
        await waitFor(() => expect(screen.queryByText(/unsaved changes/)).toBeNull());
    });

    it("cancels an edit with Escape and returns focus to the cell", async () => {
        const user = userEvent.setup();
        setup();
        await screen.findByText("Zinc");
        await user.click(editBtn(1));
        const input = screen.getByLabelText("Item Name for Desc 1");
        input.focus();
        await user.keyboard("{Escape}");
        await waitFor(() => expect(editBtn(1)).toHaveFocus());
        expect(screen.queryByText(/unsaved/i)).toBeNull();
    });

    it("on 409 keeps drafts, highlights rows and reloads only the listed rows", async () => {
        const user = userEvent.setup();
        setup();
        await screen.findByText("Zinc");
        await user.click(editBtn(1));
        await user.click(screen.getByText("pick-steel"));
        await user.click(editBtn(2));
        await user.click(screen.getByText("pick-copper"));
        h.post.mockImplementation(async (url: string) => {
            if (url.endsWith("/preview/")) return { data: { previews: [previewFor(1), previewFor(2)] } };
            throw { response: { status: 409, data: { detail: "Rows changed", import_item_ids: [1] } } };
        });
        await user.click(screen.getByRole("button", { name: "Save all" }));
        await user.click(await within(await screen.findByRole("dialog")).findByRole("button", { name: "Save changes" }));
        expect(await screen.findByText("Rows changed")).toBeInTheDocument();
        expect(screen.getByText("Changed by someone else")).toBeInTheDocument();
        expect(screen.getByText("2 unsaved changes")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Reload these rows" }));
        await waitFor(() => expect(screen.getByText("1 unsaved change")).toBeInTheDocument());
        expect(screen.queryByText("Rows changed")).toBeNull();
    });

    it("shows the detail on a 400", async () => {
        const user = userEvent.setup();
        setup();
        await screen.findByText("Zinc");
        await user.click(editBtn(2));
        await user.click(screen.getByText("pick-steel"));
        h.post.mockImplementation(async (url: string) => {
            if (url.endsWith("/preview/")) return { data: { previews: [previewFor(2)] } };
            throw { response: { status: 400, data: { detail: "Item is inactive" } } };
        });
        await user.click(screen.getByRole("button", { name: "Save all" }));
        await user.click(await within(await screen.findByRole("dialog")).findByRole("button", { name: "Save changes" }));
        expect(await screen.findByText("Item is inactive")).toBeInTheDocument();
        expect(screen.getByText("1 unsaved change")).toBeInTheDocument();
    });

    it("reverts an override after confirmation", async () => {
        const user = userEvent.setup();
        namesPayload.rows[0] = nameRow(1, {
            items: [{ id: 9, name: "Steel" }], status: "MAPPED", source: "OVERRIDE", overridden: true,
            description_mapping: { id: 3, version: 1, status: "ACTIVE", items: [{ id: 1, name: "Zinc" }] },
        });
        setup();
        await screen.findByText("Steel");
        expect(screen.getAllByRole("button", { name: /Revert to description mapping/ }).length).toBe(1);
        await user.click(screen.getByRole("button", { name: "Revert to description mapping for Desc 1" }));
        h.post.mockResolvedValue({ data: { reverted: 1, rows: [] } });
        const dialog = await screen.findByRole("dialog");
        expect(h.post).not.toHaveBeenCalled();
        await user.click(within(dialog).getByRole("button", { name: "Revert" }));
        await waitFor(() => expect(h.post).toHaveBeenCalledWith("licenses/5/import-item-names/revert/", { import_item_ids: [1] }));
    });

    it("opens row history", async () => {
        const user = userEvent.setup();
        setup();
        await screen.findByText("Zinc");
        await user.click(screen.getByRole("button", { name: "Item Name history for Desc 1" }));
        const dialog = await screen.findByRole("dialog");
        expect(await within(dialog).findByText("OVERRIDE")).toBeInTheDocument();
        expect(within(dialog).getByText(/Not Mapped → Steel/)).toBeInTheDocument();
    });

    it("record-only scope is sent as scope=record and saves without a preview", async () => {
        const user = userEvent.setup();
        setup();
        await screen.findByText("Zinc");
        await user.click(editBtn(1));
        await user.click(screen.getByText("pick-steel"));
        const group = screen.getByRole("group", { name: "Scope for Desc 1" });
        expect(within(group).getByRole("button", { name: "All matching records" })).toHaveAttribute("aria-pressed", "true");
        await user.click(within(group).getByRole("button", { name: "This record only" }));
        expect(within(group).getByRole("button", { name: "This record only" })).toHaveAttribute("aria-pressed", "true");
        h.post.mockResolvedValue(saveResponse);
        await user.click(screen.getByRole("button", { name: "Save all" }));
        await waitFor(() => expect(h.post).toHaveBeenCalledTimes(1));
        expect(h.post.mock.calls[0][0]).toBe("licenses/5/import-item-names/save/");
        expect(h.post.mock.calls[0][1]).toEqual({ changes: [{ import_item_id: 1, item_id: 9, expected_item_ids: [1], scope: "record" }] });
    });

    it("sends expected_approval_version for an approved row and shows records, licences and overridden in the preview", async () => {
        const user = userEvent.setup();
        namesPayload.rows[0] = nameRow(1, {
            items: [{ id: 1, name: "Zinc" }], status: "MAPPED", source: "APPROVAL",
            approval: { id: 7, status: "USER_APPROVED", version: 3, item: { id: 1, name: "Zinc" }, records: 5, licences: 2, updated_by: "ann", updated_on: "2026-01-01" },
        });
        setup();
        await screen.findByText("Zinc");
        expect(screen.getByText("Approved v3")).toHaveAttribute("title", expect.stringContaining("5 records on 2 licences"));
        await user.click(editBtn(1));
        await user.click(screen.getByText("pick-steel"));
        h.post.mockImplementation(async (url: string) => {
            if (url.endsWith("/preview/")) return { data: { previews: [previewFor(1)] } };
            return saveResponse;
        });
        await user.click(screen.getByRole("button", { name: "Save all" }));
        const dialog = await screen.findByRole("dialog");
        expect(h.post.mock.calls[0][1]).toEqual({ changes: [{ import_item_id: 1, item_id: 9 }] });
        expect(await within(dialog).findByText("37 records")).toBeInTheDocument();
        expect(within(dialog).getByText("12 licences")).toBeInTheDocument();
        expect(within(dialog).getByText("2 overridden")).toBeInTheDocument();
        expect(within(dialog).getByText(/0310000001, 0310000002/)).toBeInTheDocument();
        expect(within(dialog).getByText(/Zinc × 30, Not Mapped × 7/)).toBeInTheDocument();
        expect(within(dialog).getByText("Steel")).toBeInTheDocument();
        await user.click(within(dialog).getByRole("button", { name: "Save changes" }));
        await waitFor(() => expect(saveCalls()).toHaveLength(1));
        expect(saveCalls()[0][1]).toEqual({ changes: [{ import_item_id: 1, item_id: 9, expected_item_ids: [1], scope: "global", expected_approval_version: 3 }] });
    });

    it("summarises propagation in a toast and lists conflict licences", async () => {
        const user = userEvent.setup();
        setup();
        await screen.findByText("Zinc");
        await user.click(editBtn(1));
        await user.click(screen.getByText("pick-steel"));
        saveResponse = { data: { saved: 1, unchanged: 0, mapping_change: null, rows: [], propagation: [{
            import_item_id: 1, combination: { description: "Desc 1", hsn_code: "7208" }, records: 40, licences: 12, applied: 37, unchanged: 0, overridden: 2, conflicts: 1,
            conflict_licences: [{ id: 3, license_number: "0310000099" }] }] } };
        await saveAllAndConfirm(user, [previewFor(1)]);
        await waitFor(() => expect(h.toastSuccess).toHaveBeenCalledWith("Applied to 37 records on 12 licences; 2 overridden; 1 conflict"));
        const alert = await screen.findByRole("status", { name: "Item Name conflicts" });
        expect(within(alert).getByText(/0310000099/)).toBeInTheDocument();
    });

    it("shows Cleared distinct from Not Mapped, and the cleared approval chip", async () => {
        namesPayload.rows[1] = nameRow(2, {
            status: "CLEARED", source: "APPROVAL",
            approval: { id: 8, status: "USER_APPROVED_CLEAR", version: 1, item: null, records: 3, licences: 1, updated_by: null, updated_on: null },
        });
        setup();
        await screen.findByText("Zinc");
        expect(screen.getByText("Cleared")).toBeInTheDocument();
        expect(screen.getByText("Cleared · approved v1")).toBeInTheDocument();
        expect(screen.queryByText("Not Mapped")).toBeNull();
    });

    it("rows sharing Description + HSN with a global draft show 'will follow' and are not editable", async () => {
        const user = userEvent.setup();
        namesPayload.rows[1] = nameRow(2, { description: "Desc 1" });
        setup();
        await screen.findByText("Zinc");
        const edits = screen.getAllByRole("button", { name: "Edit Item Name for Desc 1" });
        expect(edits).toHaveLength(2);
        await user.click(edits[0]);
        await user.click(screen.getByText("pick-steel"));
        expect(screen.getByText("will follow")).toBeInTheDocument();
        expect(screen.getAllByRole("button", { name: "Edit Item Name for Desc 1" })).toHaveLength(1);
        await user.click(within(screen.getAllByRole("group", { name: "Scope for Desc 1" })[0]).getByRole("button", { name: "This record only" }));
        expect(screen.queryByText("will follow")).toBeNull();
    });
});
