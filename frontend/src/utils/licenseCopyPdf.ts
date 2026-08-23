import { toast } from "sonner";
import api from "../api/axios";
import { openPdfPreview } from "./pdfPreview";

/**
 * Canonical License Copy PDF opener — reused across all modules.
 *
 * Opens the License Copy PDF in a new browser tab.
 * Keeps the current page open and doesn't navigate.
 *
 * Used by: /licenses, /allotments, /bill-of-entries, etc.
 */
export async function openLicenseCopyPdf(licenseId: number, licenseNumber: string) {
    try {
        const r = await api.get(`licenses/${licenseId}/merged-documents/`, {
            responseType: "blob",
            headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
        });
        openPdfPreview(r.data as Blob, `${licenseNumber || licenseId}-documents.pdf`);
    } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 404) {
            toast.warning("Document files are not available on this server.");
        } else {
            toast.error("Failed to load license documents");
        }
    }
}
