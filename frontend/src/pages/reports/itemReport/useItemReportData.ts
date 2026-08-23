import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import api from "@/api/axios";
import { openAuthedFile } from "@/utils/documentDownload";
import type { ReportFilterValues, ReportQueryOptions } from "./reportQueryString";
import type { SelectOption } from "./useItemReportFilters";

export type ItemReportEditingCell = {
    itemId: unknown;
    field: "notes" | "condition_sheet";
} | null;

interface UseItemReportDataOptions {
    /** e.g. `buildItemReportPath` or `buildPlannedReportPath`. */
    buildPath: (options: ReportQueryOptions) => string;
    /** e.g. `item-report/available-items/` or `planned-report/available-items/`. */
    availableItemsPath: string;
    /** Debounced filters — changes to these (re)load the report. */
    debouncedFilters: ReportFilterValues;
    /** Filename used for the Excel export download. */
    exportFilename: string;
}

/**
 * Owns report data/loading/export state shared by Item Report and Planned
 * Report: fetching the report itself, the item-name dropdown options, Excel
 * export, and the Notes / Condition Sheet inline-edit-on-license flow (both
 * reports patch the same `licenses/{id}/` fields, identically).
 */
export function useItemReportData({ buildPath, availableItemsPath, debouncedFilters, exportFilename }: UseItemReportDataOptions) {
    const [reportData, setReportData] = useState<Record<string, any> | null>(null);
    const [loading, setLoading] = useState(false);
    const [downloading, setDownloading] = useState(false);
    const [itemNameOptions, setItemNameOptions] = useState<SelectOption[]>([]);

    // Inline edit state — Notes / Condition Sheet (shared by both reports).
    const [editingCell, setEditingCell] = useState<ItemReportEditingCell>(null);
    const [editValue, setEditValue] = useState("");

    useEffect(() => {
        let isMounted = true;

        const fetchItems = async () => {
            try {
                const response = await api.get(availableItemsPath);
                const items = response.data || [];
                if (isMounted) {
                    setItemNameOptions(items.map((item: any) => ({value: item.id, label: item.name})));
                }
            } catch {
                if (isMounted) {
                    setItemNameOptions([]);
                }
            }
        };

        fetchItems();

        return () => {
            isMounted = false;
        };
    }, [availableItemsPath]);

    const loadReport = useCallback(async () => {
        setLoading(true);
        try {
            const response = await api.get(buildPath({format: "json", ...debouncedFilters}));
            setReportData(response.data);
        } catch {
            toast.error('Failed to load report. Please try again.');
            setReportData(null);
        } finally {
            setLoading(false);
        }
    }, [buildPath, debouncedFilters]);

    useEffect(() => {
        if ((debouncedFilters.selectedItemNames?.length ?? 0) > 0 || debouncedFilters.productDescSearch || debouncedFilters.hsnCodeSearch) {
            loadReport();
        } else {
            setReportData(null);
        }
    }, [debouncedFilters, loadReport]);

    const handleExport = useCallback(async (currentFilters: ReportFilterValues) => {
        setDownloading(true);
        try {
            await openAuthedFile(buildPath({format: "excel", ...currentFilters}), exportFilename);
        } catch {
            toast.error('Failed to download report. Please try again.');
        } finally {
            setDownloading(false);
        }
    }, [buildPath, exportFilename]);

    const startEdit = useCallback((itemId: unknown, field: "notes" | "condition_sheet", currentValue: string) => {
        setEditingCell({itemId, field});
        setEditValue(currentValue || "");
    }, []);

    const cancelEdit = useCallback(() => {
        setEditingCell(null);
        setEditValue("");
    }, []);

    const saveEdit = useCallback(async (item: any) => {
        if (!editingCell) return;

        const {field} = editingCell;

        try {
            // Update notes or condition_sheet on the license
            const updateData: Record<string, any> = {};
            if (field === 'notes') {
                updateData.balance_report_notes = editValue;
            } else if (field === 'condition_sheet') {
                updateData.condition_sheet = editValue;
            }
            await api.patch(`licenses/${item.license_id}/`, updateData);

            toast.success('Updated successfully');
            setEditingCell(null);
            setEditValue("");

            // Update only the current row instead of reloading entire report
            setReportData((prev) => {
                if (!prev) return prev;
                const updatedItems = prev.items.map((i: any) => {
                    if (i.id === item.id) {
                        return {
                            ...i,
                            notes: field === 'notes' ? editValue : i.notes,
                            condition_sheet: field === 'condition_sheet' ? editValue : i.condition_sheet,
                        };
                    }
                    return i;
                });
                return {...prev, items: updatedItems};
            });
        } catch {
            toast.error('Failed to update. Please try again.');
        }
    }, [editingCell, editValue]);

    return {
        reportData,
        setReportData,
        loading,
        downloading,
        itemNameOptions,
        loadReport,
        handleExport,
        editingCell,
        editValue,
        setEditValue,
        startEdit,
        cancelEdit,
        saveEdit,
    };
}
