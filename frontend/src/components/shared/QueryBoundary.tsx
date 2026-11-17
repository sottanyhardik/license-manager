import type { ReactNode } from "react";

import { InlineError } from "./InlineError";
import { LoadingState } from "./LoadingState";

/** The subset of a TanStack `UseQueryResult` the boundary reads. */
export interface QueryBoundaryState<T> {
    data: T | undefined;
    isPending: boolean;
    isError: boolean;
    error: unknown;
    refetch: () => unknown;
}

export interface QueryBoundaryProps<T> {
    /** Query result (e.g. the return value of `useQuery`). */
    query: QueryBoundaryState<T>;
    /** Accessible label of the loading skeleton (`role="status"`). */
    loadingLabel: string;
    /** Title of the inline error. */
    errorTitle: string;
    /** Number of skeleton rows while pending (default 3). */
    rows?: number;
    /** Renders the loaded data. */
    children: (data: T) => ReactNode;
}

/**
 * Pending / error / data switch for a single query: a skeleton while pending,
 * an `InlineError` with a Retry action (calls `refetch`) on error or empty
 * data, otherwise `children(data)`.
 *
 * Accessibility: the skeleton is a labelled `role="status"` region; the error
 * is rendered by `InlineError`, whose Retry is a native, keyboard-operable button.
 */
export function QueryBoundary<T>({ query, loadingLabel, errorTitle, rows = 3, children }: QueryBoundaryProps<T>) {
    const { data, isPending, isError, error, refetch } = query;
    if (isPending) return <LoadingState variant="skeleton-rows" rows={rows} label={loadingLabel} />;
    if (isError || !data) return <InlineError error={error} onRetry={() => { void refetch(); }} title={errorTitle} />;
    return <>{children(data)}</>;
}
