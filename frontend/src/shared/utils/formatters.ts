// ── Currency ──────────────────────────────────────────────────────────────────

const INR_FORMATTER = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const INR_COMPACT_FORMATTER = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  notation: 'compact',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})

export function formatINR(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return '—'
  return INR_FORMATTER.format(value)
}

export function formatINRCompact(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return '—'
  return INR_COMPACT_FORMATTER.format(value)
}

// ── Numbers ───────────────────────────────────────────────────────────────────

/** General number formatter — trims trailing zeros (0–3 dp). */
const NUMBER_FORMATTER = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 3,
})

/**
 * 3dp quantity formatter — always shows exactly 3 decimal places.
 * Matches the backend's 3dp precision for trade/BOE quantities
 * (DecimalField max_digits=15, decimal_places=3).
 */
const QTY_3DP_FORMATTER = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
})

export function formatNumber(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return '—'
  return NUMBER_FORMATTER.format(value)
}

/**
 * Format a quantity with exactly 3 decimal places, matching the backend's
 * 3dp storage precision.  Optionally appends a unit string.
 */
export function formatQuantity(value: number | null | undefined, unit?: string): string {
  if (value == null || isNaN(value)) return '—'
  const formatted = QTY_3DP_FORMATTER.format(value)
  return unit ? `${formatted} ${unit}` : formatted
}

// ── Dates ─────────────────────────────────────────────────────────────────────

const DATE_FORMATTER = new Intl.DateTimeFormat('en-IN', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

const DATETIME_FORMATTER = new Intl.DateTimeFormat('en-IN', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return '—'
  try {
    const date = typeof value === 'string' ? new Date(value) : value
    if (isNaN(date.getTime())) return '—'
    return DATE_FORMATTER.format(date)
  } catch {
    return '—'
  }
}

export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return '—'
  try {
    const date = typeof value === 'string' ? new Date(value) : value
    if (isNaN(date.getTime())) return '—'
    return DATETIME_FORMATTER.format(date)
  } catch {
    return '—'
  }
}

/** Format an ISO date string as YYYY-MM-DD (for <input type="date"> value) */
export function toInputDateValue(value: string | Date | null | undefined): string {
  if (!value) return ''
  try {
    const date = typeof value === 'string' ? new Date(value) : value
    if (isNaN(date.getTime())) return ''
    return date.toISOString().split('T')[0]
  } catch {
    return ''
  }
}

// ── Percentages ───────────────────────────────────────────────────────────────

export function formatPercent(value: number | null | undefined, decimals = 1): string {
  if (value == null || isNaN(value)) return '—'
  return `${value.toFixed(decimals)}%`
}
