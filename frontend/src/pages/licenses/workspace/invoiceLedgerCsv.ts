/**
 * CSV export of the rows currently shown on the Invoices & Sales tab. Cells
 * hold the same display strings the table shows, so the file matches the screen.
 */
import { formatCifAmount, formatInrAmount, formatLedgerDate } from "./invoiceLedgerFormat";
import type { LedgerRow } from "./types";

export interface ExportLedgerRow {
  company: string;
  row: LedgerRow;
}

/** Spreadsheet programs run a cell that starts with these as a formula. Such text is prefixed with an apostrophe. */
const FORMULA_START = /^[=+@\t\r]/;

function csvCell(value: string): string {
  const guarded = FORMULA_START.test(value) ? `'${value}` : value;
  return /[",\r\n]/.test(guarded) ? `"${guarded.replace(/"/g, '""')}"` : guarded;
}

/** Builds the CSV text. Rows are written in the order given. */
export function buildLedgerCsv(rows: readonly ExportLedgerRow[], currency: string): string {
  const header = [
    "Company",
    "Date",
    "Particulars",
    "Invoice",
    "Type",
    "Items",
    `Sale (${currency})`,
    `Purchase (${currency})`,
    "Sale Bill (₹)",
    "Purchase Bill (₹)",
    "Status",
  ];
  const lines = rows.map(({ company, row }) =>
    [
      company,
      formatLedgerDate(row.date),
      row.particulars,
      row.invoice,
      row.type,
      row.items,
      formatCifAmount(row.sale_cif),
      formatCifAmount(row.purchase_cif),
      formatInrAmount(row.sale_bill_inr),
      formatInrAmount(row.purchase_bill_inr),
      row.status,
    ].map(csvCell).join(","),
  );
  return [header.map(csvCell).join(","), ...lines].join("\r\n");
}

/** `licence-{licence_number}-invoices.csv`, or `licence-{id}-invoices.csv` when the number is unknown. */
export function ledgerExportFileName(licenceNumber: string | null | undefined, licenceId: number): string {
  const safeNumber = (licenceNumber ?? "").trim().replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
  return safeNumber ? `licence-${safeNumber}-invoices.csv` : `licence-${licenceId}-invoices.csv`;
}

/** Starts a browser download of the CSV text. A UTF-8 byte-order mark keeps ₹ intact when opened in a spreadsheet. */
export function downloadLedgerCsv(fileName: string, content: string): void {
  const blob = new Blob(["﻿", content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
