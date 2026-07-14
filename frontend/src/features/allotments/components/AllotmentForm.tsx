// AllotmentForm — create / edit allotment header fields.
// Covers: basic info, financial details, additional info, status.
// AllotmentItems linking is a separate concern handled at /allotments/:id.
//
// Auto-calc rules:
//   1. unit_value AND qty change  → cif_fc = unit_value * qty (2dp)
//   2. cif_fc set but unit_value absent AND qty → unit_value = ceil(cif_fc/qty, 3dp)
//   3. cif_fc AND exchange_rate   → cif_inr = cif_fc * exchange_rate (2dp)
//   4. cif_inr AND exchange_rate  → cif_fc = cif_inr / exchange_rate (2dp) → recalc unit_value

import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Loader2 } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { cn } from '@/shared/utils/cn'
import { MasterSelect } from '@/features/masters/components/MasterSelect'
import { useCompaniesAll, usePortsAll } from '@/features/masters/queries'
import type { Company, Port } from '@/features/masters/types'
import { useCreateAllotment, useUpdateAllotment } from '../queries'
import type { Allotment, AllotmentFormValues } from '../types'

// ─── Zod schema ───────────────────────────────────────────────────────────────

const allotmentSchema = z.object({
  company: z.number({ required_error: 'Company is required' }),
  type: z.enum(['AT', 'TR']),
  port: z.number().nullable().optional(),
  item_name: z.string().min(1, 'Item name is required'),
  required_quantity: z.string().min(1, 'Required quantity is required'),
  unit_value_per_unit: z.string().default('0'),
  cif_fc: z.string().default('0'),
  cif_inr: z.string().default('0'),
  exchange_rate: z.string().default('0'),
  invoice: z.string().optional(),
  estimated_arrival_date: z.string().optional(),
  bl_detail: z.string().optional(),
  is_approved: z.boolean().default(false),
})

type AllotmentSchemaValues = z.infer<typeof allotmentSchema>

// Lightweight zod resolver — avoids the @hookform/resolvers peer dep.
function zodResolver<T extends z.ZodTypeAny>(schema: T) {
  return async (values: unknown) => {
    const result = await schema.safeParseAsync(values)
    if (result.success) {
      return { values: result.data as z.infer<T>, errors: {} }
    }
    const errors: Record<string, { type: string; message: string }> = {}
    for (const issue of result.error.issues) {
      const key = issue.path.join('.')
      if (!errors[key]) {
        errors[key] = { type: issue.code, message: issue.message }
      }
    }
    return { values: {}, errors }
  }
}

// ─── Props ────────────────────────────────────────────────────────────────────

export interface AllotmentFormProps {
  mode: 'create' | 'edit'
  allotmentId?: number
  defaultValues?: Partial<AllotmentFormValues>
  onSuccess?: (allotment: Allotment) => void
  onCancel?: () => void
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function toFixed2(n: number): string {
  return n.toFixed(2)
}

function toFixed3Ceil(numerator: number, denominator: number): string {
  // ceiling to 3 decimal places
  const raw = numerator / denominator
  const ceiled = Math.ceil(raw * 1000) / 1000
  return ceiled.toFixed(3)
}

function parseNum(v: string | undefined | null): number {
  const n = parseFloat(v ?? '')
  return isNaN(n) ? 0 : n
}

// ─── Section wrapper ──────────────────────────────────────────────────────────

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <fieldset className="rounded-lg border p-4">
      <legend className="px-1 text-sm font-semibold text-foreground">{title}</legend>
      <div className="mt-2 grid grid-cols-1 gap-4 sm:grid-cols-2">{children}</div>
    </fieldset>
  )
}

// ─── Field wrapper ────────────────────────────────────────────────────────────

function Field({
  label,
  error,
  required,
  children,
  className,
}: {
  label: string
  error?: string
  required?: boolean
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <Label>
        {label}
        {required && <span className="ml-0.5 text-destructive" aria-hidden="true">*</span>}
      </Label>
      {children}
      {error && (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

// ─── Prefixed input ───────────────────────────────────────────────────────────

function PrefixedInput({
  prefix,
  ...props
}: { prefix: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="flex items-stretch">
      <span className="inline-flex items-center rounded-l-md border border-r-0 border-input bg-muted px-2.5 text-sm text-muted-foreground">
        {prefix}
      </span>
      <Input className="rounded-l-none" {...props} />
    </div>
  )
}

// ─── Component ────────────────────────────────────────────────────────────────

export function AllotmentForm({
  mode,
  allotmentId,
  defaultValues,
  onSuccess,
  onCancel,
}: AllotmentFormProps) {
  const createMutation = useCreateAllotment()
  const updateMutation = useUpdateAllotment(allotmentId ?? 0)
  const isPending = createMutation.isPending || updateMutation.isPending

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<AllotmentSchemaValues>({
    resolver: zodResolver(allotmentSchema),
    defaultValues: {
      company: defaultValues?.company ?? undefined,
      type: defaultValues?.type ?? 'AT',
      port: defaultValues?.port ?? null,
      item_name: defaultValues?.item_name ?? '',
      required_quantity: defaultValues?.required_quantity ?? '',
      unit_value_per_unit: defaultValues?.unit_value_per_unit ?? '0',
      cif_fc: defaultValues?.cif_fc ?? '0',
      cif_inr: defaultValues?.cif_inr ?? '0',
      exchange_rate: defaultValues?.exchange_rate ?? '0',
      invoice: defaultValues?.invoice ?? '',
      estimated_arrival_date: defaultValues?.estimated_arrival_date ?? '',
      bl_detail: defaultValues?.bl_detail ?? '',
      is_approved: defaultValues?.is_approved ?? false,
    },
  })

  // Watch fields for auto-calc
  const [qty, unitValue, cifFc, cifInr, exchangeRate] = watch([
    'required_quantity',
    'unit_value_per_unit',
    'cif_fc',
    'cif_inr',
    'exchange_rate',
  ])

  // Rule 1 & 2: when unit_value or qty changes → recalc cif_fc (rule 1),
  // or back-calc unit_value when cif_fc is known (rule 2).
  useEffect(() => {
    const qtyN = parseNum(qty)
    const unitN = parseNum(unitValue)
    const cifFcN = parseNum(cifFc)
    if (qtyN <= 0) return

    if (unitN > 0) {
      // Rule 1: unit_value AND qty → cif_fc
      const newCifFc = toFixed2(unitN * qtyN)
      if (newCifFc !== cifFc) {
        setValue('cif_fc', newCifFc, { shouldValidate: false })
      }
    } else if (cifFcN > 0) {
      // Rule 2: cif_fc known, unit_value absent → back-calc unit_value
      const newUnit = toFixed3Ceil(cifFcN, qtyN)
      if (newUnit !== unitValue) {
        setValue('unit_value_per_unit', newUnit, { shouldValidate: false })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qty, unitValue])

  // Rule 3: cif_fc AND exchange_rate → cif_inr
  useEffect(() => {
    const cifFcN = parseNum(cifFc)
    const rateN = parseNum(exchangeRate)
    if (cifFcN > 0 && rateN > 0) {
      const newCifInr = toFixed2(cifFcN * rateN)
      if (newCifInr !== cifInr) {
        setValue('cif_inr', newCifInr, { shouldValidate: false })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cifFc, exchangeRate])

  // Rule 4: cif_inr AND exchange_rate → cif_fc → recalc unit_value
  useEffect(() => {
    const cifInrN = parseNum(cifInr)
    const rateN = parseNum(exchangeRate)
    const qtyN = parseNum(qty)
    if (cifInrN > 0 && rateN > 0) {
      const newCifFc = toFixed2(cifInrN / rateN)
      setValue('cif_fc', newCifFc, { shouldValidate: false })
      if (qtyN > 0) {
        const newUnit = toFixed3Ceil(parseNum(newCifFc), qtyN)
        setValue('unit_value_per_unit', newUnit, { shouldValidate: false })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cifInr, exchangeRate])

  // ─── Submit ────────────────────────────────────────────────────────────────

  function onSubmit(values: AllotmentSchemaValues) {
    const payload: AllotmentFormValues = {
      ...values,
      company: values.company,
      port: values.port ?? null,
      invoice: values.invoice ?? '',
      estimated_arrival_date: values.estimated_arrival_date ?? '',
      bl_detail: values.bl_detail ?? '',
    }

    if (mode === 'create') {
      createMutation.mutate(payload, {
        onSuccess: (allotment) => {
          onSuccess?.(allotment)
        },
      })
    } else {
      updateMutation.mutate(payload, {
        onSuccess: (allotment) => {
          onSuccess?.(allotment)
        },
      })
    }
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
      {/* 1. Basic Information */}
      <Section title="Basic Information">
        <Field label="Company" required error={errors.company?.message} className="sm:col-span-2">
          <MasterSelect<Company>
            queryHook={useCompaniesAll}
            value={watch('company') ?? null}
            onChange={(id) => setValue('company', id ?? (undefined as unknown as number), { shouldValidate: true })}
            getLabel={(c) => c.name}
            placeholder="Select company..."
            aria-label="Company"
          />
        </Field>

        <Field label="Type" error={errors.type?.message} required>
          <div className="flex items-center gap-4" role="radiogroup" aria-label="Allotment type">
            {(['AT', 'TR'] as const).map((t) => (
              <label key={t} className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="radio"
                  value={t}
                  {...register('type')}
                  className="accent-primary"
                />
                {t === 'AT' ? 'Allotment (AT)' : 'Transfer (TR)'}
              </label>
            ))}
          </div>
        </Field>

        <Field label="Port" error={errors.port?.message}>
          <MasterSelect<Port>
            queryHook={usePortsAll}
            value={watch('port') ?? null}
            onChange={(id) => setValue('port', id, { shouldValidate: false })}
            getLabel={(p) => `${p.port_code} — ${p.port_name}`}
            placeholder="Select port..."
            aria-label="Port"
          />
        </Field>

        <Field label="Item Name" required error={errors.item_name?.message} className="sm:col-span-2">
          <Input
            {...register('item_name')}
            placeholder="Item name"
            aria-required="true"
          />
        </Field>

        <Field label="Required Quantity" required error={errors.required_quantity?.message}>
          <Input
            {...register('required_quantity')}
            type="number"
            step="0.01"
            min="0"
            placeholder="0.00"
          />
        </Field>
      </Section>

      {/* 2. Financial Details */}
      <Section title="Financial Details">
        <Field label="CIF INR" error={errors.cif_inr?.message}>
          <PrefixedInput prefix="₹" {...register('cif_inr')} type="number" step="0.01" min="0" placeholder="0.00" />
        </Field>

        <Field label="Exchange Rate" error={errors.exchange_rate?.message}>
          <Input
            {...register('exchange_rate')}
            type="number"
            step="0.01"
            min="0"
            placeholder="0.00"
          />
        </Field>

        <Field label="CIF FC" error={errors.cif_fc?.message}>
          <PrefixedInput prefix="$" {...register('cif_fc')} type="number" step="0.01" min="0" placeholder="0.00" />
        </Field>

        <Field label="Unit Value per Unit" error={errors.unit_value_per_unit?.message}>
          <PrefixedInput prefix="$" {...register('unit_value_per_unit')} type="number" step="0.001" min="0" placeholder="0.000" />
        </Field>
      </Section>

      {/* 3. Additional Info */}
      <Section title="Additional Info">
        <Field label="Invoice" error={errors.invoice?.message}>
          <Input {...register('invoice')} placeholder="Invoice reference" />
        </Field>

        <Field label="Estimated Arrival Date" error={errors.estimated_arrival_date?.message}>
          <Input {...register('estimated_arrival_date')} type="date" />
        </Field>

        <Field label="BL Detail" error={errors.bl_detail?.message} className="sm:col-span-2">
          <Input {...register('bl_detail')} placeholder="Bill of Lading detail" />
        </Field>
      </Section>

      {/* 4. Status */}
      <Section title="Status">
        <Field label="Approved" error={errors.is_approved?.message} className="sm:col-span-2">
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              {...register('is_approved')}
              className="h-4 w-4 rounded accent-primary"
            />
            Mark as approved
          </label>
        </Field>
      </Section>

      {/* Actions */}
      <div className="flex items-center justify-end gap-3 pt-2">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel} disabled={isPending}>
            Cancel
          </Button>
        )}
        <Button type="submit" disabled={isPending}>
          {isPending && <Loader2 className="animate-spin" aria-hidden="true" />}
          {mode === 'create' ? 'Create Allotment' : 'Save Changes'}
        </Button>
      </div>
    </form>
  )
}
