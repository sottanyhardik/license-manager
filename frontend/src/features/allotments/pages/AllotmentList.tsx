// AllotmentList — paginated list page at /allotments.
// Features: search (300 ms debounce), type filter, edit/delete actions,
//           "New Allotment" dialog, pagination.

import { useCallback, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { Plus, Search, X } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Skeleton } from '@/shared/ui/skeleton'
import { cn } from '@/shared/utils/cn'
import { useDebounce } from '@/shared/hooks/useDebounce'
import { AllotmentForm } from '../components/AllotmentForm'
import { AllotmentStatusBadge } from '../components/AllotmentStatusBadge'
import { useAllotments, useDeleteAllotment } from '../queries'
import type { Allotment, AllotmentType } from '../types'

// ─── Type filter options ───────────────────────────────────────────────────────

type TypeFilter = 'all' | AllotmentType

const TYPE_OPTIONS: { value: TypeFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'AT', label: 'Allotment' },
  { value: 'TR', label: 'Transfer' },
]

// ─── Skeleton rows ─────────────────────────────────────────────────────────────

function TableSkeletonRows({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <tr key={i} className="border-b">
          {Array.from({ length: 8 }).map((__, j) => (
            <td key={j} className="px-3 py-3">
              <Skeleton className="h-4 w-full" />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

// ─── Confirm dialog ────────────────────────────────────────────────────────────

function ConfirmDeleteDialog({
  allotment,
  onConfirm,
  onCancel,
  isPending,
}: {
  allotment: Allotment
  onConfirm: () => void
  onCancel: () => void
  isPending: boolean
}) {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Delete allotment{' '}
        <span className="font-semibold text-foreground">&ldquo;{allotment.item_name}&rdquo;</span>
        ? This action cannot be undone.
      </p>
      <div className="flex justify-end gap-3">
        <Button variant="outline" onClick={onCancel} disabled={isPending}>
          Cancel
        </Button>
        <Button variant="destructive" onClick={onConfirm} disabled={isPending}>
          Delete
        </Button>
      </div>
    </div>
  )
}

// ─── Main component ────────────────────────────────────────────────────────────

export default function AllotmentList() {
  const [searchInput, setSearchInput] = useState('')
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all')
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 25

  const debouncedSearch = useDebounce(searchInput, 300)

  const { data, isLoading } = useAllotments({
    search: debouncedSearch || undefined,
    type: typeFilter === 'all' ? undefined : typeFilter,
    page,
    page_size: PAGE_SIZE,
  })

  const deleteMutation = useDeleteAllotment()

  // ─── Create dialog state ─────────────────────────────────────────────────
  const [createOpen, setCreateOpen] = useState(false)

  // ─── Edit dialog state ───────────────────────────────────────────────────
  const [editTarget, setEditTarget] = useState<Allotment | null>(null)

  // ─── Delete confirm state ────────────────────────────────────────────────
  const [deleteTarget, setDeleteTarget] = useState<Allotment | null>(null)

  const handleDeleteConfirm = useCallback(() => {
    if (!deleteTarget) return
    deleteMutation.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
      onError: () => setDeleteTarget(null),
    })
  }, [deleteTarget, deleteMutation])

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchInput(e.target.value)
    setPage(1)
  }, [])

  const allotments = data?.results ?? []
  const totalCount = data?.count ?? 0
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE))

  return (
    <div className="flex flex-col gap-4 p-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Allotments</h1>
          {!isLoading && (
            <p className="mt-0.5 text-sm text-muted-foreground">
              {totalCount} record{totalCount !== 1 ? 's' : ''}
            </p>
          )}
        </div>

        {/* Create dialog */}
        <Dialog.Root open={createOpen} onOpenChange={setCreateOpen}>
          <Dialog.Trigger asChild>
            <Button size="sm">
              <Plus aria-hidden="true" />
              New Allotment
            </Button>
          </Dialog.Trigger>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
            <Dialog.Content
              className={cn(
                'fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-full max-w-2xl -translate-x-1/2 -translate-y-1/2',
                'overflow-y-auto rounded-lg border bg-background p-6 shadow-lg',
                'data-[state=open]:animate-in data-[state=closed]:animate-out',
                'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
                'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
                'data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%]',
                'data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]',
              )}
            >
              <div className="mb-4 flex items-center justify-between">
                <Dialog.Title className="text-lg font-semibold">New Allotment</Dialog.Title>
                <Dialog.Close asChild>
                  <Button variant="ghost" size="icon" aria-label="Close">
                    <X className="size-4" aria-hidden="true" />
                  </Button>
                </Dialog.Close>
              </div>
              <AllotmentForm
                mode="create"
                onSuccess={() => setCreateOpen(false)}
                onCancel={() => setCreateOpen(false)}
              />
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative max-w-xs flex-1">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            value={searchInput}
            onChange={handleSearchChange}
            placeholder="Search allotments..."
            className="pl-8"
            aria-label="Search allotments"
          />
        </div>

        <div className="flex items-center gap-1 rounded-lg border p-1" role="group" aria-label="Filter by type">
          {TYPE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => {
                setTypeFilter(opt.value)
                setPage(1)
              }}
              className={cn(
                'rounded-md px-3 py-1 text-sm font-medium transition-colors',
                typeFilter === opt.value
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
              )}
              aria-pressed={typeFilter === opt.value}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border bg-card shadow-sm">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-3 py-3 text-left font-medium text-muted-foreground">Item Name</th>
              <th className="px-3 py-3 text-left font-medium text-muted-foreground">Company</th>
              <th className="px-3 py-3 text-left font-medium text-muted-foreground">Status</th>
              <th className="px-3 py-3 text-right font-medium text-muted-foreground">Req. Qty</th>
              <th className="px-3 py-3 text-left font-medium text-muted-foreground">Invoice</th>
              <th className="px-3 py-3 text-left font-medium text-muted-foreground">Arrival Date</th>
              <th className="px-3 py-3 text-left font-medium text-muted-foreground">Approved</th>
              <th className="px-3 py-3 text-right font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <TableSkeletonRows count={8} />
            ) : allotments.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-12 text-center text-sm text-muted-foreground">
                  No allotments found.
                </td>
              </tr>
            ) : (
              allotments.map((row) => (
                <tr key={row.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-3 py-3 font-medium">{row.item_name}</td>
                  <td className="px-3 py-3 text-muted-foreground">{row.company_name}</td>
                  <td className="px-3 py-3">
                    <AllotmentStatusBadge
                      type={row.type}
                      isApproved={row.is_approved}
                      isAllotted={row.is_allotted}
                    />
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">{row.required_quantity}</td>
                  <td className="px-3 py-3 text-muted-foreground">{row.invoice ?? '—'}</td>
                  <td className="px-3 py-3 text-muted-foreground">
                    {row.estimated_arrival_date ?? '—'}
                  </td>
                  <td className="px-3 py-3">
                    <span
                      className={cn(
                        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold',
                        row.is_approved
                          ? 'border-emerald-400/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                          : 'border-border bg-muted text-muted-foreground',
                      )}
                    >
                      {row.is_approved ? 'Yes' : 'No'}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex items-center justify-end gap-2">
                      {/* Edit */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setEditTarget(row)}
                        aria-label={`Edit ${row.item_name}`}
                      >
                        Edit
                      </Button>
                      {/* Delete */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeleteTarget(row)}
                        aria-label={`Delete ${row.item_name}`}
                        className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                      >
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between gap-4 text-sm text-muted-foreground">
        <span>
          Page {page} of {totalPages} &mdash; {totalCount} total
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => p - 1)}
            disabled={page <= 1 || isLoading}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => p + 1)}
            disabled={page >= totalPages || isLoading}
          >
            Next
          </Button>
        </div>
      </div>

      {/* Edit dialog */}
      <Dialog.Root open={editTarget !== null} onOpenChange={(open) => { if (!open) setEditTarget(null) }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
          <Dialog.Content
            className={cn(
              'fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-full max-w-2xl -translate-x-1/2 -translate-y-1/2',
              'overflow-y-auto rounded-lg border bg-background p-6 shadow-lg',
              'data-[state=open]:animate-in data-[state=closed]:animate-out',
              'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
              'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
              'data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%]',
              'data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]',
            )}
          >
            <div className="mb-4 flex items-center justify-between">
              <Dialog.Title className="text-lg font-semibold">Edit Allotment</Dialog.Title>
              <Dialog.Close asChild>
                <Button variant="ghost" size="icon" aria-label="Close">
                  <X className="size-4" aria-hidden="true" />
                </Button>
              </Dialog.Close>
            </div>
            {editTarget && (
              <AllotmentForm
                mode="edit"
                allotmentId={editTarget.id}
                defaultValues={{
                  company: editTarget.company,
                  type: editTarget.type,
                  port: editTarget.port,
                  item_name: editTarget.item_name,
                  required_quantity: editTarget.required_quantity,
                  unit_value_per_unit: editTarget.unit_value_per_unit,
                  cif_fc: editTarget.cif_fc ?? '0',
                  cif_inr: editTarget.cif_inr ?? '0',
                  exchange_rate: editTarget.exchange_rate ?? '0',
                  invoice: editTarget.invoice ?? '',
                  estimated_arrival_date: editTarget.estimated_arrival_date ?? '',
                  bl_detail: editTarget.bl_detail ?? '',
                  is_approved: editTarget.is_approved,
                }}
                onSuccess={() => setEditTarget(null)}
                onCancel={() => setEditTarget(null)}
              />
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Delete confirm dialog */}
      <Dialog.Root open={deleteTarget !== null} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
          <Dialog.Content
            className={cn(
              'fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2',
              'rounded-lg border bg-background p-6 shadow-lg',
              'data-[state=open]:animate-in data-[state=closed]:animate-out',
              'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
              'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
            )}
          >
            <Dialog.Title className="mb-2 text-lg font-semibold text-destructive">
              Delete Allotment
            </Dialog.Title>
            {deleteTarget && (
              <ConfirmDeleteDialog
                allotment={deleteTarget}
                onConfirm={handleDeleteConfirm}
                onCancel={() => setDeleteTarget(null)}
                isPending={deleteMutation.isPending}
              />
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  )
}
