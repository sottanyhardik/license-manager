// LicenseExportItems — read-only table of export items for a license.
// Fetches from /api/v1/licenses/{id}/export-items/.

import { Inbox, Loader2 } from 'lucide-react'
import { cn } from '@/shared/utils/cn'
import { useLicenseExportItems } from '../queries'

interface LicenseExportItemsProps {
  licenseId: number
  className?: string
}

function fmt(value: string | null | undefined): string {
  if (value == null || value === '') return '—'
  const n = parseFloat(value)
  return isNaN(n) ? value : n.toFixed(2)
}

export function LicenseExportItems({ licenseId, className }: LicenseExportItemsProps) {
  const { data: items, isLoading, isError } = useLicenseExportItems(licenseId)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        Loading export items…
      </div>
    )
  }

  if (isError) {
    return (
      <div className="py-10 text-center text-sm text-destructive">
        Failed to load export items.
      </div>
    )
  }

  if (!items || items.length === 0) {
    return (
      <div
        className={cn(
          'flex flex-col items-center gap-2 py-10 text-center text-muted-foreground',
          className,
        )}
      >
        <Inbox className="size-8 opacity-50" aria-hidden="true" />
        <p className="text-sm">No export items for this license.</p>
      </div>
    )
  }

  const COLS = [
    { key: 'description', label: 'Description', align: 'left' },
    { key: 'norm_class_label', label: 'Norm Class', align: 'left' },
    { key: 'item_label', label: 'Item Name', align: 'left' },
    { key: 'cif_fc', label: 'CIF FC', align: 'right' },
    { key: 'fob_fc', label: 'FOB FC', align: 'right' },
    { key: 'net_quantity', label: 'Quantity', align: 'right' },
    { key: 'unit', label: 'Unit', align: 'left' },
  ] as const

  return (
    <div className={cn('overflow-x-auto rounded-lg border', className)}>
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/60">
          <tr>
            {COLS.map((col) => (
              <th
                key={col.key}
                className={cn(
                  'px-3 py-2.5 text-xs font-semibold text-muted-foreground',
                  col.align === 'right' ? 'text-right' : 'text-left',
                )}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
            <tr
              key={item.id}
              className={cn(
                'border-b last:border-0 hover:bg-accent/40',
                idx % 2 === 1 && 'bg-muted/20',
              )}
            >
              <td className="max-w-xs truncate px-3 py-2">{item.description ?? '—'}</td>
              <td className="px-3 py-2">{item.norm_class_label ?? '—'}</td>
              <td className="px-3 py-2">{item.item_label ?? '—'}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmt(item.cif_fc)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmt(item.fob_fc)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmt(item.net_quantity)}</td>
              <td className="px-3 py-2">{item.unit ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
