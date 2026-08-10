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

    it("shows the earliest purchase date and deduped SION norms on the LICENSE LEDGER SUMMARY sheet", async () => {
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
                            date: "2026-03-01", debit_amount: 1000, sion_norms: "E1",
                        },
                        // Earlier purchase, different invoice — the summary must
                        // report THIS date, not the first one encountered.
                        {
                            id: 2, type: "PURCHASE", particular: "Purchase", company_id: 7, company_name: "Acme",
                            date: "2026-01-15", debit_amount: 500, sion_norms: "E1, E5",
                        },
                        {
                            id: 3, type: "SALE", particular: "Sale", company_id: 7, company_name: "Acme",
                            date: "2026-04-01", credit_amount: 200, sion_norms: "E1",
                        },
                    ],
                },
            ],
            "test.xlsx",
        );

        expect(capturedBuffer).not.toBeNull();
        const wb = new ExcelJS.Workbook();
        await wb.xlsx.load(capturedBuffer as ArrayBuffer);
        const summary = wb.getWorksheet("Summary");
        expect(summary).toBeDefined();

        const headerRow = summary!.getRow(3).values as unknown[];
        expect(headerRow).toContain("1st Purchase Date");
        expect(headerRow).toContain("SION Norms");

        let licenseRow: import("exceljs").Row | null = null;
        summary!.eachRow((row) => {
            if (row.getCell(1).text === "LIC-1") licenseRow = row;
        });
        expect(licenseRow).not.toBeNull();
        // Columns: License Number(1), Type(2), Date(3), 1st Purchase Date(4), SION Norms(5), ...
        expect(licenseRow!.getCell(4).text).toBe("15-01-2026");
        expect(licenseRow!.getCell(5).text).toBe("E1, E5");
    });
});

describe("ledgerExport — Phase 4E-C Canonical Balance Usage", () => {
    /**
     * Helper: Create a canonical transaction with running balance
     */
    function createCanonicalTxn(overrides: any = {}): any {
        return {
            id: 1,
            date: "2026-01-15",
            type: "PURCHASE",
            company_id: 101,
            company_name: "Company A",
            amount: "500.00",
            is_commission: false,
            license_running_balance: "1500.00",  // ← CANONICAL BALANCE
            affects_balance: true,
            company_utilization_after: "500.00",
            display_status: "NORMAL",
            ...overrides,
        };
    }

    /**
     * Helper: Create a canonical ledger response
     */
    function createCanonicalLedger(overrides: any = {}): any {
        return {
            license_id: 1001,
            license_type: "DFIA",
            license_number: "LIC001",
            license_date: "2026-01-01",
            expiry_date: "2026-12-31",
            exporter_id: 5,
            exporter_name: "Acme Corp",
            port_id: 10,
            port_name: "Mumbai Port",

            opening_balance: "1000.00",
            license_running_balance: "1500.00",
            closing_balance: "1500.00",

            transactions: [
                createCanonicalTxn({
                    id: 0,
                    type: "OPENING",
                    amount: "1000.00",
                    license_running_balance: "1000.00",
                    company_id: null,
                    company_name: null,
                }),
                createCanonicalTxn({
                    id: 1,
                    type: "PURCHASE",
                    amount: "500.00",
                    license_running_balance: "1500.00",
                    company_id: 101,
                    company_name: "Company A",
                }),
            ],

            company_utilizations: {
                101: {
                    company_id: 101,
                    company_name: "Company A",
                    utilization_balance: "500.00",
                },
            },

            totals: {
                total_purchases: "500.00",
                total_sales: "0.00",
                total_commission: "0.00",
            },

            ...overrides,
        };
    }

    it("Phase 4E-C: Detects canonical ledger structure and preserves canonical balance", () => {
        const canonical = createCanonicalLedger();
        const normalized = normalizeLedgerLicensesData([canonical]);

        expect(normalized).toHaveLength(1);
        const license = normalized[0];
        // Canonical balance must be preserved (not recalculated)
        // Note: values converted to numbers for formatting, but source is canonical
        expect(license.available_balance).toBe(1500);
        expect(license.license_running_balance).toBe("1500.00");
    });

    it("Phase 4E-C: Maps canonical amount to debit_cif for DFIA PURCHASE", () => {
        const canonical = createCanonicalLedger({
            license_type: "DFIA",
            transactions: [
                createCanonicalTxn({
                    type: "PURCHASE",
                    amount: "750.00",
                    license_running_balance: "1750.00",
                }),
            ],
        });

        const normalized = normalizeLedgerLicensesData([canonical]);
        const txn = normalized[0].transactions[0];

        // Amounts stored as strings from canonical, but converted to numbers
        expect(txn.debit_cif).toBe("750.00");
        expect(txn.credit_cif).toBe("0");
        expect(txn.license_running_balance).toBe("1750.00");  // ← Canonical balance preserved
    });

    it("Phase 4E-C: Uses canonical balance (not independent calculation) for PURCHASE+SALE", () => {
        const canonical = createCanonicalLedger({
            opening_balance: "1000.00",
            transactions: [
                createCanonicalTxn({
                    id: 0,
                    type: "OPENING",
                    amount: "1000.00",
                    license_running_balance: "1000.00",
                    company_id: null,
                }),
                createCanonicalTxn({
                    id: 1,
                    type: "PURCHASE",
                    amount: "500.00",
                    license_running_balance: "1500.00",
                }),
                createCanonicalTxn({
                    id: 2,
                    type: "SALE",
                    amount: "200.00",
                    license_running_balance: "1300.00",  // ← CANONICAL (not 1500-200=1300 calculated)
                }),
            ],
            license_running_balance: "1300.00",
        });

        const normalized = normalizeLedgerLicensesData([canonical]);
        const license = normalized[0];

        expect(license.available_balance).toBe(1300);  // Numeric for display
        // Verify transaction balances come from canonical
        expect(license.transactions[2].license_running_balance).toBe("1300.00");  // ← Preserved from canonical
    });

    it("Phase 4E-C: Handles multiple companies with canonical balances", () => {
        const canonical = createCanonicalLedger({
            transactions: [
                createCanonicalTxn({
                    id: 1,
                    company_id: 101,
                    company_name: "Company A",
                    amount: "500.00",
                    license_running_balance: "1500.00",
                }),
                createCanonicalTxn({
                    id: 2,
                    company_id: 102,
                    company_name: "Company B",
                    amount: "300.00",
                    license_running_balance: "1800.00",
                }),
            ],
            license_running_balance: "1800.00",
        });

        const normalized = normalizeLedgerLicensesData([canonical]);
        const license = normalized[0];
        const companiesGrouped = groupByCompany(license.transactions);

        // Both companies should use canonical balances
        expect(companiesGrouped).toHaveLength(2);
        expect(companiesGrouped[0].transactions[0].license_running_balance).toBe("1500.00");
        expect(companiesGrouped[1].transactions[0].license_running_balance).toBe("1800.00");
    });

    it("Phase 4E-C: Preserves large decimal values from canonical API", () => {
        const canonical = createCanonicalLedger({
            transactions: [
                createCanonicalTxn({
                    license_running_balance: "12345678.90",
                }),
            ],
            license_running_balance: "12345678.90",
        });

        const normalized = normalizeLedgerLicensesData([canonical]);
        const license = normalized[0];

        expect(license.available_balance).toBe(12345678.90);  // Numeric for calculations
        expect(license.transactions[0].license_running_balance).toBe("12345678.90");  // ← Canonical preserved
    });

    it("Phase 4E-C: Maintains backward compatibility with legacy format", () => {
        // Legacy format (for backward compatibility)
        const legacy = {
            id: 1001,
            license_number: "LIC001",
            license_type: "DFIA",
            exporter: "Acme",
            available_balance: 400,
            transactions: [
                {
                    id: 1,
                    type: "PURCHASE",
                    debit_cif: 500,
                    debit_amount: 1000,
                    company_id: 101,
                    company_name: "Company A",
                },
            ],
        };

        const normalized = normalizeLedgerLicensesData([legacy]);
        expect(normalized).toHaveLength(1);
        expect(normalized[0].license_number).toBe("LIC001");
    });
});
