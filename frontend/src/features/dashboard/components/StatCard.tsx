// StatCard — a self-contained KPI tile.
// Intentionally does NOT depend on shadcn Card so the design stays compact
// and the component remains trivially portable.

import { TrendingDown, TrendingUp } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/shared/utils/cn'

interface StatCardProps {
  label: string
  value: number | string
  icon: LucideIcon
  trend?: { value: number; direction: 'up' | 'down' }
  variant?: 'default' | 'warning' | 'danger'
}

const variantStyles: Record<NonNullable<StatCardProps['variant']>, string> = {
  default: 'border-border',
  warning: 'border-amber-400/60 bg-amber-50/50 dark:bg-amber-950/20',
  danger: 'border-red-400/60 bg-red-50/50 dark:bg-red-950/20',
}

const iconVariantStyles: Record<NonNullable<StatCardProps['variant']>, string> = {
  default: 'bg-primary/10 text-primary',
  warning: 'bg-amber-100 text-amber-600 dark:bg-amber-900/40 dark:text-amber-400',
  danger: 'bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400',
}

export function StatCard({
  label,
  value,
  icon: Icon,
  trend,
  variant = 'default',
}: StatCardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border p-5 transition-colors',
        'bg-card text-card-foreground shadow-sm',
        variantStyles[variant],
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-bold tabular-nums tracking-tight">{value}</p>
          {trend && (
            <div
              className={cn(
                'mt-1.5 flex items-center gap-0.5 text-xs font-medium',
                trend.direction === 'up' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400',
              )}
            >
              {trend.direction === 'up' ? (
                <TrendingUp className="h-3 w-3" />
              ) : (
                <TrendingDown className="h-3 w-3" />
              )}
              <span>{trend.value}%</span>
            </div>
          )}
        </div>
        <div
          className={cn(
            'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
            iconVariantStyles[variant],
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  )
}
