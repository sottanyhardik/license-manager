import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import { reconKeys, unwrapList, type ReconRow } from "./reconciliationHelpers";

export const RECON_DEFAULT_PAGE_SIZE = 50;

type ReconPage = { rows: ReconRow[]; count: number };

/**
 * Shared data-fetching hook for every reconciliation tab. Each `TabsContent`
 * only mounts its child once the user activates that tab (Radix `Tabs`
 * unmounts inactive panels by default), so calling this hook inside a tab
 * component gives "lazy-fetch on first activation" for free.
 *
 * The backend paginates every detection endpoint (`page` / `page_size`,
 * `ReconciliationResultsPagination`), so the hook fetches one server page at
 * a time and exposes `pagination` for `ReconPagination`. A bare-array
 * response (unpaginated) is treated as a single page.
 */
export function useReconTabQuery(tabKey: string, endpoint: string) {
    const [page, setPage] = useState(1);
    const [pageSize, setPageSizeState] = useState(RECON_DEFAULT_PAGE_SIZE);

    const query = useQuery<ReconPage>({
        queryKey: [...reconKeys.tab(tabKey), page, pageSize],
        queryFn: async () => {
            const { data } = await api.get(endpoint, { params: { page, page_size: pageSize } });
            const rows = unwrapList(data);
            const count = typeof data?.count === "number" ? data.count : rows.length;
            return { rows, count };
        },
        placeholderData: keepPreviousData,
    });

    const count = query.data?.count ?? 0;
    const totalPages = Math.max(1, Math.ceil(count / pageSize));

    return {
        data: query.data?.rows,
        isLoading: query.isLoading,
        isError: query.isError,
        error: query.error,
        pagination: {
            currentPage: page,
            totalPages,
            pageSize,
            totalItems: count,
            hasNext: page < totalPages,
            hasPrevious: page > 1,
            onPageChange: setPage,
            onPageSizeChange: (size: number) => {
                setPageSizeState(size);
                setPage(1);
            },
        },
    };
}

export type ReconPaginationState = ReturnType<typeof useReconTabQuery>["pagination"];
