import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import api from "@/api/axios";
import { openAuthedFile } from "@/utils/documentDownload";
import { getReportErrorInfo } from "@/utils/reportErrorHandling";
import { buildLicensePurchaseProfitReportPath } from "./buildLicensePurchaseProfitReportPath";

export type LicensePurchaseProfitReportQuery = {
    fromDate: string;
    toDate: string;
    norm: string;
    licenseNumber: string;
    excludeLicenseNumber: string[];
    exporter: unknown;
};

/** Auto-retry delay for a transient (network/5xx) failure — one retry only,
 * then the friendly error banner takes over. */
const RETRY_DELAY_MS = 2500;

/**
 * Fetches the License Purchase & Profit Report — auto-fetches whenever the
 * (debounced) filter values change, no explicit "Apply"/"Generate" action.
 * Cancels any in-flight request when a new one starts — same
 * `AbortController` pattern `ItemPivotReport.tsx`'s `reportAbortRef` uses,
 * to avoid a slow stale response overwriting a fresher one.
 *
 * Tracks `isInitialLoading` (fetching with no previous result — shows a
 * skeleton table) separately from `isRefetching` (fetching while a
 * previous result is still on screen — keeps it visible under a thin
 * progress bar instead of blanking the page). On a transient failure (no
 * `response` at all, or a 5xx) the first failure for a given request
 * retries once automatically after ~2.5s before surfacing the friendly
 * error from `getReportErrorInfo`; a 4xx surfaces immediately, no retry.
 *
 * Also exposes Excel/PDF export, both routed through the authenticated
 * blob-download helper so the JWT never rides a bare `<a href>`/query-param
 * link. Each export follows the same retry-once-on-transient-failure shape
 * as `load()` above (one retry after `RETRY_DELAY_MS` on a missing
 * `response` or a 5xx, immediate toast on a definitive 4xx) — but as a
 * recursive async call scoped to that single button click rather than an
 * effect, since exports are user-triggered, not filter-driven.
 */
export function useLicensePurchaseProfitReportData({ fromDate, toDate, norm, licenseNumber, excludeLicenseNumber, exporter }: LicensePurchaseProfitReportQuery) {
    const [reportData, setReportData] = useState<Record<string, any> | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [downloading, setDownloading] = useState(false);
    // Bumped by `refetch()` to re-run the fetch effect for an identical
    // filter set (the error banner's manual "Retry" button).
    const [retryToken, setRetryToken] = useState(0);

    const reportAbortRef = useRef<AbortController | null>(null);

    const canApply = Boolean(fromDate) && Boolean(toDate);

    useEffect(() => {
        if (!canApply) return undefined;

        if (reportAbortRef.current) {
            reportAbortRef.current.abort();
        }
        const controller = new AbortController();
        reportAbortRef.current = controller;

        // True once this effect run has already retried once — closed over
        // by `load`, which may call itself again after the retry delay.
        let hasRetried = false;

        const load = async () => {
            setLoading(true);
            setError(null);
            try {
                const response = await api.get(
                    buildLicensePurchaseProfitReportPath({ format: "json", fromDate, toDate, norm, licenseNumber, excludeLicenseNumber, exporter }),
                    { signal: controller.signal },
                );
                if (!controller.signal.aborted) {
                    setReportData(response.data);
                    setLoading(false);
                }
            } catch (err: any) {
                // Axios names aborted requests 'CanceledError'; ignore them silently.
                if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED' || controller.signal.aborted) {
                    return;
                }
                const { message, retryable } = getReportErrorInfo(err);
                if (retryable && !hasRetried) {
                    hasRetried = true;
                    setTimeout(() => {
                        if (!controller.signal.aborted) {
                            load();
                        }
                    }, RETRY_DELAY_MS);
                    return;
                }
                toast.error(message);
                setError(message);
                setLoading(false);
            }
        };

        load();

        return () => {
            controller.abort();
        };
    }, [canApply, fromDate, toDate, norm, licenseNumber, excludeLicenseNumber, exporter, retryToken]);

    const refetch = useCallback(() => {
        setRetryToken((t) => t + 1);
    }, []);

    const resetReport = useCallback(() => {
        if (reportAbortRef.current) {
            reportAbortRef.current.abort();
        }
        setReportData(null);
        setError(null);
        setLoading(false);
    }, []);

    const exportExcel = useCallback(async () => {
        setDownloading(true);
        // Scoped to this single invocation (not a ref) — a fresh click gets
        // its own retry budget, same one-retry-then-surface shape as `load()`.
        let hasRetried = false;
        const attempt = async (): Promise<void> => {
            try {
                await openAuthedFile(
                    buildLicensePurchaseProfitReportPath({ format: "excel", fromDate, toDate, norm, licenseNumber, excludeLicenseNumber, exporter }),
                    "license-purchase-profit-report.xlsx",
                );
            } catch (err: unknown) {
                const { message, retryable } = getReportErrorInfo(err, { action: "generate the Excel export" });
                if (retryable && !hasRetried) {
                    hasRetried = true;
                    await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
                    return attempt();
                }
                toast.error(message);
            }
        };
        try {
            await attempt();
        } finally {
            setDownloading(false);
        }
    }, [fromDate, toDate, norm, licenseNumber, excludeLicenseNumber, exporter]);

    const exportPdf = useCallback(async () => {
        setDownloading(true);
        // Scoped to this single invocation (not a ref) — a fresh click gets
        // its own retry budget, same one-retry-then-surface shape as `load()`.
        let hasRetried = false;
        const attempt = async (): Promise<void> => {
            try {
                await openAuthedFile(
                    buildLicensePurchaseProfitReportPath({ format: "pdf", fromDate, toDate, norm, licenseNumber, excludeLicenseNumber, exporter }),
                    "license-purchase-profit-report.pdf",
                );
            } catch (err: unknown) {
                const { message, retryable } = getReportErrorInfo(err, { action: "generate the PDF export" });
                if (retryable && !hasRetried) {
                    hasRetried = true;
                    await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
                    return attempt();
                }
                toast.error(message);
            }
        };
        try {
            await attempt();
        } finally {
            setDownloading(false);
        }
    }, [fromDate, toDate, norm, licenseNumber, excludeLicenseNumber, exporter]);

    const isInitialLoading = loading && reportData === null;
    const isRefetching = loading && reportData !== null;

    return {
        reportData,
        isInitialLoading,
        isRefetching,
        error,
        downloading,
        canApply,
        refetch,
        resetReport,
        exportExcel,
        exportPdf,
    };
}
