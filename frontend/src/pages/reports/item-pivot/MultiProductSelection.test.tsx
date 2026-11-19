import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
import api from "@/api/axios";
import MultiProductSelection from "./MultiProductSelection";
import type { DetectedProduct, MatchSuggestion } from "./matchingShared";

const seg = (index: number, phrase: string, item: { item_id: number; name: string } | null, extra: Partial<DetectedProduct> = {}): DetectedProduct => ({
    index, phrase, normalized: phrase.toLowerCase(), hsn_code: "39201099", suggestion: item, confidence: item ? 100 : 0, band: item ? "HIGH" : "UNMATCHED",
    compatible: !!item, conflicts: [], checks: { sion: { ok: true, detail: "ok" } }, explanation: "Exact match", candidates: item ? [{ ...item, score: 100 }] : [],
    entitlement: null, approved: null, ...extra,
});
const suggestion = (segments: DetectedProduct[]): MatchSuggestion => ({
    source_key: "pp board ldpe|39201099|E5", kind: "UNMAPPED", description: "Polypropylene Board / LDPE film", aliases: [], hsn_code: "39201099", hsn_codes: [],
    sion: "E5", import_item_ids: [5], license_numbers: ["L1"], band: "CONFLICT", action: "", confidence: 0, suggestion: null, explanation: "", conflicts: ["lists 2 products"],
    checks: {}, candidates: [], history: [], segments,
});
const BOARD = { item_id: 1, name: "POLYPROPYLENE BOARD" };
const LDPE = { item_id: 2, name: "LDPE FILM" };

function setup(segments: DetectedProduct[] = [seg(0, "Polypropylene Board", BOARD), seg(1, "LDPE film", LDPE)], canApprove = true) {
    vi.mocked(api.get).mockResolvedValue({ data: { masters: [BOARD, LDPE, { item_id: 3, name: "PLASTIC FILM" }] } });
    vi.mocked(api.post).mockResolvedValue({ data: { results: [], created: [1], revoked: [] } });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MultiProductSelection suggestion={suggestion(segments)} filters={{ sion_norm: "E5" }} canApprove={canApprove} />
    </QueryClientProvider>);
    return userEvent.setup();
}
const approve = () => screen.getByRole("button", { name: /^Approve selected/ });
const body = () => (vi.mocked(api.post).mock.calls[vi.mocked(api.post).mock.calls.length - 1]?.[1] ?? {}) as { selections: unknown[]; partial?: boolean };

beforeEach(() => vi.clearAllMocks());

describe("Multi-product selection", () => {
    it("selects nothing by default, so nothing can be approved until products are ticked", () => {
        setup();
        expect(screen.getByLabelText("Select Polypropylene Board")).not.toBeChecked();
        expect(screen.getByLabelText("Select LDPE film")).not.toBeChecked();
        expect(approve()).toBeDisabled();
        expect(screen.getByRole("status", { name: "Selection summary" })).toHaveTextContent("Detected 2Selected 0Compatible 2Excluded 2Requiring review 0");
    });

    it("approves only the one selected product", async () => {
        const user = setup();
        await user.click(screen.getByLabelText("Select Polypropylene Board"));
        await user.click(approve());
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/decide-products/", { source_key: "pp board ldpe|39201099|E5", selections: [{ index: 0, item_id: 1 }], filters: { sion_norm: "E5" } }));
    });

    it("selects both, deselects one before approving, and can clear or select all compatible", async () => {
        const user = setup();
        await user.click(screen.getByRole("button", { name: "Select all compatible (2)" }));
        expect(screen.getByRole("status", { name: "Selection summary" })).toHaveTextContent("Selected 2");
        await user.click(screen.getByLabelText("Select LDPE film"));  // reviewer changes the selection before approval
        await user.click(approve());
        await waitFor(() => expect(body().selections).toEqual([{ index: 0, item_id: 1 }]));
        await user.click(screen.getByRole("button", { name: "Clear selection" }));
        expect(approve()).toBeDisabled();
    });

    it("changes one product's canonical master and adds a product manually", async () => {
        const user = setup();
        await screen.findAllByRole("option", { name: "PLASTIC FILM" });
        await user.selectOptions(screen.getByLabelText("Canonical product for LDPE film"), "3");
        expect(screen.getByText(/changed from LDPE FILM/)).toBeInTheDocument();
        await user.click(screen.getByLabelText("Select LDPE film"));
        await user.type(screen.getByLabelText("Add a product manually"), "Board lamination");
        await user.click(screen.getByRole("button", { name: "Add" }));
        expect(approve()).toBeDisabled();  // the manual row still needs a master
        await user.selectOptions(screen.getByLabelText("Canonical product for Board lamination"), "2");
        await user.click(approve());
        await waitFor(() => expect(body().selections).toEqual([{ index: 1, item_id: 3 }, { phrase: "Board lamination", item_id: 2 }]));
    });

    it("shows exact reasons for a rejected selection and offers approving only the compatible ones", async () => {
        const user = setup([seg(0, "Olive oil", { item_id: 9, name: "PALM KERNEL OIL" }, { band: "CONFLICT", compatible: false, conflicts: ["Entitlement profile requires OLIVE OIL"], entitlement: "OLIVE OIL" }), seg(1, "PKO", { item_id: 9, name: "PALM KERNEL OIL" }, { entitlement: "PALM KERNEL OIL" })]);
        vi.mocked(api.post).mockRejectedValueOnce({ response: { data: { detail: "1 selected product(s) failed validation — nothing was approved", results: [
            { index: 0, phrase: "Olive oil", item_id: 9, item: "PALM KERNEL OIL", ok: false, reasons: ["Entitlement profile requires OLIVE OIL for 'Olive oil', not PALM KERNEL OIL"] },
            { index: 1, phrase: "PKO", item_id: 9, item: "PALM KERNEL OIL", ok: true, reasons: [] }] } } });
        expect(screen.getByRole("status", { name: "Selection summary" })).toHaveTextContent("Compatible 1");
        await user.click(screen.getByLabelText("Select Olive oil"));
        await user.click(screen.getByLabelText("Select PKO"));
        await user.click(approve());
        const reasons = await screen.findByRole("list", { name: "Rejected: Olive oil" });
        expect(within(reasons).getByText(/requires OLIVE OIL/)).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Approve the 1 compatible only" }));
        await waitFor(() => expect(body().partial).toBe(true));
    });

    it("pre-selects only previously approved products and is read-only without permission", () => {
        setup([seg(0, "Polypropylene Board", BOARD, { approved: { item_id: 1, name: "POLYPROPYLENE BOARD", by: "mgr", on: "2026-11-19" } }), seg(1, "LDPE film", LDPE)], false);
        expect(screen.getByLabelText("Select Polypropylene Board")).toBeChecked();
        expect(screen.getByLabelText("Select LDPE film")).not.toBeChecked();
        expect(screen.getByLabelText("Select LDPE film")).toBeDisabled();
        expect(screen.queryByRole("button", { name: /^Approve selected/ })).toBeNull();
    });

    it("survives a refetch that changes the detected products", async () => {
        const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
        vi.mocked(api.get).mockResolvedValue({ data: { masters: [BOARD, LDPE] } });
        const view = (segments: DetectedProduct[]) => <QueryClientProvider client={client}><MultiProductSelection suggestion={suggestion(segments)} filters={{}} canApprove /></QueryClientProvider>;
        const { rerender } = render(view([seg(0, "Polypropylene Board", BOARD)]));
        rerender(view([seg(0, "Polypropylene Board", BOARD), seg(1, "LDPE film", LDPE), seg(2, "HDPE", null)]));
        expect(screen.getByLabelText("Select HDPE")).toBeInTheDocument();  // no crash, new product listed
    });

    it("blocks duplicate manual products and excludes unvalidated master changes from select-all", async () => {
        const user = setup();
        await screen.findAllByRole("option", { name: "PLASTIC FILM" });
        await user.type(screen.getByLabelText("Add a product manually"), "ldpe FILM");
        await user.click(screen.getByRole("button", { name: "Add" }));
        expect(screen.queryByLabelText("Select ldpe FILM")).toBeNull();
        await user.selectOptions(screen.getByLabelText("Canonical product for LDPE film"), "3");
        expect(screen.getByRole("button", { name: "Select all compatible (1)" })).toBeEnabled();
        await user.click(screen.getByRole("button", { name: "Select all compatible (1)" }));
        expect(screen.getByLabelText("Select LDPE film")).not.toBeChecked();
        expect(screen.getByText(/not yet validated/)).toBeInTheDocument();
    });

    it("removes an approved classification only through the explicit action", async () => {
        const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
        const user = setup([seg(0, "Polypropylene Board", BOARD, { approved: { item_id: 1, name: "POLYPROPYLENE BOARD", by: "mgr", on: "2026-11-19" } }), seg(1, "LDPE film", LDPE)]);
        expect(screen.queryByRole("button", { name: /Remove approved classification/ })).toBeNull();  // still selected
        await user.click(screen.getByLabelText("Select Polypropylene Board"));
        expect(approve()).toBeDisabled();
        await user.click(screen.getByRole("button", { name: "Remove approved classification (1)" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/decide-products/", expect.objectContaining({ selections: [], clear: true })));
        confirm.mockRestore();
    });

    it("filters the master selectors with the search box", async () => {
        const user = setup();
        await screen.findAllByRole("option", { name: "PLASTIC FILM" });
        await user.type(screen.getByLabelText("Search canonical masters"), "plastic");
        const select = screen.getByLabelText("Canonical product for Polypropylene Board");
        expect(within(select).getByRole("option", { name: "PLASTIC FILM" })).toBeInTheDocument();
        expect(within(select).queryByRole("option", { name: "LDPE FILM" })).toBeNull();
    });
});
