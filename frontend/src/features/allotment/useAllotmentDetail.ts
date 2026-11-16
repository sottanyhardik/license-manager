import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import { qk } from "@/lib/queryKeys";
import type { AllotmentRecord } from "./types";

/**
 * `allotments/:id/` — the same retrieve endpoint AllotmentAction uses for its
 * header. Shared by the Overview / Licence Mapping / Utilisation tabs, so a
 * record is fetched once, only when the first of those tabs opens.
 */
export function useAllotmentDetail(id: number) {
    return useQuery<AllotmentRecord>({
        queryKey: qk.allotments.detail(id),
        queryFn: ({ signal }) => api.get(`allotments/${id}/`, { signal }).then((r) => r.data),
        staleTime: 30_000,
        refetchOnWindowFocus: false,
    });
}
