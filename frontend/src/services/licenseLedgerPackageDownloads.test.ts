import { describe, expect, it, vi } from "vitest";
import api from "../api/axios";
import { choosePackageDirectory, SequentialPackageDownloadManager, type PackageLicence } from "./licenseLedgerPackageDownloads";

vi.mock("../api/axios", () => ({ default: { get: vi.fn() } }));

const digest = "00".repeat(32);
const pdf = new Blob(["%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"], { type: "application/pdf" });

describe("SequentialPackageDownloadManager", () => {
    it("requires an explicit writable folder and never falls back to an anchor download", async () => {
        vi.stubGlobal("showDirectoryPicker", undefined);
        const click = vi.spyOn(HTMLAnchorElement.prototype, "click");
        expect(await choosePackageDirectory()).toBeUndefined();
        const manager = new SequentialPackageDownloadManager({ jobId: "job", queued: [], downloading: null, downloaded: [], failed: [], expected: {} });
        const error = vi.fn(); manager.onError = error;
        manager.enqueue([{ id: 1, licence_number: "0311051359", status: "server_ready", filename: "0311051359.pdf", download_url: "/api/one", size: 10, sha256: digest }]);
        await new Promise(resolve => setTimeout(resolve, 10));
        expect(vi.mocked(api.get)).not.toHaveBeenCalled();
        expect(click).not.toHaveBeenCalled();
        expect(error).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ message: expect.stringContaining("No destination folder") }));
    });

    it("sorts out-of-order completions and downloads every verified PDF exactly once with one request in flight", async () => {
        vi.stubGlobal("crypto", { subtle: { digest: vi.fn(async () => new Uint8Array(32).buffer) } });
        let active = 0; let maximum = 0;
        vi.mocked(api.get).mockImplementation(async () => {
            active += 1; maximum = Math.max(maximum, active);
            await new Promise(resolve => setTimeout(resolve, 5)); active -= 1;
            return { status: 200, headers: { "content-type": "application/pdf" }, data: pdf };
        });
        const files = new Map<string, File>();
        const directory = {
            name: "job-folder",
            getDirectoryHandle: vi.fn(),
            getFileHandle: vi.fn(async (name: string) => ({
                getFile: async () => files.get(name)!,
                createWritable: async () => ({ write: async (blob: Blob) => { files.set(name, new File([blob], name, { type: "application/pdf" })); }, close: async () => {} }),
            })),
        };
        const manager = new SequentialPackageDownloadManager({ jobId: "job", directory, queued: [], downloading: null, downloaded: [], failed: [], expected: {} });
        const items: PackageLicence[] = [
            { id: 2, licence_number: "0311051360", status: "completed", completed_at: "2026-08-28T12:00:02Z", filename: "0311051360.pdf", download_url: "/api/second", size: pdf.size, sha256: digest },
            { id: 1, licence_number: "0311051359", status: "completed", completed_at: "2026-08-28T12:00:01Z", filename: "0311051359.pdf", download_url: "/api/first", size: pdf.size, sha256: digest },
        ];
        manager.enqueue(items);
        await new Promise(resolve => setTimeout(resolve, 40));

        expect(maximum).toBe(1);
        expect(vi.mocked(api.get)).toHaveBeenCalledTimes(2);
        expect([...files.keys()]).toEqual(["0311051359.pdf", "0311051360.pdf"]);
        expect(manager.snapshot().downloaded).toEqual(["1", "2"]);
        manager.enqueue(items);
        await new Promise(resolve => setTimeout(resolve, 5));
        expect(vi.mocked(api.get)).toHaveBeenCalledTimes(2);
    });
});
