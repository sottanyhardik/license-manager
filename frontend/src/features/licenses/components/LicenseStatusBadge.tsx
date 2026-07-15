// LicenseStatusBadge — displays expired / near-expiry / active / negative-balance state.
// Near-expiry threshold: < 30 days to expiry date.
// BD-003: also shows a Negative Balance variant when flags.balance_status === "negative".

import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'
import { cn } from '@/shared/utils/cn'
import type { LicenseFlags } from '../types'

export type LicenseStatus = 'expired' | 'near-expiry' | 'active'

interface LicenseStatusBadgeProps {
  isExpired: boolean
  expiryDate: string
  flags?: LicenseFlags
  className?: string
  showLabel?: boolean
}

function getStatus(isExpired: boolean, expiryDate: string): LicenseStatus {
  if (isExpired) return 'expired'
  const msToExpiry = new Date(expiryDate).getTime() - Date.now()
  const daysToExpiry = msToExpiry / (1000 * 60 * 60 * 24)
  if (daysToExpiry < 30) return 'near-expiry'
  return 'active'
}

const STATUS_CONFIG: Record<
  LicenseStatus,
  {
    label: string
    icon: React.ComponentType<{ className?: string }>
    classes: string
  }
> = {
  expired: {
    label: 'Expired',
    icon: XCircle,
    classes:
      'bg-destructive/10 text-destructive border-destructive/30',
  },
  'near-expiry': {
    label: 'Near Expiry',
    icon: AlertTriangle,
    classes:
      'bg-amber-500/10 text-amber-700 border-amber-400/40 dark:text-amber-400',
  },
  active: {
    label: 'Active',
    icon: CheckCircle2,
    classes:
      'bg-emerald-500/10 text-emerald-700 border-emerald-400/40 dark:text-emerald-400',
  },
}

export function LicenseStatusBadge({
  isExpired,
  expiryDate,
  flags,
  className,
  showLabel = true,
}: LicenseStatusBadgeProps) {
  // BD-003: Negative balance takes priority over expiry/near-expiry unless already expired.
  if (!isExpired && flags?.balance_status === 'negative') {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold',
          'bg-destructive/10 text-destructive border-destructive/30',
          className,
        )}
      >
        <AlertTriangle className="size-3 shrink-0" aria-hidden="true" />
        {showLabel && 'Negative Balance'}
      </span>
    )
  }

  const status = getStatus(isExpired, expiryDate)
  const config = STATUS_CONFIG[status]
  const Icon = config.icon

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold',
        config.classes,
        className,
      )}
    >
      <Icon className="size-3 shrink-0" aria-hidden="true" />
      {showLabel && config.label}
    </span>
  )
}
