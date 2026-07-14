// MasterDataTable — generic TanStack Table wrapper for master list pages.
//
// Features:
//   - Column definitions provided by the caller via `columns` prop.
//   - Server-side search (debounced 300 ms) wired to onSearchChange callback.
//   - Column header click triggers onSortChange callback.
//   - Pagination controls (prev / next / page size selector).
//   - Edit / Delete action buttons gated by `canWrite` prop.
//   - Empty state with icon when no data is present.
//   - Loading skeleton while the query is in flight.
//
// All state (search, sort, page) is lifted out to the parent page component so
// the URL / query can be driven from a single source of truth.

import { useState } from 'react'
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { ChevronDown, ChevronUp, ChevronsUpDown, Inbox, Pencil, Search, Trash2 } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Skeleton } from '@/shared/ui/skeleton'
import { cn } from '@/shared/utils/cn'
import { useDebounce } from '@/shared/hooks/useDebounce'

export interface MasterDataTableProps<TData> {
  /** Column definitions — use TanStack Table's ColumnDef format. */
  columns: ColumnDef<TData, unknown>[]
  /** The current page of data from the server. */
  data: TData[]
  /** Total number of records (used for pagination display). */
  totalCount: number
  /** Current 1-based page number. */
  currentPage: number
  /** Rows per page — 25 / 50 / 100 selectable. */
  pageSize: number
  /** Whether the query is fetching (shows skeleton). */
  isLoading: boolean
  /** Called when user changes the search string (debounced). */
  onSearchChange: (search: string) => void
  /** Called when user clicks a column header to sort. */
  onSortChange: (ordering: string) => void
  /** Called when user clicks prev/next/page-size. */
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
  /** When true, Edit and Delete action buttons are rendered. */
  canWrite?: boolean
  /** Called when user clicks the Edit button for a row. */
  onEdit?: (row: TData) => void
  /** Called when user clicks the Delete button for a row. */
  onDelete?: (row: TData) => void
  /** Text shown in the search input placeholder. */
  searchPlaceholder?: string
}

const PAGE_SIZE_OPTIONS = [25, 50, 100] as const

export function MasterDataTable<TData>({
  columns,
  data,
  totalCount,
  currentPage,
  pageSize,
  isLoading,
  onSearchChange,
  onSortChange,
  onPageChange,
  onPageSizeChange,
  canWrite = false,
  onEdit,
  onDelete,
  searchPlaceholder = 'Search...',
}: MasterDataTableProps<TData>) {
  const [searchInput, setSearchInput] = useState('')
  const [sorting, setSorting] = useState<SortingState>([])

  const debouncedSearch = useDebounce(searchInput, 300)

  // Notify parent when debounced search changes.
  // We track the previous value to avoid firing on mount.
  const [lastSearch, setLastSearch] = useState('')
  if (debouncedSearch !== lastSearch) {
    setLastSearch(debouncedSearch)
    onSearchChange(debouncedSearch)
  }

  // Augment caller's columns with an Actions column when write-access is on.
  const allColumns: ColumnDef<TData, unknown>[] = [
    ...columns,
    ...(canWrite && (onEdit ?? onDelete)
      ? [
          {
            id: '__actions',
            header: '',
            enableSorting: false,
            cell: ({ row }: { row: { original: TData } }) => (
              <div className="flex items-center justify-end gap-1">
                {onEdit && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onEdit(row.original)}
                    aria-label="Edit"
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                  >
                    <Pencil className="size-3.5" aria-hidden="true" />
                  </Button>
                )}
                {onDelete && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onDelete(row.original)}
                    aria-label="Delete"
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="size-3.5" aria-hidden="true" />
                  </Button>
                )}
              </div>
            ),
          } satisfies ColumnDef<TData, unknown>,
        ]
      : []),
  ]

  const table = useReactTable<TData>({
    data,
    columns: allColumns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    manualPagination: true,
    rowCount: totalCount,
    state: { sorting },
    onSortingChange: (updater) => {
      const next = typeof updater === 'function' ? updater(sorting) : updater
      setSorting(next)
      if (next.length > 0) {
        const { id, desc } = next[0]
        onSortChange(desc ? `-${id}` : id)
      } else {
        onSortChange('')
      }
    },
  })

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))

  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-2">
        <div className="relative w-64">
          <Search
            className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            placeholder={searchPlaceholder}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="h-8 pl-8 text-sm"
            aria-label={searchPlaceholder}
          />
        </div>
        <p className="shrink-0 text-xs text-muted-foreground">
          {totalCount.toLocaleString()} record{totalCount !== 1 ? 's' : ''}
        </p>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm" role="grid">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b bg-muted/50">
                {hg.headers.map((header) => {
                  const canSort = header.column.getCanSort()
                  const sorted = header.column.getIsSorted()
                  return (
                    <th
                      key={header.id}
                      scope="col"
                      className={cn(
                        'px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground',
                        canSort && 'cursor-pointer select-none hover:text-foreground',
                      )}
                      onClick={canSort ? header.column.getToggleSortingHandler() : undefined}
                      aria-sort={
                        sorted === 'asc'
                          ? 'ascending'
                          : sorted === 'desc'
                          ? 'descending'
                          : 'none'
                      }
                    >
                      <span className="inline-flex items-center gap-1">
                        {header.isPlaceholder
                          ? null
                          : flexRender(header.column.columnDef.header, header.getContext())}
                        {canSort && (
                          <span aria-hidden="true">
                            {sorted === 'asc' ? (
                              <ChevronUp className="size-3" />
                            ) : sorted === 'desc' ? (
                              <ChevronDown className="size-3" />
                            ) : (
                              <ChevronsUpDown className="size-3 opacity-40" />
                            )}
                          </span>
                        )}
                      </span>
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {isLoading
              ? Array.from({ length: pageSize > 10 ? 10 : pageSize }).map((_, i) => (
                  <tr key={i} className="border-b last:border-0">
                    {allColumns.map((_, ci) => (
                      <td key={ci} className="px-3 py-2.5">
                        <Skeleton className="h-4 w-full" />
                      </td>
                    ))}
                  </tr>
                ))
              : table.getRowModel().rows.length === 0
              ? (
                  <tr>
                    <td colSpan={allColumns.length}>
                      <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
                        <Inbox className="size-8 opacity-40" aria-hidden="true" />
                        <p className="text-sm">No records found.</p>
                      </div>
                    </td>
                  </tr>
                )
              : table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className="border-b last:border-0 hover:bg-muted/30 transition-colors"
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-3 py-2.5">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      {/* Pagination controls */}
      <div className="flex items-center justify-between gap-4 text-sm">
        <div className="flex items-center gap-2">
          <label htmlFor="page-size-select" className="text-xs text-muted-foreground">
            Rows per page
          </label>
          <select
            id="page-size-select"
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className={cn(
              'h-8 rounded-md border border-input bg-background px-2 text-xs',
              'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
            )}
          >
            {PAGE_SIZE_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <p className="text-xs text-muted-foreground">
          Page {currentPage} of {totalPages}
        </p>

        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2"
            disabled={currentPage <= 1 || isLoading}
            onClick={() => onPageChange(currentPage - 1)}
            aria-label="Previous page"
          >
            Prev
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2"
            disabled={currentPage >= totalPages || isLoading}
            onClick={() => onPageChange(currentPage + 1)}
            aria-label="Next page"
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
