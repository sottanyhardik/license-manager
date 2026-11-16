/**
 * Frontend list contract over DRF `page` / `page_size` (04 §3).
 * Pure helpers: no React, no network.
 */

export type FilterValue = string | number | boolean | readonly string[] | null | undefined;

export interface ListParams {
    page: number;
    pageSize: number;
    search?: string;
    ordering?: string;
    filters: Record<string, FilterValue>;
}

export interface ListResult<T> {
    rows: T[];
    count: number;
    page: number;
    pageSize: number;
    totalPages: number;
    hasNext: boolean;
    hasPrevious: boolean;
}

/** Backend StandardPagination max_page_size is 200; never request more. */
export const PAGE_SIZE_MAX = 200;
export const PAGE_SIZE_DEFAULT = 25;
export const PAGE_SIZES = [25, 50, 100, 200] as const;

export function clampPageSize(n: number, max: number = PAGE_SIZE_MAX): number {
    const cap = Math.min(max, PAGE_SIZE_MAX);
    if (!Number.isFinite(n) || n < 1) return Math.min(PAGE_SIZE_DEFAULT, cap);
    return Math.min(Math.floor(n), cap);
}

const isEmpty = (v: FilterValue): boolean =>
    v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0);

/** `_from` / `_to` UI names map to `__gte` / `__lte` on the wire (as MasterList does). */
function wireKey(key: string): string {
    if (key.endsWith("_from")) return `${key.slice(0, -5)}__gte`;
    if (key.endsWith("_to")) return `${key.slice(0, -3)}__lte`;
    return key;
}

/** Build the API query string. page_size is clamped to the cap. */
export function toQuery(p: ListParams, maxPageSize: number = PAGE_SIZE_MAX): URLSearchParams {
    const q = new URLSearchParams();
    q.set("page", String(Math.max(1, Math.floor(p.page) || 1)));
    q.set("page_size", String(clampPageSize(p.pageSize, maxPageSize)));
    if (p.search) q.set("search", p.search);
    if (p.ordering) q.set("ordering", p.ordering);
    for (const [k, v] of Object.entries(p.filters)) {
        if (isEmpty(v)) continue;
        if (Array.isArray(v)) v.forEach((item) => q.append(wireKey(k), String(item)));
        else q.set(wireKey(k), String(v));
    }
    return q;
}

/** Accepts StandardPagination, DRF default, MasterViewSet, `{count, results}` or a plain array. */
export function normalizeList<T>(raw: unknown, sent: ListParams): ListResult<T> {
    const pageSize = sent.pageSize;
    if (Array.isArray(raw)) {
        return {
            rows: raw as T[], count: raw.length, page: 1, pageSize,
            totalPages: 1, hasNext: false, hasPrevious: false,
        };
    }
    const r = (raw ?? {}) as Record<string, unknown>;
    const rows = (Array.isArray(r.results) ? r.results : []) as T[];
    const count = typeof r.count === "number" ? r.count : rows.length;
    const size = typeof r.page_size === "number" && r.page_size > 0 ? r.page_size : pageSize;
    const page = typeof r.current_page === "number" ? r.current_page : sent.page;
    const totalPages = typeof r.total_pages === "number"
        ? r.total_pages
        : Math.max(1, Math.ceil(count / size));
    const hasNext = typeof r.has_next === "boolean" ? r.has_next : r.next != null ? true : page < totalPages;
    const hasPrevious = typeof r.has_previous === "boolean" ? r.has_previous : r.previous != null ? true : page > 1;
    return { rows, count, page, pageSize: size, totalPages, hasNext, hasPrevious };
}

export interface UrlOptions {
    /** Allow-list of filter param names owned by this list. */
    filterKeys: readonly string[];
    /** Prefix isolating two lists on one page, e.g. "avail_". */
    urlPrefix?: string;
    defaults?: Partial<Omit<ListParams, "page">>;
    maxPageSize?: number;
}

const RESERVED = ["page", "page_size", "search", "ordering"] as const;

/** URL -> params. URL wins over defaults. */
export function parseListParams(sp: URLSearchParams, opts: UrlOptions): ListParams {
    const pre = opts.urlPrefix ?? "";
    const d = opts.defaults ?? {};
    const page = parseInt(sp.get(`${pre}page`) ?? "", 10);
    const size = parseInt(sp.get(`${pre}page_size`) ?? "", 10);
    const filters: Record<string, FilterValue> = { ...(d.filters ?? {}) };
    for (const key of opts.filterKeys) {
        const all = sp.getAll(`${pre}${key}`);
        if (all.length === 1) filters[key] = all[0];
        else if (all.length > 1) filters[key] = all;
    }
    return {
        page: page >= 1 ? page : 1,
        pageSize: clampPageSize(size >= 1 ? size : d.pageSize ?? PAGE_SIZE_DEFAULT, opts.maxPageSize),
        search: sp.get(`${pre}search`) ?? d.search,
        ordering: sp.get(`${pre}ordering`) ?? d.ordering,
        filters,
    };
}

const sameValue = (a: FilterValue, b: FilterValue): boolean =>
    Array.isArray(a) || Array.isArray(b)
        ? JSON.stringify(a ?? []) === JSON.stringify(b ?? [])
        : (a ?? "") === (b ?? "");

/**
 * params -> URL. Returns a NEW URLSearchParams: unrelated params (tab, expanded...)
 * are preserved, only keys owned by this list are rewritten; defaults are omitted.
 */
export function writeListParams(base: URLSearchParams, p: ListParams, opts: UrlOptions): URLSearchParams {
    const pre = opts.urlPrefix ?? "";
    const d = opts.defaults ?? {};
    const next = new URLSearchParams(base);
    [...RESERVED, ...opts.filterKeys].forEach((k) => next.delete(`${pre}${k}`));
    if (p.page > 1) next.set(`${pre}page`, String(p.page));
    const defSize = clampPageSize(d.pageSize ?? PAGE_SIZE_DEFAULT, opts.maxPageSize);
    if (p.pageSize !== defSize) next.set(`${pre}page_size`, String(p.pageSize));
    if (p.search && p.search !== (d.search ?? "")) next.set(`${pre}search`, p.search);
    if (p.ordering && p.ordering !== (d.ordering ?? "")) next.set(`${pre}ordering`, p.ordering);
    for (const key of opts.filterKeys) {
        const v = p.filters[key];
        if (isEmpty(v) || sameValue(v, d.filters?.[key])) continue;
        if (Array.isArray(v)) v.forEach((item) => next.append(`${pre}${key}`, String(item)));
        else next.set(`${pre}${key}`, String(v));
    }
    return next;
}
