import { beforeEach, describe, expect, it, vi } from "vitest";

const { handlers, client, toastError } = vi.hoisted(() => {
    const handlers: { onError?: (e: unknown) => Promise<unknown> } = {};
    return {
        handlers,
        toastError: vi.fn(),
        client: Object.assign(vi.fn(), {
            interceptors: {
                request: { use: vi.fn() },
                response: { use: vi.fn((_ok, err) => { handlers.onError = err; }) },
            },
            get: vi.fn(),
        }),
    };
});

vi.mock("axios", () => ({ default: { create: vi.fn(() => client), post: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { error: toastError } }));

import { _resetThrottleToastForTests, parseRetryAfterSeconds } from "./axios";
import { shouldRetryQuery } from "./queryClient";

const err = (status: number, headers: Record<string, string> = {}, method = "get") => ({
    config: { method, url: "x/" },
    response: { status, headers },
});

describe("429 handling", () => {
    beforeEach(() => {
        toastError.mockReset();
        client.mockReset();
        _resetThrottleToastForTests();
        vi.useRealTimers();
    });

    it("shows one toast with Retry-After seconds and does not replay", async () => {
        const e = err(429, { "retry-after": "12" }, "post");
        await expect(handlers.onError!(e)).rejects.toBe(e);
        expect(toastError).toHaveBeenCalledTimes(1);
        expect(toastError.mock.calls[0][0]).toBe("Too many requests — please wait 12s and try again.");
        expect(client).not.toHaveBeenCalled();
    });

    it("dedupes 10 concurrent 429s into one toast", async () => {
        await Promise.allSettled(Array.from({ length: 10 }, () => handlers.onError!(err(429, { "retry-after": "5" }))));
        expect(toastError).toHaveBeenCalledTimes(1);
        expect(client).not.toHaveBeenCalled();
    });

    it("parses HTTP-date and falls back when missing", () => {
        const now = Date.parse("2026-01-01T00:00:00Z");
        expect(parseRetryAfterSeconds("Thu, 01 Jan 2026 00:00:20 GMT", now)).toBe(20);
        expect(parseRetryAfterSeconds("garbage", now)).toBeNull();
        expect(parseRetryAfterSeconds(undefined, now)).toBeNull();
    });

    it("leaves 5xx replay behaviour unchanged (GET replays, no 429 toast)", async () => {
        vi.useFakeTimers();
        client.mockResolvedValue({ data: "ok" });
        const p = handlers.onError!(err(503));
        await vi.advanceTimersByTimeAsync(1000);
        await expect(p).resolves.toEqual({ data: "ok" });
        expect(client).toHaveBeenCalledTimes(1);
        expect(toastError).not.toHaveBeenCalled();
    });

    it("query retry: none on 429, one retry otherwise", () => {
        expect(shouldRetryQuery(0, { response: { status: 429 } })).toBe(false);
        expect(shouldRetryQuery(0, { response: { status: 500 } })).toBe(true);
        expect(shouldRetryQuery(1, { response: { status: 500 } })).toBe(false);
        expect(shouldRetryQuery(0, new Error("net"))).toBe(true);
    });
});
