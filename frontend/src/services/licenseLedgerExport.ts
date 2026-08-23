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
    const url = URL.createObjectURL(blob);
    try {
        const link = document.createElement("a");
        link.href = url;
        link.download = filename(scope, "xlsx");
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
