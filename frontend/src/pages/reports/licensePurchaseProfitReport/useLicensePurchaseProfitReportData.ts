import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import api from "@/api/axios";
import { openAuthedFile } from "@/utils/documentDownload";
import { buildLicensePurchaseProfitReportPath } from "./buildLicensePurchaseProfitReportPath";

export type LicensePurchaseProfitReportQuery = {
    fromDate: string;
    toDate: string;
    norm: string;
    licenseNumber: string;
    exporter: unknown;
};

/**
 * Fetches the License Purchase & Profit Report for the given (already
 * debounced/settled) filters, cancelling any in-flight request when the
 * filters change again before it resolves — same `AbortController` pattern
 * `ItemPivotReport.tsx`'s `reportAbortRef`/`loadReport` use, to avoid a slow
 * stale response overwriting a fresher one. Also exposes Excel/PDF export,
 * both routed through the authenticated blob-download helper so the JWT
 * never rides a bare `<a href>`/query-param link.
 */
export function useLicensePurchaseProfitReportData({ fromDate, toDate, norm, licenseNumber, exporter }: LicensePurchaseProfitReportQuery) {
    const [reportData, setReportData] = useState<Record<string, any> | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [downloading, setDownloading] = useState(false);

    const reportAbortRef = useRef<AbortController | null>(null);

    const hasQuery = Boolean(fromDate) && Boolean(toDate);

    const loadReport = useCallback(async () => {
        if (!hasQuery) return;

        if (reportAbortRef.current) {
            reportAbortRef.current.abort();
        }
        const controller = new AbortController();
        reportAbortRef.current = controller;

        setLoading(true);
        setError(null);
        try {
            const response = await api.get(
                buildLicensePurchaseProfitReportPath({ format: "json", fromDate, toDate, norm, licenseNumber, exporter }),
                { signal: controller.signal },
            );
            if (!controller.signal.aborted) {
                setReportData(response.data);
            }
        } catch (err: any) {
            // Axios names aborted requests 'CanceledError'; ignore them silently.
            if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED' || controller.signal.aborted) {
                return;
            }
            const message = err?.response?.data?.error || 'Failed to load report. Please try again.';
            toast.error(message);
            setError(message);
            setReportData(null);
        } finally {
            if (!controller.signal.aborted) {
                setLoading(false);
            }
        }
    }, [hasQuery, fromDate, toDate, norm, licenseNumber, exporter]);

    useEffect(() => {
        if (hasQuery) {
            loadReport();
        } else {
            setReportData(null);
            setError(null);
        }
    }, [hasQuery, loadReport]);

    const exportExcel = useCallback(async () => {
        setDownloading(true);
        try {
            await openAuthedFile(
                buildLicensePurchaseProfitReportPath({ format: "excel", fromDate, toDate, norm, licenseNumber, exporter }),
                "license-purchase-profit-report.xlsx",
            );
        } catch (err: any) {
            toast.error(err?.response?.data?.error || 'Failed to download report. Please try again.');
        } finally {
            setDownloading(false);
        }
    }, [fromDate, toDate, norm, licenseNumber, exporter]);

    const exportPdf = useCallback(async () => {
        setDownloading(true);
        try {
            await openAuthedFile(
                buildLicensePurchaseProfitReportPath({ format: "pdf", fromDate, toDate, norm, licenseNumber, exporter }),
                "license-purchase-profit-report.pdf",
            );
        } catch (err: any) {
            toast.error(err?.response?.data?.error || 'Failed to download report. Please try again.');
        } finally {
            setDownloading(false);
        }
    }, [fromDate, toDate, norm, licenseNumber, exporter]);

    return {
        reportData,
        loading,
        error,
        downloading,
        hasQuery,
        exportExcel,
        exportPdf,
    };
}
