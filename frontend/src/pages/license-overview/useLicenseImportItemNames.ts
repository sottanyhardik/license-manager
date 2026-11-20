import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import { qk } from "@/lib/queryKeys";
import type {
    ImportItemNameChange,
    ImportItemNameHistoryEvent,
    ImportItemNamePreview,
    ImportItemNamePropagation,
    ImportItemNameRow,
    ImportItemNamesResponse,
} from "./types";

export const importItemNamesKey = (licenseId: string | number) =>
    qk.licenses.overview(String(licenseId), "import-item-names");

/** `GET /licenses/<id>/import-item-names/` — Item Name column of the Items tab. */
export function useLicenseImportItemNames(licenseId: string | number | undefined, isActive: boolean = true) {
    return useQuery<ImportItemNamesResponse>({
        queryKey: importItemNamesKey(licenseId ?? ""),
        queryFn: async () => (await api.get(`licenses/${licenseId}/import-item-names/`)).data,
        enabled: isActive && licenseId !== undefined && licenseId !== null && licenseId !== "",
    });
}

export interface SaveImportItemNamesResult {
    saved: number;
    unchanged: number;
    mapping_change?: unknown;
    rows: ImportItemNameRow[];
    propagation?: ImportItemNamePropagation[];
}

/** `POST /licenses/<id>/import-item-names/preview/` — what a global change would touch (no write). */
export async function previewImportItemNames(
    licenseId: string | number,
    changes: { import_item_id: number; item_id: number | null }[],
): Promise<ImportItemNamePreview[]> {
    const { data } = await api.post(`licenses/${licenseId}/import-item-names/preview/`, { changes });
    return (data as { previews: ImportItemNamePreview[] }).previews;
}

export async function saveImportItemNames(
    licenseId: string | number,
    changes: ImportItemNameChange[],
    reason?: string,
): Promise<SaveImportItemNamesResult> {
    const body: { changes: ImportItemNameChange[]; reason?: string } = { changes };
    if (reason) body.reason = reason;
    return (await api.post(`licenses/${licenseId}/import-item-names/save/`, body)).data;
}

export async function revertImportItemNames(licenseId: string | number, importItemIds: number[]) {
    const { data } = await api.post(`licenses/${licenseId}/import-item-names/revert/`, {
        import_item_ids: importItemIds,
    });
    return data as { reverted: number; reapplied?: number; rows: ImportItemNameRow[] };
}

export function useImportItemNameHistory(licenseId: string | number, importItemId: number, enabled: boolean) {
    return useQuery<{ events: ImportItemNameHistoryEvent[] }>({
        queryKey: [...importItemNamesKey(licenseId), "history", importItemId],
        queryFn: async () =>
            (await api.get(`licenses/${licenseId}/import-item-names/${importItemId}/history/`)).data,
        enabled,
        staleTime: 0,
    });
}
