import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
vi.mock("@/api/axios", () => ({ default: { get: (...a: unknown[]) => get(...a) } }));

import { useListQuery } from "./useListQuery";
import { useDebouncedValue } from "./useDebouncedValue";
import { qk } from "@/lib/queryKeys";

function wrapper(initial: string) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>
            <MemoryRouter initialEntries={[initial]}>{children}</MemoryRouter>
        </QueryClientProvider>
    );
}
const envelope = { count: 120, next: "n", previous: null, page_size: 25, total_pages: 5, current_page: 1, results: [{ id: 1 }] };
const useIt = () => ({
    q: useListQuery<{ id: number }>({ key: qk.licenses.list, endpoint: "licenses/", filterKeys: ["status"] }),
    loc: useLocation(),
});

describe("useListQuery", () => {
    beforeEach(() => { get.mockReset(); get.mockResolvedValue({ data: envelope }); });

    it("reads params from URL, forwards AbortSignal and query string to axios", async () => {
        const { result } = renderHook(useIt, { wrapper: wrapper("/l?page=2&status=x&tab=t&page_size=999") });
        await waitFor(() => expect(result.current.q.status).toBe("success"));
        const [url, cfg] = get.mock.calls[0];
        expect(url).toBe("licenses/");
        expect(cfg.signal).toBeInstanceOf(AbortSignal);
        expect(cfg.params.get("page")).toBe("2");
        expect(cfg.params.get("page_size")).toBe("200");
        expect(cfg.params.get("status")).toBe("x");
        expect(result.current.q.result?.totalPages).toBe(5);
    });

    it("writes URL on changes, resets page, preserves unrelated params, omits defaults", async () => {
        const { result } = renderHook(useIt, { wrapper: wrapper("/l?page=3&tab=t") });
        await waitFor(() => expect(result.current.q.status).toBe("success"));
        act(() => result.current.q.setFilters({ status: "open" }));
        expect(new URLSearchParams(result.current.loc.search).get("page")).toBeNull();
        expect(result.current.loc.search).toContain("status=open");
        expect(result.current.loc.search).toContain("tab=t");
        act(() => result.current.q.setOrdering("-id"));
        expect(result.current.loc.search).toContain("ordering=-id");
        act(() => result.current.q.setPage(4));
        expect(result.current.loc.search).toContain("page=4");
        act(() => result.current.q.setPageSize(25));
        expect(result.current.loc.search).not.toContain("page_size");
        act(() => result.current.q.setPageSize(1000));
        expect(result.current.loc.search).toContain("page_size=200");
        expect(result.current.loc.search).not.toContain("page=4");
    });

    it("aborts the in-flight request when params change", async () => {
        let first: AbortSignal | undefined;
        get.mockImplementationOnce((_u: string, cfg: { signal: AbortSignal }) => { first = cfg.signal; return new Promise(() => {}); });
        const { result } = renderHook(useIt, { wrapper: wrapper("/l") });
        await waitFor(() => expect(first).toBeDefined());
        act(() => result.current.q.setPage(2));
        await waitFor(() => expect(first?.aborted).toBe(true));
    });

    it("debounces setSearch 300ms and resets page", async () => {
        vi.useFakeTimers({ shouldAdvanceTime: true });
        const { result } = renderHook(useIt, { wrapper: wrapper("/l?page=3") });
        act(() => result.current.q.setSearch("abc"));
        expect(result.current.loc.search).not.toContain("search");
        act(() => { vi.advanceTimersByTime(300); });
        expect(result.current.loc.search).toContain("search=abc");
        expect(result.current.loc.search).not.toContain("page=3");
        vi.useRealTimers();
    });

    it("surfaces errors", async () => {
        get.mockRejectedValue(new Error("nope"));
        const { result } = renderHook(useIt, { wrapper: wrapper("/l") });
        await waitFor(() => expect(result.current.q.status).toBe("error"));
    });
});

describe("useDebouncedValue", () => {
    it("emits the latest value after the delay", () => {
        vi.useFakeTimers();
        const { result, rerender } = renderHook(({ v }) => useDebouncedValue(v, 300), { initialProps: { v: "a" } });
        rerender({ v: "b" });
        expect(result.current).toBe("a");
        act(() => { vi.advanceTimersByTime(300); });
        expect(result.current).toBe("b");
        vi.useRealTimers();
    });
});
