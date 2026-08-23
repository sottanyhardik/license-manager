import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useSmoothListFilters } from "./useSmoothListFilters";

describe("useSmoothListFilters", () => {
    it("debounces text criteria for 400ms and keeps the draft value", () => {
        vi.useFakeTimers();
        const { result } = renderHook(() => useSmoothListFilters({ search: "", status: "all" }));
        act(() => result.current.setTextFilter("search", "aluminium"));
        expect(result.current.filters.search).toBe("aluminium");
        expect(result.current.appliedFilters.search).toBe("");
        act(() => vi.advanceTimersByTime(399));
        expect(result.current.appliedFilters.search).toBe("");
        act(() => vi.advanceTimersByTime(1));
        expect(result.current.appliedFilters.search).toBe("aluminium");
        vi.useRealTimers();
    });

    it("applies select criteria immediately without losing typed criteria", () => {
        const { result } = renderHook(() => useSmoothListFilters({ search: "foil", status: "all" }));
        act(() => result.current.setImmediateFilter("status", "active"));
        expect(result.current.filters).toEqual({ search: "foil", status: "active" });
        expect(result.current.appliedFilters).toEqual({ search: "foil", status: "active" });
    });

    it("cleans up a pending debounce on unmount", () => {
        vi.useFakeTimers();
        const { result, unmount } = renderHook(() => useSmoothListFilters({ search: "" }));
        act(() => result.current.setTextFilter("search", "one"));
        unmount();
        act(() => vi.advanceTimersByTime(400));
        vi.useRealTimers();
    });
});
