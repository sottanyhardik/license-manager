import { beforeEach, describe, expect, it, vi } from "vitest";

import { escapeHtmlAttribute, openPdfPreview, sanitizePdfFilename } from "./pdfPreview";

describe("pdfPreview helpers", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        Object.defineProperty(window.URL, "createObjectURL", {
            configurable: true,
            value: vi.fn(() => "blob:preview"),
        });
        Object.defineProperty(window.URL, "revokeObjectURL", {
            configurable: true,
            value: vi.fn(),
        });
    });

    it("sanitizes blank, unsafe, and extensionless PDF names", () => {
        expect(sanitizePdfFilename(" ")).toBe("document.pdf");
        expect(sanitizePdfFilename(' invoice:/<bad>"name ')).toBe("invoice_bad_name.pdf");
        expect(sanitizePdfFilename("report.PDF")).toBe("report.PDF");
        expect(sanitizePdfFilename("report")).toBe("report.pdf");
    });

    it("escapes HTML-sensitive attribute content", () => {
        expect(escapeHtmlAttribute(`a&b<"'>`)).toBe("a&amp;b&lt;&quot;&#39;&gt;");
    });

    it("revokes the object URL when popup creation is blocked", () => {
        vi.spyOn(window, "open").mockReturnValue(null);

        expect(openPdfPreview(new Blob(["pdf"], { type: "application/pdf" }), "blocked.pdf")).toBeNull();
        expect(window.URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview");
    });

    it("writes escaped wrapper HTML with a sanitized download name", () => {
        const fakeWindow = {
            document: {
                open: vi.fn(),
                write: vi.fn(),
                close: vi.fn(),
            },
            addEventListener: vi.fn(),
        };
        vi.spyOn(window, "open").mockReturnValue(fakeWindow as unknown as Window);

        expect(openPdfPreview(new Blob(["pdf"], { type: "application/pdf" }), `<bad>.pdf`)).toBe(fakeWindow);

        const html = fakeWindow.document.write.mock.calls[0][0];
        expect(html).toContain("<title>bad.pdf</title>");
        expect(html).toContain('download="bad.pdf"');
        expect(html).not.toContain("<bad>");
        expect(fakeWindow.addEventListener).toHaveBeenCalledWith("unload", expect.any(Function));
    });
});
