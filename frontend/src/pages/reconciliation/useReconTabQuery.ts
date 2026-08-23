import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import { reconKeys, unwrapList, type ReconRow } from "./reconciliationHelpers";

/**
 * Shared data-fetching hook for every reconciliation tab. Each `TabsContent`
 * only mounts its child once the user activates that tab (Radix `Tabs`
 * unmounts inactive panels by default — verified against
 * `@radix-ui/react-tabs`'s `Presence` usage), so simply calling this hook
 * inside a tab component already gives the "lazy-fetch on first activation"
 * behavior the panel needs, without a separate manually-tracked "visited
 * tabs" set.
 */
export function useReconTabQuery(tabKey: string, endpoint: string) {
    return useQuery<ReconRow[]>({
        queryKey: reconKeys.tab(tabKey),
        queryFn: async () => {
            const { data } = await api.get(endpoint);
            return unwrapList(data);
        },
    });
}
