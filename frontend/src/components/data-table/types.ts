import type { ColumnDef, RowSelectionState, SortingState, VisibilityState, RowData } from "@tanstack/react-table";
import type React from "react";

declare module "@tanstack/react-table" {
    interface ColumnMeta<TData extends RowData, TValue> {
        align?: "start" | "end";
        numeric?: boolean;
        sticky?: "start";
        hideBelow?: "md" | "lg";
        /** Optional totals cell rendered in the footer row. */
        footer?: React.ReactNode;
    }
}

export type Density = "compact" | "default";

export interface DataTableState {
    status: "loading" | "error" | "success";
    error?: unknown;
    isFetching?: boolean;
}

export interface DataTableProps<T> {
    columns: ColumnDef<T, unknown>[];
    data: T[];
    getRowId: (row: T) => string;
    /** Rendered as sr-only <caption>. */
    caption: string;
    state: DataTableState;
    onRetry?: () => void;
    empty?: { title: string; description?: string; action?: React.ReactNode };
    /** Controlled server sort. Column ids are the backend `ordering` fields. Omit = not sortable. */
    sorting?: { value: SortingState; onChange: (s: SortingState) => void };
    selection?: {
        value: RowSelectionState;
        onChange: (s: RowSelectionState) => void;
        bulkActions?: (ids: string[]) => React.ReactNode;
    };
    columnVisibility?: { value: VisibilityState; onChange: (v: VisibilityState) => void; storageKey?: string };
    resizable?: boolean;
    /** Rendered in a trailing cell. Pass an ActionMenu (kept ReactNode so this table has no menu dependency). */
    rowActions?: (row: T) => React.ReactNode;
    onRowClick?: (row: T) => void;
    density?: Density;
    stickyHeader?: boolean;
    /** Slot for <Pagination>. */
    footer?: React.ReactNode;
    className?: string;
}

export interface ExpandableDataTableProps<T extends { id: number }> extends DataTableProps<T> {
    renderExpanded: (row: T) => React.ReactNode;
    expandedId?: number | null;
    onExpandedChange?: (id: number | null) => void;
    /** Default true. */
    singleExpand?: boolean;
    /** Accessible name of a row, used for expand button and region. Default `Row {id}`. */
    getRowLabel?: (row: T) => string;
}
