// TradeSummary — card displaying the financial summary of a trade.
// due_amount colour:
//   green  → 0 (fully settled)
//   orange → partial (0 < due < total)
//   red    → full due (due >= total or no payment made)

import { cn } from '@/shared/utils/cn'

// ─── Props ────────────────────────────────────────────────────────────────────

interface TradeSummaryProps {
  subtotal_amount: string
  roundoff: string
  total_amount: string
  paid_or_received: string
  due_amount: string
}

// ─── helpers ──────────────────────────────────────────────────────────────────

function fmt(value: string): string {
  const n = parseFloat(value)
  if (isNaN(n)) return '—'
  return new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n)
}

function dueCls(due: string, total: string): string {
  const d = parseFloat(due) || 0
  const t = parseFloat(total) || 0
  if (d <= 0) return 'text-emerald-700 dark:text-emerald-400'
  if (d < t) return 'text-amber-600 dark:text-amber-400'
  return 'text-destructive'
}

// ─── Row ──────────────────────────────────────────────────────────────────────

function Row({
  label,
  value,
  valueClassName,
  bold = false,
}: {
  label: string
  value: string
  valueClassName?: string
  bold?: boolean
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span className={cn('text-sm text-muted-foreground', bold && 'font-semibold text-foreground')}>
        {label}
      </span>
      <span className={cn('tabular-nums text-sm', bold && 'font-bold text-base', valueClassName)}>
        {value}
      </span>
    </div>
  )
}

// ─── Component ────────────────────────────────────────────────────────────────

export function TradeSummary({
  subtotal_amount,
  roundoff,
  total_amount,
  paid_or_received,
  due_amount,
}: TradeSummaryProps) {
  return (
    <div className="rounded-lg border bg-card p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold">Financial Summary</h3>
      <div className="divide-y">
        <Row label="Subtotal" value={fmt(subtotal_amount)} />
        <Row label="Roundoff" value={fmt(roundoff)} />
        <Row label="Total Amount" value={fmt(total_amount)} bold />
        <Row label="Paid / Received" value={fmt(paid_or_received)} />
        <Row
          label="Due Amount"
          value={fmt(due_amount)}
          bold
          valueClassName={dueCls(due_amount, total_amount)}
        />
      </div>
    </div>
  )
}
