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
import { useCompaniesAll } from '@/features/masters/queries'
import type { Company } from '@/features/masters/types'
import { useCreateLicense, useUpdateLicense } from '../mutations'
import type { License } from '../types'

type FormValues = {
  license_number: string
  license_type: string
  license_date: string
  license_expiry_date: string
  company: number | undefined
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
      notes: '',
    },
  })

  const companyValue = watch('company')

  // Pre-fill when editing.
  useEffect(() => {
    if (open) {
      if (license) {
        reset({
          license_number: license.license_number,
          license_type: license.license_type,
          license_date: license.license_date,
          license_expiry_date: license.license_expiry_date,
          company: license.company,
          notes: license.balance_report_notes ?? '',
        })
      } else {
        reset({
          license_number: '',
          license_type: 'DFIA',
          license_date: '',
          license_expiry_date: '',
          company: undefined,
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
            'fixed left-[50%] top-[50%] z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2',
            'rounded-xl border bg-background shadow-xl',
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
            <div className="space-y-4 px-6 py-5">
              {/* License number */}
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

              {/* License type */}
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

              {/* Company */}
              <Field
                label="Company"
                htmlFor="license-company"
                error={errors.company?.message}
                required
              >
                {/* Hidden input so RHF tracks company validity */}
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

              {/* Dates row */}
              <div className="grid grid-cols-2 gap-4">
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
