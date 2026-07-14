// TradeLineTable — editable table for DFIA billing lines.
// Column visibility is governed by the line's billing mode:
//   QTY     → qty_kg, rate_inr_per_kg (amount = qty * rate)
//   CIF_INR → cif_fc, exc_rate, cif_inr, pct (amount = round(cif_inr * pct / 100))
//   FOB_INR → fob_inr, pct (amount = round(fob_inr * pct / 100))
// pct is always 3 decimal places.

import { Trash2, Plus } from 'lucide-react'
import { cn } from '@/shared/utils/cn'
import type { TradeLine, TradeBillingMode } from '../types'

// ─── helpers ──────────────────────────────────────────────────────────────────

function emptyLine(): TradeLine {
  return {
    sr_number: null,
    description: '',
    hsn_code: '',
    mode: 'CIF_INR',
    qty_kg: '0',
    rate_inr_per_kg: '0',
    cif_fc: '0',
    exc_rate: '0',
    cif_inr: '0',
    fob_inr: '0',
    pct: '0.000',
    amount_inr: '0',
  }
}

function computeAmount(line: TradeLine): string {
  const pct = parseFloat(line.pct) || 0
  if (line.mode === 'QTY') {
    const qty = parseFloat(line.qty_kg) || 0
    const rate = parseFloat(line.rate_inr_per_kg) || 0
    return (Math.round(qty * rate * 100) / 100).toFixed(2)
  }
  if (line.mode === 'CIF_INR') {
    const cif = parseFloat(line.cif_inr) || 0
    return (Math.round((cif * pct / 100) * 100) / 100).toFixed(2)
  }
  // FOB_INR
  const fob = parseFloat(line.fob_inr) || 0
  return (Math.round((fob * pct / 100) * 100) / 100).toFixed(2)
}

function reverseCalcPct(amount: string, line: TradeLine): string {
  const amt = parseFloat(amount) || 0
  if (line.mode === 'CIF_INR') {
    const cif = parseFloat(line.cif_inr) || 0
    if (cif === 0) return '0.000'
    return (Math.round((amt / cif * 100) * 1000) / 1000).toFixed(3)
  }
  if (line.mode === 'FOB_INR') {
    const fob = parseFloat(line.fob_inr) || 0
    if (fob === 0) return '0.000'
    return (Math.round((amt / fob * 100) * 1000) / 1000).toFixed(3)
  }
  return '0.000'
}

// ─── sub-component helpers ────────────────────────────────────────────────────

const cellCls = 'px-2 py-1 text-xs font-semibold text-muted-foreground whitespace-nowrap'
const inputCls =
  'w-full rounded border border-input bg-transparent px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50'

interface FieldProps {
  value: string
  onChange: (v: string) => void
  type?: string
  step?: string
  placeholder?: string
  className?: string
  readOnly?: boolean
}

function Field({ value, onChange, type = 'text', step, placeholder, className, readOnly }: FieldProps) {
  return (
    <input
      type={type}
      step={step}
      placeholder={placeholder}
      value={value}
      readOnly={readOnly}
      onChange={(e) => onChange(e.target.value)}
      className={cn(inputCls, readOnly && 'bg-muted/40 text-muted-foreground', className)}
    />
  )
}

// ─── Props ────────────────────────────────────────────────────────────────────

export interface TradeLineTableProps {
  lines: TradeLine[]
  onChange: (lines: TradeLine[]) => void
  readOnly?: boolean
}

// ─── Component ────────────────────────────────────────────────────────────────

export function TradeLineTable({ lines, onChange, readOnly = false }: TradeLineTableProps) {
  function updateLine(idx: number, patch: Partial<TradeLine>) {
    const next = lines.map((l, i) => {
      if (i !== idx) return l
      const updated = { ...l, ...patch }
      // Recompute amount_inr on any field change
      updated.amount_inr = computeAmount(updated)
      return updated
    })
    onChange(next)
  }

  function updateLineAmount(idx: number, amount: string) {
    const line = lines[idx]
    const pct = reverseCalcPct(amount, line)
    const updated = { ...line, pct, amount_inr: amount }
    onChange(lines.map((l, i) => (i === idx ? updated : l)))
  }

  function addLine() {
    onChange([...lines, emptyLine()])
  }

  function removeLine(idx: number) {
    onChange(lines.filter((_, i) => i !== idx))
  }

  const MODES: TradeBillingMode[] = ['QTY', 'CIF_INR', 'FOB_INR']

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              <th className={cellCls}>#</th>
              <th className={cellCls}>Description</th>
              <th className={cellCls}>HSN</th>
              <th className={cellCls}>Mode</th>
              <th className={cellCls}>Qty (kg)</th>
              <th className={cellCls}>Rate/kg</th>
              <th className={cellCls}>CIF FC</th>
              <th className={cellCls}>Exc. Rate</th>
              <th className={cellCls}>CIF INR</th>
              <th className={cellCls}>FOB INR</th>
              <th className={cellCls}>Pct %</th>
              <th className={cellCls}>Amount INR</th>
              {!readOnly && <th className={cellCls}></th>}
            </tr>
          </thead>
          <tbody>
            {lines.length === 0 && (
              <tr>
                <td
                  colSpan={readOnly ? 12 : 13}
                  className="px-4 py-6 text-center text-sm text-muted-foreground"
                >
                  No lines. {!readOnly && 'Add a line below.'}
                </td>
              </tr>
            )}
            {lines.map((line, idx) => {
              const isQty = line.mode === 'QTY'
              const isCif = line.mode === 'CIF_INR'
              const isFob = line.mode === 'FOB_INR'
              return (
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
                  <td className="min-w-[160px] px-1 py-1">
                    <Field
                      value={line.description}
                      onChange={(v) => updateLine(idx, { description: v })}
                      readOnly={readOnly}
                    />
                  </td>
                  <td className="min-w-[80px] px-1 py-1">
                    <Field
                      value={line.hsn_code}
                      onChange={(v) => updateLine(idx, { hsn_code: v })}
                      readOnly={readOnly}
                    />
                  </td>
                  <td className="min-w-[100px] px-1 py-1">
                    {readOnly ? (
                      <span className="text-sm">{line.mode}</span>
                    ) : (
                      <select
                        value={line.mode}
                        onChange={(e) =>
                          updateLine(idx, { mode: e.target.value as TradeBillingMode })
                        }
                        className={cn(inputCls, 'pr-1')}
                      >
                        {MODES.map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))}
                      </select>
                    )}
                  </td>
                  {/* QTY columns */}
                  <td className={cn('min-w-[80px] px-1 py-1', !isQty && 'opacity-30')}>
                    <Field
                      value={line.qty_kg}
                      onChange={(v) => updateLine(idx, { qty_kg: v })}
                      type="number"
                      step="0.001"
                      placeholder="0.000"
                      readOnly={readOnly || !isQty}
                    />
                  </td>
                  <td className={cn('min-w-[80px] px-1 py-1', !isQty && 'opacity-30')}>
                    <Field
                      value={line.rate_inr_per_kg}
                      onChange={(v) => updateLine(idx, { rate_inr_per_kg: v })}
                      type="number"
                      step="0.01"
                      placeholder="0.00"
                      readOnly={readOnly || !isQty}
                    />
                  </td>
                  {/* CIF columns */}
                  <td className={cn('min-w-[80px] px-1 py-1', !isCif && 'opacity-30')}>
                    <Field
                      value={line.cif_fc}
                      onChange={(v) => updateLine(idx, { cif_fc: v })}
                      type="number"
                      step="0.01"
                      placeholder="0.00"
                      readOnly={readOnly || !isCif}
                    />
                  </td>
                  <td className={cn('min-w-[80px] px-1 py-1', !isCif && 'opacity-30')}>
                    <Field
                      value={line.exc_rate}
                      onChange={(v) => updateLine(idx, { exc_rate: v })}
                      type="number"
                      step="0.0001"
                      placeholder="0.0000"
                      readOnly={readOnly || !isCif}
                    />
                  </td>
                  <td className={cn('min-w-[90px] px-1 py-1', !isCif && 'opacity-30')}>
                    <Field
                      value={line.cif_inr}
                      onChange={(v) => updateLine(idx, { cif_inr: v })}
                      type="number"
                      step="0.01"
                      placeholder="0.00"
                      readOnly={readOnly || !isCif}
                    />
                  </td>
                  {/* FOB column */}
                  <td className={cn('min-w-[90px] px-1 py-1', !isFob && 'opacity-30')}>
                    <Field
                      value={line.fob_inr}
                      onChange={(v) => updateLine(idx, { fob_inr: v })}
                      type="number"
                      step="0.01"
                      placeholder="0.00"
                      readOnly={readOnly || !isFob}
                    />
                  </td>
                  {/* Pct (CIF + FOB only) */}
                  <td className={cn('min-w-[80px] px-1 py-1', isQty && 'opacity-30')}>
                    <Field
                      value={line.pct}
                      onChange={(v) => updateLine(idx, { pct: v })}
                      type="number"
                      step="0.001"
                      placeholder="0.000"
                      readOnly={readOnly || isQty}
                    />
                  </td>
                  {/* Amount */}
                  <td className="min-w-[90px] px-1 py-1">
                    <Field
                      value={line.amount_inr}
                      onChange={(v) => updateLineAmount(idx, v)}
                      type="number"
                      step="0.01"
                      placeholder="0.00"
                      className="font-semibold"
                      readOnly={readOnly}
                    />
                  </td>
                  {!readOnly && (
                    <td className="px-1 py-1">
                      <button
                        type="button"
                        onClick={() => removeLine(idx)}
                        className="flex items-center justify-center rounded p-1 text-destructive hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        aria-label={`Remove line ${idx + 1}`}
                      >
                        <Trash2 className="size-3.5" aria-hidden="true" />
                      </button>
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
          {lines.length > 0 && (
            <tfoot>
              <tr className="border-t bg-muted/20">
                <td
                  colSpan={readOnly ? 11 : 11}
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
          Add line
        </button>
      )}
    </div>
  )
}
