import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";

import PDFViewer, { normalizePdfApiPath } from "./PDFViewer";
import api from "../api/axios";

vi.mock("../api/axios", () => ({
    default: {
        get: vi.fn(),
    },
}));

const mockedGet = api.get as unknown as Mock;

beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window.URL, "createObjectURL", {
        configurable: true,
        value: vi.fn(() => "blob:pdf-preview"),
    });
    Object.defineProperty(window.URL, "revokeObjectURL", {
        configurable: true,
        value: vi.fn(),
    });
});

function renderPdfViewer(path: string) {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route path="/pdf-viewer" element={<PDFViewer />} />
            </Routes>
        </MemoryRouter>,
    );
}

describe("PDFViewer", () => {
    it("normalizes only relative API paths", () => {
        expect(normalizePdfApiPath(" license-ledger/export/all/ ")).toBe(
            "license-ledger/export/all/",
        );
        expect(normalizePdfApiPath("/license-ledger/export/all/")).toBe(
            "/license-ledger/export/all/",
        );
        expect(normalizePdfApiPath("https://example.com/report.pdf")).toBeNull();
        expect(normalizePdfApiPath("//example.com/report.pdf")).toBeNull();
        expect(normalizePdfApiPath("javascript:alert(1)")).toBeNull();
        expect(normalizePdfApiPath("reports\\example.pdf")).toBeNull();
        expect(normalizePdfApiPath("")).toBeNull();
        expect(normalizePdfApiPath(null)).toBeNull();
    });

    it("rejects unsafe urls before making an API request", async () => {
        renderPdfViewer("/pdf-viewer?url=https%3A%2F%2Fexample.com%2Freport.pdf");

        expect(await screen.findByText("Invalid or missing PDF URL")).toBeInTheDocument();
        expect(mockedGet).not.toHaveBeenCalled();
    });

    it("fetches a safe relative PDF path and renders an iframe", async () => {
        mockedGet.mockResolvedValueOnce({ data: new Blob(["%PDF"], { type: "application/pdf" }) });

        renderPdfViewer("/pdf-viewer?url=license-ledger%2Fexport%2Fall%2F");

        await waitFor(() => {
            expect(mockedGet).toHaveBeenCalledWith(
                "license-ledger/export/all/",
                { responseType: "blob" },
            );
        });
        expect(await screen.findByTitle("PDF Viewer")).toHaveAttribute(
            "src",
            "blob:pdf-preview",
        );
    });
});
