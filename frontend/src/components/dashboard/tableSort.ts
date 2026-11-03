import { useState } from "react";
export type SortDirection = "ascending" | "descending";
export type SortState<K extends string> = { key: K; direction: SortDirection } | null;
export type SortValue = string | number | null | undefined;

/**
 * Sorts a copy of `rows`. Missing values always sort last, whichever direction
 * is chosen, so a blank cell never jumps to the top of the table.
 */
export function sortRows<T, K extends string>(
    rows: readonly T[],
    sort: SortState<K>,
    accessors: Record<K, (row: T) => SortValue>,
): T[] {
    if (!sort) return [...rows];
    const read = accessors[sort.key];
    const sign = sort.direction === "ascending" ? 1 : -1;
    return [...rows].sort((a, b) => {
        const left = read(a);
        const right = read(b);
        if (left == null && right == null) return 0;
        if (left == null) return 1;
        if (right == null) return -1;
        if (typeof left === "number" && typeof right === "number") return (left - right) * sign;
        return String(left).localeCompare(String(right), "en", { numeric: true, sensitivity: "base" }) * sign;
    });
}

export function useTableSort<K extends string>(initial: SortState<K> = null) {
    const [sort, setSort] = useState<SortState<K>>(initial);

    const toggle = (key: K) =>
        setSort((previous) =>
            previous?.key === key
                ? { key, direction: previous.direction === "ascending" ? "descending" : "ascending" }
                : { key, direction: "ascending" },
        );

    const ariaSort = (key: K): SortDirection | "none" => (sort?.key === key ? sort.direction : "none");

    return { sort, toggle, ariaSort };
}
