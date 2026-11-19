import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
import api from "@/api/axios";
import ProductMatchingView, { type MatchSuggestion } from "./ProductMatchingView";

const row = (key: string, band: MatchSuggestion["band"], extra: Partial<MatchSuggestion> = {}): MatchSuggestion => ({
    source_key: key, kind: "UNMAPPED", description: `${key} description`, aliases: [], hsn_code: "39206991", hsn_codes: ["39206991"], sion: "E5",
    import_item_ids: [1, 2], license_numbers: ["0310000001"], band, action: "", confidence: band === "HIGH" ? 100 : 82, matcher: "deterministic-v1",
    suggestion: { item_id: 7, name: "ALUMINIUM FOIL" }, explanation: "Exact match", conflicts: band === "CONFLICT" ? ["Description lists 2 products"] : [],
    checks: { entitlement: { ok: true, detail: "No entitlement-profile alias" } }, candidates: [{ item_id: 7, name: "ALUMINIUM FOIL", score: 100 }, { item_id: 9, name: "PP", score: 60 }],
    semantic: { model_version: "minilm", similarity: 0.81, candidates: [{ item_id: 11, name: "HDPE", similarity: 0.7 }] }, history: [], ...extra,
});
const payload = (canApprove = true) => ({
    matcher: "deterministic", can_approve: canApprove, summary: { HIGH: 1, REVIEW: 1, CONFLICT: 1 }, latest_job: null, decisions: [],
    suggestions: [row("alu", "HIGH"), row("cane", "REVIEW"), row("mixed", "CONFLICT")],
});

function setup(canApprove = true) {
    vi.mocked(api.get).mockImplementation(async (url: string) => url.startsWith("item-pivot/matching/health")
        ? { data: { model: { ok: true, variant: "arm64" }, worker: { ok: false }, available_memory_mb: null } }
        : { data: payload(canApprove) });
    vi.mocked(api.post).mockResolvedValue({ data: {} });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><ProductMatchingView query="sion_norm=E5" /></QueryClientProvider>);
    return userEvent.setup();
}

describe("ProductMatchingView", () => {
    beforeEach(() => vi.clearAllMocks());

    it("shows bands, engine health and allows bulk selection only for HIGH matches", async () => {
        setup();
        const table = await screen.findByRole("table", { name: "Product matches" });
        expect(within(table).getAllByRole("checkbox")).toHaveLength(1);
        expect(screen.getByText("No matching worker")).toBeInTheDocument();
        expect(screen.getByText("Model arm64")).toBeInTheDocument();
    });

    it("approves a different candidate with the audited decision endpoint", async () => {
        const user = setup();
        await screen.findByRole("table", { name: "Product matches" });
        await user.click(screen.getByRole("button", { name: /cane description/ }));
        await user.click(screen.getByLabelText(/HDPE/));
        await user.click(screen.getByRole("button", { name: "Approve selected product" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/decide/", { source_keys: ["cane"], decision: "APPROVED", item_id: 11, filters: { sion_norm: "E5" } }));
    });

    it("shows conflicts and keeps read-only users from deciding or starting jobs", async () => {
        const user = setup(false);
        await screen.findByRole("table", { name: "Product matches" });
        await user.click(screen.getByRole("button", { name: /mixed description/ }));
        expect(screen.getByRole("alert")).toHaveTextContent("Description lists 2 products");
        expect(screen.queryByRole("button", { name: /Approve/ })).toBeNull();
        expect(screen.queryByRole("button", { name: /Run semantic classification/ })).toBeNull();
    });

    it("starts a background classification job with the current filters", async () => {
        const user = setup();
        await user.click(await screen.findByRole("button", { name: /Run semantic classification/ }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/jobs/", { filters: { sion_norm: "E5" }, batch_size: 4 }));
    });

    it("never bulk-approves selected rows that a filter has hidden", async () => {
        const user = setup();
        const table = await screen.findByRole("table", { name: "Product matches" });
        await user.click(within(table).getByLabelText("Select alu description"));
        expect(screen.getByRole("button", { name: "Approve selected (1)" })).toBeEnabled();
        await user.type(screen.getByLabelText("Search matches"), "cane");
        expect(screen.getByRole("button", { name: "Approve selected (0)" })).toBeDisabled();
        expect(api.post).not.toHaveBeenCalled();
    });

    it("requires confirmation before replacing the links of an ambiguous record", async () => {
        vi.mocked(api.get).mockImplementation(async (url: string) => url.startsWith("item-pivot/matching/health")
            ? { data: { model: { ok: true }, worker: { ok: true }, available_memory_mb: null } }
            : { data: { ...payload(), suggestions: [row("amb", "REVIEW", { kind: "AMBIGUOUS" })] } });
        vi.mocked(api.post).mockResolvedValue({ data: {} });
        const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
        render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ProductMatchingView query="sion_norm=E5" /></QueryClientProvider>);
        const user = userEvent.setup();
        await user.click(await screen.findByRole("button", { name: /amb description/ }));
        await user.click(screen.getByRole("button", { name: "Approve" }));
        expect(api.post).not.toHaveBeenCalled();  // declined
        await user.click(screen.getByRole("button", { name: "Approve" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/decide/", expect.objectContaining({ source_keys: ["amb"], replace_links: true })));
        confirm.mockRestore();
    });
});
