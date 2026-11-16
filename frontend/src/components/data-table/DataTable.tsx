import React, { useEffect, useId } from "react";
import {
    flexRender,
    getCoreRowModel,
    useReactTable,
    type Header,
    type OnChangeFn,
    type RowSelectionState,
    type VisibilityState,
} from "@tanstack/react-table";
import { AlertCircle, ArrowDown, ArrowUp, ArrowUpDown, ChevronRight, Columns3, Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
    DropdownMenu,
    DropdownMenuCheckboxItem,
    DropdownMenuContent,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { nextSorting } from "./helpers";
import type { DataTableProps, Density } from "./types";

/** @internal wiring used by ExpandableDataTable only. */
export interface DataTableExpansion<T> {
    isExpanded: (row: T) => boolean;
    onToggle: (row: T) => void;
    renderExpanded: (row: T) => React.ReactNode;
    getRowLabel: (row: T) => string;
    regionId: (rowId: string) => string;
}

const DENSITY: Record<Density, { head: string; cell: string }> = {
    compact: { head: "h-8 px-2 py-1 text-xs", cell: "h-8 px-2 py-1 text-xs" },
    default: { head: "h-9 px-3 py-2 text-sm", cell: "h-10 px-3 py-2 text-sm" },
};

const HIDE: Record<string, string> = { md: "hidden md:table-cell", lg: "hidden lg:table-cell" };
const SKELETON_ROWS = 6;

function errorMessage(error: unknown): string {
    if (error instanceof Error && error.message) return error.message;
    return "Something went wrong while loading this list.";
}

export function DataTable<T>({
    columns,
    data,
    getRowId,
    caption,
    state,
    onRetry,
    empty,
    sorting,
    selection,
    columnVisibility,
    resizable = false,
    rowActions,
    onRowClick,
    density = "default",
    stickyHeader = true,
    footer,
    className,
    expansion,
}: DataTableProps<T> & { expansion?: DataTableExpansion<T> }) {
    const d = DENSITY[density];
    const storageKey = columnVisibility?.storageKey;
    const visibilityValue = columnVisibility?.value;
    const onVisibilityChange = columnVisibility?.onChange;

    // Restore persisted column visibility once (only when the caller has none yet).
    useEffect(() => {
        if (!storageKey || !onVisibilityChange) return;
        try {
            const raw = localStorage.getItem(`dt-cols:${storageKey}`);
            if (raw && Object.keys(visibilityValue ?? {}).length === 0) onVisibilityChange(JSON.parse(raw) as VisibilityState);
        } catch { /* ignore corrupt storage */ }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [storageKey]);

    const handleVisibility: OnChangeFn<VisibilityState> = (updater) => {
        if (!columnVisibility) return;
        const next = typeof updater === "function" ? updater(columnVisibility.value) : updater;
        columnVisibility.onChange(next);
        if (storageKey) {
            try { localStorage.setItem(`dt-cols:${storageKey}`, JSON.stringify(next)); } catch { /* quota */ }
        }
    };
    const handleSelection: OnChangeFn<RowSelectionState> = (updater) => {
        if (!selection) return;
        selection.onChange(typeof updater === "function" ? updater(selection.value) : updater);
    };

    const table = useReactTable<T>({
        data,
        columns,
        getRowId: (row) => getRowId(row),
        getCoreRowModel: getCoreRowModel(),
        manualSorting: true,
        manualPagination: true,
        manualFiltering: true,
        enableSorting: !!sorting,
        enableRowSelection: !!selection,
        enableColumnResizing: resizable,
        columnResizeMode: "onChange",
        state: {
            columnVisibility: columnVisibility?.value ?? {},
            rowSelection: selection?.value ?? {},
        },
        onColumnVisibilityChange: handleVisibility,
        onRowSelectionChange: handleSelection,
    });

    const uid = useId();
    const leafColumns = table.getVisibleLeafColumns();
    const colSpan = leafColumns.length + (selection ? 1 : 0) + (expansion ? 1 : 0) + (rowActions ? 1 : 0);
    const selectedIds = selection ? Object.keys(selection.value).filter((k) => selection.value[k]) : [];
    const hasFooter = leafColumns.some((c) => c.columnDef.meta?.footer != null);
    const isLoading = state.status === "loading";
    const isError = state.status === "error";
    const isEmpty = state.status === "success" && data.length === 0;

    const cellClass = (meta: { align?: string; numeric?: boolean; sticky?: string; hideBelow?: string } | undefined, head: boolean) =>
        cn(
            head ? d.head : d.cell,
            (meta?.align === "end" || meta?.numeric) && "text-right",
            meta?.numeric && "tabular-nums",
            meta?.sticky === "start" && "sticky left-0 z-[1] bg-card",
            meta?.hideBelow && HIDE[meta.hideBelow],
        );

    const renderHead = (header: Header<T, unknown>) => {
        const col = header.column;
        const sortable = !!sorting && col.getCanSort();
        const sort = sorting?.value.find((s) => s.id === col.id);
        const ariaSort = sortable ? (sort ? (sort.desc ? "descending" : "ascending") : "none") : undefined;
        const content = header.isPlaceholder ? null : flexRender(col.columnDef.header, header.getContext());
        const SortIcon = sort ? (sort.desc ? ArrowDown : ArrowUp) : ArrowUpDown;
        return (
            <TableHead
                key={header.id}
                scope="col"
                aria-sort={ariaSort}
                style={resizable ? { width: header.getSize(), position: "relative" } : undefined}
                className={cellClass(col.columnDef.meta, true)}
            >
                {sortable ? (
                    <button
                        type="button"
                        onClick={() => sorting.onChange(nextSorting(sorting.value, col.id))}
                        className="inline-flex items-center gap-1 rounded-sm outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/40"
                    >
                        {content}
                        <SortIcon className={cn("size-3.5", !sort && "opacity-40")} aria-hidden="true" />
                    </button>
                ) : (
                    content
                )}
                {resizable && col.getCanResize() && (
                    <div
                        role="separator"
                        aria-orientation="vertical"
                        aria-label={`Resize column ${col.id}`}
                        onMouseDown={header.getResizeHandler()}
                        onTouchStart={header.getResizeHandler()}
                        className={cn(
                            "absolute right-0 top-0 h-full w-1 cursor-col-resize select-none touch-none hover:bg-primary/40",
                            col.getIsResizing() && "bg-primary",
                        )}
                    />
                )}
            </TableHead>
        );
    };

    const hideable = table.getAllLeafColumns().filter((c) => c.getCanHide() && typeof c.columnDef.header === "string");

    return (
        <div className={cn("flex flex-col gap-2", className)}>
            {(selectedIds.length > 0 && selection?.bulkActions) || (columnVisibility && hideable.length > 0) ? (
                <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2" data-slot="bulk-actions">
                        {selectedIds.length > 0 && selection?.bulkActions && (
                            <>
                                <span className="text-xs text-muted-foreground" aria-live="polite">{selectedIds.length} selected</span>
                                {selection.bulkActions(selectedIds)}
                            </>
                        )}
                    </div>
                    {columnVisibility && hideable.length > 0 && (
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="outline" size="sm"><Columns3 aria-hidden="true" /> Columns</Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                {hideable.map((c) => (
                                    <DropdownMenuCheckboxItem
                                        key={c.id}
                                        checked={c.getIsVisible()}
                                        onCheckedChange={(v) => c.toggleVisibility(!!v)}
                                        onSelect={(e) => e.preventDefault()}
                                    >
                                        {c.columnDef.header as string}
                                    </DropdownMenuCheckboxItem>
                                ))}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    )}
                </div>
            ) : null}

            <Table
                aria-busy={state.isFetching || isLoading || undefined}
                style={resizable ? { width: table.getTotalSize(), minWidth: "100%", tableLayout: "fixed" } : undefined}
                containerClassName={cn(state.isFetching && !isLoading && "opacity-80 transition-opacity")}
            >
                <caption className="sr-only">{caption}</caption>
                <TableHeader className={cn(stickyHeader && "sticky top-[var(--app-sticky-offset,0px)] z-10 bg-card shadow-[0_1px_0_var(--border)]")}>
                    {table.getHeaderGroups().map((hg) => (
                        <TableRow key={hg.id} className="hover:bg-transparent">
                            {expansion && <TableHead scope="col" className={cn(d.head, "w-8")}><span className="sr-only">Expand</span></TableHead>}
                            {selection && (
                                <TableHead scope="col" className={cn(d.head, "w-8")}>
                                    <Checkbox
                                        aria-label="Select all on page"
                                        checked={table.getIsAllPageRowsSelected() ? true : table.getIsSomePageRowsSelected() ? "indeterminate" : false}
                                        onCheckedChange={(v) => table.toggleAllPageRowsSelected(!!v)}
                                        disabled={data.length === 0}
                                    />
                                </TableHead>
                            )}
                            {hg.headers.map(renderHead)}
                            {rowActions && <TableHead scope="col" className={cn(d.head, "w-10")}><span className="sr-only">Actions</span></TableHead>}
                        </TableRow>
                    ))}
                </TableHeader>

                <TableBody>
                    {isLoading &&
                        Array.from({ length: SKELETON_ROWS }, (_, i) => (
                            <TableRow key={`sk-${i}`} data-testid="dt-skeleton-row" className="hover:bg-transparent">
                                <TableCell colSpan={colSpan} className={d.cell}><Skeleton className="h-4 w-full" /></TableCell>
                            </TableRow>
                        ))}

                    {isError && (
                        <TableRow className="hover:bg-transparent">
                            <TableCell colSpan={colSpan}>
                                <div role="alert" className="flex flex-col items-center gap-2 px-6 py-10 text-center">
                                    <AlertCircle className="size-6 text-danger-text" aria-hidden="true" />
                                    <p className="text-sm font-medium">Could not load data</p>
                                    <p className="text-xs text-muted-foreground">{errorMessage(state.error)}</p>
                                    {onRetry && <Button variant="outline" size="sm" onClick={onRetry}>Retry</Button>}
                                </div>
                            </TableCell>
                        </TableRow>
                    )}

                    {isEmpty && (
                        <TableRow className="hover:bg-transparent">
                            <TableCell colSpan={colSpan}>
                                <div data-testid="dt-empty" className="flex flex-col items-center gap-1 px-6 py-10 text-center">
                                    <Inbox className="size-6 text-muted-foreground" aria-hidden="true" />
                                    <p className="text-sm font-medium">{empty?.title ?? "No records found"}</p>
                                    {empty?.description && <p className="text-xs text-muted-foreground">{empty.description}</p>}
                                    {empty?.action}
                                </div>
                            </TableCell>
                        </TableRow>
                    )}

                    {state.status === "success" &&
                        table.getRowModel().rows.map((row) => {
                            const original = row.original;
                            const expanded = expansion?.isExpanded(original) ?? false;
                            const label = expansion?.getRowLabel(original) ?? row.id;
                            const rid = expansion?.regionId(row.id) ?? `${uid}-${row.id}`;
                            return (
                                <React.Fragment key={row.id}>
                                    <TableRow
                                        data-state={row.getIsSelected() ? "selected" : undefined}
                                        tabIndex={onRowClick ? 0 : undefined}
                                        className={cn(onRowClick && "cursor-pointer")}
                                        onClick={onRowClick ? (e) => {
                                            if ((e.target as HTMLElement).closest("button,a,input,[role=checkbox]")) return;
                                            onRowClick(original);
                                        } : undefined}
                                        onKeyDown={onRowClick ? (e) => {
                                            if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
                                                e.preventDefault();
                                                onRowClick(original);
                                            }
                                        } : undefined}
                                    >
                                        {expansion && (
                                            <TableCell className={cn(d.cell, "w-8")}>
                                                <button
                                                    type="button"
                                                    aria-expanded={expanded}
                                                    aria-controls={rid}
                                                    aria-label={`${expanded ? "Collapse" : "Expand"} ${label}`}
                                                    onClick={() => expansion.onToggle(original)}
                                                    className="inline-flex size-6 items-center justify-center rounded-sm outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40"
                                                >
                                                    <ChevronRight className={cn("size-4 transition-transform motion-reduce:transition-none", expanded && "rotate-90")} aria-hidden="true" />
                                                </button>
                                            </TableCell>
                                        )}
                                        {selection && (
                                            <TableCell className={cn(d.cell, "w-8")}>
                                                <Checkbox
                                                    aria-label={`Select row ${row.id}`}
                                                    checked={row.getIsSelected()}
                                                    onCheckedChange={(v) => row.toggleSelected(!!v)}
                                                />
                                            </TableCell>
                                        )}
                                        {row.getVisibleCells().map((cell) => (
                                            <TableCell key={cell.id} style={resizable ? { width: cell.column.getSize() } : undefined} className={cellClass(cell.column.columnDef.meta, false)}>
                                                {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                            </TableCell>
                                        ))}
                                        {rowActions && <TableCell className={cn(d.cell, "w-10")}>{rowActions(original)}</TableCell>}
                                    </TableRow>
                                    {expansion && expanded && (
                                        <TableRow className="hover:bg-transparent">
                                            <TableCell colSpan={colSpan} className="bg-muted/20 p-0">
                                                <div id={rid} role="region" aria-label={`Details for ${label}`} className="p-3">
                                                    {expansion.renderExpanded(original)}
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </React.Fragment>
                            );
                        })}
                </TableBody>

                {hasFooter && state.status === "success" && (
                    <TableFooter>
                        <TableRow className="hover:bg-transparent">
                            {expansion && <TableCell className={d.cell} />}
                            {selection && <TableCell className={d.cell} />}
                            {leafColumns.map((c) => (
                                <TableCell key={c.id} className={cellClass(c.columnDef.meta, false)}>{c.columnDef.meta?.footer}</TableCell>
                            ))}
                            {rowActions && <TableCell className={d.cell} />}
                        </TableRow>
                    </TableFooter>
                )}
            </Table>

            {footer}
        </div>
    );
}
