// BOEList — main Bill of Entry list page.
// Features: search by BOE number, date range filter, paginated table,
// skeleton loaders, navigation to BOEDetail on row click.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ClipboardList, Loader2, Plus, Search } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Skeleton } from '@/shared/ui/skeleton'
import { cn } from '@/shared/utils/cn'
import { formatDate } from '@/shared/utils/formatters'
import { useDebounce } from '@/shared/hooks/useDebounce'
import { useBOEs } from '../queries'
import type { BOEListParams } from '../types'

// ── Table skeleton ─────────────────────────────────────────────────────────────

function TableSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <Skeleton className="h-9 w-1/5" />
          <Skeleton className="h-9 w-1/8" />
          <Skeleton className="h-9 w-1/6" />
          <Skeleton className="h-9 w-1/6" />
          <Skeleton className="h-9 w-1/6" />
          <Skeleton className="h-9 w-1/8" />
          <Skeleton className="h-9 w-20" />
        </div>
      ))}
    </div>
  )
}

// ── Pagination controls ───────────────────────────────────────────────────────

interface PaginationProps {
  page: number
  totalCount: number
  pageSize: number
  onPageChange: (page: number) => void
}

function Pagination({ page, totalCount, pageSize, onPageChange }: PaginationProps) {
  const totalPages = Math.ceil(totalCount / pageSize)
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center justify-between border-t px-4 py-3 text-sm">
      <span className="text-muted-foreground">
        Page {page} of {totalPages} ({totalCount} results)
      </span>
      <div className="flex gap-1">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
        >
          Next
        </Button>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

const PAGE_SIZE = 25

export default function BOEList() {
  const navigate = useNavigate()

  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 350)
  const [page, setPage] = useState(1)
  const [dateAfter, setDateAfter] = useState('')
  const [dateBefore, setDateBefore] = useState('')

  function handleSearchChange(value: string) {
    setSearch(value)
    setPage(1)
  }

  function handleDateAfterChange(value: string) {
    setDateAfter(value)
    setPage(1)
  }

  function handleDateBeforeChange(value: string) {
    setDateBefore(value)
    setPage(1)
  }

  const queryParams: BOEListParams = {
    search: debouncedSearch || undefined,
    bill_of_entry_number: debouncedSearch || undefined,
    bill_of_entry_date_after: dateAfter || undefined,
    bill_of_entry_date_before: dateBefore || undefined,
    page,
    page_size: PAGE_SIZE,
  }

  const { data, isLoading, isFetching, isError } = useBOEs(queryParams)

  // Handle both envelope and direct response shapes gracefully.
  const envelope = data as unknown as {
    data?: { count: number; results: unknown[] }
    count?: number
    results?: unknown[]
  }

  const results = envelope?.data?.results ?? envelope?.results ?? []
  const totalCount = envelope?.data?.count ?? envelope?.count ?? 0

  const boes = results as Array<{
    id: number
    bill_of_entry_number: string
    bill_of_entry_date: string | null
    company_name: string | null
    port_name: string | null
    product_name: string
    total_fc: string
    total_inr: string
    total_quantity: string
    invoice_no: string | null
  }>

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Page header */}
      <div className="border-b bg-card px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <ClipboardList
              className="size-5 text-muted-foreground"
              aria-hidden="true"
            />
            <div>
              <h1 className="text-lg font-semibold">Bills of Entry</h1>
              <p className="text-sm text-muted-foreground">
                Import bills of entry and their item rows
              </p>
            </div>
          </div>
          {/* Create placeholder — wired when form modal is built */}
          <Button size="sm" disabled aria-label="Create Bill of Entry (coming soon)">
            <Plus className="size-4" aria-hidden="true" />
            New BOE
          </Button>
        </div>
      </div>

      <div className="flex-1 space-y-4 p-6">
        {/* Search + date filters */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="relative max-w-sm flex-1">
            <Search
              className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              type="search"
              placeholder="Search BOE number…"
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="pl-9"
              aria-label="Search BOE number"
            />
          </div>

          <div className="flex items-end gap-2">
            <div className="space-y-1">
              <label
                htmlFor="date-after"
                className="text-xs font-medium text-muted-foreground"
              >
                Date from
              </label>
              <Input
                id="date-after"
                type="date"
                value={dateAfter}
                onChange={(e) => handleDateAfterChange(e.target.value)}
                className="w-36"
                aria-label="Filter BOEs from date"
              />
            </div>
            <div className="space-y-1">
              <label
                htmlFor="date-before"
                className="text-xs font-medium text-muted-foreground"
              >
                Date to
              </label>
              <Input
                id="date-before"
                type="date"
                value={dateBefore}
                onChange={(e) => handleDateBeforeChange(e.target.value)}
                className="w-36"
                aria-label="Filter BOEs to date"
              />
            </div>
            {(dateAfter || dateBefore) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setDateAfter('')
                  setDateBefore('')
                  setPage(1)
                }}
              >
                Clear dates
              </Button>
            )}
          </div>
        </div>

        {/* Table */}
        <div className="rounded-lg border bg-card shadow-sm">
          {/* Table header */}
          <div className="flex items-center justify-between border-b px-4 py-2.5">
            <span className="text-sm text-muted-foreground">
              {isFetching && !isLoading && (
                <Loader2
                  className="mr-2 inline size-3.5 animate-spin"
                  aria-hidden="true"
                />
              )}
              {isLoading
                ? 'Loading…'
                : `${totalCount} bill${totalCount !== 1 ? 's' : ''} of entry`}
            </span>
          </div>

          {isError ? (
            <div className="px-4 py-8 text-center text-sm text-destructive">
              Failed to load Bills of Entry. Please try again.
            </div>
          ) : isLoading ? (
            <TableSkeleton />
          ) : boes.length === 0 ? (
            <div className="px-4 py-12 text-center">
              <ClipboardList
                className="mx-auto mb-3 size-10 text-muted-foreground opacity-40"
                aria-hidden="true"
              />
              <p className="text-sm text-muted-foreground">
                No bills of entry found.
              </p>
              {(search || dateAfter || dateBefore) && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Try clearing the filters.
                </p>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    {[
                      'BOE Number',
                      'Date',
                      'Company',
                      'Port',
                      'Product',
                      'Total FC',
                      'Total INR',
                      'Total Qty',
                      'Invoice No',
                    ].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {boes.map((boe, idx) => (
                    <tr
                      key={boe.id}
                      className={cn(
                        'cursor-pointer border-b transition-colors hover:bg-accent/40',
                        idx % 2 === 1 && 'bg-muted/20',
                      )}
                      onClick={() => navigate(`/boe/${boe.id}`)}
                      tabIndex={0}
                      role="row"
                      aria-label={`View BOE ${boe.bill_of_entry_number}`}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          navigate(`/boe/${boe.id}`)
                        }
                      }}
                    >
                      <td className="px-4 py-2.5 font-mono font-semibold">
                        {boe.bill_of_entry_number}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {formatDate(boe.bill_of_entry_date ?? '')}
                      </td>
                      <td className="max-w-[160px] truncate px-4 py-2.5 text-muted-foreground">
                        {boe.company_name ?? '—'}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {boe.port_name ?? '—'}
                      </td>
                      <td className="max-w-[160px] truncate px-4 py-2.5 text-muted-foreground">
                        {boe.product_name}
                      </td>
                      <td className="px-4 py-2.5 tabular-nums font-semibold text-emerald-700 dark:text-emerald-400">
                        {boe.total_fc !== ''
                          ? parseFloat(boe.total_fc).toFixed(2)
                          : '—'}
                      </td>
                      <td className="px-4 py-2.5 tabular-nums font-semibold">
                        {boe.total_inr !== ''
                          ? parseFloat(boe.total_inr).toFixed(2)
                          : '—'}
                      </td>
                      <td className="px-4 py-2.5 tabular-nums">
                        {boe.total_quantity !== ''
                          ? parseFloat(boe.total_quantity).toFixed(3)
                          : '—'}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                        {boe.invoice_no ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {!isLoading && !isError && (
            <Pagination
              page={page}
              totalCount={totalCount}
              pageSize={PAGE_SIZE}
              onPageChange={setPage}
            />
          )}
        </div>
      </div>
    </div>
  )
}
