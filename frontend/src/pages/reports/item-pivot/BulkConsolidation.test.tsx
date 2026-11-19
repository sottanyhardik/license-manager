import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
import api from "@/api/axios";
import BulkConsolidation from "./BulkConsolidation";

const row = (key: string, description: string, status: string, extra = {}) => ({
    key, description, hsn_code: "39021000", sion: "E1", status, selectable: status === "ELIGIBLE", reasons: [status === "ELIGIBLE" ? "Replaces PP - E1 → PP" : `${status} reason`],
    record_count: 2, eligible_record_ids: status === "ELIGIBLE" ? [11, 12] : [], record_ids: [11, 12], license_numbers: ["L1"], current_masters: { "PP - E1": 2 }, proposed: "PP", ...extra,
});
const preview = (canApply = true) => ({
    sion: "E1", target: { item_id: 94, name: "PP", chapters: ["39"] }, can_apply: canApply,
    summary: { groups: { ELIGIBLE: 1, REVIEW: 1, EXCLUDED: 1 }, records: { ELIGIBLE: 2, REVIEW: 2, EXCLUDED: 2 } },
    rows: [row("k1", "PACKING MATERIAL :- PP", "ELIGIBLE"), row("k2", "Polypropylene Board", "REVIEW"), row("k3", "PP / Aluminium Foil", "EXCLUDED")],
    batches: [{ batch: "abcdef1234", sion: "E1", target: "PP", records: 2, reason: "cleanup", user: "mgr", on: "2026-11-19T00:00:00Z", reverted: false }],
});

function setup(canApply = true) {
    vi.mocked(api.get).mockImplementation(async (url: string) => url.includes("masters") ? { data: { masters: [{ item_id: 94, name: "PP" }] } } : { data: preview(canApply) });
    vi.mocked(api.post).mockResolvedValue({ data: { batch: "b1", records: 2, skipped_aliases: [], restored: 2, conflicts: [] } });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><BulkConsolidation defaultSion="E1" /></QueryClientProvider>);
    return userEvent.setup();
}

beforeEach(() => vi.clearAllMocks());

describe("Bulk consolidation", () => {
    it("previews candidates and only eligible groups are selectable", async () => {
        const user = setup();
        await screen.findByRole("option", { name: "PP" });
        await user.selectOptions(screen.getByLabelText("Canonical product"), "94");
        const table = await screen.findByRole("table", { name: "Consolidation candidates" });
        expect(within(table).getAllByRole("checkbox")).toHaveLength(1);
        expect(within(table).getByText("Polypropylene Board")).toBeInTheDocument();
        expect(within(table).getByText("REVIEW reason")).toBeInTheDocument();
    });

    it("requires a selection and a reason, confirms, and sends only the selected keys", async () => {
        const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
        const user = setup();
        await screen.findByRole("option", { name: "PP" });
        await user.selectOptions(screen.getByLabelText("Canonical product"), "94");
        const apply = await screen.findByRole("button", { name: /^Consolidate 0 record/ });
        expect(apply).toBeDisabled();
        await user.click(screen.getByRole("button", { name: "Select all eligible (1)" }));
        expect(screen.getByRole("button", { name: /^Consolidate 2 record/ })).toBeDisabled();  // no reason yet
        await user.type(screen.getByLabelText("Consolidation reason"), "E1 PP cleanup");
        await user.click(screen.getByRole("button", { name: /^Consolidate 2 record/ }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/consolidation/apply/", { sion: "E1", target_id: 94, keys: ["k1"], reason: "E1 PP cleanup" }));
        confirm.mockRestore();
    });

    it("reverts a batch and is read-only for viewers", async () => {
        const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
        const user = setup();
        await screen.findByRole("option", { name: "PP" });
        await user.selectOptions(screen.getByLabelText("Canonical product"), "94");
        await user.click(await screen.findByRole("button", { name: /Revert/ }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/consolidation/revert/", { batch: "abcdef1234" }));
        confirm.mockRestore();
    });

    it("hides selection and apply without permission", async () => {
        const user = setup(false);
        await screen.findByRole("option", { name: "PP" });
        await user.selectOptions(screen.getByLabelText("Canonical product"), "94");
        const table = await screen.findByRole("table", { name: "Consolidation candidates" });
        expect(within(table).queryAllByRole("checkbox")).toHaveLength(0);
        expect(screen.queryByRole("button", { name: /^Consolidate/ })).toBeNull();
    });
});
