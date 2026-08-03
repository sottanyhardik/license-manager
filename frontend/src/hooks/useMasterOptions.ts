/**
 * Shared, portal-wide source of truth for two filters that used to be
 * hardcoded (and had drifted out of sync) on individual pages: Purchase
 * Status and SION Norm class.
 *
 * Both hooks fetch straight from the master tables — never from
 * transaction data, never from a literal array baked into a page — so
 * every screen that uses them sees the exact same list, labels, order,
 * and active/inactive filtering. Results are cached at module scope (keyed
 * by fetch, not by component) so multiple pages/components mounted in the
 * same session share one network request instead of each re-fetching the
 * same small, rarely-changing list.
 */
import { useEffect, useState } from "react";
import api from "@/api/axios";

export type SelectOption = { value: string; label: string };

type OptionsCache = {
    promise: Promise<SelectOption[]> | null;
    data: SelectOption[] | null;
};

function useCachedOptions(cache: OptionsCache, fetcher: () => Promise<SelectOption[]>) {
    const [options, setOptions] = useState<SelectOption[]>(cache.data ?? []);
    const [loading, setLoading] = useState(cache.data === null);

    useEffect(() => {
        let isMounted = true;

        if (cache.data) {
            setOptions(cache.data);
            setLoading(false);
            return;
        }

        if (!cache.promise) {
            cache.promise = fetcher()
                .then((result) => {
                    cache.data = result;
                    return result;
                })
                .catch(() => {
                    cache.data = [];
                    return [];
                });
        }

        cache.promise.then((result) => {
            if (isMounted) {
                setOptions(result);
                setLoading(false);
            }
        });

        return () => {
            isMounted = false;
        };
    }, [cache, fetcher]);

    return { options, loading };
}

const purchaseStatusCache: OptionsCache = { promise: null, data: null };

async function fetchPurchaseStatusOptions(): Promise<SelectOption[]> {
    const response = await api.get("masters/purchase-statuses/", {
        params: { is_active: true, ordering: "display_order,label", page_size: 200 },
    });
    const results = response.data?.results ?? response.data ?? [];
    return results.map((row: { code: string; label: string }) => ({
        value: row.code,
        label: row.label,
    }));
}

/**
 * Purchase Status options — always the Purchase Status master's
 * `is_active=true` rows, ordered by `display_order` then `label` (the
 * master's own declared display order — never re-derived from license or
 * allotment transaction data).
 */
export function usePurchaseStatusOptions() {
    return useCachedOptions(purchaseStatusCache, fetchPurchaseStatusOptions);
}

const sionNormCache: OptionsCache = { promise: null, data: null };

async function fetchSionNormOptions(): Promise<SelectOption[]> {
    const response = await api.get("masters/sion-classes/", {
        params: { is_active: true, ordering: "norm_class", page_size: 500 },
    });
    const results = response.data?.results ?? response.data ?? [];
    return results
        .map((row: { norm_class: string }) => ({ value: row.norm_class, label: row.norm_class }))
        // Belt-and-suspenders: the SION norms master has no curated
        // display-order field, so alphabetical is the defined fallback
        // order regardless of what the backend returns.
        .sort((a: SelectOption, b: SelectOption) => a.label.localeCompare(b.label));
}

/**
 * SION Norm options — always the SION Norms master's `is_active=true`
 * rows (of ~2,000+ total norm classes in the master, only a handful are
 * active for this business — inactive norms must never reach a dropdown),
 * sorted alphabetically by norm class code, and displayed using that
 * business code (e.g. "E1") rather than its long description.
 */
export function useSionNormOptions() {
    return useCachedOptions(sionNormCache, fetchSionNormOptions);
}
