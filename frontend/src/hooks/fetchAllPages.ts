import api from "@/api/axios";

/** Backend StandardPagination / MasterViewSet `max_page_size`; larger values are silently capped. */
export const MAX_PAGE_SIZE = 200;
const MAX_PAGES = 50; // safety cap: 10,000 rows

/**
 * Fetch every row of a paginated DRF list endpoint by requesting
 * `MAX_PAGE_SIZE` rows per request and following `next` until exhausted.
 * Unpaginated (bare-array) responses are returned as-is.
 */
export async function fetchAllPages<T = unknown>(
    url: string,
    params: Record<string, unknown> = {},
): Promise<T[]> {
    const rows: T[] = [];
    for (let page = 1; page <= MAX_PAGES; page++) {
        const { data } = await api.get(url, { params: { ...params, page_size: MAX_PAGE_SIZE, page } });
        if (Array.isArray(data)) return data as T[];
        rows.push(...((data?.results ?? []) as T[]));
        if (!data?.next) return rows;
    }
    return rows;
}
