import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import api from "@/api/axios";
import { openAuthedFile } from "@/utils/documentDownload";
import { buildLicenseTradingRegisterReportPath } from "./buildLicenseTradingRegisterReportPath";

export type LicenseTradingRegisterReportQuery = {
    fromDate: string;
    toDate: string;
    norm: string;
    licenseType: string;
    licenseNumber: string;
    exporter: unknown;
    item: unknown;
    customer: unknown;
    supplier: unknown;
};

/**
 * Fetches the License Trading Register & Profit Report for the given
 * (already debounced/settled) filters, cancelling any in-flight request
 * when the filters change again before it resolves — same `AbortController`
 * pattern `useLicensePurchaseProfitReportData.ts` uses, to avoid a slow
 * stale response overwriting a fresher one. Also exposes Excel/PDF export,
 * both routed through the authenticated blob-download helper so the JWT
 * never rides a bare `<a href>`/query-param link.
 */
export function useLicenseTradingRegisterReportData({
    fromDate,
    toDate,
    norm,
    licenseType,
    licenseNumber,
    exporter,
    item,
    customer,
    supplier,
}: LicenseTradingRegisterReportQuery) {
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
                buildLicenseTradingRegisterReportPath({
                    format: "json",
                    fromDate,
                    toDate,
                    norm,
                    licenseType,
                    licenseNumber,
                    exporter,
                    item,
                    customer,
                    supplier,
                }),
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
    }, [hasQuery, fromDate, toDate, norm, licenseType, licenseNumber, exporter, item, customer, supplier]);

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
                buildLicenseTradingRegisterReportPath({
                    format: "excel",
                    fromDate,
                    toDate,
                    norm,
                    licenseType,
                    licenseNumber,
                    exporter,
                    item,
                    customer,
                    supplier,
                }),
                "license-trading-register-profit-report.xlsx",
            );
        } catch (err: any) {
            toast.error(err?.response?.data?.error || 'Failed to download report. Please try again.');
        } finally {
            setDownloading(false);
        }
    }, [fromDate, toDate, norm, licenseType, licenseNumber, exporter, item, customer, supplier]);

    const exportPdf = useCallback(async () => {
        setDownloading(true);
        try {
            await openAuthedFile(
                buildLicenseTradingRegisterReportPath({
                    format: "pdf",
                    fromDate,
                    toDate,
                    norm,
                    licenseType,
                    licenseNumber,
                    exporter,
                    item,
                    customer,
                    supplier,
                }),
                "license-trading-register-profit-report.pdf",
            );
        } catch (err: any) {
            toast.error(err?.response?.data?.error || 'Failed to download report. Please try again.');
        } finally {
            setDownloading(false);
        }
    }, [fromDate, toDate, norm, licenseType, licenseNumber, exporter, item, customer, supplier]);

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
