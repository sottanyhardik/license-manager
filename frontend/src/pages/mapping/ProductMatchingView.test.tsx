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
    suggestion: { item_id: 7, name: "ALUMINIUM FOIL" }, explanation: "Exact match", conflicts: band === "CONFLICT" ? ["HSN chapter 48 differs"] : [],
    checks: {}, candidates: [{ item_id: 7, name: "ALUMINIUM FOIL", score: 100 }, { item_id: 9, name: "PP", score: 60 }],
    semantic: { model_version: "minilm", similarity: 0.81, candidates: [{ item_id: 11, name: "HDPE", similarity: 0.7 }] }, history: [], ...extra,
});

function setup(suggestions: MatchSuggestion[], canApprove = true) {
    vi.mocked(api.get).mockImplementation(async (url: string) => url.startsWith("item-pivot/matching/masters")
        ? { data: { masters: [{ item_id: 7, name: "ALUMINIUM FOIL" }, { item_id: 9, name: "PP" }, { item_id: 11, name: "HDPE" }] } }
        : { data: { matcher: "deterministic", can_approve: canApprove, summary: {}, latest_job: null, decisions: [], suggestions } });
    vi.mocked(api.post).mockResolvedValue({ data: { recorded: [1] } });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ProductMatchingView query="sion_norm=E5" /></QueryClientProvider>);
    return userEvent.setup();
}

const tableOf = () => screen.findByRole("table", { name: "Pending licence import item mappings" });
const rowOf = (table: HTMLElement, text: string) => within(table).getByText(text).closest("tr") as HTMLElement;

beforeEach(() => vi.clearAllMocks());

describe("Licence Import Item mapping (simple table)", () => {
    it("shows the suggestion as a reference only — selector empty, Approve disabled, status Pending", async () => {
        setup([row("alu", "HIGH")]);
        const tr = rowOf(await tableOf(), "alu description");
        expect(within(tr).getByText("ALUMINIUM FOIL", { selector: "span" })).toBeInTheDocument();
        expect(within(tr).getByText(/Suggestion only/)).toBeInTheDocument();
        expect((within(tr).getByLabelText("Item Name for alu description") as HTMLSelectElement).value).toBe("");
        expect(within(tr).getByRole("button", { name: "Approve alu description" })).toBeDisabled();
        expect(within(tr).getByText("Pending")).toBeInTheDocument();
        expect(screen.queryByText(/Run semantic classification/)).toBeNull(); // engine / band dashboards removed
    });

    it("approves only the explicitly selected Item Name id", async () => {
        const user = setup([row("cane", "REVIEW")]);
        const tr = rowOf(await tableOf(), "cane description");
        await within(tr).findAllByRole("option", { name: "HDPE" });
        await user.selectOptions(within(tr).getByLabelText("Item Name for cane description"), "11");
        expect(within(tr).getByText("Ready to approve")).toBeInTheDocument();
        await user.click(within(tr).getByRole("button", { name: "Approve cane description" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/decide/", { source_keys: ["cane"], decision: "APPROVED", item_id: 11, filters: { sion_norm: "E5" } }));
    });

    it("has exactly the seven spec columns and no row checkboxes", async () => {
        setup([row("alu", "HIGH")]);
        const table = await tableOf();
        expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(
            ["Original Item Description", "HSN", "SION", "Suggested Item Name", "Select Item Name", "Status", "Action"]);
        expect(within(table).queryByRole("checkbox")).toBeNull();
    });

    it("bulk approves only rows with their own selection, names the rows that stay pending, and removes approved rows at once", async () => {
        const user = setup([row("a", "HIGH"), row("b", "HIGH", { suggestion: { item_id: 9, name: "PP" } }), row("c", "REVIEW")]);
        const table = await tableOf();
        await within(table).findAllByRole("option", { name: "HDPE" });
        expect(screen.queryByRole("button", { name: /ready rows/ })).toBeNull(); // suggestions never count
        await user.selectOptions(within(table).getByLabelText("Item Name for a description"), "7");
        expect(screen.queryByRole("button", { name: /ready rows/ })).toBeNull(); // one ready row → its own Approve button
        await user.selectOptions(within(table).getByLabelText("Item Name for c description"), "9");
        await user.click(screen.getByRole("button", { name: "Approve 2 ready rows" }));
        const dialog = await screen.findByRole("alertdialog");
        expect(dialog).toHaveTextContent("a description → ALUMINIUM FOIL");
        expect(dialog).toHaveTextContent("c description → PP");
        expect(dialog).toHaveTextContent("1 other row(s) on this page have no Item Name selected");
        expect(api.post).not.toHaveBeenCalled();
        // Hold the post-approval refetch open: the rows must leave Pending immediately, not only after fresh data.
        const get = vi.mocked(api.get).getMockImplementation()!;
        vi.mocked(api.get).mockImplementation((url: string, ...rest: unknown[]) => url.startsWith("item-pivot/matching/?") ? new Promise(() => {}) : get(url, ...rest as []));
        await user.click(within(dialog).getByRole("button", { name: "Approve" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/decide/", { source_keys: ["a", "c"], decision: "APPROVED", item_ids: { a: 7, c: 9 }, filters: { sion_norm: "E5" } }));
        await waitFor(() => expect(within(table).queryByText("a description")).toBeNull());
        expect(within(table).queryByText("c description")).toBeNull();
        expect(within(table).getByText("b description")).toBeInTheDocument(); // b stays Pending
    });

    it("keeps a failed approval pending and shows the server reason", async () => {
        const user = setup([row("cane", "REVIEW")]);
        vi.mocked(api.post).mockRejectedValueOnce({ response: { data: { detail: "HDPE is not a legitimate item for E5" } } });
        const tr = rowOf(await tableOf(), "cane description");
        await within(tr).findAllByRole("option", { name: "HDPE" });
        await user.selectOptions(within(tr).getByLabelText("Item Name for cane description"), "11");
        await user.click(within(tr).getByRole("button", { name: "Approve cane description" }));
        expect(await within(tr).findByRole("alert")).toHaveTextContent("not a legitimate item");
        expect(within(await tableOf()).getByText("cane description")).toBeInTheDocument();
    });

    it("conflicts block approval; multi-product rows need the product review; read-only users get no actions", async () => {
        setup([row("mixed", "CONFLICT"), row("multi", "CONFLICT", { segments: [{ index: 0, phrase: "a" }, { index: 1, phrase: "b" }] as unknown as MatchSuggestion["segments"] })], false);
        const table = await tableOf();
        expect(within(rowOf(table, "mixed description")).getByText("Conflict")).toBeInTheDocument();
        expect(within(rowOf(table, "multi description")).getByText("Review required")).toBeInTheDocument();
        expect(within(table).queryByRole("button", { name: /^Approve/ })).toBeNull();
    });

    it("requires confirmation before replacing the links of an ambiguous record", async () => {
        const user = setup([row("amb", "REVIEW", { kind: "AMBIGUOUS" })]);
        const tr = rowOf(await tableOf(), "amb description");
        await within(tr).findAllByRole("option", { name: "PP" });
        await user.selectOptions(within(tr).getByLabelText("Item Name for amb description"), "7");
        await user.click(within(tr).getByRole("button", { name: "Approve amb description" }));
        await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Cancel" }));
        expect(api.post).not.toHaveBeenCalled(); // declined
        await user.click(within(tr).getByRole("button", { name: "Approve amb description" }));
        const dialog = await screen.findByRole("alertdialog");
        expect(dialog).toHaveTextContent("already linked to several Item Names");
        await user.click(within(dialog).getByRole("button", { name: "Approve" }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/decide/", expect.objectContaining({ source_keys: ["amb"], item_id: 7, replace_links: true })));
    });
});
