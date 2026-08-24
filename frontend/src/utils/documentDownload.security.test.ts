import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { openAuthedFile, openDocument } from "./documentDownload";

vi.mock("../api/axios", () => ({ default: { get: vi.fn() } }));

const mockedGet = vi.mocked(api.get);
const createObjectURL = vi.fn(() => "blob:protected-document");
const revokeObjectURL = vi.fn();
const open = vi.fn();

beforeEach(() => {
    vi.useFakeTimers();
    mockedGet.mockReset();
    createObjectURL.mockClear();
    revokeObjectURL.mockClear();
    open.mockClear();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });
    vi.stubGlobal("open", open);
});

afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
});

describe("protected document opening", () => {
    it("fetches the stored document through the authenticated API then uses noopener for the blob tab", async () => {
        mockedGet.mockResolvedValueOnce({ data: new Blob(["pdf"]) });

        await openDocument("https://storage.example/media/licenses/2260/copy.pdf");

        expect(mockedGet).toHaveBeenCalledWith("/media/licenses/2260/copy.pdf", { responseType: "blob" });
        expect(open).toHaveBeenCalledWith("blob:protected-document", "_blank", "noopener");
        vi.advanceTimersByTime(60_000);
        expect(revokeObjectURL).toHaveBeenCalledWith("blob:protected-document");
    });

    it("does not open a tab when authentication or authorization rejects the protected blob fetch", async () => {
        mockedGet.mockRejectedValueOnce(Object.assign(new Error("Forbidden"), { response: { status: 403 } }));

        await expect(openAuthedFile("/media/licenses/2260/private.pdf")).rejects.toThrow("Forbidden");

        expect(createObjectURL).not.toHaveBeenCalled();
        expect(open).not.toHaveBeenCalled();
    });

    it("rejects unsafe document paths before any authenticated request or window action", () => {
        expect(() => openDocument("folder\\private.pdf")).toThrow("Protected media path is required.");
        expect(mockedGet).not.toHaveBeenCalled();
        expect(open).not.toHaveBeenCalled();
    });
});
