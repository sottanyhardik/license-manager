/**
 * Standardized export filename convention — mirrors
 * `backend/apps/core/reports/export_naming.py`'s `build_export_filename`.
 *
 * The backend's `Content-Disposition` header is NOT what the browser
 * actually saves the file as here: `openAuthedFile` (see
 * `utils/documentDownload.ts`) fetches the export as a Blob (to attach the
 * auth header) and sets `<a download>` explicitly, which browsers use over
 * any header on a blob: URL. So the filename must be decided client-side —
 * this helper keeps that name consistent with the backend's own convention
 * instead of each report inventing its own ad hoc string.
 */
export function buildExportFilename(
    reportSlug: string,
    ext: string,
    range?: { fromDate?: string | null; toDate?: string | null },
): string {
    const { fromDate, toDate } = range ?? {};
    let stamp: string;
    if (fromDate && toDate) {
        stamp = fromDate === toDate ? fromDate : `${fromDate}_to_${toDate}`;
    } else if (fromDate) {
        stamp = fromDate;
    } else {
        stamp = new Date().toISOString().slice(0, 10);
    }
    return `${reportSlug}_${stamp}.${ext}`;
}
