// LicenseImportItems — SR number table for a license's import items.
// Clicking a row expands it to show BOE/allotment usage detail.
// Isolated from LicenseBalancePanel to keep each component focused.

import { useState } from 'react'
import { ChevronDown, ChevronRight, Inbox, Loader2 } from 'lucide-react'
import { cn } from '@/shared/utils/cn'
import { useLicenseItemUsage } from '../queries'
import type { LicenseImportItem, ItemUsageBOE, ItemUsageAllotment } from '../types'
import { formatDate } from '@/shared/utils/formatters'

interface LicenseImportItemsProps {
  licenseId: number
  items: LicenseImportItem[]
  className?: string
}

function fmt(value: string | null | undefined): string {
  if (value == null || value === '') return '—'
  return parseFloat(value).toFixed(2)
}

function UsageDetail({
  licenseId,
  itemId,
  itemType,
}: {
  licenseId: number
  itemId: number
  itemType: 'import'
}) {
  const { data: usage, isLoading } = useLicenseItemUsage(licenseId, itemId, itemType)

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-3 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        Loading usage details…
      </div>
    )
  }

  const boes: ItemUsageBOE[] = usage?.boes ?? []
  const allotments: ItemUsageAllotment[] = usage?.allotments ?? []

  return (
    <div className="bg-muted/30 p-4 text-sm">
      {/* BOEs */}
      <p className="mb-2 font-semibold text-foreground">Bill of Entry Usage</p>
      {boes.length === 0 ? (
        <p className="mb-4 text-muted-foreground">No BOE usage found.</p>
      ) : (
        <div className="mb-4 overflow-x-auto rounded border">
          <table className="w-full text-xs">
            <thead className="border-b bg-muted/60">
              <tr>
                {['BOE Number', 'Date', 'Port', 'Company', 'Qty', 'CIF $', 'CIF INR'].map((h) => (
                  <th key={h} className="px-3 py-2 text-left font-semibold text-muted-foreground">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {boes.map((boe) => (
                <tr key={boe.id} className="border-b last:border-0 hover:bg-muted/40">
                  <td className="px-3 py-1.5 font-mono">{boe.bill_of_entry_number}</td>
                  <td className="px-3 py-1.5">{formatDate(boe.date)}</td>
                  <td className="px-3 py-1.5">{boe.port ?? '—'}</td>
                  <td className="px-3 py-1.5">{boe.company ?? '—'}</td>
                  <td className="px-3 py-1.5 text-right">{fmt(boe.quantity)}</td>
                  <td className="px-3 py-1.5 text-right">{fmt(boe.cif_fc)}</td>
                  <td className="px-3 py-1.5 text-right">{fmt(boe.cif_inr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Allotments */}
      <p className="mb-2 font-semibold text-foreground">Allotment Usage</p>
      {allotments.length === 0 ? (
        <p className="text-muted-foreground">No allotment usage found.</p>
      ) : (
        <div className="overflow-x-auto rounded border">
          <table className="w-full text-xs">
            <thead className="border-b bg-muted/60">
              <tr>
                {['Company', 'Qty', 'CIF $', 'CIF INR'].map((h) => (
                  <th key={h} className="px-3 py-2 text-left font-semibold text-muted-foreground">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {allotments.map((a) => (
                <tr key={a.id} className="border-b last:border-0 hover:bg-muted/40">
                  <td className="px-3 py-1.5">{a.company ?? '—'}</td>
                  <td className="px-3 py-1.5 text-right">{fmt(a.quantity)}</td>
                  <td className="px-3 py-1.5 text-right">{fmt(a.cif_fc)}</td>
                  <td className="px-3 py-1.5 text-right">{fmt(a.cif_inr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function LicenseImportItems({ licenseId, items, className }: LicenseImportItemsProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null)

  if (items.length === 0) {
    return (
      <div
        className={cn(
          'flex flex-col items-center gap-2 py-10 text-center text-muted-foreground',
          className,
        )}
      >
        <Inbox className="size-8 opacity-50" aria-hidden="true" />
        <p className="text-sm">No import items found.</p>
      </div>
    )
  }

  function toggleRow(id: number) {
    setExpandedId((prev) => (prev === id ? null : id))
  }

  const COLS = [
    { key: 'sr', label: 'Sr No', align: 'left' },
    { key: 'hs_code', label: 'HS Code', align: 'left' },
    { key: 'description', label: 'Description', align: 'left' },
    { key: 'quantity', label: 'Total Qty', align: 'right' },
    { key: 'allotted_quantity', label: 'Allotted', align: 'right' },
    { key: 'debited_quantity', label: 'Debited', align: 'right' },
    { key: 'available_quantity', label: 'Available', align: 'right' },
    { key: 'cif_fc', label: 'CIF FC', align: 'right' },
    { key: 'balance_cif_fc', label: 'Balance CIF FC', align: 'right' },
  ] as const

  return (
    <div className={cn('overflow-x-auto rounded-lg border', className)}>
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/60">
          <tr>
            <th className="w-8 px-2 py-2.5" aria-hidden="true" />
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
          {items.map((item, idx) => {
            const isExpanded = expandedId === item.id
            return (
              <>
                <tr
                  key={item.id}
                  className={cn(
                    'cursor-pointer border-b transition-colors hover:bg-accent/40',
                    isExpanded && 'bg-accent/20',
                    idx % 2 === 1 && !isExpanded && 'bg-muted/20',
                  )}
                  onClick={() => toggleRow(item.id)}
                  aria-expanded={isExpanded}
                >
                  {/* Expand chevron */}
                  <td className="px-2 py-2 text-center text-muted-foreground">
                    {isExpanded ? (
                      <ChevronDown className="size-4" aria-hidden="true" />
                    ) : (
                      <ChevronRight className="size-4" aria-hidden="true" />
                    )}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {item.serial_number ?? idx + 1}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {item.hs_code_label ?? item.hs_code ?? '—'}
                  </td>
                  <td className="max-w-xs truncate px-3 py-2">{item.description ?? '—'}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(item.quantity)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(item.allotted_quantity)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(item.debited_quantity)}</td>
                  <td
                    className={cn(
                      'px-3 py-2 text-right tabular-nums font-semibold',
                      parseFloat(item.available_quantity ?? '0') > 0
                        ? 'text-emerald-700 dark:text-emerald-400'
                        : 'text-muted-foreground',
                    )}
                  >
                    {fmt(item.available_quantity)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(item.cif_fc)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(item.balance_cif_fc)}</td>
                </tr>
                {isExpanded && (
                  <tr key={`${item.id}-usage`}>
                    <td
                      colSpan={COLS.length + 1}
                      className="border-b border-dashed"
                    >
                      <UsageDetail
                        licenseId={licenseId}
                        itemId={item.id}
                        itemType="import"
                      />
                    </td>
                  </tr>
                )}
              </>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
