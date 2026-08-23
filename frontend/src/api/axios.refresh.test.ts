import { beforeEach, describe, expect, it, vi } from "vitest";

const { rawPost, client } = vi.hoisted(() => ({
    rawPost: vi.fn(),
    client: {
        interceptors: {
            request: { use: vi.fn() },
            response: { use: vi.fn() },
        },
        get: vi.fn(),
    },
}));

vi.mock("axios", () => ({
    default: {
        create: vi.fn(() => client),
        post: rawPost,
    },
}));

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

import { refreshAccessToken } from "./axios";

describe("refreshAccessToken", () => {
    beforeEach(() => {
        localStorage.clear();
        rawPost.mockReset();
    });

    it("shares one SimpleJWT refresh request across concurrent callers", async () => {
        localStorage.setItem("refresh", "refresh-before-rotation");
        let resolveRefresh;
        rawPost.mockImplementationOnce(() => new Promise(resolve => { resolveRefresh = resolve; }));

        const first = refreshAccessToken();
        const second = refreshAccessToken();
        expect(rawPost).toHaveBeenCalledTimes(1);

        resolveRefresh({ data: { access: "fresh-access", refresh: "rotated-refresh" } });
        await expect(Promise.all([first, second])).resolves.toEqual(["fresh-access", "fresh-access"]);
        expect(localStorage.getItem("access")).toBe("fresh-access");
        expect(localStorage.getItem("refresh")).toBe("rotated-refresh");
    });
});
