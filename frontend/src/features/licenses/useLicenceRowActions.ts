import { useCallback, useState, type MouseEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/api/axios";
import { autoPlanLicense } from "@/api/planningRuleApi";
import { invalidateLicence } from "@/lib/queryKeys";
import { openPdfPreview } from "@/utils/pdfPreview";
import { openAuthedFile } from "@/utils/documentDownload";

import type { LicenseListItem } from "./types";

export interface LicenceRowActionContext {
    entityName: string;
    filterParams: Record<string, unknown>;
    currentPage: number;
    pageSize: number;
    navigate: (path: string) => void;
}

function excelErrorMessage(err: unknown): string {
    if (err && typeof err === "object") {
        const apiError = (err as { response?: { data?: { error?: string } } }).response?.data?.error;
        if (apiError) return apiError;
        if ("message" in err) return String((err as { message: unknown }).message);
    }
    return "Failed to download Excel file";
}

/**
 * The register card's per-licence handlers, moved unchanged from LicensesTable:
 * same endpoints, payloads, toasts, filenames and invalidations.
 */
export function useLicenceRowActions(item: LicenseListItem, ctx: LicenceRowActionContext) {
    const queryClient = useQueryClient();
    const [isPlanning, setIsPlanning] = useState(false);
    const { navigate } = ctx;

    const openMergedDocuments = useCallback(async (e: MouseEvent) => {
        e.stopPropagation(); // never toggles the card
        if (!item.has_tl && !item.has_copy) return;
        try {
            const r = await api.get(`licenses/${item.id}/merged-documents/`, {
                responseType: "blob",
                headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
            });
            openPdfPreview(r.data as Blob, `${item.license_number || item.id}-documents.pdf`);
        } catch (err: unknown) {
            const status = (err as { response?: { status?: number } })?.response?.status;
            if (status === 404) toast.warning("Document files are not available on this server.");
            else toast.error("Failed to load license documents");
        }
    }, [item.id, item.license_number, item.has_tl, item.has_copy]);

    const openOverview = useCallback(() => {
        navigate(`/licenses/${item.id}/overview`);
    }, [navigate, item.id]);

    const autoPlan = useCallback(async () => {
        if (isPlanning) return;
        setIsPlanning(true);
        try {
            const result = await autoPlanLicense(item.id);
            const id = String(item.id);
            await Promise.all([
                invalidateLicence(queryClient, id),
                queryClient.invalidateQueries({ queryKey: ["entity-list", "licenses"] }),
            ]);
            toast.success(result.message || "Licence planning has completed.");
        } catch {
            toast.error("Failed to auto-plan licence.");
        } finally {
            setIsPlanning(false);
        }
    }, [isPlanning, item.id, queryClient]);

    const downloadPdf = useCallback(async () => {
        try {
            const r = await api.get(`licenses/${item.id}/balance-pdf/`, { responseType: "blob" });
            openPdfPreview(r.data as Blob, `${item.license_number || item.id}-balance.pdf`);
        } catch (err: unknown) {
            toast.error((err as { response?: { data?: { error?: string } } })?.response?.data?.error || "Failed to generate PDF");
        }
    }, [item.id, item.license_number]);

    const downloadExcel = useCallback(async () => {
        try {
            toast.info("Generating Excel file...");
            await openAuthedFile(`licenses/${item.id}/balance-excel/`, `${item.license_number || item.id}-balance.xlsx`);
            toast.success("Excel file downloaded successfully!");
        } catch (err: unknown) {
            console.error("Excel download error:", err);
            toast.error(excelErrorMessage(err));
        }
    }, [item.id, item.license_number]);

    return { isPlanning, openMergedDocuments, openOverview, autoPlan, downloadPdf, downloadExcel };
}
