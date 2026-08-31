import api from "../api/axios";
import { relativeApiUrl } from "./licenseLedgerExport";

export type ReadinessRow = Record<string, unknown>;
export type PackageReadiness = {
    job_id: string;
    summary?: Record<string, unknown>;
    missing_purchases?: ReadinessRow[];
    orphan_candidates?: ReadinessRow[];
    unknown_sales?: ReadinessRow[];
    resolved?: ReadinessRow[];
    csv_urls?: Record<string, string>;
};

const base = (jobId: string) => `license-ledger/download-package/${jobId}/readiness/`;

export async function getPackageReadiness(jobId: string): Promise<PackageReadiness> {
    return (await api.get(base(jobId))).data;
}

/** The server owns the audit trail and authorization checks for every change. */
export async function postReadinessAction(jobId: string, action: string, body: unknown): Promise<void> {
    await api.post(`${base(jobId)}${action.replace(/^\//, "")}/`, body);
}

export async function decideSaleClassification(saleId: string | number, body: { decision: string; reason: string; provenance: string }): Promise<void> {
    await api.post(`trades/${saleId}/sales-classification-review/`, body);
}

export async function uploadPurchaseDocument(jobId: string, tradeId: string | number, file: File, note?: string): Promise<void> {
    const form = new FormData(); form.append("file", file); if (note) form.append("note", note);
    await api.post(`${base(jobId)}purchase-trades/${tradeId}/upload/`, form, { headers: { "Content-Type": "multipart/form-data" } });
}

export async function recoverUniqueOrphan(jobId: string, tradeId: string | number, sourceStorageKey: string, evidence: Record<string, unknown>): Promise<void> {
    await api.post(`${base(jobId)}purchase-trades/${tradeId}/recover-orphan/`, { source_storage_key: sourceStorageKey, evidence });
}

/** CSVs are explicit review exports, not package PDF downloads. */
export async function downloadReadinessCsv(url: string): Promise<void> {
    const response = await api.get(relativeApiUrl(url), { responseType: "blob" });
    const blob = response.data instanceof Blob ? response.data : new Blob([response.data], { type: "text/csv" });
    if (!blob.size) throw new Error("The review export was empty.");
    const link = document.createElement("a");
    const objectUrl = URL.createObjectURL(blob);
    link.href = objectUrl;
    link.download = url.split("/").filter(Boolean).pop() || "package-readiness.csv";
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}
