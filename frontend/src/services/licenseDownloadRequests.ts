import api from "@/api/axios";

export const safeCount = (value: unknown): number => {
    const parsed = Number(value); return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
};
export type DownloadRequest = { id: string; request_key: string; status: string; requested_count: number; queued_count: number; processing_count: number; server_ready_count: number; blocked_count: number; failed_count: number; created_at: string; created_by: string; zip_ready: boolean; zip_download_url?: string | null; items?: DownloadItem[] };
export type DownloadItem = { id: number; licence_number: string; license_id: number; status: string; purchase_expected_count: number; purchase_included_count: number; sales_expected_count: number; sales_included_count: number; interlinked_sales_excluded_count: number; page_count: number; size: number; download_url?: string | null; draft_download_url?: string | null; error?: string | null; remarks?: string[]; blocking_reason_codes: string[] };
export async function getDownloadRequests(params = "") { return (await api.get(`license-ledger/download-requests/${params ? `?${params}` : ""}`)).data as { results: DownloadRequest[]; count: number }; }
export async function getDownloadRequest(id: string) { return (await api.get(`license-ledger/download-requests/${id}/`)).data as DownloadRequest; }
export async function retryDownloadRequest(id: string) { return (await api.post(`license-ledger/download-requests/${id}/retry/`)).data as DownloadRequest; }
export async function createDownloadRequest(license_ids: Array<string | number>, idempotency_key: string) { return (await api.post("license-ledger/download-requests/", { license_ids, idempotency_key }, { headers: { "Idempotency-Key": idempotency_key } })).data as DownloadRequest; }
/** Download through Axios so bearer/session authentication reaches Django.
 * A plain <a href="/api/..."> cannot include the app's bearer token. */
export async function downloadUrl(url: string, filename: string): Promise<void> {
    const response = await api.get(url.replace(/^\/api\//, ""), { responseType: "blob" });
    const blob = response.data instanceof Blob ? response.data : new Blob([response.data], { type: "application/pdf" });
    if (!blob.size) throw new Error("The server returned an empty download.");
    const disposition = String(response.headers?.["content-disposition"] ?? "");
    const matched = /filename\*?=(?:UTF-8''|\")?([^\";]+)/i.exec(disposition);
    const objectUrl = URL.createObjectURL(blob);
    try {
        const link = document.createElement("a");
        link.href = objectUrl;
        link.download = matched?.[1] ? decodeURIComponent(matched[1]) : filename;
        document.body.appendChild(link); link.click(); link.remove();
    } finally { setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000); }
}
