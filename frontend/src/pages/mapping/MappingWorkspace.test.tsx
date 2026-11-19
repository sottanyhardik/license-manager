import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
import api from "@/api/axios";
import MappingWorkspace, { type MappingGroup } from "./MappingWorkspace";

const group = (over: Partial<MappingGroup>): MappingGroup => ({
    key: "k", description: "D", record_ids: [1], records: 1, statuses: { UNMAPPED_AMBIGUOUS: 1 }, licence_count: 1, licence_numbers: ["0310000001"],
    hsn_codes: ["15131900"], sion: ["E126"], quantity: "40.000", units: ["kg"], legitimate: [{ item_id: 5, name: "PKO" }], mappable: true,
    suggestion: { item_id: 5, name: "PKO", confidence: 100, explanation: "Same wording approved in another source: Licence import item approval #3" },
    similar: [], conflicts: [], boe_numbers: ["987654321"], latest_boe_date: "2026-01-02", ...over,
});
const boeQueue = { kind: "boe", total_groups: 3, total_records: 4, offset: 0, limit: 50, can_apply: true, groups: [
    group({ key: "boe:crude palm kernel oil:5", description: "CRUDE PALM KERNEL OIL", record_ids: [11, 12], records: 2 }),
    group({ key: "boe:palm kernel oil:5", description: "PALM KERNEL OIL", record_ids: [14], suggestion: null }),
    group({ key: "boe:widget:", description: "WIDGET", record_ids: [13], legitimate: [], mappable: false, suggestion: null,
        conflicts: [{ code: "SION", detail: "No Item Name is a legitimate planning target" }] }),
] };
const counts = { import: { records: 9, descriptions: 4 }, boe: { records: 4, descriptions: 3 }, allotment: { records: 2, descriptions: 1 } };

function setup() {
    vi.mocked(api.get).mockImplementation(async (url: string) => {
        if (url.includes("item-name-mapping/counts")) return { data: counts };
        if (url.includes("import/descriptions")) return { data: { rows: [], total: 0, summary: {}, offset: 0, limit: 50, can_apply: true } };
        if (url.includes("/history/")) return { data: { rows: [{ id: 11, description: "CRUDE PALM KERNEL OIL", item_id: 5, item: "PKO", hsn_codes: ["15131900"], mapping_version: 7, by: "hardik", on: "2026-11-19T10:00:00Z" }], total: 1 } };
        if (url.includes("item-name-mapping/boe")) return { data: boeQueue };
        if (url.includes("matching/masters")) return { data: { masters: [{ item_id: 5, name: "PKO" }, { item_id: 6, name: "OLIVE OIL" }] } };
        if (url.includes("available-norms")) return { data: [{ norm_class: "E126", description: "Biscuits" }] };
        if (url.includes("matching/health")) return { data: { model: { ok: true }, worker: { ok: true }, available_memory_mb: null } };
        if (url.includes("mapping-changes")) return { data: { changes: [], can_retry: false } };
        return { data: {} };
    });
    vi.mocked(api.post).mockResolvedValue({ data: { mapped: 2, unchanged: 0 } });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><MappingWorkspace /></MemoryRouter></QueryClientProvider>);
    return userEvent.setup();
}

async function openBoe(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole("tab", { name: /^BOE/ }));
    const table = await screen.findByRole("table", { name: "Pending BOE mappings" });
    await screen.findAllByRole("option", { name: "OLIVE OIL" });
    return table;
}

beforeEach(() => vi.clearAllMocks());

describe("Mapping workspace", () => {
    it("has exactly three primary tabs with pending counts", async () => {
        setup();
        const tabs = within(screen.getByRole("tablist", { name: "Mapping sources" })).getAllByRole("tab");
        expect(tabs).toHaveLength(3);
        await waitFor(() => expect(tabs.map((t) => t.textContent)).toEqual(["Licence Import Item (4)", "BOE (3)", "Allotment (1)"]));
    });

    it("BOE: suggestion is a reference only; the explicitly selected Item Name id is posted", async () => {
        const user = setup();
        const table = await openBoe(user);
        const row = within(table).getByText("CRUDE PALM KERNEL OIL").closest("tr")!;
        expect(within(row).getByText(/Suggestion only/)).toBeInTheDocument();
        expect(within(row).getByText(/987654321/)).toBeInTheDocument();
        expect((within(row).getByLabelText("Item Name for CRUDE PALM KERNEL OIL") as HTMLSelectElement).value).toBe("");
        const approve = within(row).getByRole("button", { name: "Approve CRUDE PALM KERNEL OIL" });
        expect(approve).toBeDisabled();
        await user.selectOptions(within(row).getByLabelText("Item Name for CRUDE PALM KERNEL OIL"), "5");
        await user.click(approve);
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/item-name-mapping/boe/apply/", { record_ids: [11, 12], item_id: 5 }));
        expect(within(table).getByText(/No legitimate Item Name under the SION rules/)).toBeInTheDocument();
        expect(within(within(table).getByText("WIDGET").closest("tr")!).getByText("Review required")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Create it in Masters/ })).toHaveAttribute("href", "/masters/item-names");
    });

    it("bulk approval requires an individually selected Item Name per row (a suggestion never counts)", async () => {
        const user = setup();
        const table = await openBoe(user);
        await user.click(within(table).getByLabelText("Select CRUDE PALM KERNEL OIL"));
        await user.click(within(table).getByLabelText("Select PALM KERNEL OIL"));
        const bulk = screen.getByRole("button", { name: "Approve selected (2)" });
        await user.selectOptions(within(table).getByLabelText("Item Name for CRUDE PALM KERNEL OIL"), "5");
        expect(bulk).toBeDisabled(); // second row has a suggestion but no selection
        await user.selectOptions(within(table).getByLabelText("Item Name for PALM KERNEL OIL"), "5");
        expect(bulk).toBeEnabled();
        await user.click(bulk);
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/item-name-mapping/boe/apply/", {
            entries: [{ record_ids: [11, 12], item_id: 5 }, { record_ids: [14], item_id: 5 }] }));
    });

    it("keeps the entry pending and shows the server's validation reason on failure", async () => {
        const user = setup();
        vi.mocked(api.post).mockRejectedValueOnce({ response: { data: { detail: "1 record(s) failed validation — nothing was mapped. #11: OLIVE OIL is not a legitimate planning target" } } });
        const table = await openBoe(user);
        await user.selectOptions(within(table).getByLabelText("Item Name for CRUDE PALM KERNEL OIL"), "6");
        await user.click(within(table).getByRole("button", { name: "Approve CRUDE PALM KERNEL OIL" }));
        expect(await within(table).findByRole("alert")).toHaveTextContent("not a legitimate planning target");
        expect(within(table).getByText("CRUDE PALM KERNEL OIL")).toBeInTheDocument();
    });

    it("shows approved history", async () => {
        const user = setup();
        await openBoe(user);
        await user.click(screen.getByRole("button", { name: "Approved history" }));
        const hist = await screen.findByRole("table", { name: "Approved BOE mappings" });
        expect(within(hist).getByText("PKO")).toBeInTheDocument();
        expect(within(hist).getByText("v7")).toBeInTheDocument();
    });

    it("licence import item tab is the one-row description mapping table (no suggestion / product review)", async () => {
        setup();
        expect(await screen.findByRole("table", { name: "Licence import item descriptions" })).toBeInTheDocument();
        expect(screen.queryByText(/Suggested Item Name/)).toBeNull();
        expect(screen.queryByText(/Review products/)).toBeNull();
    });
});
