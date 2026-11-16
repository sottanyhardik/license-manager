import { useCallback, useContext } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { invalidateLicence, qk } from "@/lib/queryKeys";
import { buildLicenseEndpoint, normalizeUsageData } from "@/components/licenseBalanceHelpers";
import { ROLES } from "../../routes/authorizationRoles";

/**
 * Doc 06 D3 option (c): features ported from `LicenseBalanceModal` into the
 * overview workspace. Same endpoints and PATCH payloads as the modal; cache
 * refresh goes through `invalidateLicence` (shared `licenses/:id` prefix)
 * instead of the modal's local state patching.
 */

type Id = string | number;
type ApiError = { response?: { data?: { detail?: string; error?: string; condition_type?: string[] } } };

export type LicenceTextField = "condition_sheet" | "balance_report_notes";
export type UsageType = "import" | "export";

export interface ItemUsageBoe {
    id: number;
    bill_of_entry_number?: string | null;
    date?: string | null;
    port?: string | null;
    company?: string | null;
    quantity?: number | string | null;
    cif_fc?: number | string | null;
    cif_inr?: number | string | null;
}

export interface ItemUsageAllotment {
    id: number;
    company?: string | null;
    quantity?: number | string | null;
    cif_fc?: number | string | null;
    cif_inr?: number | string | null;
}

export interface ItemUsage {
    boes: ItemUsageBoe[];
    allotments: ItemUsageAllotment[];
}

/**
 * The modal is only reachable from MasterForm, whose `/licenses/:id/edit`
 * route requires `LICENSE_MANAGER`; that is the writer gate reused here.
 */
export function useCanEditLicence(): boolean {
    const { hasRole } = useContext(AuthContext);
    return hasRole(ROLES.LICENSE_MANAGER);
}

/** Licence and licence-item PATCHes, each followed by a licence-wide invalidation. */
export function useLicenceModalEdits(licenseId: Id) {
    const queryClient = useQueryClient();
    const refresh = useCallback(() => invalidateLicence(queryClient, licenseId), [queryClient, licenseId]);

    /** Same as the modal's `InlineEditableText`: `PATCH licenses/:id/ { [field]: value }`. */
    const saveLicenceText = useCallback(
        async (field: LicenceTextField, value: string, label: string): Promise<boolean> => {
            try {
                await api.patch(`licenses/${licenseId}/`, { [field]: value });
                toast.success(`${label} saved successfully`);
                void refresh();
                return true;
            } catch {
                toast.error(`Failed to save ${label}`);
                return false;
            }
        },
        [licenseId, refresh],
    );

    /** Same as the modal's `patchItemTags`: `PATCH license-items/:id/ { items: ids }`. */
    const saveItemTags = useCallback(
        async (itemId: number, itemIds: number[]): Promise<boolean> => {
            try {
                await api.patch(`license-items/${itemId}/`, { items: itemIds });
                void refresh();
                return true;
            } catch (error) {
                const data = (error as ApiError).response?.data;
                toast.error(data?.detail || data?.error || "Failed to update items");
                return false;
            }
        },
        [refresh],
    );

    /** Same as the modal's `handleConditionTypeChange`: `PATCH license-items/:id/ { condition_type }`. */
    const saveItemMarking = useCallback(
        async (itemId: number, conditionType: string): Promise<boolean> => {
            try {
                await api.patch(`license-items/${itemId}/`, { condition_type: conditionType });
                toast.success("License marking updated");
                void refresh();
                return true;
            } catch (error) {
                const data = (error as ApiError).response?.data;
                toast.error(data?.detail || data?.condition_type?.[0] || "Failed to update license marking");
                return false;
            }
        },
        [refresh],
    );

    return { saveLicenceText, saveItemTags, saveItemMarking };
}

/** Same request as the modal's `fetchItemUsage`: `GET licenses/:id/item-usage/?item_id&type`. */
export function useItemUsage(licenseId: Id, itemId: number, type: UsageType, enabled: boolean) {
    return useQuery({
        queryKey: qk.licenses.sub(String(licenseId), "item-usage", itemId, type),
        queryFn: async (): Promise<ItemUsage> => {
            try {
                const { data } = await api.get(buildLicenseEndpoint(licenseId, "item-usage/"), {
                    params: { item_id: itemId, type },
                });
                return normalizeUsageData(data);
            } catch (error) {
                toast.error("Failed to load usage details.");
                throw error;
            }
        },
        enabled,
        // One request and one error toast per open, like the modal's one-shot fetch.
        retry: false,
    });
}

/** License Marking values map directly to the backend `condition_type` field ("" clears it). */
export const LICENSE_MARKING_OPTIONS = [
    { value: "", label: "None" },
    { value: "AU", label: "AU" },
    { value: "10%", label: "10%" },
    { value: "5%", label: "5%" },
    { value: "3%", label: "3%" },
    { value: "2%", label: "2%" },
] as const;
