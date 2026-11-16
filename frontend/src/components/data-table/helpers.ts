import type { SortingState } from "@tanstack/react-table";

/** `-field` / `field` -> SortingState (single column). */
export function orderingToSorting(ordering: string | undefined): SortingState {
    if (!ordering) return [];
    return ordering.startsWith("-") ? [{ id: ordering.slice(1), desc: true }] : [{ id: ordering, desc: false }];
}

/** SortingState -> DRF `ordering` string (undefined when unsorted). */
export function sortingToOrdering(sorting: SortingState): string | undefined {
    const s = sorting[0];
    if (!s) return undefined;
    return s.desc ? `-${s.id}` : s.id;
}

/** asc -> desc -> none. */
export function nextSorting(current: SortingState, id: string): SortingState {
    const cur = current.find((s) => s.id === id);
    if (!cur) return [{ id, desc: false }];
    if (!cur.desc) return [{ id, desc: true }];
    return [];
}
