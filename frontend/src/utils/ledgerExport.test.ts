import ExcelJS from "exceljs";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import {
    buildLicenseLedgerUrl,
    generateExcel,
    groupByCompany,
    normalizeLedgerLicensesData,
    sanitizeExportFilename,
    sanitizeWorksheetName,
} from "./ledgerExport";

// jsdom doesn't implement anchor-click navigation, Blob URL revocation, or
// `Blob.prototype.arrayBuffer()` — stub the download plumbing once for the
// whole file so `generateExcel`'s real flow (writeBuffer → new Blob →
// createObjectURL → anchor click → revokeObjectURL on a timer) never
// throws, and capture the raw workbook buffer via a `Blob` subclass instead
// of round-tripping through jsdom's broken Blob (a `Response(blob).
// arrayBuffer()` round-trip silently produced corrupt zip bytes here).
let capturedBuffer: BlobPart | null = null;
const OriginalBlob = globalThis.Blob;
const originalCreateObjectURL = URL.createObjectURL;
const originalRevokeObjectURL = URL.revokeObjectURL;

beforeAll(() => {
    class CapturingBlob extends OriginalBlob {
        constructor(parts?: BlobPart[], options?: BlobPropertyBag) {
            super(parts, options);
            capturedBuffer = parts?.[0] ?? null;
        }
    }
    globalThis.Blob = CapturingBlob as unknown as typeof Blob;
    URL.createObjectURL = (() => "blob:mock") as typeof URL.createObjectURL;
    URL.revokeObjectURL = (() => {}) as typeof URL.revokeObjectURL;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
});

beforeEach(() => {
    capturedBuffer = null;
});

afterAll(() => {
    globalThis.Blob = OriginalBlob;
    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
    vi.restoreAllMocks();
});

describe("ledgerExport helpers", () => {
    it("normalizes malformed ledger export data before PDF/XLSX generation", () => {
        expect(normalizeLedgerLicensesData([
            null,
            {
                license_id: "LIC/1",
                license_number: " LIC/1 ",
                license_type: "",
                exporter: "",
                total_value: "bad",
                available_balance: "12.4",
                transactions: [
                    { type: "", company_id: null, company_name: "", debit_amount: "10", credit_amount: "bad" },
                    "skip",
                ],
            },
        ])).toEqual([
            {
                id: "LIC/1",
                license_id: "LIC/1",
                license_number: "LIC/1",
                license_type: "UNKNOWN",
                license_date: null,
                expiry_date: null,
                exporter: "N/A",
                total_value: 0,
                available_balance: 12.4,
                transactions: [{
                    type: "UNKNOWN",
                    company_id: null,
                    company_name: "N/A",
                    date: null,
                    particular: "-",
                    invoice_number: "",
                    items: "",
                    debit_cif: 0,
                    credit_cif: 0,
                    debit_license_value: 0,
                    credit_license_value: 0,
                    debit_amount: 10,
                    credit_amount: 0,
                    rate: 0,
                    profit_loss: null,
                    _row_key: 0,
                }],
            },
        ]);
    });

    it("sanitizes export filenames and worksheet names", () => {
        expect(sanitizeExportFilename(' Ledger:/<bad>"name.pdf ', "fallback.pdf")).toBe("Ledger_bad_name.pdf");
        expect(sanitizeExportFilename("   ", "fallback.pdf")).toBe("fallback.pdf");
        expect(sanitizeWorksheetName("ABC:/[]*? very long worksheet name that should be trimmed")).toHaveLength(31);
        expect(sanitizeWorksheetName("")).toBe("License");
    });

    it("groups malformed transactions without merging unknown companies", () => {
        expect(groupByCompany([
            { company_id: null, company_name: "", debit_amount: "10" },
            { company_id: null, company_name: "", debit_amount: "20" },
            { company_id: 7, company_name: "Acme", debit_amount: "30" },
        ])).toEqual(expect.arrayContaining([
            expect.objectContaining({ company_id: "unknown-0", company_name: "N/A", transactions: [expect.objectContaining({ debit_amount: 10 })] }),
            expect.objectContaining({ company_id: "unknown-1", company_name: "N/A", transactions: [expect.objectContaining({ debit_amount: 20 })] }),
            expect.objectContaining({ company_id: 7, company_name: "Acme", transactions: [expect.objectContaining({ debit_amount: 30 })] }),
        ]));
    });

    it("builds encoded absolute ledger links", () => {
        expect(buildLicenseLedgerUrl("LIC/1")).toBe("http://localhost/license-ledger/LIC%2F1");
        expect(buildLicenseLedgerUrl(" ")).toBeNull();
    });

    it("computes a correct running Balance column in the Excel export (regression: stale object-identity Map)", async () => {
        // `generateExcel` used to key a running-balance Map by the
        // transaction objects from `license.transactions`, but the rows it
        // actually writes come from `groupByCompany(license.transactions)`,
        // which re-normalizes into brand-new object references internally
        // — every Map lookup missed, and every Balance cell silently
        // rendered as the "-" fmtNum(0) placeholder regardless of the real
        // running balance. Fixed by computing the running balance inline
        // while iterating the same rows being written (same fix already
        // applied to the PDF export's `buildPdfBody`).
        await generateExcel(
            [
                {
                    license_id: 1,
                    license_number: "LIC-1",
                    license_type: "DFIA",
                    exporter: "Exporter",
                    available_balance: 400,
                    transactions: [
                        {
                            id: 1, type: "PURCHASE", particular: "Purchase", company_id: 7, company_name: "Acme",
                            date: "2026-01-01", debit_cif: 500, debit_amount: 1000,
                        },
                        {
                            id: 2, type: "SALE", particular: "Sale", company_id: 7, company_name: "Acme",
                            date: "2026-02-01", credit_cif: 100, credit_amount: 200,
                        },
                    ],
                },
            ],
            "test.xlsx",
        );

        expect(capturedBuffer).not.toBeNull();
        const wb = new ExcelJS.Workbook();
        await wb.xlsx.load(capturedBuffer as ArrayBuffer);
        const ws = wb.getWorksheet("LIC-1");
        expect(ws).toBeDefined();

        // Balance is the 9th column for a DFIA sheet (Date, Particulars,
        // Items, CIF $ Dr, CIF $ Cr, Rate, Debit, Credit, Balance, P/L).
        const balanceCol = 9;
        const rows: string[] = [];
        ws!.eachRow((row) => {
            rows.push(String(row.getCell(2).value ?? "").concat("|", String(row.getCell(balanceCol).value ?? "")));
        });

        const purchaseRow = rows.find((r) => r.startsWith("Purchase"));
        const saleRow = rows.find((r) => r.startsWith("Sale"));
        const totalRow = rows.find((r) => r.startsWith("Total"));

        expect(purchaseRow?.split("|")[1]).toBe("500.00");
        expect(saleRow?.split("|")[1]).toBe("400.00");
        expect(totalRow?.split("|")[1]).toBe("400.00");
    });
});
