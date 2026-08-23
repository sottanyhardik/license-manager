import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";

/**
 * A single `LicenseExportItemModel` row as returned by `GET licenses/{id}/`
 * (the same full License detail endpoint the Masters "Edit License" modal
 * already uses — see `LicenseDetailsSerializer` / `LicenseExportItemSerializer`
 * in `backend/apps/license/serializers/license.py`). Only the fields this
 * page actually needs are declared here; the wire payload has more
 * (fob_fc, cif_fc, unit, etc.) that we deliberately don't type/consume.
 */
export interface LicenseExportRow {
    id: number;
    norm_class: number | null;
    norm_class_detail: { id: number; norm_class: string; description: string } | null;
    norm_class_label?: string | null;
}

export const licenseSionNormKeys = {
    detail: (licenseId: string | number) => ["license-sion-norm", String(licenseId)] as const,
};

/**
 * Fetches `GET licenses/{id}/` purely to source the license's current SION
 * Norm for display/edit on the Overview tab. By convention (the same one
 * `detect_norm()` / `_calculate_import_quantity()` use on the backend), the
 * first `export_license` row — `exportRows[0]` — is treated as "the" export
 * item; a license normally has exactly one.
 *
 * Also returns every row's bare `id` (via `exportRows`), which the SION Norm
 * PATCH needs to round-trip: `LicenseWriteMixin.update` deletes any existing
 * `export_license` row whose `id` is missing from the array you send once you
 * include the `export_license` key at all, so a norm-only edit must still
 * list every sibling row's id even though it only changes one row's
 * `norm_class`.
 *
 * Lazy per-tab convention, same as the other `useLicenseOverview*` hooks —
 * only fetched once the Overview tab is active.
 */
export function useLicenseSionNorm(licenseId: string | number | undefined, isActive: boolean = true) {
    const query = useQuery<LicenseExportRow[]>({
        queryKey: licenseSionNormKeys.detail(licenseId ?? ""),
        queryFn: async () => {
            const { data } = await api.get(`licenses/${licenseId}/`);
            return (data?.export_license ?? []) as LicenseExportRow[];
        },
        enabled: isActive && licenseId !== undefined && licenseId !== null && licenseId !== "",
    });

    const exportRows = query.data ?? [];
    const primaryRow = exportRows[0] ?? null;

    return { ...query, exportRows, primaryRow };
}
