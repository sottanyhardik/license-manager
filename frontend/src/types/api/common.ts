/** Shared loose request/response types for the API wrappers in `src/api/`. */

/** Query-string params passed straight to axios. */
export type ApiParams = Record<string, unknown>;

/** Loose JSON object body/response where the exact shape is not modelled yet. */
export type ApiRecord = Record<string, unknown>;

/** DRF page envelope; wrappers that return `response.data` may yield this or a bare list. */
export interface PaginatedResponse<T = ApiRecord> {
    count?: number;
    next?: string | null;
    previous?: string | null;
    results: T[];
}

/** Id as used in URL paths. */
export type ApiId = number | string;
