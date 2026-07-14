// AllotmentStatusBadge — renders up to three coloured pills describing an
// allotment's type, approval state, and allotment state.

import { cn } from '@/shared/utils/cn'
import type { AllotmentType } from '../types'

interface AllotmentStatusBadgeProps {
  type: AllotmentType
  isApproved: boolean
  isAllotted: boolean
  className?: string
}

export function AllotmentStatusBadge({
  type,
  isApproved,
  isAllotted,
  className,
}: AllotmentStatusBadgeProps) {
  return (
    <span className={cn('inline-flex flex-wrap items-center gap-1', className)}>
      {/* Type pill */}
      <span
        className={cn(
          'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold',
          type === 'AT'
            ? 'border-blue-400/40 bg-blue-500/10 text-blue-700 dark:text-blue-400'
            : 'border-purple-400/40 bg-purple-500/10 text-purple-700 dark:text-purple-400',
        )}
      >
        {type === 'AT' ? 'Allotment' : 'Transfer'}
      </span>

      {/* Approval pill */}
      <span
        className={cn(
          'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold',
          isApproved
            ? 'border-emerald-400/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
            : 'border-border bg-muted text-muted-foreground',
        )}
      >
        {isApproved ? 'Approved' : 'Pending'}
      </span>

      {/* Allotment state pill */}
      <span
        className={cn(
          'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold',
          isAllotted
            ? 'border-teal-400/40 bg-teal-500/10 text-teal-700 dark:text-teal-400'
            : 'border-border bg-muted/50 text-muted-foreground/70',
        )}
      >
        {isAllotted ? 'Allotted' : 'Unallotted'}
      </span>
    </span>
  )
}
