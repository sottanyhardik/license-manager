import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import api from "@/api/axios";
import { openAuthedFile } from "@/utils/documentDownload";
import { buildItemReportProductsPath } from "../reportPaths";
import type { ReportFilterValues } from "./reportQueryString";
import type { ProductReport } from "./productTypes";

/** Loads the product-wise (Item Name × SION) report whenever the debounced filters change. */
export function useItemReportProducts(debouncedFilters: ReportFilterValues, enabled: boolean) {
    const [data, setData] = useState<ProductReport | null>(null);
    const [loading, setLoading] = useState(false);
    const [downloading, setDownloading] = useState(false);

    useEffect(() => {
        if (!enabled) return;
        let cancelled = false;
        setLoading(true);
        api.get(buildItemReportProductsPath({ format: "json", ...debouncedFilters }))
            .then((response) => { if (!cancelled) setData(response.data as ProductReport); })
            .catch(() => {
                if (cancelled) return;
                setData(null);
                toast.error("Failed to load product report. Please try again.");
            })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [debouncedFilters, enabled]);

    const exportExcel = useCallback(async (currentFilters: ReportFilterValues) => {
        setDownloading(true);
        try {
            await openAuthedFile(buildItemReportProductsPath({ format: "excel", ...currentFilters }), "item_report_products.xlsx");
        } catch {
            toast.error("Failed to download report. Please try again.");
        } finally {
            setDownloading(false);
        }
    }, []);

    return { data, loading, downloading, exportExcel };
}
