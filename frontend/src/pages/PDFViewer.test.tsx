import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";

import PDFViewer from "./PDFViewer";
import { normalizePdfApiPath } from "./pdfApiPath";
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
        expect(normalizePdfApiPath(" reports/example.pdf ")).toBe(
            "reports/example.pdf",
        );
        expect(normalizePdfApiPath("/reports/example.pdf")).toBe(
            "/reports/example.pdf",
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

        renderPdfViewer("/pdf-viewer?url=reports%2Fexample.pdf");

        await waitFor(() => {
            expect(mockedGet).toHaveBeenCalledWith(
                "reports/example.pdf",
                { responseType: "blob" },
            );
        });
        expect(await screen.findByTitle("PDF Viewer")).toHaveAttribute(
            "src",
            "blob:pdf-preview",
        );
    });
});
