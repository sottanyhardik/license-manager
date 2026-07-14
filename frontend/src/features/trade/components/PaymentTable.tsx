// PaymentTable — editable table for trade payment records.

import { Trash2, Plus } from 'lucide-react'
import { cn } from '@/shared/utils/cn'
import type { TradePayment } from '../types'

// ─── helpers ──────────────────────────────────────────────────────────────────

function emptyPayment(): TradePayment {
  return { date: '', amount: '0', note: '' }
}

const inputCls =
  'w-full rounded border border-input bg-transparent px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50'

const cellCls = 'px-2 py-1 text-xs font-semibold text-muted-foreground whitespace-nowrap'

// ─── Props ────────────────────────────────────────────────────────────────────

export interface PaymentTableProps {
  payments: TradePayment[]
  onChange: (payments: TradePayment[]) => void
  readOnly?: boolean
}

// ─── Component ────────────────────────────────────────────────────────────────

export function PaymentTable({ payments, onChange, readOnly = false }: PaymentTableProps) {
  function updatePayment(idx: number, patch: Partial<TradePayment>) {
    onChange(payments.map((p, i) => (i === idx ? { ...p, ...patch } : p)))
  }

  function addPayment() {
    onChange([...payments, emptyPayment()])
  }

  function removePayment(idx: number) {
    onChange(payments.filter((_, i) => i !== idx))
  }

  const totalPaid = payments.reduce((sum, p) => sum + (parseFloat(p.amount) || 0), 0)

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              <th className={cellCls}>#</th>
              <th className={cellCls}>Date</th>
              <th className={cellCls}>Amount (INR)</th>
              <th className={cellCls}>Note</th>
              {!readOnly && <th className={cellCls}></th>}
            </tr>
          </thead>
          <tbody>
            {payments.length === 0 && (
              <tr>
                <td
                  colSpan={readOnly ? 4 : 5}
                  className="px-4 py-6 text-center text-sm text-muted-foreground"
                >
                  No payments recorded. {!readOnly && 'Add a payment below.'}
                </td>
              </tr>
            )}
            {payments.map((payment, idx) => (
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
                <td className="min-w-[140px] px-1 py-1">
                  <input
                    type="date"
                    value={payment.date}
                    readOnly={readOnly}
                    onChange={(e) => updatePayment(idx, { date: e.target.value })}
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
                    value={payment.amount}
                    readOnly={readOnly}
                    onChange={(e) => updatePayment(idx, { amount: e.target.value })}
                    className={cn(
                      inputCls,
                      readOnly && 'bg-muted/40 text-muted-foreground',
                    )}
                  />
                </td>
                <td className="min-w-[200px] px-1 py-1">
                  <input
                    type="text"
                    placeholder="Payment note"
                    value={payment.note}
                    readOnly={readOnly}
                    onChange={(e) => updatePayment(idx, { note: e.target.value })}
                    className={cn(
                      inputCls,
                      readOnly && 'bg-muted/40 text-muted-foreground',
                    )}
                  />
                </td>
                {!readOnly && (
                  <td className="px-1 py-1">
                    <button
                      type="button"
                      onClick={() => removePayment(idx)}
                      className="flex items-center justify-center rounded p-1 text-destructive hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      aria-label={`Remove payment ${idx + 1}`}
                    >
                      <Trash2 className="size-3.5" aria-hidden="true" />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
          {payments.length > 0 && (
            <tfoot>
              <tr className="border-t bg-muted/20">
                <td
                  colSpan={2}
                  className="px-2 py-2 text-right text-xs font-semibold text-muted-foreground"
                >
                  Total paid
                </td>
                <td className="px-2 py-2 text-sm font-bold tabular-nums text-emerald-700 dark:text-emerald-400">
                  {totalPaid.toFixed(2)}
                </td>
                <td colSpan={readOnly ? 1 : 2} />
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {!readOnly && (
        <button
          type="button"
          onClick={addPayment}
          className="flex items-center gap-1.5 rounded border border-dashed px-3 py-1.5 text-sm text-muted-foreground hover:border-ring hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Plus className="size-3.5" aria-hidden="true" />
          Add payment
        </button>
      )}
    </div>
  )
}
