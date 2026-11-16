import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

const get = vi.fn();
vi.mock("@/api/axios", () => ({ default: { get: (...a: unknown[]) => get(...a) } }));

import { useSionNormOptions } from "./useMasterOptions";

describe("useSionNormOptions", () => {
    beforeEach(() => { get.mockReset(); });

    it("returns all 450 options via requests of at most 200", async () => {
        const all = Array.from({ length: 450 }, (_, i) => ({ norm_class: `N${String(i).padStart(4, "0")}` }));
        get.mockImplementation(async (_url: string, opts: { params: { page: number; page_size: number } }) => { const { params } = opts;
            const start = (params.page - 1) * params.page_size;
            const slice = all.slice(start, start + params.page_size);
            return { data: { count: 450, next: start + params.page_size < 450 ? "more" : null, results: slice } };
        });
        const { result } = renderHook(() => useSionNormOptions());
        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.options).toHaveLength(450);
        expect(get).toHaveBeenCalledTimes(3);
        for (const call of get.mock.calls) expect(call[1].params.page_size).toBeLessThanOrEqual(200);
    });
});
