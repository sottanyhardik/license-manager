import { useCallback, useId, useState } from "react";
import { DataTable } from "./DataTable";
import type { ExpandableDataTableProps } from "./types";

/**
 * DataTable with an inline expandable row (05 §16).
 * - Single expand by default; `expandedId` is controlled when provided
 *   (use `useExpandedParam()` for `?expanded=`), otherwise internal state.
 * - The expanded region renders only while open: collapse or switching rows
 *   unmounts it, so stale panel state/data cannot leak between records.
 */
export function ExpandableDataTable<T extends { id: number }>({
    renderExpanded,
    expandedId,
    onExpandedChange,
    singleExpand = true,
    getRowLabel,
    ...table
}: ExpandableDataTableProps<T>) {
    const uid = useId();
    const [internalSingle, setInternalSingle] = useState<number | null>(null);
    const [internalMulti, setInternalMulti] = useState<ReadonlySet<number>>(new Set());

    const controlled = expandedId !== undefined;
    const single = controlled ? expandedId : internalSingle;

    const isExpanded = useCallback(
        (row: T) => (singleExpand ? single === row.id : internalMulti.has(row.id)),
        [singleExpand, single, internalMulti],
    );

    const onToggle = useCallback(
        (row: T) => {
            if (singleExpand) {
                const next = single === row.id ? null : row.id;
                if (!controlled) setInternalSingle(next);
                onExpandedChange?.(next);
                return;
            }
            const next = new Set(internalMulti);
            if (next.has(row.id)) next.delete(row.id);
            else next.add(row.id);
            setInternalMulti(next);
            onExpandedChange?.(next.has(row.id) ? row.id : null);
        },
        [singleExpand, single, controlled, internalMulti, onExpandedChange],
    );

    return (
        <DataTable<T>
            {...table}
            expansion={{
                isExpanded,
                onToggle,
                renderExpanded,
                getRowLabel: getRowLabel ?? ((row) => `Row ${row.id}`),
                regionId: (rowId) => `${uid}-region-${rowId}`,
            }}
        />
    );
}
