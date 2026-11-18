import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { useFileUpload } from "../hooks";
import LedgerUpload from "./LedgerUpload";
import {
    buildAsyncUploadErrorMessage,
    getLedgerUploadErrorMessage,
    normalizeLedgerFileTasks,
    normalizeLedgerUploadErrors,
    normalizeProgressValue,
} from "./ledgerUploadHelpers";

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

function renderPage() {
    return render(<MemoryRouter><LedgerUpload /></MemoryRouter>);
}

describe("LedgerUpload", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        vi.clearAllMocks();
        mockUploadHook();
    });

    it("renders selected files with an accessible remove action", () => {
        const file = ledgerFile("daily-ledger.csv");
        mockUploadHook({ files: [file] });

        renderPage();

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

        renderPage();
        fireEvent.click(screen.getByRole("button", { name: /upload & process/i }));

        await waitFor(() => {
            expect(mockedApiPost).toHaveBeenCalledWith(
                "upload-ledger/",
                expect.any(FormData),
                {
                    headers: {
                        "Content-Type": "multipart/form-data",
                        "X-Upload-Operation-Id": expect.any(String),
                    },
                },
            );
        });

        const formData = mockedApiPost.mock.calls[0][1] as FormData;
        expect(formData.get("async")).toBe("true");
        expect(formData.getAll("ledger")).toHaveLength(1);

        expect(await screen.findByText("Processing Ledger Files")).toBeInTheDocument();
        // modal heading + modal progress + the new "Queued for Processing" summary row
        expect(screen.getAllByText("batch.csv")).toHaveLength(3);
        expect(screen.getByText("LIC-1")).toBeInTheDocument();
        expect(screen.queryByText("SKIP")).not.toBeInTheDocument();
        expect(screen.getByText("1 file(s) failed: bad.csv: parse failed")).toBeInTheDocument();
        expect(clearFiles).toHaveBeenCalled();
    });
    it("renders the shared toolbar H1 and supported-format guidance derived from the accept config", () => {
        renderPage();

        expect(screen.getByRole("heading", { level: 1, name: "Ledger Upload" })).toBeInTheDocument();
        expect(screen.getByText(/Accepted: \.csv, \.htm, \.html · Max 50MB per file/)).toBeInTheDocument();
        const input = screen.getByLabelText("Ledger files") as HTMLInputElement;
        expect(input.accept).toBe(".csv,.htm,.html");
        expect(mockedUseFileUpload).toHaveBeenCalledWith(expect.objectContaining({
            endpoint: "upload-ledger/",
            fileFieldName: "ledger",
            accept: ".csv,.htm,.html",
            maxFileSize: 50 * 1024 * 1024,
        }));
        expect(screen.getByText("No uploads yet")).toBeInTheDocument();
    });

    it("shows the client-side rejection reason inline, not only as a toast", () => {
        mockUploadHook({ error: 'File "notes.txt" has invalid type. Expected: .csv,.htm,.html' });

        renderPage();

        const alert = screen.getByRole("alert");
        expect(within(alert).getByText("File not accepted")).toBeInTheDocument();
        expect(within(alert).getByText('File "notes.txt" has invalid type. Expected: .csv,.htm,.html')).toBeInTheDocument();
    });

    it("shows a processing state and prevents a double submit while an async upload is in flight", async () => {
        mockUploadHook({ files: [ledgerFile("slow.csv")] });
        mockedApiPost.mockReturnValue(new Promise(() => {}));

        renderPage();
        const submit = screen.getByRole("button", { name: /upload & process/i });
        fireEvent.click(submit);
        fireEvent.click(submit);

        expect(await screen.findByText(/Uploading batch 1 of 1/)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /Uploading batch 1\/1/ })).toBeDisabled();
        expect(mockedApiPost).toHaveBeenCalledTimes(1);
    });

    it("guards against double submit in sync mode too", () => {
        mockUploadHook({ files: [ledgerFile("sync.csv")] });
        originalHandleUpload.mockReturnValue(new Promise(() => {}));

        renderPage();
        fireEvent.click(screen.getByRole("switch"));
        const submit = screen.getByRole("button", { name: /upload & process/i });
        fireEvent.click(submit);
        fireEvent.click(submit);

        expect(originalHandleUpload).toHaveBeenCalledTimes(1);
        expect(mockedApiPost).not.toHaveBeenCalled();
    });

    it("renders each sync result category the API returns: imported, failed licenses and rejected files", () => {
        mockUploadHook({
            results: [
                {
                    fileName: "good.csv", success: true, message: "Processed 2 license(s) from 1 file(s)",
                    licenses: ["0311000001", "0311000002"], stats: { total_licenses: 2 },
                    data: { results: [{ failed: [{ license: "0311000003", error: "Missing IEC" }] }] },
                },
                { fileName: "bad.xlsx", success: false, error: "Only CSV and HTM/HTML files are supported" },
            ],
        });

        renderPage();

        const region = screen.getByRole("region", { name: "Upload results" });
        expect(within(region).getByText("1/2 succeeded")).toBeInTheDocument();
        expect(within(region).getByText("2 licenses imported")).toBeInTheDocument();
        expect(within(region).getByText("1 licenses failed")).toBeInTheDocument();
        expect(within(region).getByText("1 files rejected")).toBeInTheDocument();
        expect(within(region).getByText("Partly imported")).toBeInTheDocument();
        expect(within(region).getByText("Rejected")).toBeInTheDocument();
        expect(within(region).getByText("View License Numbers (2)")).toBeInTheDocument();
        expect(within(region).getByText("0311000001")).toBeInTheDocument();
        expect(within(region).getByText("Failed Licenses (1)")).toBeInTheDocument();
        expect(within(region).getByText("Missing IEC")).toBeInTheDocument();
        expect(within(region).getByText("Only CSV and HTM/HTML files are supported")).toBeInTheDocument();
    });

    it("summarises queued async licenses after the task dialog is closed", async () => {
        mockUploadHook({ files: [ledgerFile("batch.csv")] });
        mockedApiPost.mockResolvedValue({
            data: { file_tasks: [{ file: "batch.csv", total: 1, tasks: [{ task_id: "t1", license: "LIC-1" }] }], errors: [] },
        });

        renderPage();
        fireEvent.click(screen.getByRole("button", { name: /upload & process/i }));
        await screen.findByText("Processing Ledger Files");
        fireEvent.click(screen.getAllByRole("button", { name: "Close" })[0]);

        const region = await screen.findByRole("region", { name: "Queued for processing" });
        expect(within(region).getByText("1 licenses queued")).toBeInTheDocument();
        expect(within(region).getByText("batch.csv")).toBeInTheDocument();
    });
});
