// LicenseFormModal — create / edit license dialog.
// React Hook Form with inline validation rules.
// On success invalidates ['licenses'] cache via the mutation hooks.

import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { Loader2, X } from 'lucide-react'
import * as Dialog from '@radix-ui/react-dialog'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { cn } from '@/shared/utils/cn'
import { MasterSelect } from '@/features/masters/components/MasterSelect'
import {
  useCompaniesAll,
  usePortsAll,
  useSchemeCodesAll,
  useNotificationNumbersAll,
  usePurchaseStatusesAll,
} from '@/features/masters/queries'
import type { Company, Port, SchemeCode, NotificationNumber, PurchaseStatus } from '@/features/masters/types'
import { useCreateLicense, useUpdateLicense } from '../mutations'
import type { License } from '../types'

type FormValues = {
  license_number: string
  license_type: string
  license_date: string
  license_expiry_date: string
  company: number | undefined
  port: number | undefined
  scheme_code: number | undefined
  notification_number: number | undefined
  purchase_status: number | undefined
  file_number: string
  registration_number: string
  registration_date: string
  notes: string
}

const LICENSE_TYPES = ['DFIA', 'RODTEP', 'ROSTL', 'MEIS', 'INCENTIVE']

// ── Props ──────────────────────────────────────────────────────────────────────

interface LicenseFormModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** When provided, the modal is in edit mode pre-filled with this license. */
  license?: License | null
}

// ── Field wrapper ──────────────────────────────────────────────────────────────

interface FieldProps {
  label: string
  htmlFor?: string
  error?: string
  required?: boolean
  children: React.ReactNode
}

function Field({ label, htmlFor, error, required, children }: FieldProps) {
  return (
    <div>
      <Label
        htmlFor={htmlFor}
        className="mb-1.5 block text-xs font-semibold text-muted-foreground"
      >
        {label}
        {required && <span className="ml-0.5 text-destructive">*</span>}
      </Label>
      {children}
      {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
    </div>
  )
}

// ── Component ──────────────────────────────────────────────────────────────────

export function LicenseFormModal({ open, onOpenChange, license }: LicenseFormModalProps) {
  const isEditing = license != null

  const createMutation = useCreateLicense()
  const updateMutation = useUpdateLicense(license?.id ?? 0)

  const isPending = isEditing ? updateMutation.isPending : createMutation.isPending

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    defaultValues: {
      license_number: '',
      license_type: 'DFIA',
      license_date: '',
      license_expiry_date: '',
      company: undefined,
      port: undefined,
      scheme_code: undefined,
      notification_number: undefined,
      purchase_status: undefined,
      file_number: '',
      registration_number: '',
      registration_date: '',
      notes: '',
    },
  })

  const companyValue = watch('company')
  const portValue = watch('port')
  const schemeCodeValue = watch('scheme_code')
  const notificationNumberValue = watch('notification_number')
  const purchaseStatusValue = watch('purchase_status')

  // Pre-fill when editing.
  useEffect(() => {
    if (open) {
      if (license) {
        reset({
          license_number: license.license_number,
          license_type: license.license_type ?? license.scheme_code_display ?? 'DFIA',
          license_date: license.license_date ?? '',
          license_expiry_date: license.license_expiry_date ?? '',
          // Use the FK ID fields from LicenseDetailSerializer
          // (the API returns both the FK integer AND a display string)
          company: license.exporter ?? license.company ?? undefined,
          port: license.port ?? undefined,
          scheme_code: license.scheme_code ?? undefined,
          notification_number: license.notification_number ?? undefined,
          purchase_status: license.purchase_status ?? undefined,
          file_number: license.file_number ?? '',
          registration_number: license.registration_number ?? '',
          registration_date: license.registration_date ?? '',
          notes: license.balance_report_notes ?? license.condition_sheet ?? '',
        })
      } else {
        reset({
          license_number: '',
          license_type: 'DFIA',
          license_date: '',
          license_expiry_date: '',
          company: undefined,
          port: undefined,
          scheme_code: undefined,
          notification_number: undefined,
          purchase_status: undefined,
          file_number: '',
          registration_number: '',
          registration_date: '',
          notes: '',
        })
      }
    }
  }, [open, license, reset])

  function onSubmit(values: FormValues) {
    if (values.company == null) {
      return
    }

    const payload = {
      license_number: values.license_number,
      license_type: values.license_type,
      license_date: values.license_date,
      license_expiry_date: values.license_expiry_date,
      company: values.company,
      port: values.port ?? null,
      scheme_code: values.scheme_code ?? null,
      notification_number: values.notification_number ?? null,
      purchase_status: values.purchase_status ?? null,
      file_number: values.file_number || undefined,
      registration_number: values.registration_number || undefined,
      registration_date: values.registration_date || undefined,
      notes: values.notes,
      balance_report_notes: values.notes,
    }

    if (isEditing) {
      updateMutation.mutate(payload, {
        onSuccess: () => onOpenChange(false),
      })
    } else {
      createMutation.mutate(payload, {
        onSuccess: () => onOpenChange(false),
      })
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content
          className={cn(
            'fixed left-[50%] top-[50%] z-50 w-full max-w-2xl -translate-x-1/2 -translate-y-1/2',
            'max-h-[90vh] overflow-y-auto rounded-xl border bg-background shadow-xl',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
            'data-[state=closed]:slide-out-to-left-1/2 data-[state=open]:slide-in-from-left-1/2',
            'data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-top-[48%]',
          )}
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b px-6 py-4">
            <Dialog.Title className="text-base font-semibold">
              {isEditing ? 'Edit License' : 'New License'}
            </Dialog.Title>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon" className="size-8" aria-label="Close">
                <X className="size-4" aria-hidden="true" />
              </Button>
            </Dialog.Close>
          </div>

          {/* Body */}
          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <div className="space-y-5 px-6 py-5">

              {/* Row 1: License number + License type */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field
                  label="License Number"
                  htmlFor="license-number"
                  error={errors.license_number?.message}
                  required
                >
                  <Input
                    id="license-number"
                    placeholder="e.g. 0310252856"
                    {...register('license_number', {
                      required: 'License number is required',
                      maxLength: { value: 100, message: 'License number too long' },
                    })}
                    aria-invalid={!!errors.license_number}
                  />
                </Field>

                <Field
                  label="License Type"
                  htmlFor="license-type"
                  error={errors.license_type?.message}
                  required
                >
                  <select
                    id="license-type"
                    {...register('license_type', { required: 'License type is required' })}
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    aria-invalid={!!errors.license_type}
                  >
                    {LICENSE_TYPES.map((lt) => (
                      <option key={lt} value={lt}>
                        {lt}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>

              {/* Row 2: Company (full width) */}
              <Field
                label="Company"
                htmlFor="license-company"
                error={errors.company?.message}
                required
              >
                <input
                  type="hidden"
                  {...register('company', {
                    validate: (v) => (v != null && v > 0) || 'Company is required',
                  })}
                />
                <MasterSelect<Company>
                  id="license-company"
                  queryHook={useCompaniesAll}
                  value={companyValue ?? null}
                  onChange={(id) => setValue('company', id ?? undefined, { shouldValidate: true })}
                  getLabel={(c) => c.name}
                  placeholder="Select company"
                  aria-label="Select company"
                />
              </Field>

              {/* Row 3: Issue date + Expiry date */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field
                  label="Issue Date"
                  htmlFor="license-date"
                  error={errors.license_date?.message}
                  required
                >
                  <Input
                    id="license-date"
                    type="date"
                    {...register('license_date', { required: 'Issue date is required' })}
                    aria-invalid={!!errors.license_date}
                  />
                </Field>
                <Field
                  label="Expiry Date"
                  htmlFor="license-expiry"
                  error={errors.license_expiry_date?.message}
                  required
                >
                  <Input
                    id="license-expiry"
                    type="date"
                    {...register('license_expiry_date', { required: 'Expiry date is required' })}
                    aria-invalid={!!errors.license_expiry_date}
                  />
                </Field>
              </div>

              {/* Row 4: Port + Scheme Code */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Port" htmlFor="license-port">
                  <input type="hidden" {...register('port')} />
                  <MasterSelect<Port>
                    id="license-port"
                    queryHook={usePortsAll}
                    value={portValue ?? null}
                    onChange={(id) => setValue('port', id ?? undefined)}
                    getLabel={(p) => `${p.port_code} — ${p.port_name}`}
                    placeholder="Select port"
                    aria-label="Select port"
                  />
                </Field>

                <Field label="Scheme Code" htmlFor="license-scheme-code">
                  <input type="hidden" {...register('scheme_code')} />
                  <MasterSelect<SchemeCode>
                    id="license-scheme-code"
                    queryHook={useSchemeCodesAll}
                    value={schemeCodeValue ?? null}
                    onChange={(id) => setValue('scheme_code', id ?? undefined)}
                    getLabel={(s) => s.code}
                    placeholder="Select scheme code"
                    aria-label="Select scheme code"
                  />
                </Field>
              </div>

              {/* Row 5: Notification Number + Purchase Status */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Notification Number" htmlFor="license-notification-number">
                  <input type="hidden" {...register('notification_number')} />
                  <MasterSelect<NotificationNumber>
                    id="license-notification-number"
                    queryHook={useNotificationNumbersAll}
                    value={notificationNumberValue ?? null}
                    onChange={(id) => setValue('notification_number', id ?? undefined)}
                    getLabel={(n) => n.code}
                    placeholder="Select notification number"
                    aria-label="Select notification number"
                  />
                </Field>

                <Field label="Purchase Status" htmlFor="license-purchase-status">
                  <input type="hidden" {...register('purchase_status')} />
                  <MasterSelect<PurchaseStatus>
                    id="license-purchase-status"
                    queryHook={usePurchaseStatusesAll}
                    value={purchaseStatusValue ?? null}
                    onChange={(id) => setValue('purchase_status', id ?? undefined)}
                    getLabel={(ps) => ps.label ?? ps.code}
                    placeholder="Select purchase status"
                    aria-label="Select purchase status"
                  />
                </Field>
              </div>

              {/* Row 6: File Number + Registration Number */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="File Number" htmlFor="license-file-number">
                  <Input
                    id="license-file-number"
                    placeholder="Optional file number"
                    {...register('file_number')}
                  />
                </Field>
                <Field label="Registration Number" htmlFor="license-registration-number">
                  <Input
                    id="license-registration-number"
                    placeholder="Optional registration number"
                    {...register('registration_number')}
                  />
                </Field>
              </div>

              {/* Row 7: Registration Date */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Registration Date" htmlFor="license-registration-date">
                  <Input
                    id="license-registration-date"
                    type="date"
                    {...register('registration_date')}
                  />
                </Field>
              </div>

              {/* Notes */}
              <Field label="Notes" htmlFor="license-notes" error={errors.notes?.message}>
                <textarea
                  id="license-notes"
                  rows={3}
                  placeholder="Optional notes about this license…"
                  {...register('notes')}
                  className={cn(
                    'w-full rounded-md border border-input bg-background px-3 py-2 text-sm',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    'placeholder:text-muted-foreground',
                  )}
                />
              </Field>
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-3 border-t px-6 py-4">
              <Dialog.Close asChild>
                <Button type="button" variant="outline" disabled={isPending}>
                  Cancel
                </Button>
              </Dialog.Close>
              <Button type="submit" disabled={isPending}>
                {isPending && (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                )}
                {isEditing ? 'Save Changes' : 'Create License'}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
