// BOERowsTable — renders the item_details rows for a Bill of Entry.
//
// Frozen rows: lock icon (Lock from lucide-react), edit/delete buttons
//   disabled + opacity-50.
// Dispute rows: red "Dispute" badge, "Resolve" action button.

import { Lock, Pencil, Trash2 } from 'lucide-react'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/utils/cn'
import type { RowDetail } from '../types'

export interface BOERowsTableProps {
  rows: RowDetail[]
  boeId: number
  onResolve: (rowId: number) => void
  onEdit?: (row: RowDetail) => void
  onDelete?: (rowId: number) => void
}

const COLUMN_HEADERS = [
  'Sr No',
  'License No',
  'Item Description',
  'HS Code',
  'Qty',
  'CIF FC',
  'CIF INR',
  'Type',
  'Actions',
]

export default function BOERowsTable({
  rows,
  onResolve,
  onEdit,
  onDelete,
}: BOERowsTableProps) {
  if (rows.length === 0) {
    return (
      <div className="py-10 text-center text-sm text-muted-foreground">
        No rows for this Bill of Entry.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border bg-card shadow-sm">
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/40">
          <tr>
            {COLUMN_HEADERS.map((h) => (
              <th
                key={h}
                className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr
              key={row.id}
              className={cn(
                'border-b transition-colors',
                idx % 2 === 1 && 'bg-muted/20',
                row.is_frozen && 'opacity-70',
              )}
            >
              {/* Sr No + frozen indicator */}
              <td className="px-3 py-2 tabular-nums">
                <span className="inline-flex items-center gap-1">
                  {row.sr_number}
                  {row.is_frozen && (
                    <Lock
                      className="size-3 text-muted-foreground"
                      aria-label="Row is frozen"
                    />
                  )}
                </span>
              </td>

              {/* License number */}
              <td className="px-3 py-2 font-mono text-xs">
                {row.license_number ?? '—'}
              </td>

              {/* Item description */}
              <td className="max-w-[200px] truncate px-3 py-2 text-muted-foreground">
                {row.item_description ?? '—'}
              </td>

              {/* HS code */}
              <td className="px-3 py-2 tabular-nums text-muted-foreground">
                {row.hs_code ?? '—'}
              </td>

              {/* Qty */}
              <td className="px-3 py-2 tabular-nums">
                {row.qty !== '' ? parseFloat(row.qty).toFixed(3) : '—'}
              </td>

              {/* CIF FC */}
              <td className="px-3 py-2 tabular-nums font-semibold">
                {row.cif_fc !== '' ? parseFloat(row.cif_fc).toFixed(2) : '—'}
              </td>

              {/* CIF INR */}
              <td className="px-3 py-2 tabular-nums font-semibold">
                {row.cif_inr !== '' ? parseFloat(row.cif_inr).toFixed(2) : '—'}
              </td>

              {/* Transaction type */}
              <td className="px-3 py-2">
                <span
                  className={cn(
                    'rounded px-1.5 py-0.5 text-xs font-semibold',
                    row.transaction_type === 'C'
                      ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                      : 'bg-rose-500/10 text-rose-700 dark:text-rose-400',
                  )}
                >
                  {row.transaction_type === 'C' ? 'Credit' : 'Debit'}
                </span>
              </td>

              {/* Actions */}
              <td className="px-3 py-2">
                <div className="flex items-center gap-1.5">
                  {/* Dispute badge + resolve button */}
                  {row.is_dispute && (
                    <>
                      <Badge
                        variant="destructive"
                        className="shrink-0 text-[10px]"
                      >
                        Dispute
                      </Badge>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-6 px-2 text-xs"
                        onClick={() => onResolve(row.id)}
                        aria-label={`Resolve dispute for row ${row.sr_number}`}
                      >
                        Resolve
                      </Button>
                    </>
                  )}

                  {/* Edit */}
                  {onEdit && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className={cn(
                        'size-7',
                        row.is_frozen && 'cursor-not-allowed opacity-50',
                      )}
                      disabled={row.is_frozen}
                      onClick={() => !row.is_frozen && onEdit(row)}
                      aria-label={`Edit row ${row.sr_number}`}
                    >
                      <Pencil className="size-3.5" aria-hidden="true" />
                    </Button>
                  )}

                  {/* Delete */}
                  {onDelete && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className={cn(
                        'size-7 text-destructive hover:text-destructive',
                        row.is_frozen && 'cursor-not-allowed opacity-50',
                      )}
                      disabled={row.is_frozen}
                      onClick={() => !row.is_frozen && onDelete(row.id)}
                      aria-label={`Delete row ${row.sr_number}`}
                    >
                      <Trash2 className="size-3.5" aria-hidden="true" />
                    </Button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
