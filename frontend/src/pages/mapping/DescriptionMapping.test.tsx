import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
import api from "@/api/axios";
import DescriptionMapping, { type DescriptionRow } from "./DescriptionMapping";

const row = (over: Partial<DescriptionRow>): DescriptionRow => ({
    key: "K", description: "D", wordings: 1, records: 3, licence_count: 2, licence_numbers: ["0310000001"], hsn_codes: ["15131900"], sion: ["E126"],
    status: "MAPPING_REQUIRED", counts: { applied: 0, auto: 0, conflict: 0, stale: 0 }, conflicts: [], mapping: null, licences: [{ id: 1, license_number: "0310000001" }], ...over,
});
const MASTERS = [{ item_id: 5, name: "PKO" }, { item_id: 6, name: "OLIVE OIL" }, { item_id: 7, name: "RBD PALMOLEIN OIL" }];
let rows: DescriptionRow[] = [];

function setup(canApply = true) {
    vi.mocked(api.get).mockImplementation(async (url: string) => url.includes("matching/masters")
        ? { data: { masters: MASTERS } }
        : { data: { rows, total: rows.length, total_records: rows.reduce((n, r) => n + r.records, 0), summary: { MAPPING_REQUIRED: 1 }, offset: 0, limit: 50, can_apply: canApply } });
    vi.mocked(api.post).mockResolvedValue({ data: { action: "CREATE", applied: 3, unchanged: 0, conflicts: 0, mapping: { id: 1, version: 1, items: [] } } });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><DescriptionMapping /></MemoryRouter></QueryClientProvider>);
    return userEvent.setup();
}
const tableRow = async (text: string) =>
    within(await screen.findByRole("table", { name: "Licence import item descriptions" })).getByText(text).closest("tr") as HTMLElement;

beforeEach(() => { vi.clearAllMocks(); rows = []; });

describe("Licence import description mapping (map once)", () => {
    it("shows exactly the six columns and starts empty for a new description", async () => {
        rows = [row({ key: "RELEVANT FATS", description: "RELEVANT FATS AND OILS NAMELY SESAME OIL / OLIVE OIL / PALM BASED OIL" })];
        setup();
        const table = await screen.findByRole("table", { name: "Licence import item descriptions" });
        expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(
            ["", "Original Item Description", "HSN", "SION", "Select Item Name", "Status", "Action"]); // row-selection checkbox + the six business columns
        const tr = (await tableRow("RELEVANT FATS AND OILS NAMELY SESAME OIL / OLIVE OIL / PALM BASED OIL"));
        expect(within(tr).queryByRole("list", { name: /Selected Item Names/ })).toBeNull(); // no chips
        expect(within(tr).getByText("Mapping Required")).toBeInTheDocument();
        expect(within(tr).getByRole("button", { name: /Save mapping/ })).toBeDisabled();
    });

    it("selects several Item Names as removable chips and saves them once for the description", async () => {
        rows = [row({ key: "RELEVANT FATS", description: "RELEVANT FATS AND OILS" })];
        const user = setup();
        const tr = (await tableRow("RELEVANT FATS AND OILS"));
        await within(tr).findAllByRole("option", { name: "PKO" });
        const add = within(tr).getByLabelText("Add Item Name for RELEVANT FATS AND OILS");
        await user.selectOptions(add, "6");
        await user.selectOptions(add, "5");
        await user.selectOptions(add, "7");
        await user.click(within(tr).getByRole("button", { name: "Remove RBD PALMOLEIN OIL from RELEVANT FATS AND OILS" }));
        expect(within(within(tr).getByRole("list", { name: /Selected Item Names/ })).getAllByRole("listitem").map((l) => l.textContent)).toEqual(["OLIVE OIL", "PKO"]);
        expect(within(tr).getByText("Ready to save")).toBeInTheDocument();
        await user.click(within(tr).getByRole("button", { name: "Save mapping for RELEVANT FATS AND OILS" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/item-name-mapping/import/descriptions/save/",
            { description: "RELEVANT FATS AND OILS", item_ids: [6, 5] }));
    });

    it("an applied mapping shows its Item Names; editing sends a REPLACE with the expected version", async () => {
        rows = [row({ key: "PALM KERNEL OIL", description: "PALM KERNEL OIL", status: "APPLIED", counts: { applied: 2, auto: 1, conflict: 0, stale: 0 },
            mapping: { id: 9, version: 3, items: [{ item_id: 5, name: "PKO" }] } })];
        const user = setup();
        const tr = (await tableRow("PALM KERNEL OIL"));
        expect(within(tr).getByText("Applied")).toBeInTheDocument();
        expect(within(tr).getByText(/1 mapped automatically/)).toBeInTheDocument();
        expect(within(tr).getByRole("button", { name: /Save mapping/ })).toBeDisabled(); // unchanged
        await within(tr).findAllByRole("option", { name: "OLIVE OIL" });
        await user.selectOptions(within(tr).getByLabelText("Add Item Name for PALM KERNEL OIL"), "6");
        await user.click(within(tr).getByRole("button", { name: "Save mapping for PALM KERNEL OIL" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/item-name-mapping/import/descriptions/save/",
            { description: "PALM KERNEL OIL", item_ids: [5, 6], expected_version: 3 }));
    });

    it("keeps the selection and shows the server error when saving fails", async () => {
        rows = [row({ key: "X", description: "X OIL" })];
        const user = setup();
        vi.mocked(api.post).mockRejectedValueOnce({ response: { data: { detail: "Choose existing, active Item Names" } } });
        const tr = (await tableRow("X OIL"));
        await within(tr).findAllByRole("option", { name: "PKO" });
        await user.selectOptions(within(tr).getByLabelText("Add Item Name for X OIL"), "5");
        await user.click(within(tr).getByRole("button", { name: "Save mapping for X OIL" }));
        expect(await within(tr).findByRole("alert")).toHaveTextContent("Choose existing, active Item Names");
        expect(within(tr).getByRole("list", { name: /Selected Item Names/ })).toHaveTextContent("PKO");
    });

    it("conflicts are shown; partially applied mappings offer Retry; viewers cannot edit", async () => {
        rows = [
            row({ key: "C", description: "CONFLICTING OIL", status: "CONFLICT", conflicts: ["PKO not legitimate for licence SION E5"], mapping: { id: 1, version: 1, items: [{ item_id: 5, name: "PKO" }] } }),
            row({ key: "P", description: "PARTIAL OIL", status: "PARTIAL", counts: { applied: 1, auto: 0, conflict: 0, stale: 1 }, mapping: { id: 2, version: 1, items: [{ item_id: 5, name: "PKO" }] } }),
        ];
        const user = setup();
        expect(within((await tableRow("CONFLICTING OIL"))).getByText("PKO not legitimate for licence SION E5")).toBeInTheDocument();
        await user.click(within((await tableRow("PARTIAL OIL"))).getByRole("button", { name: "Retry applying PARTIAL OIL" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/item-name-mapping/import/descriptions/2/reapply/", {}));
    });

    it("read-only users see the mapping but no editing or Save", async () => {
        rows = [row({ key: "R", description: "READ OIL", status: "APPLIED", mapping: { id: 3, version: 1, items: [{ item_id: 5, name: "PKO" }] } })];
        setup(false);
        const tr = (await tableRow("READ OIL"));
        expect(within(tr).getByText("PKO")).toBeInTheDocument();
        expect(within(tr).queryByRole("button")).toBeNull();
        expect(within(tr).queryByLabelText(/Add Item Name/)).toBeNull();
    });

    it("drops an unsaved edit when someone else saves a newer version first", async () => {
        rows = [row({ key: "S", description: "SHARED OIL", status: "APPLIED", mapping: { id: 4, version: 1, items: [{ item_id: 5, name: "PKO" }] } })];
        const user = setup();
        let tr = await tableRow("SHARED OIL");
        await within(tr).findAllByRole("option", { name: "OLIVE OIL" });
        await user.selectOptions(within(tr).getByLabelText("Add Item Name for SHARED OIL"), "6");
        expect(within(tr).getByText("Ready to save")).toBeInTheDocument();
        rows = [row({ key: "S", description: "SHARED OIL", status: "APPLIED", mapping: { id: 4, version: 2, items: [{ item_id: 7, name: "RBD PALMOLEIN OIL" }] } })];
        await user.selectOptions(screen.getByLabelText("Filter by status"), ""); // refetch → peer's version 2
        await waitFor(async () => expect(within(await tableRow("SHARED OIL")).getByText("RBD PALMOLEIN OIL")).toBeInTheDocument());
        tr = await tableRow("SHARED OIL");
        expect(within(tr).queryByText("Ready to save")).toBeNull();
        expect(within(tr).getByRole("button", { name: /Save mapping/ })).toBeDisabled();
    });
});

