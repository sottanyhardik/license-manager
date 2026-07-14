// LicenseBalancePanel — shows the balance summary for a license.
// Splits the information out of the legacy 1082-LOC LicenseBalanceModal
// into a focused presentational panel.
// Composes: balance summary cards + inline-editable fields (condition sheet, notes).

import { useState } from 'react'
import { CheckCircle2, FileText, Loader2, PenSquare, X } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/shared/utils/cn'
import { Button } from '@/shared/ui/button'
import { usePatchLicenseField } from '../mutations'
import type { License } from '../types'

// ── Balance stat card ─────────────────────────────────────────────────────────

interface StatCardProps {
  label: string
  value: string | null | undefined
  highlight?: boolean
  negative?: boolean
}

function BalanceStat({ label, value, highlight, negative }: StatCardProps) {
  const displayValue = value != null ? parseFloat(value).toFixed(2) : '—'
  return (
    <div className="flex flex-col gap-1 rounded-lg border bg-muted/30 p-3">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span
        className={cn(
          'text-xl font-bold tabular-nums',
          highlight && !negative && 'text-emerald-700 dark:text-emerald-400',
          negative && 'text-destructive',
          !highlight && !negative && 'text-foreground',
        )}
      >
        {displayValue}
      </span>
    </div>
  )
}

// ── Inline editable text (condition sheet / notes) ────────────────────────────

interface InlineEditableProps {
  licenseId: number
  fieldName: string
  label: string
  value: string | null | undefined
  onUpdate: (newText: string) => void
}

function InlineEditable({ licenseId, fieldName, label, value, onUpdate }: InlineEditableProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value ?? '')
  const patchMutation = usePatchLicenseField(licenseId)

  function handleSave() {
    patchMutation.mutate(
      { [fieldName]: draft },
      {
        onSuccess: () => {
          onUpdate(draft)
          setEditing(false)
          toast.success(`${label} saved.`)
        },
      },
    )
  }

  function handleCancel() {
    setDraft(value ?? '')
    setEditing(false)
  }

  if (editing) {
    return (
      <div>
        <textarea
          rows={4}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={`Enter ${label.toLowerCase()}…`}
          className={cn(
            'mb-2 w-full rounded-md border border-input bg-background px-3 py-2 text-sm',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          )}
          aria-label={label}
        />
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={handleSave}
            disabled={patchMutation.isPending}
          >
            {patchMutation.isPending ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <CheckCircle2 className="size-3.5" aria-hidden="true" />
            )}
            Save
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleCancel}
            disabled={patchMutation.isPending}
          >
            <X className="size-3.5" aria-hidden="true" />
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={() => {
        setDraft(value ?? '')
        setEditing(true)
      }}
      className={cn(
        'block w-full min-h-[80px] rounded-md border border-input px-3 py-2.5 text-left text-sm',
        'transition-colors hover:border-ring hover:bg-accent/30',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        value ? 'bg-amber-50/60 dark:bg-amber-900/10' : 'bg-muted/30 text-muted-foreground',
      )}
      aria-label={`Click to edit ${label}`}
    >
      {value ? (
        <span className="whitespace-pre-wrap">{value}</span>
      ) : (
        <span className="italic text-muted-foreground">Click to add {label.toLowerCase()}…</span>
      )}
    </button>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

interface LicenseBalancePanelProps {
  license: License
  onUpdate: (updated: Partial<License>) => void
  className?: string
}

export function LicenseBalancePanel({ license, onUpdate, className }: LicenseBalancePanelProps) {
  const balanceCif = license.balance?.balance_cif ?? license.balance_cif
  const totalAuthorised = license.balance?.total_authorised
  const totalDebited = license.balance?.total_debited
  const totalAllotted = license.balance?.total_allotted

  const balanceNum = balanceCif != null ? parseFloat(balanceCif) : null
  const isNegative = balanceNum !== null && balanceNum < 0

  return (
    <div className={cn('space-y-5', className)}>
      {/* Balance summary */}
      <div>
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold border-b pb-2">
          <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
          Balance Summary
        </h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <BalanceStat
            label="Balance CIF"
            value={balanceCif}
            highlight={!isNegative}
            negative={isNegative}
          />
          {totalAuthorised != null && (
            <BalanceStat label="Total Authorised" value={totalAuthorised} />
          )}
          {totalDebited != null && (
            <BalanceStat label="Total Debited" value={totalDebited} />
          )}
          {totalAllotted != null && (
            <BalanceStat label="Total Allotted" value={totalAllotted} />
          )}
        </div>
      </div>

      {/* Additional info */}
      {(license.purchase_status != null ||
        license.get_norm_class != null ||
        license.latest_transfer != null) && (
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
          {license.purchase_status && (
            <div>
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Purchase Status
              </span>
              <p className="mt-0.5 font-medium">{license.purchase_status}</p>
            </div>
          )}
          {license.get_norm_class && (
            <div>
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Norm Class
              </span>
              <p className="mt-0.5 font-medium">{license.get_norm_class}</p>
            </div>
          )}
          {license.latest_transfer && (
            <div>
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Latest Transfer
              </span>
              <p className="mt-0.5 font-medium text-sm truncate" title={license.latest_transfer}>
                {license.latest_transfer}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Condition sheet */}
      <div>
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold border-b pb-2">
          <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
          Condition Sheet
        </h3>
        <InlineEditable
          licenseId={license.id}
          fieldName="condition_sheet"
          label="Condition Sheet"
          value={license.condition_sheet}
          onUpdate={(text) => onUpdate({ condition_sheet: text })}
        />
      </div>

      {/* Notes */}
      <div>
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold border-b pb-2">
          <PenSquare className="size-4 text-muted-foreground" aria-hidden="true" />
          Notes
        </h3>
        <InlineEditable
          licenseId={license.id}
          fieldName="balance_report_notes"
          label="Notes"
          value={license.balance_report_notes}
          onUpdate={(text) => onUpdate({ balance_report_notes: text })}
        />
      </div>
    </div>
  )
}
