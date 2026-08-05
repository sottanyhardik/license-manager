/**
 * Generic axios/fetch error -> friendly report-loading message mapper.
 *
 * `retryable` is true for anything that looks transient — no `response` at
 * all (network drop, timeout, CORS preflight failure) or a 5xx from the
 * server — and false for a definitive 4xx (bad filters, validation error,
 * auth), which should surface immediately instead of being retried.
 *
 * Deliberately report-agnostic (no imports from any specific report's
 * files) so other report pages can adopt the same mapping later without
 * rewriting it; today it's only wired into the License Purchase & Profit
 * Report's data hook.
 */

export type ReportErrorInfo = {
    message: string;
    retryable: boolean;
};

const RETRYABLE_MESSAGE =
    "Unable to load the report. The server is temporarily busy. Please try again in a few seconds.";
const GENERIC_MESSAGE = "Something went wrong loading the report.";

export function getReportErrorInfo(err: unknown): ReportErrorInfo {
    const response = (err as { response?: { status?: number; data?: { error?: unknown } } } | undefined)?.response;
    const status = response?.status;
    const retryable = !response || (typeof status === "number" && status >= 500);

    if (retryable) {
        return { message: RETRYABLE_MESSAGE, retryable: true };
    }

    const backendMessage = response?.data?.error;
    const message = typeof backendMessage === "string" && backendMessage.trim() ? backendMessage : GENERIC_MESSAGE;
    return { message, retryable: false };
}
