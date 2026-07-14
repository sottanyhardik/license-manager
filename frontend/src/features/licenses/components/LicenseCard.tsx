// LicenseCard — summary card for the license list view.
// Shows key fields; clicking the card navigates to the detail page.

import { Building2, Calendar, FileText } from 'lucide-react'
import { cn } from '@/shared/utils/cn'
import { formatDate } from '@/shared/utils/formatters'
import type { License } from '../types'
import { LicenseStatusBadge } from './LicenseStatusBadge'

interface LicenseCardProps {
  license: License
  onClick?: () => void
  className?: string
}

const LICENSE_TYPE_STYLES: Record<string, string> = {
  DFIA: 'bg-blue-500/10 text-blue-700 dark:text-blue-400',
  RODTEP: 'bg-violet-500/10 text-violet-700 dark:text-violet-400',
  ROSTL: 'bg-teal-500/10 text-teal-700 dark:text-teal-400',
  MEIS: 'bg-orange-500/10 text-orange-700 dark:text-orange-400',
  INCENTIVE: 'bg-pink-500/10 text-pink-700 dark:text-pink-400',
}

function getLicenseTypeStyle(type: string): string {
  return LICENSE_TYPE_STYLES[type] ?? 'bg-muted text-muted-foreground'
}

export function LicenseCard({ license, onClick, className }: LicenseCardProps) {
  const balanceCif = license.balance?.balance_cif ?? license.balance_cif

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'group w-full rounded-lg border bg-card p-4 text-left',
        'transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        className,
      )}
    >
      {/* Header row */}
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <FileText
            className="size-4 shrink-0 text-muted-foreground"
            aria-hidden="true"
          />
          <span className="truncate font-semibold text-foreground">
            {license.license_number}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-xs font-semibold',
              getLicenseTypeStyle(license.license_type ?? ''),
            )}
          >
            {license.license_type}
          </span>
          <LicenseStatusBadge
            isExpired={license.is_expired ?? false}
            expiryDate={license.license_expiry_date ?? ''}
          />
        </div>
      </div>

      {/* Details grid */}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
        {license.company_label && (
          <>
            <dt className="flex items-center gap-1 text-muted-foreground">
              <Building2 className="size-3.5" aria-hidden="true" />
              Company
            </dt>
            <dd className="truncate font-medium">{license.company_label}</dd>
          </>
        )}

        <dt className="flex items-center gap-1 text-muted-foreground">
          <Calendar className="size-3.5" aria-hidden="true" />
          Issue Date
        </dt>
        <dd className="font-medium">{formatDate(license.license_date)}</dd>

        <dt className="flex items-center gap-1 text-muted-foreground">
          <Calendar className="size-3.5" aria-hidden="true" />
          Expiry
        </dt>
        <dd className="font-medium">{formatDate(license.license_expiry_date)}</dd>

        {balanceCif != null && (
          <>
            <dt className="text-muted-foreground">Balance CIF</dt>
            <dd className="font-semibold text-emerald-700 dark:text-emerald-400">
              {parseFloat(balanceCif).toFixed(2)}
            </dd>
          </>
        )}
      </dl>
    </button>
  )
}
