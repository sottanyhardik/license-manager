import api from "../api/axios";

export type LicenseLedgerExportScope = {
    params?: URLSearchParams;
    licenseId?: string | number;
    itemId?: string | number;
    licenseType?: string;
};

function exportParams(scope: LicenseLedgerExportScope, format: "pdf" | "xlsx"): URLSearchParams {
    const params = new URLSearchParams(scope.params);
    params.set("file_format", format);
    if (scope.licenseId != null) params.set("license_id", String(scope.licenseId));
    if (scope.itemId != null) params.set("item_id", String(scope.itemId));
    if (scope.licenseType) params.set("license_type", scope.licenseType);
    return params;
}

function filename(scope: LicenseLedgerExportScope, extension: "pdf" | "xlsx"): string {
    const parts = ["license-ledger", scope.licenseId, scope.itemId]
        .filter(value => value !== undefined && value !== null && String(value).trim())
        .map(value => String(value).replace(/[^a-zA-Z0-9_-]+/g, "-"));
    return `${parts.join("-")}.${extension}`;
}

export async function previewLicenseLedgerPdf(scope: LicenseLedgerExportScope): Promise<void> {
    // Open synchronously from the click event so browsers do not classify the
    // eventual authenticated blob navigation as an unsolicited popup.
    const preview = window.open("", "_blank");
    if (!preview) throw new Error("PDF preview was blocked. Allow popups and try again.");
    preview.opener = null;
    preview.document.title = "Generating License Ledger PDF…";

    try {
        const response = await api.get(`license-ledger/export/?${exportParams(scope, "pdf")}`, { responseType: "blob" });
        const blob = response.data instanceof Blob
            ? response.data
            : new Blob([response.data], { type: "application/pdf" });
        if (!blob.size) throw new Error("The PDF export was empty.");
        const url = URL.createObjectURL(blob);
        preview.location.replace(`${url}#zoom=100`);
        // The new tab owns the blob. Delay revocation so its native viewer can read it.
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
        preview.close();
        throw error;
    }
}

export async function downloadLicenseLedgerExcel(scope: LicenseLedgerExportScope): Promise<void> {
    const response = await api.get(`license-ledger/export/?${exportParams(scope, "xlsx")}`, { responseType: "blob" });
    const blob = response.data instanceof Blob
        ? response.data
        : new Blob([response.data], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    if (!blob.size) throw new Error("The Excel export was empty.");
    const objectUrl = URL.createObjectURL(blob);
    try {
        const link = document.createElement("a");
        link.href = objectUrl;
        link.download = filename(scope, "xlsx");
        document.body.appendChild(link);
        link.click();
        link.remove();
    } finally {
        setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    }
}

export type LicenseLedgerPackageAudit = {
    expected_purchase_invoices?: number; included_purchase_invoices?: number;
    expected_final_party_sales_invoices?: number; included_final_party_sales_invoices?: number;
    excluded_interlinked_sales_invoices?: number; expected_pdf_pages?: number; actual_pdf_pages?: number;
    server_validation?: "passed" | "failed" | string;
    final_party_sales_invoice_numbers?: string[]; excluded_interlinked_sale_ids?: Array<string | number>;
};
export type LicenseLedgerPackageJob = { job_id: string; status: string; total: number; queued: number; running: number; completed: number; failed: number; percentage: number; status_url: string; download_url: string | null; licences?: Array<{ id: number; license_id?: number; licence_number: string; status: string; completed_at?: string | null; error?: string; download_url?: string | null; filename?: string; size?: number | null; sha256?: string | null; audit?: LicenseLedgerPackageAudit }> };

export async function createLicenseLedgerPackage(licenseIds: Array<string | number>, idempotencyKey?: string, clientJobKey?: string): Promise<LicenseLedgerPackageJob> {
    const payload = { license_ids: licenseIds, ...(clientJobKey ? { client_job_key: clientJobKey } : {}) };
    const response = idempotencyKey
        ? await api.post("license-ledger/download-package/", payload, { headers: { "Idempotency-Key": idempotencyKey } })
        : await api.post("license-ledger/download-package/", payload);
    return response.data;
}

/** API clients already have `/api/` as their base URL; server links are absolute API paths. */
export const relativeApiUrl = (url: string) => url.replace(/^\/api\//, "");

async function downloadPackageUrl(url: string, fallback: string): Promise<void> {
    const response = await api.get(relativeApiUrl(url), { responseType: "blob" });
    const blob = response.data instanceof Blob ? response.data : new Blob([response.data], { type: "application/zip" });
    if (!blob.size) throw new Error("The package export was empty.");
    const disposition = String(response.headers?.["content-disposition"] ?? "");
    const matched = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(disposition);
    const objectUrl = URL.createObjectURL(blob);
    try {
        const link = document.createElement("a");
        link.href = objectUrl;
        link.download = matched?.[1] ? decodeURIComponent(matched[1]) : fallback;
        document.body.appendChild(link);
        link.click();
        link.remove();
    } finally {
        setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    }
}

export const downloadLicenseLedgerPackage = (url: string) => downloadPackageUrl(url, "license-ledger-package.zip");
export const retryLicenseLedgerPackage = async (jobId: string) => (await api.post(`license-ledger/download-package/${jobId}/retry/`)).data as LicenseLedgerPackageJob;

export async function downloadMergedLicenseLedgerPackage(licenseIds: Array<string | number>): Promise<void> {
    const response = await api.post("license-ledger/download-package-pdf/", { license_ids: licenseIds }, { responseType: "blob" });
    const blob = response.data instanceof Blob ? response.data : new Blob([response.data], { type: "application/pdf" });
    const disposition = String(response.headers?.["content-disposition"] ?? "");
    const matched = /filename\*?=(?:UTF-8''|\")?([^\";]+)/i.exec(disposition);
    const url = URL.createObjectURL(blob);
    try {
        const link = document.createElement("a"); link.href = url; link.download = matched?.[1] ? decodeURIComponent(matched[1]) : `${licenseIds[0]}.pdf`;
        document.body.appendChild(link); link.click(); link.remove();
    } finally { setTimeout(() => URL.revokeObjectURL(url), 60_000); }
}

export async function downloadCustomLedgerPdf(licenseId: string | number): Promise<void> {
    const response = await api.get(`license-ledger/${licenseId}/custom-ledger-pdf/?license_type=DFIA`, { responseType: "blob" });
    const blob = response.data instanceof Blob ? response.data : new Blob([response.data], { type: "application/pdf" });
    if (!blob.size) throw new Error("The Custom Ledger PDF was empty.");
    const disposition = String(response.headers?.["content-disposition"] ?? "");
    const matched = /filename="?([^";]+)"?/i.exec(disposition);
    const url = URL.createObjectURL(blob);
    try {
        const link = document.createElement("a");
        link.href = url;
        link.download = matched?.[1] ?? `${licenseId}-customs-ledger.pdf`;
        document.body.appendChild(link);
        link.click();
        link.remove();
    } finally {
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
    }
}

export function licenseLedgerExportError(error: unknown, fallback: string): string {
    if (typeof error === "object" && error !== null && "response" in error) {
        const response = (error as { response?: { data?: unknown } }).response;
        const data = response?.data;
        if (typeof data === "object" && data !== null) {
            const record = data as Record<string, unknown>;
            const message = record.error ?? record.detail ?? record.message;
            if (message) return String(message);
        }
    }
    return error instanceof Error && error.message ? error.message : fallback;
}
