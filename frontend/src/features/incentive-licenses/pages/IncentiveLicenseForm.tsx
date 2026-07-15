/**
 * IncentiveLicenseForm — create or edit an incentive license.
 *
 * - Create mode: /incentive-licenses/new
 * - Edit mode:   /incentive-licenses/:id/edit
 *
 * Fields: license_number, license_type, license_date, exporter (ID), port_code (ID),
 *         license_value, is_active, notes
 * Read-only (backend-computed): sold_value, balance_value, sold_status
 */

import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ArrowLeft, Check, X } from 'lucide-react'

import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { ROUTES } from '@/shared/routes'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { cn } from '@/shared/utils/cn'

import type { IncentiveLicense, IncentiveLicenseFormValues, LicenseType } from '../types'

// ── Constants ──────────────────────────────────────────────────────────────────

const EMPTY_FORM: IncentiveLicenseFormValues = {
  license_type: '',
  license_number: '',
  license_date: '',
  exporter: null,
  port_code: null,
  license_value: '',
  is_active: true,
  notes: '',
}

const LICENSE_TYPES: { value: LicenseType; label: string }[] = [
  { value: 'RODTEP', label: 'RODTEP' },
  { value: 'ROSTL', label: 'ROSTL' },
  { value: 'MEIS', label: 'MEIS' },
]

// ── Sub-components ─────────────────────────────────────────────────────────────

function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return <p className="mt-1 text-[11.5px] text-destructive">{message}</p>
}

function ToggleSwitch({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5 text-sm">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          checked ? 'bg-primary' : 'bg-muted',
        )}
      >
        <span
          className={cn(
            'pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg ring-0 transition-transform',
            checked ? 'translate-x-4' : 'translate-x-0',
          )}
        />
      </button>
      {label}
    </label>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function IncentiveLicenseForm() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const isEdit = Boolean(id)

  const [form, setForm] = useState<IncentiveLicenseFormValues>(EMPTY_FORM)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | undefined>>({})

  useEffect(() => {
    if (!isEdit || !id) return

    const init = async () => {
      setLoading(true)
      try {
        const { data } = await apiClient.get<IncentiveLicense>(
          ENDPOINTS.INCENTIVE_LICENSES.DETAIL(id),
        )
        setForm({
          license_type: data.license_type,
          license_number: data.license_number ?? '',
          license_date: data.license_date ?? '',
          exporter: data.exporter,
          port_code: data.port_code,
          license_value: data.license_value ?? '',
          is_active: data.is_active,
          notes: data.notes ?? '',
        })
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to load license'
        toast.error(msg)
      } finally {
        setLoading(false)
      }
    }
    void init()
  }, [id, isEdit])

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) => {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    setFieldErrors((prev) => ({ ...prev, [name]: undefined }))
  }

  const handleNumberChange = (e: React.ChangeEvent<HTMLInputElement>, field: 'exporter' | 'port_code') => {
    const raw = e.target.value
    const parsed = raw === '' ? null : Number(raw)
    setForm((prev) => ({ ...prev, [field]: parsed }))
    setFieldErrors((prev) => ({ ...prev, [field]: undefined }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setFieldErrors({})

    // Build payload — never send read-only fields
    const payload: Omit<IncentiveLicenseFormValues, 'license_type'> & { license_type: LicenseType | '' } =
      { ...form }

    try {
      if (isEdit && id) {
        await apiClient.patch(ENDPOINTS.INCENTIVE_LICENSES.DETAIL(id), payload)
        toast.success('Incentive license updated')
      } else {
        await apiClient.post(ENDPOINTS.INCENTIVE_LICENSES.LIST, payload)
        toast.success('Incentive license created')
      }
      navigate(ROUTES.INCENTIVE_LICENSES)
    } catch (err: unknown) {
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        err.response &&
        typeof err.response === 'object' &&
        'data' in err.response &&
        err.response.data &&
        typeof err.response.data === 'object'
      ) {
        setFieldErrors(err.response.data as Record<string, string>)
      }
      const msg = err instanceof Error ? err.message : 'Failed to save incentive license'
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  const selectClass = cn(
    'h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground',
    'focus:outline-none focus:ring-2 focus:ring-ring',
  )

  if (loading) {
    return <div className="p-8 text-center text-sm text-muted-foreground">Loading…</div>
  }

  return (
    <div className="mx-auto max-w-3xl">
      {/* Back + title */}
      <div className="mb-5 flex items-center gap-3">
        <Button variant="outline" size="sm" onClick={() => navigate(ROUTES.INCENTIVE_LICENSES)}>
          <ArrowLeft className="size-4" />
          Back
        </Button>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          {isEdit ? 'Edit Incentive License' : 'Create Incentive License'}
        </h1>
      </div>

      <form onSubmit={(e) => void handleSubmit(e)} className="flex flex-col gap-4">
        {/* License details */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-sm">License Details</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-4 pt-5 sm:grid-cols-2">
            {/* License Number */}
            <div>
              <Label className="mb-1.5" htmlFor="license_number">
                License Number <span className="text-destructive">*</span>
              </Label>
              <Input
                id="license_number"
                name="license_number"
                value={form.license_number}
                onChange={handleChange}
                required
                autoComplete="off"
                aria-invalid={!!fieldErrors.license_number}
              />
              <FieldError message={fieldErrors.license_number} />
            </div>

            {/* License Type */}
            <div>
              <Label className="mb-1.5" htmlFor="license_type">
                License Type <span className="text-destructive">*</span>
              </Label>
              <select
                id="license_type"
                name="license_type"
                value={form.license_type}
                onChange={handleChange}
                required
                className={selectClass}
                aria-invalid={!!fieldErrors.license_type}
              >
                <option value="">Select type…</option>
                {LICENSE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
              <FieldError message={fieldErrors.license_type} />
            </div>

            {/* License Date */}
            <div>
              <Label className="mb-1.5" htmlFor="license_date">
                License Date <span className="text-destructive">*</span>
              </Label>
              <Input
                id="license_date"
                type="date"
                name="license_date"
                value={form.license_date}
                onChange={handleChange}
                required
                aria-invalid={!!fieldErrors.license_date}
              />
              <FieldError message={fieldErrors.license_date} />
            </div>

            {/* License Value */}
            <div>
              <Label className="mb-1.5" htmlFor="license_value">
                License Value (₹) <span className="text-destructive">*</span>
              </Label>
              <Input
                id="license_value"
                name="license_value"
                type="text"
                inputMode="decimal"
                value={form.license_value}
                onChange={handleChange}
                required
                placeholder="0.00"
                aria-invalid={!!fieldErrors.license_value}
              />
              <FieldError message={fieldErrors.license_value} />
            </div>

            {/* Exporter ID */}
            <div>
              <Label className="mb-1.5" htmlFor="exporter">
                Exporter (ID)
              </Label>
              <Input
                id="exporter"
                type="number"
                min={1}
                value={form.exporter ?? ''}
                onChange={(e) => handleNumberChange(e, 'exporter')}
                placeholder="Enter exporter ID"
                aria-invalid={!!fieldErrors.exporter}
              />
              <FieldError message={fieldErrors.exporter} />
            </div>

            {/* Port Code ID */}
            <div>
              <Label className="mb-1.5" htmlFor="port_code">
                Port Code (ID)
              </Label>
              <Input
                id="port_code"
                type="number"
                min={1}
                value={form.port_code ?? ''}
                onChange={(e) => handleNumberChange(e, 'port_code')}
                placeholder="Enter port code ID"
                aria-invalid={!!fieldErrors.port_code}
              />
              <FieldError message={fieldErrors.port_code} />
            </div>
          </CardContent>
        </Card>

        {/* Flags + Notes */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-sm">Settings</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 pt-5">
            <ToggleSwitch
              checked={form.is_active}
              onChange={(v) => setForm((prev) => ({ ...prev, is_active: v }))}
              label="Active"
            />
            <div>
              <Label className="mb-1.5" htmlFor="notes">
                Notes
              </Label>
              <textarea
                id="notes"
                name="notes"
                value={form.notes}
                onChange={handleChange}
                rows={3}
                className={cn(
                  'w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground',
                  'placeholder:text-muted-foreground',
                  'focus:outline-none focus:ring-2 focus:ring-ring',
                  'resize-none',
                )}
                placeholder="Optional notes…"
              />
              <FieldError message={fieldErrors.notes} />
            </div>
          </CardContent>
        </Card>

        {/* Form actions */}
        <div className="flex gap-2">
          <Button type="submit" disabled={saving}>
            <Check className="size-4" />
            {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Create License'}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate(ROUTES.INCENTIVE_LICENSES)}
          >
            <X className="size-4" />
            Cancel
          </Button>
        </div>
      </form>
    </div>
  )
}
