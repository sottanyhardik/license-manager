import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
import api from "@/api/axios";
import DescriptionMapping, { type DescriptionRow } from "./DescriptionMapping";

const row = (key: string, over: Partial<DescriptionRow> = {}): DescriptionRow => ({
    key, description: key, wordings: 1, records: 2, licence_count: 1, licence_numbers: ["0310000001"], hsn_codes: ["08021100"], sion: ["E126"],
    status: "MAPPING_REQUIRED", counts: { applied: 0, auto: 0, conflict: 0, stale: 0 }, conflicts: [], mapping: null, licences: [{ id: 7, license_number: "0310000001" }], ...over,
});
const MASTERS = [{ item_id: 5, name: "PKO" }, { item_id: 6, name: "OLIVE OIL" }];
const page1 = Array.from({ length: 50 }, (_, n) => row(`DESC ${String(n).padStart(2, "0")}`));
const page2 = [row("DESC 50"), row("DESC 51")];
let bulkResult = { succeeded: [{ key: "DESC 00", description: "DESC 00", action: "CREATE", applied: 2 }], skipped: [], failed: [] as { key: string; description: string; reason: string }[], descriptions: 1, records: 2 };

function setup() {
    vi.mocked(api.get).mockImplementation(async (url: string, cfg?: { params?: Record<string, unknown> }) => {
        if (url.includes("matching/masters")) return { data: { masters: MASTERS } };
        const rows = Number(cfg?.params?.offset ?? 0) >= 50 ? page2 : page1;
        return { data: { rows, total: 52, total_records: 104, summary: { MAPPING_REQUIRED: 52 }, offset: cfg?.params?.offset ?? 0, limit: 50, can_apply: true } };
    });
    vi.mocked(api.post).mockImplementation(async (url: string, body?: unknown) => {
        if (url.endsWith("bulk/preview/")) {
            const b = body as { mode: string; keys?: string[] };
            const n = b.mode === "keys" ? b.keys!.length : 52;
            return { data: { descriptions: n, records: n * 2, licence_count: 2, licences: [{ id: 7, license_number: "0310000001" }, { id: 9, license_number: "0310000002" }],
                licences_truncated: false, fingerprint: "fp-1", sample: [], missing: [], limit: 150, too_many: false } };
        }
        return { data: bulkResult };
    });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><DescriptionMapping /></MemoryRouter></QueryClientProvider>);
    return userEvent.setup();
}
const lastGetParams = () => {
    const calls = vi.mocked(api.get).mock.calls.filter(([u]) => String(u).endsWith("import/descriptions/"));
    return (calls[calls.length - 1]?.[1] as { params: Record<string, unknown> }).params;
};

beforeEach(() => { vi.clearAllMocks(); bulkResult = { ...bulkResult, failed: [] }; });

describe("Description mapping — filter conditions and bulk update", () => {
    it("builds nested ALL / ANY groups like Licence Planning (Example A) and sends the tree", async () => {
        const user = setup();
        await screen.findByRole("table", { name: "Licence import item descriptions" });
        await user.click(screen.getByRole("button", { name: /Filter Conditions/ }));
        await user.selectOptions(screen.getByLabelText("Root filter group logic"), "OR");
        await user.click(screen.getByRole("button", { name: "Add group to Root filter group" }));
        await user.click(screen.getByRole("button", { name: "Add group to Root filter group" }));
        // group 1: Description contains DIETARY AND HSN starts with 0802
        await user.type(screen.getByLabelText("Condition 1.1 value"), "DIETARY");
        await user.click(screen.getByRole("button", { name: "Add condition to Filter group 1" }));
        await user.selectOptions(screen.getByLabelText("Condition 1.2 field"), "hsn");
        await user.selectOptions(screen.getByLabelText("Condition 1.2 operator"), "starts_with");
        await user.type(screen.getByLabelText("Condition 1.2 value"), "0802");
        // group 2: Description contains NUTS AND SION equals E1
        await user.type(screen.getByLabelText("Condition 2.1 value"), "NUTS");
        await user.click(screen.getByRole("button", { name: "Add condition to Filter group 2" }));
        await user.selectOptions(screen.getByLabelText("Condition 2.2 field"), "sion");
        await user.selectOptions(screen.getByLabelText("Condition 2.2 operator"), "equals");
        await user.type(screen.getByLabelText("Condition 2.2 value"), "E1");
        await user.click(screen.getByRole("button", { name: "Apply Filters" }));
        await waitFor(() => expect(JSON.parse(String(lastGetParams().filters))).toEqual({ operator: "OR", conditions: [
            { operator: "AND", conditions: [{ field: "description", op: "contains", value: "DIETARY" }, { field: "hsn", op: "starts_with", value: "0802" }] },
            { operator: "AND", conditions: [{ field: "description", op: "contains", value: "NUTS" }, { field: "sion", op: "equals", value: "E1" }] }] }));
        await user.click(screen.getByRole("button", { name: "Clear Filters" }));
        await waitFor(() => expect(lastGetParams().filters).toBeUndefined());
    });

    it("nested group: three levels, independent logic, edit + remove, populated group asks before removal", async () => {
        const user = setup();
        await screen.findByRole("table", { name: "Licence import item descriptions" });
        await user.click(screen.getByRole("button", { name: /Filter Conditions/ }));
        await user.click(screen.getByRole("button", { name: "Add condition to Root filter group" }));
        await user.type(screen.getByLabelText("Condition 1 value"), "PALM");
        await user.click(screen.getByRole("button", { name: "Add group to Root filter group" }));
        await user.selectOptions(screen.getByLabelText("Filter group 2 logic"), "OR");
        await user.selectOptions(screen.getByLabelText("Condition 2.1 operator"), "not_contains");
        await user.type(screen.getByLabelText("Condition 2.1 value"), "CRUDE");
        await user.click(screen.getByRole("button", { name: "Add group to Filter group 2" }));
        await user.selectOptions(screen.getByLabelText("Condition 2.2.1 operator"), "starts_with");
        await user.type(screen.getByLabelText("Condition 2.2.1 value"), "REFINED");
        await user.click(screen.getByRole("button", { name: "Add condition to Filter group 2.2" }));
        await user.selectOptions(screen.getByLabelText("Condition 2.2.2 field"), "sion");
        await user.selectOptions(screen.getByLabelText("Condition 2.2.2 operator"), "not_empty");
        expect(screen.queryByLabelText("Condition 2.2.2 value")).toBeNull(); // Is Not Empty needs no value
        await user.click(screen.getByRole("button", { name: "Remove Condition 2.2.2" }));
        await user.click(screen.getByRole("button", { name: "Apply Filters" }));
        await waitFor(() => expect(JSON.parse(String(lastGetParams().filters))).toEqual({ operator: "AND", conditions: [
            { field: "description", op: "contains", value: "PALM" },
            { operator: "OR", conditions: [{ field: "description", op: "not_contains", value: "CRUDE" },
                { operator: "AND", conditions: [{ field: "description", op: "starts_with", value: "REFINED" }] }] }] }));
        await user.click(screen.getByRole("button", { name: "Remove Filter group 2" }));
        const dialog = await screen.findByRole("alertdialog");
        expect(dialog).toHaveTextContent("Remove populated group?");
        await user.click(within(dialog).getByRole("button", { name: "Remove Group" }));
        expect(screen.queryByRole("group", { name: "Filter group 2" })).toBeNull();
        expect(screen.getByText(/Unapplied changes/)).toBeInTheDocument();
    });

    it("Apply is blocked while any nested condition lacks a value", async () => {
        const user = setup();
        await screen.findByRole("table", { name: "Licence import item descriptions" });
        await user.click(screen.getByRole("button", { name: /Filter Conditions/ }));
        await user.click(screen.getByRole("button", { name: "Add group to Root filter group" }));
        expect(screen.getByRole("button", { name: "Apply Filters" })).toBeDisabled();
        await user.selectOptions(screen.getByLabelText("Condition 1.1 field"), "sion");
        await user.selectOptions(screen.getByLabelText("Condition 1.1 operator"), "empty");
        expect(screen.getByRole("button", { name: "Apply Filters" })).toBeEnabled();
    });

    it("rows show record + licence counts with licence chips linking to the licence page by id; +N more expands", async () => {
        setup();
        const table = await screen.findByRole("table", { name: "Licence import item descriptions" });
        const tr = within(table).getByText("DESC 00").closest("tr") as HTMLElement;
        expect(within(tr).getByText("2 records · 1 licence")).toBeInTheDocument();
        expect(within(tr).getByRole("link", { name: "0310000001" })).toHaveAttribute("href", "/licenses/7/overview");
    });

    it("individual selection survives pagination; bulk confirms counts, Item Names and REPLACE, then posts the fingerprint", async () => {
        const user = setup();
        const table = await screen.findByRole("table", { name: "Licence import item descriptions" });
        await user.click(within(table).getByLabelText("Select DESC 00"));
        await user.click(screen.getByRole("button", { name: /Next/ }));
        await user.click(within(await screen.findByRole("table", { name: "Licence import item descriptions" })).getByLabelText("Select DESC 51"));
        expect(screen.getByText("2 description(s) selected")).toBeInTheDocument();
        await user.selectOptions(await screen.findByLabelText("Add Item Name for bulk update"), "5");
        await user.click(screen.getByRole("button", { name: "Apply Bulk Update" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith(expect.stringMatching(/bulk\/preview\/$/), { mode: "keys", keys: ["DESC 00", "DESC 51"] }));
        const dialog = await screen.findByRole("alertdialog");
        expect(dialog).toHaveTextContent("2 unique description(s) · 4 existing licence import record(s)");
        expect(dialog).toHaveTextContent("Item Names: PKO");
        expect(dialog).toHaveTextContent("REPLACE");
        expect(dialog).toHaveTextContent("2 distinct licence(s)");
        expect(within(dialog).getByRole("link", { name: "0310000002" })).toHaveAttribute("href", "/licenses/9/overview");
        await user.click(within(dialog).getByRole("button", { name: "Update 2 description(s)" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith(expect.stringMatching(/bulk\/apply\/$/),
            { mode: "keys", keys: ["DESC 00", "DESC 51"], fingerprint: "fp-1", item_ids: [5] }));
        expect(await screen.findByText(/Bulk update finished/)).toBeInTheDocument();
    });

    it("Select All Matching targets the table's current criteria; changing them clears the selection", async () => {
        const user = setup();
        await screen.findByRole("table", { name: "Licence import item descriptions" });
        await user.click(screen.getByRole("button", { name: "Select All Matching" }));
        expect(screen.getByText("52 description(s) selected (all matching)")).toBeInTheDocument();
        await user.selectOptions(await screen.findByLabelText("Add Item Name for bulk update"), "6");
        await user.click(screen.getByRole("button", { name: "Apply Bulk Update" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith(expect.stringMatching(/bulk\/preview\/$/),
            { mode: "filter", filters: { operator: "AND", conditions: [] }, status: "MAPPING_REQUIRED", q: "" }));
        await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Cancel" }));
        await user.selectOptions(screen.getByLabelText("Filter by status"), "");
        expect(screen.queryByText(/description\(s\) selected/)).toBeNull(); // a different set → selection cleared
    });

    it("reports failed descriptions and retries only those", async () => {
        bulkResult = { ...bulkResult, failed: [{ key: "DESC 01", description: "DESC 01", reason: "Choose existing, active Item Names" }] };
        const user = setup();
        const table = await screen.findByRole("table", { name: "Licence import item descriptions" });
        await user.click(within(table).getByLabelText("Select DESC 00"));
        await user.click(within(table).getByLabelText("Select DESC 01"));
        await user.selectOptions(await screen.findByLabelText("Add Item Name for bulk update"), "5");
        await user.click(screen.getByRole("button", { name: "Apply Bulk Update" }));
        await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: /Update 2/ }));
        expect(await screen.findByText(/DESC 01: Choose existing, active Item Names/)).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Retry failed" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith(expect.stringMatching(/bulk\/preview\/$/), { mode: "keys", keys: ["DESC 01"] }));
    });

    it("bulk Item Names are cleared after an apply and never pre-filled for the next selection", async () => {
        const user = setup();
        const table = await screen.findByRole("table", { name: "Licence import item descriptions" });
        await user.click(within(table).getByLabelText("Select DESC 00"));
        await user.selectOptions(await screen.findByLabelText("Add Item Name for bulk update"), "5");
        await user.click(screen.getByRole("button", { name: "Apply Bulk Update" }));
        await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: /Update 1/ }));
        expect(await screen.findByRole("status", { name: "Bulk update result" })).toHaveTextContent("PKO, REPLACE");
        await user.click(within(table).getByLabelText("Select DESC 02"));
        expect(screen.queryByRole("list", { name: /Selected Item Names for bulk update/ })).toBeNull();
        expect(screen.getByRole("button", { name: "Apply Bulk Update" })).toBeDisabled();
    });

    it("select-page checkbox selects the visible rows", async () => {
        const user = setup();
        await screen.findByRole("table", { name: "Licence import item descriptions" });
        await user.click(screen.getByLabelText("Select this page"));
        expect(screen.getByText("50 description(s) selected")).toBeInTheDocument();
    });

    it("removing a sibling group keeps the other groups' collapsed state (stable keys)", async () => {
        const user = setup();
        await screen.findByRole("table", { name: "Licence import item descriptions" });
        await user.click(screen.getByRole("button", { name: /Filter Conditions/ }));
        for (let n = 0; n < 3; n++) await user.click(screen.getByRole("button", { name: "Add group to Root filter group" }));
        await user.type(screen.getByLabelText("Condition 3.1 value"), "THIRD");
        await user.click(screen.getByRole("button", { name: "Collapse Filter group 3" }));
        await user.click(screen.getByRole("button", { name: "Remove Filter group 2" }));
        await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Remove Group" }));
        // the former group 3 is now group 2 — still collapsed, its condition intact
        expect(screen.getByRole("button", { name: "Expand Filter group 2" })).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Expand Filter group 2" }));
        expect(screen.getByLabelText("Condition 2.1 value")).toHaveValue("THIRD");
    });
});

