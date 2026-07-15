// TradeForm — create / edit trade page.
// Renders:
//   - header fields (direction, license_type, companies, invoice_number, invoice_date, remarks)
//   - TradeLineTable (when license_type=DFIA)
//   - IncentiveLineTable (when license_type=INCENTIVE)
//   - PaymentTable
//   - TradeSummary
// Submits via useCreateTrade or useUpdateTrade.

import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeftRight, ChevronLeft, Loader2, Wand2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { cn } from '@/shared/utils/cn'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { normaliseApiErrorString } from '@/shared/utils/errors'
import { useTrade } from '../queries'
import { useCreateTrade, useUpdateTrade } from '../mutations'
import { TradeLineTable } from '../components/TradeLineTable'
import { IncentiveLineTable } from '../components/IncentiveLineTable'
import { PaymentTable } from '../components/PaymentTable'
import { TradeSummary } from '../components/TradeSummary'
import type {
  TradeDirection,
  TradeLicenseType,
  TradeLine,
  IncentiveTradeLine,
  TradePayment,
  TradeFormValues,
} from '../types'

// ─── constants ────────────────────────────────────────────────────────────────

const DIRECTION_OPTIONS: Array<{ value: TradeDirection; label: string }> = [
  { value: 'PURCHASE', label: 'Purchase' },
  { value: 'SALE', label: 'Sale' },
  { value: 'COMMISSION_PURCHASE', label: 'Commission Purchase' },
  { value: 'COMMISSION_SALE', label: 'Commission Sale' },
]

const LICENSE_TYPE_OPTIONS: Array<{ value: TradeLicenseType; label: string }> = [
  { value: 'DFIA', label: 'DFIA' },
  { value: 'INCENTIVE', label: 'Incentive' },
]

// ─── helpers ──────────────────────────────────────────────────────────────────

const selectCls =
  'flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring'

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-3 border-b pb-1 text-sm font-semibold text-muted-foreground uppercase tracking-wide">
      {children}
    </h2>
  )
}

function FormField({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('space-y-1', className)}>
      <Label className="text-xs text-muted-foreground">{label}</Label>
      {children}
    </div>
  )
}

// ─── default form values ──────────────────────────────────────────────────────

function defaultValues(): TradeFormValues {
  return {
    direction: 'PURCHASE',
    license_type: 'DFIA',
    incentive_license: null,
    boe: null,
    from_company: null,
    to_company: null,
    invoice_number: '',
    invoice_date: null,
    remarks: '',
    lines: [],
    incentive_lines: [],
    payments: [],
  }
}

// ─── page ─────────────────────────────────────────────────────────────────────

export function TradeForm() {
  const navigate = useNavigate()
  const { id: idParam } = useParams<{ id: string }>()
  const tradeId = idParam ? parseInt(idParam, 10) : null
  const isEdit = tradeId !== null

  const { data: existing, isLoading: loadingExisting } = useTrade(tradeId)

  const createMutation = useCreateTrade()
  const updateMutation = useUpdateTrade(tradeId ?? 0)

  const [form, setForm] = useState<TradeFormValues>(defaultValues())
  const [prefillLoading, setPrefillLoading] = useState(false)

  // Derive the "seller" company for prefill: for PURCHASE the buyer is to_company,
  // but the invoice belongs to the seller (from_company). The backend expects
  // company_id = the company whose invoice sequence to increment. We pass
  // from_company when it exists, otherwise to_company as fallback.
  const prefillCompanyId = form.from_company ?? form.to_company

  async function handlePrefillInvoice() {
    if (!prefillCompanyId) return
    setPrefillLoading(true)
    try {
      const { data } = await apiClient.get<{ invoice_number: string }>(
        ENDPOINTS.TRADES.PREFILL_INVOICE,
        {
          params: {
            direction: form.direction,
            company_id: prefillCompanyId,
            ...(form.invoice_date ? { invoice_date: form.invoice_date } : {}),
          },
        },
      )
      patch('invoice_number', data.invoice_number)
      toast.success('Invoice number generated.')
    } catch (err) {
      toast.error(normaliseApiErrorString(err))
    } finally {
      setPrefillLoading(false)
    }
  }

  // Populate form when editing an existing trade
  useEffect(() => {
    if (existing) {
      setForm({
        direction: existing.direction,
        license_type: existing.license_type,
        incentive_license: null,
        boe: existing.boe?.id ?? null,
        from_company: existing.from_company?.id ?? null,
        to_company: existing.to_company?.id ?? null,
        invoice_number: existing.invoice_number,
        invoice_date: existing.invoice_date,
        remarks: existing.remarks ?? '',
        lines: existing.lines,
        incentive_lines: existing.incentive_lines,
        payments: existing.payments,
      })
    }
  }, [existing])

  function patch<K extends keyof TradeFormValues>(key: K, value: TradeFormValues[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (isEdit) {
      updateMutation.mutate(form, {
        onSuccess: (updated) => navigate(`/trades/${updated.id}`),
      })
    } else {
      createMutation.mutate(form, {
        onSuccess: (created) => navigate(`/trades/${created.id}`),
      })
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  // Derive summary from form state for display while editing
  const localSubtotal = form.license_type === 'DFIA'
    ? form.lines.reduce((s, l) => s + (parseFloat(l.amount_inr) || 0), 0)
    : form.incentive_lines.reduce((s, l) => s + (parseFloat(l.amount_inr) || 0), 0)
  const localTotalPaid = form.payments.reduce((s, p) => s + (parseFloat(p.amount) || 0), 0)
  const localRoundoff = Math.round((Math.round(localSubtotal) - localSubtotal) * 100) / 100
  const localTotal = parseFloat((localSubtotal + localRoundoff).toFixed(2))
  const localDue = parseFloat((localTotal - localTotalPaid).toFixed(2))

  // For saved trades, prefer the server's computed summary
  const summarySource = existing
    ? {
        subtotal_amount: existing.subtotal_amount,
        roundoff: existing.roundoff,
        total_amount: existing.total_amount,
        paid_or_received: existing.paid_or_received,
        due_amount: existing.due_amount,
      }
    : {
        subtotal_amount: localSubtotal.toFixed(2),
        roundoff: localRoundoff.toFixed(2),
        total_amount: localTotal.toFixed(2),
        paid_or_received: localTotalPaid.toFixed(2),
        due_amount: localDue.toFixed(2),
      }

  if (isEdit && loadingExisting) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" aria-hidden="true" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Header */}
      <div className="border-b bg-card px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigate('/trades')}
              className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label="Back to trades"
            >
              <ChevronLeft className="size-4" aria-hidden="true" />
              Trades
            </button>
            <ArrowLeftRight className="size-4 text-muted-foreground" aria-hidden="true" />
            <h1 className="text-lg font-semibold">
              {isEdit ? `Edit Trade #${tradeId}` : 'New Trade'}
            </h1>
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => navigate('/trades')}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="trade-form"
              size="sm"
              disabled={isPending}
            >
              {isPending && <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" />}
              {isEdit ? 'Save Changes' : 'Create Trade'}
            </Button>
          </div>
        </div>
      </div>

      {/* Form */}
      <form
        id="trade-form"
        onSubmit={handleSubmit}
        className="flex flex-1 flex-col gap-6 p-6"
        noValidate
      >
        {/* Header fields */}
        <section>
          <SectionHeading>Trade Details</SectionHeading>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            <FormField label="Direction">
              <select
                value={form.direction}
                onChange={(e) => patch('direction', e.target.value as TradeDirection)}
                className={selectCls}
                required
                aria-label="Trade direction"
              >
                {DIRECTION_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </FormField>

            <FormField label="License Type">
              <select
                value={form.license_type}
                onChange={(e) => patch('license_type', e.target.value as TradeLicenseType)}
                className={selectCls}
                required
                aria-label="License type"
              >
                {LICENSE_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </FormField>

            <FormField label="From Company (ID)">
              <Input
                type="number"
                placeholder="Company ID"
                value={form.from_company ?? ''}
                onChange={(e) =>
                  patch('from_company', e.target.value ? parseInt(e.target.value, 10) : null)
                }
              />
            </FormField>

            <FormField label="To Company (ID)">
              <Input
                type="number"
                placeholder="Company ID"
                value={form.to_company ?? ''}
                onChange={(e) =>
                  patch('to_company', e.target.value ? parseInt(e.target.value, 10) : null)
                }
              />
            </FormField>

            <FormField label="Invoice Number">
              <div className="flex gap-1.5">
                <Input
                  type="text"
                  placeholder="e.g. INV-2024-001"
                  value={form.invoice_number}
                  onChange={(e) => patch('invoice_number', e.target.value)}
                  required
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="shrink-0 px-2"
                  disabled={!prefillCompanyId || prefillLoading}
                  onClick={handlePrefillInvoice}
                  title={
                    prefillCompanyId
                      ? 'Generate next invoice number'
                      : 'Select a company first'
                  }
                  aria-label="Generate invoice number"
                >
                  {prefillLoading ? (
                    <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                  ) : (
                    <Wand2 className="size-3.5" aria-hidden="true" />
                  )}
                </Button>
              </div>
            </FormField>

            <FormField label="Invoice Date">
              <Input
                type="date"
                value={form.invoice_date ?? ''}
                onChange={(e) => patch('invoice_date', e.target.value || null)}
              />
            </FormField>

            <FormField label="BOE (ID)" className="sm:col-span-1">
              <Input
                type="number"
                placeholder="BOE ID (optional)"
                value={form.boe ?? ''}
                onChange={(e) =>
                  patch('boe', e.target.value ? parseInt(e.target.value, 10) : null)
                }
              />
            </FormField>

            <FormField label="Remarks" className="sm:col-span-2 xl:col-span-1">
              <Input
                type="text"
                placeholder="Optional remarks"
                value={form.remarks ?? ''}
                onChange={(e) => patch('remarks', e.target.value)}
              />
            </FormField>
          </div>
        </section>

        {/* Trade lines — conditional on license type */}
        <section>
          <SectionHeading>
            {form.license_type === 'DFIA' ? 'DFIA Trade Lines' : 'Incentive Lines'}
          </SectionHeading>
          {form.license_type === 'DFIA' ? (
            <TradeLineTable
              lines={form.lines}
              onChange={(lines: TradeLine[]) => patch('lines', lines)}
            />
          ) : (
            <IncentiveLineTable
              lines={form.incentive_lines}
              onChange={(lines: IncentiveTradeLine[]) => patch('incentive_lines', lines)}
            />
          )}
        </section>

        {/* Payments */}
        <section>
          <SectionHeading>Payments</SectionHeading>
          <PaymentTable
            payments={form.payments}
            onChange={(payments: TradePayment[]) => patch('payments', payments)}
          />
        </section>

        {/* Summary */}
        <section className="max-w-sm">
          <SectionHeading>Summary</SectionHeading>
          <TradeSummary {...summarySource} />
        </section>
      </form>
    </div>
  )
}
