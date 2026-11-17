import type { ReactNode } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { post, success, error } = vi.hoisted(() => ({ post: vi.fn(), success: vi.fn(), error: vi.fn() }));
vi.mock("@/api/axios", () => ({ default: { post, get: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success, error, info: vi.fn(), warning: vi.fn() } }));

import { extractBoeError } from "@/api/boeApi";
import { useBoeRowActions, type BoeRowActionContext } from "./useBoeRowActions";
import type { BoeListItem } from "./types";

const ITEM: BoeListItem = {
    id: 9, bill_of_entry_number: "BE-9", product_name: "",
    item_details: [{ id: 1, is_dispute: true }, { id: 2, is_dispute: true }],
};

function setup(over: Partial<BoeRowActionContext> = {}, item = ITEM) {
    const ctx: BoeRowActionContext = {
        canWrite: true, canTransferLetter: true, entityName: "bill-of-entries", filterParams: {}, currentPage: 1, pageSize: 25,
        navigate: vi.fn(), onDelete: vi.fn(), invalidateList: vi.fn(), onTransferLetter: vi.fn(), onMerge: vi.fn(),
        confirmDangerousAction: vi.fn(() => Promise.resolve(true)), ...over,
    };
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    const hook = renderHook(() => useBoeRowActions(item, ctx), { wrapper });
    return { ctx, invalidate, ...hook };
}
const titles = (r: { current: ReturnType<typeof useBoeRowActions> }) => r.current.actions.map(a => a.label);

beforeEach(() => { post.mockReset(); success.mockReset(); error.mockReset(); });

describe("useBoeRowActions", () => {
    it("write actions are gated on canWrite; Transfer Letter stays for read-only roles", () => {
        expect(titles(setup().result)).toEqual(["Edit", "Transfer Letter", "Merge BOE", "Resolve Dispute", "Update Product Name", "Delete"]);
        expect(titles(setup({ canWrite: false }).result)).toEqual(["Transfer Letter"]);
        expect(titles(setup({ canWrite: false, canTransferLetter: false }).result)).toEqual([]);
    });

    it("confirmed Resolve Dispute posts once, toasts the server message and invalidates the BOE lists", async () => {
        post.mockResolvedValueOnce({ data: { success: true, message: "Resolved 2" } });
        const { result, ctx, invalidate } = setup();
        await act(async () => { await result.current.actions.find(a => a.id === "resolve-dispute")!.onSelect?.(); });
        expect(ctx.confirmDangerousAction).toHaveBeenCalledWith("Resolve Dispute", expect.stringContaining("2 dispute row(s)"));
        expect(post).toHaveBeenCalledTimes(1);
        expect(post).toHaveBeenCalledWith("bill-of-entries/9/resolve-dispute/");
        await waitFor(() => expect(success).toHaveBeenCalledWith("Resolved 2"));
        expect(ctx.invalidateList).toHaveBeenCalledTimes(1);
        expect(invalidate).toHaveBeenCalledWith({ queryKey: ["boes"] });
        // Licence balances are untouched by a dispute flag.
        expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ["licenses", "detail", "5"] });
    });

    it("declined confirmation sends nothing", async () => {
        const { result } = setup({ confirmDangerousAction: vi.fn(() => Promise.resolve(false)) });
        await act(async () => { await result.current.updateProductName(); });
        expect(post).not.toHaveBeenCalled();
    });

    it("failed Update Product Name surfaces {error} first, then {detail}", async () => {
        post.mockRejectedValueOnce({ response: { data: { error: "boom", detail: "later" } } });
        const { result } = setup();
        await act(async () => { await result.current.updateProductName(); });
        expect(post).toHaveBeenCalledWith("bill-of-entries/9/update-product-name/");
        await waitFor(() => expect(error).toHaveBeenCalledWith("boom"));
        expect(extractBoeError({ response: { data: { detail: "d" } } }, "x")).toBe("d");
        expect(extractBoeError({}, "fallback")).toBe("fallback");
    });

    it("hide posts the licence-hosted endpoint and also invalidates that licence", async () => {
        post.mockResolvedValueOnce({ data: {} });
        const { result, invalidate } = setup();
        await act(async () => { await result.current.hide(5); });
        expect(post).toHaveBeenCalledWith("licenses/5/hide-boe/", { boe_id: 9 });
        await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["licenses", "detail", "5"] }));
    });
});
