export type LedgerTaskRef = { task_id: string; license: string };
export type LedgerFileTask = { file: string; total: number; tasks: LedgerTaskRef[] };
export type LedgerUploadError = { file: string; error: string };
const MAX_ERROR_DETAILS = 10;
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null;
const normalizeText = (value: unknown, fallback: string): string => String(value ?? "").trim() || fallback;
export function normalizeLedgerFileTasks(value: unknown): LedgerFileTask[] { if (!Array.isArray(value)) return []; return value.flatMap((fileEntry, fileIndex) => { if (!isRecord(fileEntry) || !Array.isArray(fileEntry.tasks)) return []; const seen = new Set<string>(); const tasks = fileEntry.tasks.flatMap((entry) => { if (!isRecord(entry)) return []; const id = String(entry.task_id ?? "").trim(); if (!id || seen.has(id)) return []; seen.add(id); return [{ task_id: id, license: normalizeText(entry.license, "Unknown license") }]; }); return tasks.length ? [{ file: normalizeText(fileEntry.file, `File ${fileIndex + 1}`), total: tasks.length, tasks }] : []; }); }
export function normalizeLedgerUploadErrors(value: unknown): LedgerUploadError[] { return !Array.isArray(value) ? [] : value.flatMap((entry, index) => isRecord(entry) ? [{ file: normalizeText(entry.file, `File ${index + 1}`), error: normalizeText(entry.error, "Unknown upload error") }] : []); }
export function buildAsyncUploadErrorMessage(errors: LedgerUploadError[]): string { const shown = errors.slice(0, MAX_ERROR_DETAILS).map((error) => `${error.file}: ${error.error}`).join("; "); const remaining = errors.length > MAX_ERROR_DETAILS ? `; ${errors.length - MAX_ERROR_DETAILS} more not shown` : ""; return `${errors.length} file(s) failed: ${shown}${remaining}`; }
export function getLedgerUploadErrorMessage(error: unknown): string { if (isRecord(error) && isRecord(error.response) && isRecord(error.response.data)) { const detail = error.response.data.error ?? error.response.data.detail ?? error.response.data.message; if (detail) return normalizeText(detail, "Upload failed. Please try again."); } return error instanceof Error ? normalizeText(error.message, "Upload failed. Please try again.") : "Upload failed. Please try again."; }
export function normalizeProgressValue(value: unknown): number { const progress = Number(value); return Number.isFinite(progress) ? Math.min(100, Math.max(0, Math.round(progress))) : 0; }

// ---- Presentation helpers (derive display values only; never alter what the server reported) ----

/** Single source for the picker `accept`, the hook's client-side type check and the on-page guidance. */
export const LEDGER_ACCEPT = ".csv,.htm,.html";
export const LEDGER_MAX_FILE_BYTES = 50 * 1024 * 1024;
export const LEDGER_MAX_FILE_MB = LEDGER_MAX_FILE_BYTES / (1024 * 1024);
export const LEDGER_ACCEPTED_EXTENSIONS: string[] = LEDGER_ACCEPT.split(",");

export type FailedLicense = { license: string; error: string };

/** One entry of the upload hook's `results` (sync mode: one request per file). */
export type LedgerSyncResult = {
    fileName?: string;
    success: boolean;
    message?: string;
    error?: string;
    licenses?: string[];
    stats?: { total_licenses?: number };
    data?: { results?: Array<{ failed?: Array<{ license?: unknown; error?: unknown }> }> };
};

/** Licences the server reported as failed for this file (`results[0].failed`), verbatim. */
export function getFailedLicenses(result: LedgerSyncResult): FailedLicense[] {
    const failed = result.data?.results?.[0]?.failed;
    if (!Array.isArray(failed)) return [];
    return failed.map((entry) => ({
        license: normalizeText(entry?.license, "Unknown"),
        error: normalizeText(entry?.error, "Unknown error"),
    }));
}

export type LedgerResultSummary = {
    files: number;
    filesSucceeded: number;
    filesFailed: number;
    licensesImported: number;
    licensesFailed: number;
};

export function summarizeLedgerResults(results: LedgerSyncResult[]): LedgerResultSummary {
    return results.reduce<LedgerResultSummary>((acc, result) => ({
        files: acc.files + 1,
        filesSucceeded: acc.filesSucceeded + (result.success ? 1 : 0),
        filesFailed: acc.filesFailed + (result.success ? 0 : 1),
        licensesImported: acc.licensesImported + (result.licenses?.length ?? 0),
        licensesFailed: acc.licensesFailed + getFailedLicenses(result).length,
    }), { files: 0, filesSucceeded: 0, filesFailed: 0, licensesImported: 0, licensesFailed: 0 });
}
