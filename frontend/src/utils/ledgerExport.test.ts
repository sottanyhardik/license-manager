import { describe, expect, it } from "vitest";

import {
    buildLicenseLedgerUrl,
    groupByCompany,
    normalizeLedgerLicensesData,
    sanitizeExportFilename,
    sanitizeWorksheetName,
} from "./ledgerExport";

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
});
