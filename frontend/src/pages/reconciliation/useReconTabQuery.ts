import { useCallback } from "react";
import api from "@/api/axios";
import { useListQuery, type ListFetcher } from "@/hooks/useListQuery";
import type { ListResult } from "@/lib/listContract";
import { reconKeys, unwrapList, type ReconRow } from "./reconciliationHelpers";

export const RECON_DEFAULT_PAGE_SIZE = 50;

const DEFAULTS = { pageSize: RECON_DEFAULT_PAGE_SIZE };
const NO_FILTERS: string[] = [];

/**
 * Shared data-fetching hook for every reconciliation tab. Each `TabsContent`
 * only mounts its child once the user activates that tab (Radix `Tabs`
 * unmounts inactive panels by default), so calling this hook inside a tab
 * component gives "lazy-fetch on first activation" for free.
 *
 * Built on `useListQuery`: page / page_size live in the URL under a per-tab
 * prefix (`<tabKey>_page`, `<tabKey>_page_size`), so tabs keep their own page,
 * and a deep link restores it. The backend paginates every detection endpoint
 * (`page` / `page_size`, `ReconciliationResultsPagination`); a bare-array
 * response (unpaginated) is treated as a single page.
 */
export function useReconTabQuery(tabKey: string, endpoint: string) {
    const fetcher = useCallback<ListFetcher<ReconRow>>(
        async (p, signal): Promise<ListResult<ReconRow>> => {
            const { data } = await api.get(endpoint, { params: { page: p.page, page_size: p.pageSize }, signal });
            const rows = unwrapList(data);
            const count = typeof data?.count === "number" ? data.count : rows.length;
            const totalPages = Math.max(1, Math.ceil(count / p.pageSize));
            return {
                rows, count, page: p.page, pageSize: p.pageSize, totalPages,
                hasNext: p.page < totalPages, hasPrevious: p.page > 1,
            };
        },
        [endpoint],
    );

    const list = useListQuery<ReconRow>({
        key: (p) => [...reconKeys.tab(tabKey), p.page, p.pageSize],
        fetcher,
        filterKeys: NO_FILTERS,
        defaults: DEFAULTS,
        urlPrefix: `${tabKey}_`,
        maxPageSize: 200,
    });

    const { page, pageSize } = list.params;
    const count = list.result?.count ?? 0;
    const totalPages = Math.max(1, Math.ceil(count / pageSize));

    return {
        data: list.result?.rows,
        isLoading: list.status === "loading",
        isError: list.status === "error",
        error: list.error,
        pagination: {
            currentPage: page,
            totalPages,
            pageSize,
            totalItems: count,
            hasNext: page < totalPages,
            hasPrevious: page > 1,
            onPageChange: list.setPage,
            onPageSizeChange: list.setPageSize,
        },
    };
}

export type ReconPaginationState = ReturnType<typeof useReconTabQuery>["pagination"];
