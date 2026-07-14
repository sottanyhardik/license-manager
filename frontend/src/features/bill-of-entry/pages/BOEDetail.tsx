// BOEDetail — detail page for a single Bill of Entry.
// Shows header metadata, summary totals, item rows table, and ledger upload.
// DisputeResolver modal opens when user clicks "Resolve" on a dispute row.

import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Building2, Calendar, ClipboardList, TriangleAlert } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Skeleton } from '@/shared/ui/skeleton'
import { formatDate } from '@/shared/utils/formatters'
import { useBOE } from '../queries'
import BOERowsTable from '../components/BOERowsTable'
import DisputeResolver from '../components/DisputeResolver'
import LedgerUpload from '../components/LedgerUpload'

// ── Header skeleton ───────────────────────────────────────────────────────────

function HeaderSkeleton() {
  return (
    <div className="space-y-3 p-6">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-5 w-96" />
      <div className="flex gap-4 pt-2">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-5 w-32" />
      </div>
    </div>
  )
}

// ── Summary stat card ─────────────────────────────────────────────────────────

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-card p-4 shadow-sm">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 tabular-nums text-lg font-semibold">{value}</p>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function BOEDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const boeId = id ? parseInt(id, 10) : null

  const { data: boe, isLoading, isError, refetch } = useBOE(boeId)

  const [resolveRowId, setResolveRowId] = useState<number | null>(null)

  function handleResolve(rowId: number) {
    setResolveRowId(rowId)
  }

  function handleResolverClose() {
    setResolveRowId(null)
  }

  function handleResolved() {
    setResolveRowId(null)
    void refetch()
  }

  // ── Guard: invalid id ────────────────────────────────────────────────────────

  if (!boeId || isNaN(boeId)) {
    return (
      <div className="p-6 text-center text-destructive">
        Invalid Bill of Entry ID.
      </div>
    )
  }

  // ── Loading state ─────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="border-b bg-card">
          <HeaderSkeleton />
        </div>
      </div>
    )
  }

  // ── Error state ───────────────────────────────────────────────────────────────

  if (isError || !boe) {
    return (
      <div className="p-6">
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
          Failed to load Bill of Entry.
        </div>
        <Button variant="outline" onClick={() => navigate(-1)}>
          <ArrowLeft className="size-4" aria-hidden="true" />
          Go Back
        </Button>
      </div>
    )
  }

  // ── Render ────────────────────────────────────────────────────────────────────

  const rows = boe.item_details ?? []

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b bg-card px-6 py-5">
        <div className="mb-4 flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(-1)}
            className="gap-1"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            Back
          </Button>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          {/* BOE identity */}
          <div>
            <div className="mb-1 flex items-center gap-2 flex-wrap">
              <ClipboardList
                className="size-5 text-muted-foreground"
                aria-hidden="true"
              />
              <h1 className="font-mono text-xl font-bold">
                {boe.bill_of_entry_number}
              </h1>
            </div>

            <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
              {boe.company_name && (
                <div className="flex items-center gap-1">
                  <Building2 className="size-3.5" aria-hidden="true" />
                  <span>{boe.company_name}</span>
                </div>
              )}
              {boe.bill_of_entry_date && (
                <div className="flex items-center gap-1">
                  <Calendar className="size-3.5" aria-hidden="true" />
                  <span>BOE Date: {formatDate(boe.bill_of_entry_date)}</span>
                </div>
              )}
              {boe.port_name && (
                <div>Port: {boe.port_name}</div>
              )}
              {boe.invoice_no && (
                <div>Invoice: {boe.invoice_no}</div>
              )}
              {boe.invoice_date && (
                <div>Invoice Date: {formatDate(boe.invoice_date)}</div>
              )}
              {boe.ooc_date && (
                <div>OOC Date: {boe.ooc_date}</div>
              )}
              {boe.cha && (
                <div>CHA: {boe.cha}</div>
              )}
              <div>
                Exchange Rate:{' '}
                {parseFloat(boe.exchange_rate).toFixed(4)}
              </div>
              <div>Product: {boe.product_name}</div>
            </dl>

            {boe.comments && (
              <p className="mt-2 max-w-xl text-sm text-muted-foreground">
                {boe.comments}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Summary totals */}
      <div className="grid grid-cols-2 gap-4 p-6 sm:grid-cols-3 lg:grid-cols-4">
        <StatCard
          label="Total FC"
          value={
            boe.total_fc !== ''
              ? parseFloat(boe.total_fc).toFixed(2)
              : '—'
          }
        />
        <StatCard
          label="Total INR"
          value={
            boe.total_inr !== ''
              ? parseFloat(boe.total_inr).toFixed(2)
              : '—'
          }
        />
        <StatCard
          label="Total Quantity"
          value={
            boe.total_quantity !== ''
              ? parseFloat(boe.total_quantity).toFixed(3)
              : '—'
          }
        />
        {boe.unit_price !== '' && (
          <StatCard
            label="Unit Price"
            value={parseFloat(boe.unit_price).toFixed(4)}
          />
        )}
      </div>

      {/* Item rows */}
      <div className="px-6 pb-6">
        <h2 className="mb-3 text-sm font-semibold">Item Rows</h2>
        <BOERowsTable
          rows={rows}
          boeId={boeId}
          onResolve={handleResolve}
        />
      </div>

      {/* Ledger upload */}
      <div className="border-t px-6 py-6">
        <LedgerUpload onUploadComplete={() => void refetch()} />
      </div>

      {/* Dispute resolver modal */}
      {resolveRowId !== null && (
        <DisputeResolver
          boeId={boeId}
          rowId={resolveRowId}
          onClose={handleResolverClose}
          onResolved={handleResolved}
        />
      )}
    </div>
  )
}
