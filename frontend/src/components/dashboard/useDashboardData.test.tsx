import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api from "@/api/axios";
import { v3Fixture } from "./fixtures";
import { useDashboardData } from "./useDashboardData";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const get = vi.mocked(api.get);
const request = { companyId: null, dateFrom: undefined, dateTo: undefined };

/** A payload missing the required `attention` list. The whole response must be rejected. */
function payloadWithoutAttention(): unknown {
    const raw = JSON.parse(JSON.stringify(v3Fixture));
    delete raw.attention;
    return raw;
}

describe("useDashboardData", () => {
    beforeEach(() => {
        get.mockReset();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("is loading until the first response arrives, then stores a valid payload", async () => {
        let resolve!: (value: unknown) => void;
        get.mockReturnValueOnce(new Promise((r) => (resolve = r)) as never);

        const { result } = renderHook(() => useDashboardData(request));
        expect(result.current.loading).toBe(true);
        expect(result.current.data).toBeNull();

        await act(async () => resolve({ data: JSON.parse(JSON.stringify(v3Fixture)) }));

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.data?.boe_activity).toEqual(v3Fixture.boe_activity);
        expect(result.current.failed).toBe(false);
        expect(result.current.lastRefreshed).toBeInstanceOf(Date);
    });

    it("fails without storing data when the request itself fails", async () => {
        get.mockRejectedValueOnce(new Error("network down"));

        const { result } = renderHook(() => useDashboardData(request));

        await waitFor(() => expect(result.current.failed).toBe(true));
        expect(result.current.data).toBeNull();
        expect(result.current.loading).toBe(false);
    });

    it("rejects a payload that does not match the contract, logs it, and never stores it", async () => {
        const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
        get.mockResolvedValueOnce({ data: payloadWithoutAttention() } as never);

        const { result } = renderHook(() => useDashboardData(request));

        await waitFor(() => expect(result.current.failed).toBe(true));
        expect(result.current.data).toBeNull();
        expect(spy).toHaveBeenCalledWith(
            expect.stringContaining("contract v3"),
            [{ section: "attention", problem: "attention should be an array" }],
        );
    });

    it("keeps the last good payload on screen when a later refresh is malformed", async () => {
        vi.spyOn(console, "error").mockImplementation(() => undefined);
        get.mockResolvedValueOnce({ data: JSON.parse(JSON.stringify(v3Fixture)) } as never);
        get.mockResolvedValueOnce({ data: payloadWithoutAttention() } as never);

        const { result } = renderHook(() => useDashboardData(request));
        await waitFor(() => expect(result.current.data).not.toBeNull());
        const good = result.current.data;

        act(() => result.current.refresh());

        await waitFor(() => expect(result.current.failed).toBe(true));
        expect(result.current.data).toBe(good);
    });

    it("keeps the last good payload on screen when a later refresh fails", async () => {
        get.mockResolvedValueOnce({ data: JSON.parse(JSON.stringify(v3Fixture)) } as never);
        get.mockRejectedValueOnce(new Error("timeout"));

        const { result } = renderHook(() => useDashboardData(request));
        await waitFor(() => expect(result.current.data).not.toBeNull());
        const good = result.current.data;

        act(() => result.current.refresh());

        await waitFor(() => expect(result.current.failed).toBe(true));
        expect(result.current.data).toBe(good);
    });

    it("sends refresh=1 only for the Refresh action, so the server recomputes", async () => {
        get.mockResolvedValue({ data: JSON.parse(JSON.stringify(v3Fixture)) } as never);

        const { result } = renderHook(() => useDashboardData({ companyId: 7, dateFrom: "2026-01-01", dateTo: undefined }));
        await waitFor(() => expect(result.current.data).not.toBeNull());
        expect(get.mock.calls[0]?.[1]).toEqual({ params: { company_id: 7, date_from: "2026-01-01" } });

        act(() => result.current.refresh());

        await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
        expect(get.mock.calls[1]?.[1]).toEqual({ params: { company_id: 7, date_from: "2026-01-01", refresh: "1" } });
    });
});
