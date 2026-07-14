// IncentiveLineTable — editable table for incentive trade lines.
// amount_inr = round(license_value * rate_pct / 100, 2)

import { Trash2, Plus } from 'lucide-react'
import { cn } from '@/shared/utils/cn'
import type { IncentiveTradeLine } from '../types'

// ─── helpers ──────────────────────────────────────────────────────────────────

function emptyLine(): IncentiveTradeLine {
  return {
    incentive_license: null,
    license_value: '0',
    rate_pct: '0.000',
    amount_inr: '0',
  }
}

function computeAmount(line: IncentiveTradeLine): string {
  const value = parseFloat(line.license_value) || 0
  const pct = parseFloat(line.rate_pct) || 0
  return (Math.round((value * pct / 100) * 100) / 100).toFixed(2)
}

// ─── shared input style ───────────────────────────────────────────────────────

const inputCls =
  'w-full rounded border border-input bg-transparent px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50'

const cellCls = 'px-2 py-1 text-xs font-semibold text-muted-foreground whitespace-nowrap'

// ─── Props ────────────────────────────────────────────────────────────────────

export interface IncentiveLineTableProps {
  lines: IncentiveTradeLine[]
  onChange: (lines: IncentiveTradeLine[]) => void
  readOnly?: boolean
}

// ─── Component ────────────────────────────────────────────────────────────────

export function IncentiveLineTable({ lines, onChange, readOnly = false }: IncentiveLineTableProps) {
  function updateLine(idx: number, patch: Partial<IncentiveTradeLine>) {
    const next = lines.map((l, i) => {
      if (i !== idx) return l
      const updated = { ...l, ...patch }
      updated.amount_inr = computeAmount(updated)
      return updated
    })
    onChange(next)
  }

  function addLine() {
    onChange([...lines, emptyLine()])
  }

  function removeLine(idx: number) {
    onChange(lines.filter((_, i) => i !== idx))
  }

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              <th className={cellCls}>#</th>
              <th className={cellCls}>Incentive License ID</th>
              <th className={cellCls}>License Value</th>
              <th className={cellCls}>Rate Pct %</th>
              <th className={cellCls}>Amount INR</th>
              {!readOnly && <th className={cellCls}></th>}
            </tr>
          </thead>
          <tbody>
            {lines.length === 0 && (
              <tr>
                <td
                  colSpan={readOnly ? 5 : 6}
                  className="px-4 py-6 text-center text-sm text-muted-foreground"
                >
                  No lines. {!readOnly && 'Add a line below.'}
                </td>
              </tr>
            )}
            {lines.map((line, idx) => (
              <tr
                key={idx}
                className={cn(
                  'border-b transition-colors',
                  idx % 2 === 1 && 'bg-muted/10',
                )}
              >
                <td className="px-2 py-1 text-center text-xs text-muted-foreground">
                  {idx + 1}
                </td>
                <td className="min-w-[120px] px-1 py-1">
                  <input
                    type="number"
                    step="1"
                    placeholder="License ID"
                    value={line.incentive_license ?? ''}
                    readOnly={readOnly}
                    onChange={(e) =>
                      updateLine(idx, {
                        incentive_license: e.target.value ? parseInt(e.target.value, 10) : null,
                      })
                    }
                    className={cn(
                      inputCls,
                      readOnly && 'bg-muted/40 text-muted-foreground',
                    )}
                  />
                </td>
                <td className="min-w-[120px] px-1 py-1">
                  <input
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    value={line.license_value}
                    readOnly={readOnly}
                    onChange={(e) => updateLine(idx, { license_value: e.target.value })}
                    className={cn(
                      inputCls,
                      readOnly && 'bg-muted/40 text-muted-foreground',
                    )}
                  />
                </td>
                <td className="min-w-[90px] px-1 py-1">
                  <input
                    type="number"
                    step="0.001"
                    placeholder="0.000"
                    value={line.rate_pct}
                    readOnly={readOnly}
                    onChange={(e) => updateLine(idx, { rate_pct: e.target.value })}
                    className={cn(
                      inputCls,
                      readOnly && 'bg-muted/40 text-muted-foreground',
                    )}
                  />
                </td>
                <td className="min-w-[100px] px-1 py-1">
                  <input
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    value={line.amount_inr}
                    readOnly
                    className={cn(inputCls, 'bg-muted/40 font-semibold text-muted-foreground')}
                  />
                </td>
                {!readOnly && (
                  <td className="px-1 py-1">
                    <button
                      type="button"
                      onClick={() => removeLine(idx)}
                      className="flex items-center justify-center rounded p-1 text-destructive hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      aria-label={`Remove incentive line ${idx + 1}`}
                    >
                      <Trash2 className="size-3.5" aria-hidden="true" />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
          {lines.length > 0 && (
            <tfoot>
              <tr className="border-t bg-muted/20">
                <td
                  colSpan={4}
                  className="px-2 py-2 text-right text-xs font-semibold text-muted-foreground"
                >
                  Subtotal
                </td>
                <td className="px-2 py-2 text-sm font-bold tabular-nums">
                  {lines
                    .reduce((sum, l) => sum + (parseFloat(l.amount_inr) || 0), 0)
                    .toFixed(2)}
                </td>
                {!readOnly && <td />}
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {!readOnly && (
        <button
          type="button"
          onClick={addLine}
          className="flex items-center gap-1.5 rounded border border-dashed px-3 py-1.5 text-sm text-muted-foreground hover:border-ring hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Plus className="size-3.5" aria-hidden="true" />
          Add incentive line
        </button>
      )}
    </div>
  )
}
