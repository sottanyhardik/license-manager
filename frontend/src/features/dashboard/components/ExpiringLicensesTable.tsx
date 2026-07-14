// ExpiringLicensesTable — compact table of licenses expiring soon.
// Days badge: <=7 red, <=15 amber, else blue.

import { cn } from '@/shared/utils/cn'
import type { ExpiringLicense } from '../types'

interface Props {
  data: ExpiringLicense[]
}

function DaysBadge({ days }: { days: number }) {
  const colorClass =
    days <= 7
      ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400'
      : days <= 15
        ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400'
        : 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400'

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium tabular-nums',
        colorClass,
      )}
    >
      {days}d
    </span>
  )
}

function formatDate(isoDate: string): string {
  // Convert YYYY-MM-DD to DD-MM-YYYY
  const [year, month, day] = isoDate.split('-')
  if (!year || !month || !day) return isoDate
  return `${day}-${month}-${year}`
}

function formatBalance(value: string): string {
  return `$${parseFloat(value).toLocaleString('en-US', { minimumFractionDigits: 2 })}`
}

export function ExpiringLicensesTable({ data }: Props) {
  if (data.length === 0) {
    return (
      <div className="flex min-h-[120px] items-center justify-center text-sm text-muted-foreground">
        No licenses expiring soon.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <th className="pb-2 pr-4">License No.</th>
            <th className="pb-2 pr-4">Expiry Date</th>
            <th className="pb-2 pr-4 text-right">Balance (CIF USD)</th>
            <th className="pb-2 text-right">Days</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {data.map((license) => (
            <tr
              key={license.license_number}
              className="transition-colors hover:bg-muted/40"
            >
              <td className="py-2.5 pr-4 font-medium tabular-nums">
                {license.license_number}
              </td>
              <td className="py-2.5 pr-4 tabular-nums text-muted-foreground">
                {formatDate(license.license_expiry_date)}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {formatBalance(license.balance_cif)}
              </td>
              <td className="py-2.5 text-right">
                <DaysBadge days={license.days_to_expiry} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
