// TradeList — paginated, filterable list of trades.
// Features: direction filter, search by invoice number, pagination, row navigation.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeftRight, FileText, Loader2, Plus, Printer, Search } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Skeleton } from '@/shared/ui/skeleton'
import { cn } from '@/shared/utils/cn'
import { formatDate } from '@/shared/utils/formatters'
import { useDebounce } from '@/shared/hooks/useDebounce'
import { useTrades } from '../queries'
import {
  useGeneratePurchaseInvoice,
  useGenerateBillOfSupply,
} from '../mutations'
import type { Trade, TradeDirection } from '../types'

// ─── Skeletons ────────────────────────────────────────────────────────────────

function TableSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <Skeleton className="h-9 w-1/5" />
          <Skeleton className="h-9 w-1/8" />
          <Skeleton className="h-9 w-1/6" />
          <Skeleton className="h-9 w-1/6" />
          <Skeleton className="h-9 w-1/8" />
          <Skeleton className="h-9 w-1/8" />
          <Skeleton className="h-9 w-1/8" />
        </div>
      ))}
    </div>
  )
}

// ─── Pagination ───────────────────────────────────────────────────────────────

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
        <Button variant="outline" size="sm" onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
          Previous
        </Button>
        <Button variant="outline" size="sm" onClick={() => onPageChange(page + 1)} disabled={page >= totalPages}>
          Next
        </Button>
      </div>
    </div>
  )
}

// ─── Direction badge ──────────────────────────────────────────────────────────

const DIRECTION_STYLES: Record<TradeDirection, string> = {
  PURCHASE: 'bg-blue-500/10 text-blue-700 dark:text-blue-400',
  SALE: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  COMMISSION_PURCHASE: 'bg-violet-500/10 text-violet-700 dark:text-violet-400',
  COMMISSION_SALE: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
}

function DirectionBadge({ direction, label }: { direction: TradeDirection; label: string }) {
  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5 text-xs font-semibold',
        DIRECTION_STYLES[direction] ?? 'bg-muted text-muted-foreground',
      )}
    >
      {label}
    </span>
  )
}

// ─── Constants ────────────────────────────────────────────────────────────────

const PAGE_SIZE = 25

const DIRECTION_OPTIONS: Array<{ value: '' | TradeDirection; label: string }> = [
  { value: '', label: 'All directions' },
  { value: 'PURCHASE', label: 'Purchase' },
  { value: 'SALE', label: 'Sale' },
  { value: 'COMMISSION_PURCHASE', label: 'Commission Purchase' },
  { value: 'COMMISSION_SALE', label: 'Commission Sale' },
]

// ─── PDF action cell ─────────────────────────────────────────────────────────

function PdfActionCell({ trade }: { trade: Trade }) {
  const purchaseMutation = useGeneratePurchaseInvoice()
  const billMutation = useGenerateBillOfSupply()

  if (trade.direction === 'PURCHASE' || trade.direction === 'COMMISSION_PURCHASE') {
    return (
      <td className="px-4 py-2.5" onClick={(e) => e.stopPropagation()}>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs"
          disabled={purchaseMutation.isPending}
          onClick={() => purchaseMutation.mutate(trade.id)}
          aria-label={`Download purchase invoice for ${trade.invoice_number}`}
          title="Download Purchase Invoice PDF"
        >
          {purchaseMutation.isPending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <Printer className="size-3.5" aria-hidden="true" />
          )}
          <span className="ml-1 hidden sm:inline">Invoice</span>
        </Button>
      </td>
    )
  }

  if (trade.direction === 'SALE' || trade.direction === 'COMMISSION_SALE') {
    return (
      <td className="px-4 py-2.5" onClick={(e) => e.stopPropagation()}>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs"
          disabled={billMutation.isPending}
          onClick={() => billMutation.mutate(trade.id)}
          aria-label={`Download bill of supply for ${trade.invoice_number}`}
          title="Download Bill of Supply PDF"
        >
          {billMutation.isPending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <FileText className="size-3.5" aria-hidden="true" />
          )}
          <span className="ml-1 hidden sm:inline">Bill</span>
        </Button>
      </td>
    )
  }

  return <td className="px-4 py-2.5" />
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function TradeList() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 350)
  const [page, setPage] = useState(1)
  const [direction, setDirection] = useState<'' | TradeDirection>('')

  function handleSearchChange(value: string) {
    setSearch(value)
    setPage(1)
  }

  function handleDirectionChange(value: '' | TradeDirection) {
    setDirection(value)
    setPage(1)
  }

  const queryParams = {
    search: debouncedSearch || undefined,
    direction: direction || undefined,
    page,
    page_size: PAGE_SIZE,
  }

  const { data, isLoading, isFetching, isError } = useTrades(queryParams)

  const results = data?.data ?? []
  const totalCount = data?.pagination?.count ?? 0

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Page header */}
      <div className="border-b bg-card px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <ArrowLeftRight className="size-5 text-muted-foreground" aria-hidden="true" />
            <div>
              <h1 className="text-lg font-semibold">Trades</h1>
              <p className="text-sm text-muted-foreground">
                Purchase, sale and commission trade invoices
              </p>
            </div>
          </div>
          <Button onClick={() => navigate('/trades/new')} size="sm">
            <Plus className="size-4" aria-hidden="true" />
            New Trade
          </Button>
        </div>
      </div>

      <div className="flex-1 space-y-4 p-6">
        {/* Filters row */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative max-w-sm flex-1">
            <Search
              className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              type="search"
              placeholder="Search invoice number…"
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="pl-9"
              aria-label="Search trades"
            />
          </div>
          <select
            value={direction}
            onChange={(e) => handleDirectionChange(e.target.value as '' | TradeDirection)}
            className="rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            aria-label="Filter by direction"
          >
            {DIRECTION_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Table */}
        <div className="rounded-lg border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b px-4 py-2.5">
            <span className="text-sm text-muted-foreground">
              {isFetching && !isLoading && (
                <Loader2 className="mr-2 inline size-3.5 animate-spin" aria-hidden="true" />
              )}
              {isLoading
                ? 'Loading…'
                : `${totalCount} trade${totalCount !== 1 ? 's' : ''}`}
            </span>
          </div>

          {isError ? (
            <div className="px-4 py-8 text-center text-sm text-destructive">
              Failed to load trades. Please try again.
            </div>
          ) : isLoading ? (
            <TableSkeleton />
          ) : results.length === 0 ? (
            <div className="px-4 py-12 text-center">
              <ArrowLeftRight
                className="mx-auto mb-3 size-10 text-muted-foreground opacity-40"
                aria-hidden="true"
              />
              <p className="text-sm text-muted-foreground">No trades found.</p>
              {(search || direction) && (
                <p className="mt-1 text-xs text-muted-foreground">Try clearing the filters.</p>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    {[
                      'Invoice Number',
                      'Direction',
                      'License Type',
                      'From Company',
                      'To Company',
                      'Invoice Date',
                      'Total Amount',
                      'Paid',
                      'Due',
                      'PDF',
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
                  {results.map((trade, idx) => {
                    const due = parseFloat(trade.due_amount) || 0
                    const total = parseFloat(trade.total_amount) || 0
                    const dueCls =
                      due <= 0
                        ? 'text-emerald-700 dark:text-emerald-400'
                        : due < total
                          ? 'text-amber-600 dark:text-amber-400'
                          : 'text-destructive'
                    return (
                      <tr
                        key={trade.id}
                        className={cn(
                          'cursor-pointer border-b transition-colors hover:bg-accent/40',
                          idx % 2 === 1 && 'bg-muted/20',
                        )}
                        onClick={() => navigate(`/trades/${trade.id}`)}
                        tabIndex={0}
                        role="row"
                        aria-label={`View trade ${trade.invoice_number}`}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            navigate(`/trades/${trade.id}`)
                          }
                        }}
                      >
                        <td className="px-4 py-2.5 font-mono font-semibold">
                          {trade.invoice_number}
                        </td>
                        <td className="px-4 py-2.5">
                          <DirectionBadge
                            direction={trade.direction}
                            label={trade.direction_label}
                          />
                        </td>
                        <td className="px-4 py-2.5 text-muted-foreground">
                          {trade.license_type_label}
                        </td>
                        <td className="max-w-[160px] truncate px-4 py-2.5 text-muted-foreground">
                          {trade.from_company?.name ?? trade.from_company_label ?? '—'}
                        </td>
                        <td className="max-w-[160px] truncate px-4 py-2.5 text-muted-foreground">
                          {trade.to_company?.name ?? trade.to_company_label ?? '—'}
                        </td>
                        <td className="px-4 py-2.5 text-muted-foreground">
                          {formatDate(trade.invoice_date)}
                        </td>
                        <td className="px-4 py-2.5 tabular-nums font-semibold">
                          {parseFloat(trade.total_amount).toFixed(2)}
                        </td>
                        <td className="px-4 py-2.5 tabular-nums text-emerald-700 dark:text-emerald-400">
                          {parseFloat(trade.paid_or_received).toFixed(2)}
                        </td>
                        <td className={cn('px-4 py-2.5 tabular-nums font-semibold', dueCls)}>
                          {parseFloat(trade.due_amount).toFixed(2)}
                        </td>
                        <PdfActionCell trade={trade} />
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

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
