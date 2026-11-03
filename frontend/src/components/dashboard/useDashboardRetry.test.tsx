import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api from "@/api/axios";
import { v3Fixture } from "./fixtures";
import { SECTION_RETRY_FAILED, useDashboardData } from "./useDashboardData";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const get = vi.mocked(api.get);
const request = { companyId: null, dateFrom: undefined, dateTo: undefined };

function clone<T>(value: T): T {
    return JSON.parse(JSON.stringify(value));
}

/** The single-section response shape: meta plus the requested section only. */
function sectionResponse(name: "boe_activity" | "invoice_activity", value: unknown) {
    return { data: { meta: clone(v3Fixture.meta), [name]: value } };
}

function dashboardCalls() {
    return get.mock.calls.filter(([url]) => url === "dashboard/");
}

describe("useDashboardData section retry", () => {
    beforeEach(() => {
        get.mockReset();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("refetches only the requested section and leaves every other section untouched", async () => {
        const failing = clone(v3Fixture);
        failing.boe_activity = { error: "Dashboard section 'boe_activity' could not be loaded" };
        get.mockResolvedValueOnce({ data: failing } as never);

        const { result } = renderHook(() => useDashboardData(request));
        await waitFor(() => expect(result.current.data).not.toBeNull());
        const invoiceBefore = result.current.data?.invoice_activity;

        get.mockResolvedValueOnce(sectionResponse("boe_activity", clone(v3Fixture.boe_activity)) as never);
        act(() => { void result.current.retrySection("boe_activity"); });

        await waitFor(() => expect(result.current.data?.boe_activity).toEqual(v3Fixture.boe_activity));
        expect(result.current.retrying.has("boe_activity")).toBe(false);
        expect(result.current.data?.invoice_activity).toBe(invoiceBefore);
        expect(get).toHaveBeenCalledTimes(2);
        expect(get.mock.calls[1]?.[1]).toEqual({ params: { section: "boe_activity", refresh: "1" } });
    });

    it("sends the scope with the section request", async () => {
        get.mockResolvedValueOnce({ data: clone(v3Fixture) } as never);
        const { result } = renderHook(() => useDashboardData({ companyId: 7, dateFrom: "2026-01-01", dateTo: "2026-06-30" }));
        await waitFor(() => expect(result.current.data).not.toBeNull());

        get.mockResolvedValueOnce(sectionResponse("invoice_activity", clone(v3Fixture.invoice_activity)) as never);
        act(() => { void result.current.retrySection("invoice_activity"); });

        await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
        expect(get.mock.calls[1]?.[1]).toEqual({
            params: { company_id: 7, date_from: "2026-01-01", date_to: "2026-06-30", section: "invoice_activity", refresh: "1" },
        });
    });

    it("marks the section as retrying while the request is in flight", async () => {
        get.mockResolvedValueOnce({ data: clone(v3Fixture) } as never);
        const { result } = renderHook(() => useDashboardData(request));
        await waitFor(() => expect(result.current.data).not.toBeNull());

        let resolve!: (value: unknown) => void;
        get.mockReturnValueOnce(new Promise((r) => (resolve = r)) as never);
        act(() => { void result.current.retrySection("boe_activity"); });

        expect(result.current.retrying.has("boe_activity")).toBe(true);
        expect(result.current.retrying.has("invoice_activity")).toBe(false);

        await act(async () => resolve(sectionResponse("boe_activity", clone(v3Fixture.boe_activity))));
        expect(result.current.retrying.has("boe_activity")).toBe(false);
    });

    it("does not send a second request for a section that is already retrying", async () => {
        get.mockResolvedValueOnce({ data: clone(v3Fixture) } as never);
        const { result } = renderHook(() => useDashboardData(request));
        await waitFor(() => expect(result.current.data).not.toBeNull());

        let resolve!: (value: unknown) => void;
        get.mockReturnValueOnce(new Promise((r) => (resolve = r)) as never);
        act(() => {
            void result.current.retrySection("boe_activity");
            void result.current.retrySection("boe_activity");
        });

        expect(dashboardCalls()).toHaveLength(2);
        await act(async () => resolve(sectionResponse("boe_activity", clone(v3Fixture.boe_activity))));
    });

    it("shows a section error with the retry message when the section request fails", async () => {
        get.mockResolvedValueOnce({ data: clone(v3Fixture) } as never);
        const { result } = renderHook(() => useDashboardData(request));
        await waitFor(() => expect(result.current.data).not.toBeNull());

        get.mockRejectedValueOnce(new Error("network down"));
        act(() => { void result.current.retrySection("boe_activity"); });

        await waitFor(() => expect(result.current.retrying.has("boe_activity")).toBe(false));
        expect(result.current.data?.boe_activity).toEqual({ error: SECTION_RETRY_FAILED });
        expect(result.current.data?.invoice_activity).toEqual(v3Fixture.invoice_activity);
    });

    it("recovers after a temporary failure when the next retry succeeds", async () => {
        get.mockResolvedValueOnce({ data: clone(v3Fixture) } as never);
        const { result } = renderHook(() => useDashboardData(request));
        await waitFor(() => expect(result.current.data).not.toBeNull());

        get.mockRejectedValueOnce(new Error("timeout"));
        act(() => { void result.current.retrySection("invoice_activity"); });
        await waitFor(() => expect(result.current.data?.invoice_activity).toEqual({ error: SECTION_RETRY_FAILED }));

        get.mockResolvedValueOnce(sectionResponse("invoice_activity", clone(v3Fixture.invoice_activity)) as never);
        act(() => { void result.current.retrySection("invoice_activity"); });
        await waitFor(() => expect(result.current.data?.invoice_activity).toEqual(v3Fixture.invoice_activity));
    });

    it("does nothing when there is no payload yet, so there is nothing to merge into", async () => {
        get.mockRejectedValueOnce(new Error("first load failed"));
        const { result } = renderHook(() => useDashboardData(request));
        await waitFor(() => expect(result.current.failed).toBe(true));

        get.mockResolvedValueOnce(sectionResponse("boe_activity", clone(v3Fixture.boe_activity)) as never);
        act(() => { void result.current.retrySection("boe_activity"); });
        await waitFor(() => expect(result.current.retrying.has("boe_activity")).toBe(false));

        expect(result.current.data).toBeNull();
    });
});
