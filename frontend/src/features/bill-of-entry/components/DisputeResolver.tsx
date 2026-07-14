// DisputeResolver — modal panel for linking a dispute row to a license item.
//
// Shows the dispute row's key fields, accepts a license_item_id from the user,
// then calls the resolve-dispute endpoint.

import { useState } from 'react'
import { Loader2, X } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { cn } from '@/shared/utils/cn'
import { useBOERows } from '../queries'
import { useResolveDispute } from '../mutations'

export interface DisputeResolverProps {
  boeId: number
  rowId: number
  onClose: () => void
  onResolved: () => void
}

export default function DisputeResolver({
  boeId,
  rowId,
  onClose,
  onResolved,
}: DisputeResolverProps) {
  const [licenseItemId, setLicenseItemId] = useState('')

  const { data: rows, isLoading: rowsLoading } = useBOERows(boeId)
  const resolveDispute = useResolveDispute(boeId, rowId)

  const row = rows?.find((r) => r.id === rowId)

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const parsed = parseInt(licenseItemId.trim(), 10)
    if (isNaN(parsed) || parsed <= 0) return
    resolveDispute.mutate(
      { license_item_id: parsed },
      {
        onSuccess: () => {
          onResolved()
          onClose()
        },
      },
    )
  }

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-label="Resolve Dispute"
    >
      <div className="relative w-full max-w-md rounded-xl border bg-card p-6 shadow-xl">
        {/* Close */}
        <button
          type="button"
          onClick={onClose}
          className={cn(
            'absolute right-4 top-4 rounded p-1 text-muted-foreground',
            'hover:bg-accent hover:text-foreground',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          )}
          aria-label="Close"
        >
          <X className="size-4" aria-hidden="true" />
        </button>

        <h2 className="mb-1 text-base font-semibold">Resolve Dispute</h2>
        <p className="mb-4 text-sm text-muted-foreground">
          Link this row to the correct license import item.
        </p>

        {/* Row details */}
        {rowsLoading ? (
          <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            Loading row details…
          </div>
        ) : row ? (
          <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-1.5 rounded-lg border bg-muted/30 p-3 text-sm">
            <dt className="text-muted-foreground">SR Number</dt>
            <dd className="tabular-nums font-semibold">{row.sr_number}</dd>

            <dt className="text-muted-foreground">License</dt>
            <dd className="font-mono text-xs">{row.license_number ?? '—'}</dd>

            <dt className="text-muted-foreground">HS Code</dt>
            <dd className="tabular-nums">{row.hs_code ?? '—'}</dd>

            <dt className="text-muted-foreground">Description</dt>
            <dd className="col-span-1 truncate">{row.item_description ?? '—'}</dd>

            <dt className="text-muted-foreground">CIF FC</dt>
            <dd className="tabular-nums">{parseFloat(row.cif_fc).toFixed(2)}</dd>

            <dt className="text-muted-foreground">Qty</dt>
            <dd className="tabular-nums">{parseFloat(row.qty).toFixed(3)}</dd>
          </dl>
        ) : (
          <p className="mb-4 text-sm text-destructive">Row not found.</p>
        )}

        {/* Resolution form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="license-item-id">License Item ID</Label>
            <Input
              id="license-item-id"
              type="number"
              min={1}
              placeholder="Enter license item ID"
              value={licenseItemId}
              onChange={(e) => setLicenseItemId(e.target.value)}
              disabled={resolveDispute.isPending}
              required
            />
            <p className="text-xs text-muted-foreground">
              Enter the numeric ID of the matching license import item.
            </p>
          </div>

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={resolveDispute.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={resolveDispute.isPending || !licenseItemId.trim()}
            >
              {resolveDispute.isPending && (
                <Loader2
                  className="mr-1.5 size-3.5 animate-spin"
                  aria-hidden="true"
                />
              )}
              {resolveDispute.isPending ? 'Resolving…' : 'Resolve Dispute'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
