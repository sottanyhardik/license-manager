import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { useFileUpload } from "../hooks";
import LedgerUpload, {
    buildAsyncUploadErrorMessage,
    getLedgerUploadErrorMessage,
    normalizeLedgerFileTasks,
    normalizeLedgerUploadErrors,
    normalizeProgressValue,
} from "./LedgerUpload";

vi.mock("../api/axios", () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
    },
}));

vi.mock("../hooks", () => ({
    useFileUpload: vi.fn(),
}));

const mockedApiPost = vi.mocked(api.post);
const mockedUseFileUpload = vi.mocked(useFileUpload);
const clearFiles = vi.fn();
const removeFile = vi.fn();
const originalHandleUpload = vi.fn();

function ledgerFile(name = "ledger.csv") {
    return new File(["Regn.No.,Lic.No."], name, { type: "text/csv", lastModified: 123 });
}

function mockUploadHook(overrides = {}) {
    mockedUseFileUpload.mockReturnValue({
        files: [],
        uploading: false,
        results: [],
        error: null,
        dragActive: false,
        fileProgress: {},
        currentFileIndex: 0,
        handleDrag: vi.fn(),
        handleDrop: vi.fn(),
        handleFileChange: vi.fn(),
        handleUpload: originalHandleUpload,
        formatFileSize: (size: number) => `${size} B`,
        removeFile,
        clearFiles,
        setFiles: vi.fn(),
        setError: vi.fn(),
        ...overrides,
    });
}

describe("LedgerUpload helpers", () => {
    it("normalizes async task responses and filters malformed task entries", () => {
        expect(normalizeLedgerFileTasks(null)).toEqual([]);
        expect(normalizeLedgerFileTasks([
            { file: " ledger.csv ", total: 99, tasks: [
                { task_id: " task-1 ", license: " LIC-1 " },
                { task_id: "", license: "SKIP" },
                { task_id: "task-1", license: "DUPLICATE" },
                { task_id: "task-2", license: "" },
            ] },
            { file: "empty.csv", tasks: [] },
            { file: "bad.csv" },
        ])).toEqual([
            {
                file: "ledger.csv",
                total: 2,
                tasks: [
                    { task_id: "task-1", license: "LIC-1" },
                    { task_id: "task-2", license: "Unknown license" },
                ],
            },
        ]);
    });

    it("normalizes and caps async upload error messages", () => {
        const errors = normalizeLedgerUploadErrors([
            { file: " a.csv ", error: " broken " },
            {},
            "skip",
            ...Array.from({ length: 10 }, (_, index) => ({ file: `f${index}.csv`, error: "bad" })),
        ]);

        expect(errors[0]).toEqual({ file: "a.csv", error: "broken" });
        expect(errors[1]).toEqual({ file: "File 2", error: "Unknown upload error" });
        expect(buildAsyncUploadErrorMessage(errors)).toContain("2 more not shown");
    });

    it("extracts useful upload error messages from API and native failures", () => {
        expect(getLedgerUploadErrorMessage({ response: { data: { detail: "Denied" } } })).toBe("Denied");
        expect(getLedgerUploadErrorMessage(new Error("Network down"))).toBe("Network down");
        expect(getLedgerUploadErrorMessage({})).toBe("Upload failed. Please try again.");
    });

    it("clamps malformed progress values for UI and ARIA output", () => {
        expect(normalizeProgressValue("45.6")).toBe(46);
        expect(normalizeProgressValue(-5)).toBe(0);
        expect(normalizeProgressValue(999)).toBe(100);
        expect(normalizeProgressValue("bad")).toBe(0);
    });
});

describe("LedgerUpload", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        vi.clearAllMocks();
        mockUploadHook();
    });

    it("renders selected files with an accessible remove action", () => {
        const file = ledgerFile("daily-ledger.csv");
        mockUploadHook({ files: [file] });

        render(<LedgerUpload />);

        expect(screen.getByText("daily-ledger.csv")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Remove daily-ledger.csv" })).toBeInTheDocument();
    });

    it("normalizes async upload responses before showing task progress", async () => {
        mockUploadHook({ files: [ledgerFile("batch.csv")] });
        mockedApiPost.mockResolvedValue({
            data: {
                file_tasks: [{
                    file: " batch.csv ",
                    total: 99,
                    tasks: [
                        { task_id: " task-1 ", license: " LIC-1 " },
                        { task_id: "", license: "SKIP" },
                        { task_id: "task-1", license: "DUPLICATE" },
                    ],
                }],
                errors: [{ file: " bad.csv ", error: " parse failed " }],
            },
        });

        render(<LedgerUpload />);
        fireEvent.click(screen.getByRole("button", { name: /upload & process/i }));

        await waitFor(() => {
            expect(mockedApiPost).toHaveBeenCalledWith(
                "upload-ledger/",
                expect.any(FormData),
                { headers: { "Content-Type": "multipart/form-data" } },
            );
        });

        const formData = mockedApiPost.mock.calls[0][1] as FormData;
        expect(formData.get("async")).toBe("true");
        expect(formData.getAll("ledger")).toHaveLength(1);

        expect(await screen.findByText("Processing Ledger Files")).toBeInTheDocument();
        expect(screen.getAllByText("batch.csv")).toHaveLength(2);
        expect(screen.getByText("LIC-1")).toBeInTheDocument();
        expect(screen.queryByText("SKIP")).not.toBeInTheDocument();
        expect(screen.getByText("1 file(s) failed: bad.csv: parse failed")).toBeInTheDocument();
        expect(clearFiles).toHaveBeenCalled();
    });
});
