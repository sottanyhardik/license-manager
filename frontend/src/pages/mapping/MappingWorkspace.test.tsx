import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
import api from "@/api/axios";
import MappingWorkspace from "./MappingWorkspace";

type NameRow = { key: string; name: string; wordings: number; records: number; licence_count: number; status: string;
    counts: { applied: number; auto: number; conflict: number; stale: number; unverified: number }; conflicts: string[]; notes: string[];
    mapping: { id: number; version: number; target: { item_id: number; name: string } } | null; licences: { id: number; license_number: string }[] };
const nameRow = (over: Partial<NameRow>): NameRow => ({
    key: "K", name: "N", wordings: 1, records: 2, licence_count: 1, status: "MAPPING_REQUIRED", counts: { applied: 0, auto: 0, conflict: 0, stale: 0, unverified: 0 },
    conflicts: [], notes: [], mapping: null, licences: [{ id: 41, license_number: "0310000041" }], ...over,
});
const boeRows = [
    nameRow({ key: "CRUDE PALM KERNEL OIL", name: "CRUDE PALM KERNEL OIL", records: 2 }),
    nameRow({ key: "RASIN", name: "RASIN", records: 5, status: "APPLIED", counts: { applied: 4, auto: 0, conflict: 0, stale: 0, unverified: 1 },
        notes: ["Not verified: no licence debit recorded yet — checked when one is recorded"], mapping: { id: 9, version: 2, target: { item_id: 6, name: "RAISIN" } } }),
];
const allotRows = [nameRow({ key: "WALNUT INSHELL", name: "WALNUT INSHELL", records: 3 })];
const counts = { import: { records: 9, descriptions: 4 }, boe: { records: 4, descriptions: 3 }, allotment: { records: 2, descriptions: 1 } };
const listing = (rows: NameRow[]) => ({ kind: "boe", rows, total: rows.length, total_records: rows.reduce((n, r) => n + r.records, 0), summary: { MAPPING_REQUIRED: 1 },
    offset: 0, limit: 50, can_apply: true });

function setup() {
    vi.mocked(api.get).mockImplementation(async (url: string) => {
        if (url.includes("item-name-mapping/counts")) return { data: counts };
        if (url.includes("import/descriptions")) return { data: { rows: [], total: 0, total_records: 0, summary: {}, offset: 0, limit: 50, can_apply: true } };
        if (url.includes("boe/names")) return { data: listing(boeRows) };
        if (url.includes("allotment/names")) return { data: listing(allotRows) };
        if (url.includes("matching/masters")) return { data: { masters: [{ item_id: 5, name: "PKO" }, { item_id: 6, name: "RAISIN" }, { item_id: 7, name: "WALNUT" }] } };
        if (url.includes("mapping-changes")) return { data: { changes: [], can_retry: false } };
        return { data: {} };
    });
    vi.mocked(api.post).mockResolvedValue({ data: { action: "CREATE", applied: 2, unchanged: 0, conflicts: 0, mapping: { id: 1, version: 1 } } });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><MappingWorkspace /></MemoryRouter></QueryClientProvider>);
    return userEvent.setup();
}

async function openTab(user: ReturnType<typeof userEvent.setup>, tab: RegExp, table: string) {
    await user.click(screen.getByRole("tab", { name: tab }));
    const found = await screen.findByRole("table", { name: table });
    await screen.findAllByRole("option", { name: "PKO" });
    return found;
}

beforeEach(() => vi.clearAllMocks());

describe("Mapping workspace", () => {
    it("has exactly three primary tabs with pending counts", async () => {
        setup();
        const tabs = within(screen.getByRole("tablist", { name: "Mapping sources" })).getAllByRole("tab");
        expect(tabs).toHaveLength(3);
        await waitFor(() => expect(tabs.map((t) => t.textContent)).toEqual(["Licence Import Item (4)", "BOE (3)", "Allotment (1)"]));
    });

    it("BOE: one row per Product Name, Planning Target Item column, empty for a new name, single target posted", async () => {
        const user = setup();
        const table = await openTab(user, /^BOE/, "BOE product names");
        expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["", "Product Name", "Select Planning Target Item", "Status", "Action"]);
        const row = within(table).getByText("CRUDE PALM KERNEL OIL").closest("tr")!;
        expect(within(row).getByText("Mapping Required")).toBeInTheDocument();
        expect(within(row).queryByRole("list", { name: /Selected Planning Target Items/ })).toBeNull(); // nothing pre-filled
        expect(within(row).getByRole("link", { name: "Open licence 0310000041" })).toBeInTheDocument();
        const save = within(row).getByRole("button", { name: "Save mapping for CRUDE PALM KERNEL OIL" });
        expect(save).toBeDisabled();
        const picker = within(row).getByLabelText("Add Planning Target Item for CRUDE PALM KERNEL OIL");
        await user.selectOptions(picker, "5");
        await user.selectOptions(within(row).getByLabelText("Change Planning Target Item for CRUDE PALM KERNEL OIL"), "7"); // single: replaces
        expect(within(within(row).getByRole("list", { name: /Selected Planning Target Items/ })).getAllByRole("listitem")).toHaveLength(1);
        await user.click(save);
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/item-name-mapping/boe/names/save/", { name: "CRUDE PALM KERNEL OIL", target_id: 7 }));
    });

    it("BOE: a saved mapping reopens with its target, version and Not verified status", async () => {
        const user = setup();
        const table = await openTab(user, /^BOE/, "BOE product names");
        const row = within(table).getByText("RASIN").closest("tr")!;
        expect(within(within(row).getByRole("list", { name: /Selected Planning Target Items/ })).getByText("RAISIN")).toBeInTheDocument();
        expect(within(row).getByText("Applied · Not verified")).toBeInTheDocument();
        expect(within(row).getByText(/no licence debit recorded yet/)).toBeInTheDocument();
        await user.click(within(row).getByRole("button", { name: "Remove RAISIN from RASIN" }));
        await user.selectOptions(within(row).getByLabelText("Add Planning Target Item for RASIN"), "5");
        await user.click(within(row).getByRole("button", { name: "Save mapping for RASIN" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/item-name-mapping/boe/names/save/", { name: "RASIN", target_id: 5, expected_version: 2 }));
    });

    it("Allotment: Item Name* column; bulk update previews then posts one target", async () => {
        const user = setup();
        const table = await openTab(user, /^Allotment/, "Allotment item names");
        expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["", "Item Name*", "Select Planning Target Item", "Status", "Action"]);
        vi.mocked(api.post).mockResolvedValueOnce({ data: { descriptions: 1, records: 3, licence_count: 1, licences: [{ id: 41, license_number: "0310000041" }],
            licences_truncated: false, fingerprint: "fp", sample: ["WALNUT INSHELL"], missing: [], limit: 150, too_many: false } });
        await user.click(within(table).getByLabelText("Select WALNUT INSHELL"));
        await user.selectOptions(screen.getByLabelText("Add Planning Target Item for bulk update"), "7");
        await user.click(screen.getByRole("button", { name: "Apply Bulk Update" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/item-name-mapping/allotment/names/bulk/preview/", { mode: "keys", keys: ["WALNUT INSHELL"] }));
        const dialog = await screen.findByRole("alertdialog");
        expect(within(dialog).getByText(/existing allotment record/)).toBeInTheDocument();
        expect(within(dialog).getByRole("link", { name: "Open licence 0310000041" })).toBeInTheDocument();
        vi.mocked(api.post).mockResolvedValueOnce({ data: { succeeded: [{ key: "WALNUT INSHELL", description: "WALNUT INSHELL", applied: 3 }], skipped: [], failed: [], descriptions: 1, records: 3 } });
        await user.click(within(dialog).getByRole("button", { name: "Update 1 item name(s)" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/item-name-mapping/allotment/names/bulk/apply/",
            { mode: "keys", keys: ["WALNUT INSHELL"], fingerprint: "fp", target_id: 7 }));
    });

    it("BOE filter builder filters by Product Name only", async () => {
        const user = setup();
        await openTab(user, /^BOE/, "BOE product names");
        await user.click(screen.getByRole("button", { name: /Filter Conditions/ }));
        await user.click(screen.getByRole("button", { name: "Add condition to Root filter group" }));
        const field = screen.getByLabelText("Condition 1 field");
        expect(within(field).getAllByRole("option").map((o) => o.textContent)).toEqual(["Product Name"]);
    });

    it("licence import item tab is the one-row description mapping table (no suggestion / product review)", async () => {
        setup();
        expect(await screen.findByRole("table", { name: "Licence import item descriptions" })).toBeInTheDocument();
        expect(screen.queryByText(/Suggested Item Name/)).toBeNull();
        expect(screen.queryByText(/Review products/)).toBeNull();
    });
});
