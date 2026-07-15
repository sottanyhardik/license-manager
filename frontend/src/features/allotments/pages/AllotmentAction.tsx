// AllotmentAction — allocation workflow page at /allotments/:id/allocate
// Port of legacy/frontend/src/pages/AllotmentAction.tsx (1175 lines).
// All business logic (calculateMaxAllocation, qty/value auto-calc, plan-gate)
// preserved identically. Adapted to new stack: Tailwind v4, TanStack Query v5,
// lucide-react, sonner, @/shared/ui/*, @/shared/api/*.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import {
  ArrowLeft,
  Building2,
  Calendar,
  CheckCircle2,
  CheckSquare,
  Clipboard,
  FileText,
  Files,
  Filter,
  Inbox,
  ListChecks,
  Network,
  PenSquare,
  Trash2,
  TriangleAlert,
  Unlock,
  X,
  XCircle,
} from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Skeleton } from '@/shared/ui/skeleton'
import { cn } from '@/shared/utils/cn'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { useAllotment, useAllocateItems, useDeleteAllotmentItem, useCopyAllotment } from '../queries'
import type { Allotment, AllotmentItem, AllocationEntry, AvailableLicense, AvailableLicensesResponse } from '../types'
import LicensePlanningPanel from '../components/LicensePlanningPanel'
import TransferLetterForm from '../components/TransferLetterForm'

// ─── Filter state ──────────────────────────────────────────────────────────────

const DEFAULT_FILTERS = {
  description: '',
  exporter: '',
  exclude_exporter: '',
  license_number: '',
  available_quantity_gte: '50',
  available_quantity_lte: '',
  available_value_gte: '100',
  available_value_lte: '',
  notification_number: '',
  norm_class: '',
  hs_code: '',
  is_expired: 'all',
  is_restricted: 'all',
  purchase_status: 'GE,GO,SM,MI',
  license_status: 'active',
  item_names: '',
  expiry_date_from: '',
  expiry_date_to: '',
}

type Filters = typeof DEFAULT_FILTERS

// ─── Allocation draft ──────────────────────────────────────────────────────────

interface AllocationDraft {
  qty: string
  cif_fc: string
}

// ─── Condition badge (inline — no external dep) ────────────────────────────────

function ConditionBadge({ type }: { type?: string }) {
  if (!type) return null
  const label =
    type === 'R'
      ? 'Restricted'
      : type === 'A'
      ? 'Actual User'
      : type === 'U'
      ? 'Unrestricted'
      : type
  const style =
    type === 'R'
      ? { background: '#FEE2E2', color: '#991B1B' }
      : type === 'A'
      ? { background: '#FEF3C7', color: '#92400E' }
      : { background: '#D1FAE5', color: '#065F46' }
  return (
    <span
      className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
      style={style}
    >
      {label}
    </span>
  )
}

// ─── Filter panel ──────────────────────────────────────────────────────────────

const PURCHASE_STATUS_OPTIONS = [
  { value: 'GE', label: 'GE Purchase' },
  { value: 'GO', label: 'GE Operating' },
  { value: 'SM', label: 'SM Purchase' },
  { value: 'MI', label: 'Conversion' },
  { value: 'IP', label: 'IP' },
  { value: 'CO', label: 'CO' },
]

interface FiltersProps {
  filters: Filters
  setFilters: (f: Filters) => void
  notificationOptions: Array<{ value: string; display_name: string }>
  availableItemNames: Array<{ value: number; label: string }>
}

function AllotmentFilters({
  filters,
  setFilters,
  notificationOptions,
  availableItemNames,
}: FiltersProps) {
  const selectedPsValues = filters.purchase_status
    ? filters.purchase_status.split(',').filter(Boolean)
    : []

  const togglePs = (val: string) => {
    const next = selectedPsValues.includes(val)
      ? selectedPsValues.filter((v) => v !== val)
      : [...selectedPsValues, val]
    setFilters({ ...filters, purchase_status: next.join(',') })
  }

  const selectedItemNameValues = filters.item_names
    ? filters.item_names.split(',').filter(Boolean).map(Number)
    : []

  const toggleItemName = (val: number) => {
    const next = selectedItemNameValues.includes(val)
      ? selectedItemNameValues.filter((v) => v !== val)
      : [...selectedItemNameValues, val]
    setFilters({ ...filters, item_names: next.join(',') })
  }

  const inputCls =
    'flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring'
  const labelCls = 'mb-1 block text-[11px] font-semibold uppercase tracking-wide text-muted-foreground'

  return (
    <div className="mb-3 overflow-hidden rounded-lg border border-border/60" style={{ background: 'var(--tb-sunken)' }}>
      <div className="flex items-center justify-between border-b border-border/60 px-3 py-2">
        <span className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
          <Filter className="size-3.5" aria-hidden="true" />
          Filters
        </span>
        <button
          type="button"
          className="flex cursor-pointer items-center gap-1 border-0 bg-transparent p-0 text-xs text-muted-foreground hover:text-foreground"
          onClick={() => setFilters(DEFAULT_FILTERS)}
        >
          <XCircle className="size-3.5" aria-hidden="true" />
          Clear All
        </button>
      </div>
      <div className="p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {/* Item Names multi-select */}
          {availableItemNames.length > 0 && (
            <div className="col-span-full">
              <label className={labelCls}>Filter By Item Name</label>
              <div className="flex flex-wrap gap-1.5">
                {availableItemNames.map((opt) => {
                  const sel = selectedItemNameValues.includes(opt.value)
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => toggleItemName(opt.value)}
                      className={cn(
                        'rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors',
                        sel
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border bg-card text-muted-foreground hover:border-primary hover:text-primary',
                      )}
                    >
                      {opt.label}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Norm Class */}
          <div>
            <label className={labelCls}>Norm Class</label>
            <input
              className={inputCls}
              placeholder="All Norm Classes"
              value={filters.norm_class}
              onChange={(e) => setFilters({ ...filters, norm_class: e.target.value })}
            />
          </div>

          {/* Notification Number */}
          <div>
            <label className={labelCls}>Notification Number</label>
            <select
              className={inputCls}
              value={filters.notification_number}
              onChange={(e) =>
                setFilters({ ...filters, notification_number: e.target.value })
              }
            >
              <option value="">All</option>
              {notificationOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.display_name}
                </option>
              ))}
            </select>
          </div>

          {/* License Number */}
          <div>
            <label className={labelCls}>License Number</label>
            <input
              className={inputCls}
              placeholder="Filter by license number..."
              value={filters.license_number}
              onChange={(e) =>
                setFilters({ ...filters, license_number: e.target.value })
              }
            />
          </div>

          {/* Description */}
          <div>
            <label className={labelCls}>Item Description</label>
            <input
              className={inputCls}
              placeholder="Filter by item description..."
              value={filters.description}
              onChange={(e) =>
                setFilters({ ...filters, description: e.target.value })
              }
            />
          </div>

          {/* Exporter */}
          <div>
            <label className={labelCls}>Exporter</label>
            <input
              className={inputCls}
              placeholder="All Exporters"
              value={filters.exporter}
              onChange={(e) =>
                setFilters({ ...filters, exporter: e.target.value })
              }
            />
          </div>

          {/* Exclude Exporter */}
          <div>
            <label className={labelCls}>Exclude Exporter</label>
            <input
              className={inputCls}
              placeholder="None"
              value={filters.exclude_exporter}
              onChange={(e) =>
                setFilters({ ...filters, exclude_exporter: e.target.value })
              }
            />
          </div>

          {/* HS Code */}
          <div>
            <label className={labelCls}>HS Code</label>
            <input
              className={inputCls}
              value={filters.hs_code}
              onChange={(e) =>
                setFilters({ ...filters, hs_code: e.target.value })
              }
            />
          </div>

          {/* Min Qty */}
          <div>
            <label className={labelCls}>Min Available Qty</label>
            <input
              type="number"
              className={inputCls}
              value={filters.available_quantity_gte}
              onChange={(e) =>
                setFilters({ ...filters, available_quantity_gte: e.target.value })
              }
            />
          </div>

          {/* Max Qty */}
          <div>
            <label className={labelCls}>Max Available Qty</label>
            <input
              type="number"
              className={inputCls}
              value={filters.available_quantity_lte}
              onChange={(e) =>
                setFilters({ ...filters, available_quantity_lte: e.target.value })
              }
            />
          </div>

          {/* Min Value */}
          <div>
            <label className={labelCls}>Min Available Value</label>
            <input
              type="number"
              className={inputCls}
              value={filters.available_value_gte}
              onChange={(e) =>
                setFilters({ ...filters, available_value_gte: e.target.value })
              }
            />
          </div>

          {/* Max Value */}
          <div>
            <label className={labelCls}>Max Available Value</label>
            <input
              type="number"
              className={inputCls}
              value={filters.available_value_lte}
              onChange={(e) =>
                setFilters({ ...filters, available_value_lte: e.target.value })
              }
            />
          </div>

          {/* Is Restricted */}
          <div>
            <label className={labelCls}>Is Restricted</label>
            <select
              className={inputCls}
              value={filters.is_restricted}
              onChange={(e) =>
                setFilters({ ...filters, is_restricted: e.target.value })
              }
            >
              <option value="all">All</option>
              <option value="true">Restricted</option>
              <option value="false">Not Restricted</option>
            </select>
          </div>

          {/* License Status */}
          <div>
            <label className={labelCls}>License Status</label>
            <select
              className={inputCls}
              value={filters.license_status}
              onChange={(e) =>
                setFilters({ ...filters, license_status: e.target.value })
              }
            >
              <option value="all">All</option>
              <option value="active">Active</option>
              <option value="expired">Expired</option>
              <option value="expiring_soon">Expiring Soon</option>
            </select>
          </div>

          {/* Expiry Date From */}
          <div>
            <label className={labelCls}>Expiry Date From</label>
            <input
              type="date"
              className={inputCls}
              value={filters.expiry_date_from}
              onChange={(e) =>
                setFilters({ ...filters, expiry_date_from: e.target.value })
              }
            />
          </div>

          {/* Expiry Date To */}
          <div>
            <label className={labelCls}>Expiry Date To</label>
            <input
              type="date"
              className={inputCls}
              value={filters.expiry_date_to}
              onChange={(e) =>
                setFilters({ ...filters, expiry_date_to: e.target.value })
              }
            />
          </div>
        </div>

        {/* Purchase Status multi-select row */}
        <div className="mt-3">
          <label className={labelCls}>Purchase Status</label>
          <div className="flex flex-wrap gap-1.5">
            {PURCHASE_STATUS_OPTIONS.map((opt) => {
              const sel = selectedPsValues.includes(opt.value)
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => togglePs(opt.value)}
                  className={cn(
                    'rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors',
                    sel
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border bg-card text-muted-foreground hover:border-primary hover:text-primary',
                  )}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function AllotmentAction() {
  const { id: paramId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const allotmentId = paramId ? parseInt(paramId, 10) : null

  // Allotment header
  const { data: allotment, isLoading: allotmentLoading } = useAllotment(allotmentId)

  // Allocation draft state: itemId → { qty, cif_fc }
  const [allocationData, setAllocationData] = useState<Record<number, AllocationDraft>>({})

  // Plan-gate: when allocate returns plan_exceeded, stash item here
  const [planModal, setPlanModal] = useState<{
    item: AvailableLicense
  } | null>(null)

  // Filter state
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [isFirstLoad, setIsFirstLoad] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)
  const PAGE_SIZE = 20

  // Error / success banners
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Available licenses (loaded after first-load filter is applied)
  const [availableData, setAvailableData] = useState<AvailableLicensesResponse | null>(null)
  const [availableLoading, setAvailableLoading] = useState(false)

  // Quasi-static data
  const [notificationOptions, setNotificationOptions] = useState<
    Array<{ value: string; display_name: string }>
  >([])
  const [availableItemNames, setAvailableItemNames] = useState<
    Array<{ value: number; label: string }>
  >([])

  // Mutations
  const allocateMutation = useAllocateItems(allotmentId ?? 0)
  const deleteMutation = useDeleteAllotmentItem(allotmentId ?? 0)
  const copyMutation = useCopyAllotment()

  // ─── On first allotment load, set description filter from item_name ───────────

  useEffect(() => {
    if (isFirstLoad && allotment?.item_name) {
      setFilters((prev) => ({ ...prev, description: allotment.item_name }))
      setIsFirstLoad(false)
    }
  }, [allotment, isFirstLoad])

  // ─── Load quasi-static data once ─────────────────────────────────────────────

  useEffect(() => {
    void apiClient
      .get(`${ENDPOINTS.MASTERS.NOTIFICATION_NUMBERS}?page_size=200&ordering=code`)
      .then((r) => {
        const list: Array<{ code: string; label?: string }> = Array.isArray(r.data)
          ? r.data
          : (r.data as { data?: Array<{ code: string; label?: string }> }).data ?? []
        setNotificationOptions(
          list.map(({ code, label }) => ({
            value: code,
            display_name: label ? `${code} — ${label}` : code,
          })),
        )
      })
      .catch(() => {})

    void apiClient
      .get('/api/v1/item-report/available-items/')
      .then((r) => {
        const list: Array<{ id: number; name: string }> = Array.isArray(r.data)
          ? r.data
          : (r.data as { data?: Array<{ id: number; name: string }> }).data ?? []
        setAvailableItemNames(list.map((item) => ({ value: item.id, label: item.name })))
      })
      .catch(() => {})
  }, [])

  // ─── Fetch available licenses when filters/page change ────────────────────────

  const apiParams = useMemo(() => {
    const params: Record<string, string | number> = {
      page: currentPage,
      page_size: PAGE_SIZE,
    }
    Object.entries(filters).forEach(([k, v]) => {
      if (v && v !== 'all') params[k] = v
    })
    return params
  }, [filters, currentPage])

  useEffect(() => {
    if (!allotmentId || isFirstLoad) return

    setAvailableLoading(true)
    void apiClient
      .get(ENDPOINTS.ALLOTMENTS.AVAILABLE_LICENSES(allotmentId), { params: apiParams })
      .then((r) => {
        setAvailableData(r.data as AvailableLicensesResponse)
      })
      .catch(() => {
        toast.error('Failed to load available licenses')
      })
      .finally(() => {
        setAvailableLoading(false)
      })
  }, [allotmentId, apiParams, isFirstLoad])

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [filters])

  // Unsaved changes warning
  const hasUnsavedChanges = Object.keys(allocationData).length > 0

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault()
        e.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [hasUnsavedChanges])

  // ─── Derived data ─────────────────────────────────────────────────────────────

  const availableItems: AvailableLicense[] = useMemo(
    () => availableData?.available_items ?? availableData?.results ?? [],
    [availableData],
  )
  const totalItems = availableData?.count ?? 0
  const totalPages = totalItems > 0 ? Math.ceil(totalItems / PAGE_SIZE) : 0

  // ─── Business logic — ported identically from legacy ─────────────────────────

  const calculateMaxAllocation = useCallback(
    (item: AvailableLicense) => {
      if (!allotment?.unit_value_per_unit) return { qty: 0, value: 0 }

      const unitPrice = parseFloat(allotment.unit_value_per_unit)
      const balancedQty = parseFloat(allotment.balanced_quantity ?? '0')
      const requiredValue = parseFloat(allotment.required_value ?? '0')
      const reqValueWithBuffer = parseFloat(
        (allotment as Allotment & { required_value_with_buffer?: string })
          .required_value_with_buffer ?? String(requiredValue + 20),
      )
      const allottedValue = parseFloat(allotment.allotted_value ?? '0')
      const balancedValueWithBuffer = reqValueWithBuffer - allottedValue
      const availableQty = Math.floor(parseFloat(item.available_quantity ?? '0'))
      const availableCifFc = parseFloat(item.balance_cif_fc ?? '0')

      let maxQty = Math.floor(Math.min(balancedQty, availableQty))
      let maxValue = maxQty * unitPrice

      if (maxValue > availableCifFc) {
        maxQty = Math.floor(availableCifFc / unitPrice)
        maxValue = maxQty * unitPrice
      }
      if (maxValue > balancedValueWithBuffer) {
        maxQty = Math.floor(balancedValueWithBuffer / unitPrice)
        maxValue = maxQty * unitPrice
      }

      maxValue = Math.min(maxValue, availableCifFc, balancedValueWithBuffer)
      maxValue = Math.floor(maxValue * 100) / 100

      return { qty: maxQty, value: maxValue }
    },
    [allotment],
  )

  const handleQuantityChange = useCallback(
    (itemId: number, qty: string) => {
      const item = availableItems.find((i) => i.id === itemId)
      if (!item || !allotment) return

      const unitPrice = parseFloat(allotment.unit_value_per_unit)
      let inputQty = parseInt(qty, 10) || 0

      const balancedQty = parseFloat(allotment.balanced_quantity ?? '0')
      const requiredValue = parseFloat(allotment.required_value ?? '0')
      const reqValueWithBuffer = parseFloat(
        (allotment as Allotment & { required_value_with_buffer?: string })
          .required_value_with_buffer ?? String(requiredValue + 20),
      )
      const allottedValue = parseFloat(allotment.allotted_value ?? '0')
      const balancedValueWithBuffer = reqValueWithBuffer - allottedValue
      const availableCifFc = parseFloat(item.balance_cif_fc ?? '0')
      const availableQty = Math.floor(parseFloat(item.available_quantity ?? '0'))

      if (inputQty > balancedQty) {
        toast.warning(`Quantity adjusted to balanced quantity: ${balancedQty}`)
        inputQty = balancedQty
      }
      if (inputQty > availableQty) {
        toast.warning(`Quantity adjusted to available quantity: ${availableQty}`)
        inputQty = availableQty
      }

      let allocateCifFc = inputQty * unitPrice

      if (allocateCifFc > balancedValueWithBuffer) {
        inputQty = Math.floor(balancedValueWithBuffer / unitPrice)
        allocateCifFc = inputQty * unitPrice
        toast.warning(`Quantity adjusted to match value limit: ${inputQty}`)
      }
      if (allocateCifFc > availableCifFc) {
        inputQty = Math.floor(availableCifFc / unitPrice)
        allocateCifFc = inputQty * unitPrice
        toast.warning(`Quantity adjusted to available CIF: ${inputQty}`)
      }

      setAllocationData((prev) => ({
        ...prev,
        [itemId]: {
          qty: inputQty.toString(),
          cif_fc: allocateCifFc.toFixed(2),
        },
      }))
    },
    [availableItems, allotment],
  )

  const handleValueChange = useCallback(
    (itemId: number, value: string) => {
      const item = availableItems.find((i) => i.id === itemId)
      if (!item || !allotment) return

      const unitPrice = parseFloat(allotment.unit_value_per_unit)
      let inputValue = parseFloat(value) || 0

      const balancedQty = parseInt(allotment.balanced_quantity ?? '0', 10)
      const requiredValue = parseFloat(allotment.required_value ?? '0')
      const reqValueWithBuffer = parseFloat(
        (allotment as Allotment & { required_value_with_buffer?: string })
          .required_value_with_buffer ?? String(requiredValue + 20),
      )
      const allottedValue = parseFloat(allotment.allotted_value ?? '0')
      const balancedValueWithBuffer = reqValueWithBuffer - allottedValue
      const availableCifFc = parseFloat(item.balance_cif_fc ?? '0')

      if (inputValue > balancedValueWithBuffer) inputValue = balancedValueWithBuffer
      if (inputValue > availableCifFc) inputValue = availableCifFc

      let allocateQty = Math.floor(inputValue / unitPrice)
      if (allocateQty > balancedQty) allocateQty = balancedQty

      const adjustedValue = (allocateQty * unitPrice).toFixed(2)

      setAllocationData((prev) => ({
        ...prev,
        [itemId]: { qty: allocateQty.toString(), cif_fc: adjustedValue },
      }))
    },
    [availableItems, allotment],
  )

  const handleMaxQuantity = useCallback(
    (item: AvailableLicense) => {
      const max = calculateMaxAllocation(item)
      setAllocationData((prev) => ({
        ...prev,
        [item.id]: { qty: max.qty.toString(), cif_fc: max.value.toFixed(2) },
      }))
    },
    [calculateMaxAllocation],
  )

  const handleConfirmAllot = useCallback(
    (item: AvailableLicense) => {
      const allocation = allocationData[item.id]
      if (!allocation || parseFloat(allocation.qty) <= 0) {
        toast.error('Please enter a valid quantity')
        setError('Please enter a valid quantity')
        return
      }
      setError('')
      setSuccess('')
      allocateMutation.mutate(
        [{ item_id: item.id, qty: allocation.qty, cif_fc: allocation.cif_fc }],
        {
          onSuccess: (data) => {
            if (data.errors && data.errors.length > 0) {
              const firstErr = data.errors[0]
              if (firstErr.plan_exceeded) {
                setPlanModal({ item })
                return
              }
              const msg = `Error: ${firstErr.error}`
              setError(msg)
              toast.error(msg)
              return
            }

            const msg = `Successfully allocated ${allocation.qty} from ${item.license_number}`
            setSuccess(msg)
            toast.success(msg)

            setAllocationData((prev) => {
              const next = { ...prev }
              delete next[item.id]
              return next
            })

            // Scroll to transfer letter if fully allotted
            if (data.allotment) {
              const reqQty = parseInt(data.allotment.required_quantity ?? '0', 10)
              const allotedQty = parseInt(data.allotment.alloted_quantity ?? '0', 10)
              if (reqQty > 0 && reqQty - allotedQty === 0) {
                setTimeout(() => {
                  document
                    .getElementById('transfer-letter-section')
                    ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                }, 800)
              }
            }
          },
          onError: (err: unknown) => {
            const e = err as { response?: { data?: { error?: string } } }
            const msg =
              e.response?.data?.error ?? 'Failed to allocate item'
            setError(msg)
            toast.error(msg)
          },
        },
      )
    },
    [allocationData, allocateMutation],
  )

  const handleDeleteAllotment = useCallback(
    (allotmentItemId: number) => {
      if (!window.confirm('Are you sure you want to remove this allocation?')) return
      setError('')
      setSuccess('')
      deleteMutation.mutate(allotmentItemId)
    },
    [deleteMutation],
  )

  const handleDownloadPdf = async () => {
    try {
      const response = await apiClient.get(
        ENDPOINTS.ALLOTMENTS.GENERATE_PDF(allotmentId!),
        { responseType: 'blob' },
      )
      const url = window.URL.createObjectURL(
        new Blob([response.data], { type: 'application/pdf' }),
      )
      const link = document.createElement('a')
      link.href = url
      link.setAttribute(
        'download',
        `Allotment - ${allotment?.invoice ?? allotmentId}.pdf`,
      )
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      setError('Failed to download PDF')
    }
  }

  const handleCopy = async () => {
    if (!window.confirm('Are you sure you want to create a copy of this allotment?'))
      return
    copyMutation.mutate(allotmentId!, {
      onSuccess: (copied) => {
        navigate(`/allotments/${copied.id}/allocate`)
      },
    })
  }

  // ─── Loading state ────────────────────────────────────────────────────────────

  if (allotmentLoading) {
    return (
      <div className="flex min-h-[60vh] flex-col gap-4 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  // ─── Stat grid ────────────────────────────────────────────────────────────────

  const unitPrice = parseFloat(allotment?.unit_value_per_unit ?? '0')
  const requiredQty = parseInt(allotment?.required_quantity ?? '0', 10)
  const requiredValue = parseFloat(allotment?.required_value ?? '0')
  const allotedQty = parseInt(allotment?.alloted_quantity ?? '0', 10)
  const allotedValue = parseFloat(allotment?.allotted_value ?? '0')
  const balanceQty = parseFloat(allotment?.balanced_quantity ?? '0')
  const balanceValue = requiredValue - allotedValue
  const progressPct =
    requiredQty > 0 ? Math.min(100, Math.round((allotedQty / requiredQty) * 100)) : 0
  const isComplete = progressPct >= 100
  const progressColor = isComplete
    ? 'var(--tb-success)'
    : progressPct >= 60
    ? 'var(--tb-brand)'
    : 'var(--tb-warning)'

  // ─── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="flex min-h-screen flex-col bg-muted/30 p-6 gap-4">
      {/* Page header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h4 className="mb-0 flex items-center gap-1.5 text-lg font-bold text-foreground">
            <Network className="size-5" aria-hidden="true" />
            Allocate License Items
          </h4>
          {allotment && (
            <p className="mt-0.5 text-sm text-muted-foreground">
              {allotment.item_name}
              {allotment.invoice && (
                <span className="ml-2">— Invoice #{allotment.invoice}</span>
              )}
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate(`/allotments`)}
          >
            <PenSquare className="size-4 mr-1" aria-hidden="true" />
            Edit
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
            disabled={copyMutation.isPending}
          >
            <Files className="size-4 mr-1" aria-hidden="true" />
            Copy
          </Button>
          <Button
            size="sm"
            onClick={handleDownloadPdf}
            style={{
              background:
                'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))',
              border: 'none',
            }}
          >
            <FileText className="size-4 mr-1" aria-hidden="true" />
            Download PDF
          </Button>
          {(allotment?.allotment_details?.length ?? 0) > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                document
                  .getElementById('transfer-letter-section')
                  ?.scrollIntoView({ behavior: 'smooth' })
              }
            >
              <FileText className="size-4 mr-1" aria-hidden="true" />
              Transfer Letter
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/allotments')}
          >
            <ArrowLeft className="size-4 mr-1" aria-hidden="true" />
            Back
          </Button>
        </div>
      </div>

      {/* Allotment stat card */}
      {allotment && (
        <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          {/* Card header */}
          <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
            <div className="flex items-center gap-3">
              <div
                className="flex size-8 shrink-0 items-center justify-center rounded-lg"
                style={{
                  background: 'var(--tb-brand-50)',
                  border: '1px solid var(--tb-brand-100)',
                }}
              >
                <ListChecks
                  className="size-4"
                  style={{ color: 'var(--tb-brand)' }}
                  aria-hidden="true"
                />
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                  Allotment Details
                </p>
                <h3 className="text-sm font-bold leading-tight tracking-tight text-foreground">
                  {allotment.item_name}
                </h3>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full transition-[width] duration-500"
                    style={{ width: `${progressPct}%`, background: progressColor }}
                  />
                </div>
                <span
                  className="text-xs font-bold tabular-nums"
                  style={{ color: progressColor }}
                >
                  {progressPct}%
                </span>
              </div>
              <span
                className="rounded-full px-2.5 py-1 text-[11px] font-semibold leading-none"
                style={{
                  background: isComplete
                    ? 'var(--tb-success-soft)'
                    : progressPct >= 60
                    ? 'var(--tb-brand-50)'
                    : 'var(--tb-warning-soft)',
                  color: isComplete
                    ? 'var(--tb-success-text)'
                    : progressPct >= 60
                    ? 'var(--tb-brand)'
                    : 'var(--tb-warning-text)',
                }}
              >
                {isComplete ? '✓ Complete' : 'In Progress'}
              </span>
            </div>
          </div>

          {/* 4-column stat grid */}
          <div className="grid grid-cols-2 divide-y divide-border/40 sm:grid-cols-4 sm:divide-x sm:divide-y-0">
            <div className="flex flex-col px-5 py-4">
              <div className="mb-2 flex items-center gap-1.5">
                <span
                  className="size-2 shrink-0 rounded-full"
                  style={{ background: 'var(--tb-info)' }}
                />
                <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                  Unit Price
                </span>
              </div>
              <span
                className="text-[1.65rem] font-extrabold leading-none tabular-nums"
                style={{ color: 'var(--tb-info)' }}
              >
                {unitPrice.toFixed(3)}
              </span>
              <span className="mt-1.5 text-[11px] text-muted-foreground">
                USD per unit
              </span>
            </div>

            <div className="flex flex-col px-5 py-4">
              <div className="mb-2 flex items-center gap-1.5">
                <span className="size-2 shrink-0 rounded-full bg-muted-foreground/40" />
                <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                  Required
                </span>
              </div>
              <span className="text-[1.65rem] font-extrabold leading-none tabular-nums text-foreground">
                {requiredQty.toLocaleString()}
              </span>
              <span className="mt-1.5 text-[11px] font-semibold text-muted-foreground">
                ${requiredValue.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            <div
              className="flex flex-col px-5 py-4"
              style={{ background: 'rgba(16,185,129,0.04)' }}
            >
              <div className="mb-2 flex items-center gap-1.5">
                <span
                  className="size-2 shrink-0 rounded-full"
                  style={{ background: 'var(--tb-success)' }}
                />
                <span
                  className="text-[10px] font-bold uppercase tracking-widest"
                  style={{ color: 'var(--tb-success-text)' }}
                >
                  Allotted
                </span>
              </div>
              <span
                className="text-[1.65rem] font-extrabold leading-none tabular-nums"
                style={{ color: 'var(--tb-success)' }}
              >
                {allotedQty.toLocaleString()}
              </span>
              <span
                className="mt-1.5 text-[11px] font-semibold"
                style={{ color: 'var(--tb-success-text)' }}
              >
                ${allotedValue.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            <div
              className="flex flex-col px-5 py-4"
              style={{
                background:
                  balanceQty <= 0 ? 'rgba(16,185,129,0.06)' : 'var(--tb-brand-50)',
              }}
            >
              <div className="mb-2 flex items-center gap-1.5">
                <span
                  className="size-2 shrink-0 rounded-full"
                  style={{
                    background:
                      balanceQty <= 0 ? 'var(--tb-success)' : 'var(--tb-brand)',
                  }}
                />
                <span
                  className="text-[10px] font-bold uppercase tracking-widest"
                  style={{
                    color:
                      balanceQty <= 0 ? 'var(--tb-success-text)' : 'var(--tb-brand)',
                  }}
                >
                  Balance
                </span>
              </div>
              <span
                className="text-[1.65rem] font-extrabold leading-none tabular-nums"
                style={{
                  color:
                    balanceQty <= 0
                      ? 'var(--tb-success)'
                      : 'var(--tb-brand-active)',
                }}
              >
                {balanceQty.toLocaleString()}
              </span>
              <span
                className="mt-1.5 text-[11px] font-semibold"
                style={{
                  color:
                    balanceQty <= 0 ? 'var(--tb-success-text)' : 'var(--tb-brand)',
                }}
              >
                ${balanceValue.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                <span className="ml-1 font-normal opacity-50">+$20 buf</span>
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Allotted items table */}
      {(allotment?.allotment_details?.length ?? 0) > 0 && (
        <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
            <h6 className="flex items-center gap-2 text-sm font-semibold">
              <CheckSquare className="size-4" aria-hidden="true" />
              Allotted Items
              <span
                className="rounded-full px-2 py-0.5 text-[10px] font-bold"
                style={{ background: 'var(--tb-success-soft)', color: 'var(--tb-success-text)' }}
              >
                {allotment!.allotment_details.length}
              </span>
            </h6>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                const headers = [
                  'License', 'Serial', 'Description', 'HSN Code',
                  'Exporter', 'Transfer Status', 'License Date',
                  'Expiry Date', 'Allotted Qty', 'Allotted Value',
                ]
                const rows = allotment!.allotment_details.map((d) => {
                  const transferInfo =
                    [
                      (d as AllotmentItem & { current_owner?: string }).current_owner,
                      (d as AllotmentItem & { file_transfer_status?: string }).file_transfer_status,
                    ]
                      .filter(Boolean)
                      .join(' - ') || '-'
                  return [
                    d.license_number,
                    d.serial_number,
                    d.product_description,
                    d.hs_code ?? '-',
                    d.exporter,
                    transferInfo,
                    d.license_date,
                    d.license_expiry,
                    parseInt(d.qty ?? '0', 10).toLocaleString(),
                    parseFloat(d.cif_fc ?? '0').toFixed(2),
                  ]
                })
                const tsv = [
                  headers.join('\t'),
                  ...rows.map((r) => r.join('\t')),
                ].join('\n')
                navigator.clipboard
                  .writeText(tsv)
                  .then(() => toast.success('Copied to clipboard!'))
                  .catch(() => toast.error('Failed to copy'))
              }}
            >
              <Clipboard className="size-4 mr-1" aria-hidden="true" />
              Copy
            </Button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead style={{ backgroundColor: 'var(--tb-sunken)', borderBottom: '2px solid var(--tb-border)' }}>
                <tr>
                  {[
                    ['License', '120px'],
                    ['Serial', '70px'],
                    ['Description', '240px'],
                    ['HSN Code', '80px'],
                    ['Exporter', '160px'],
                    ['Transfer Status', '140px'],
                    ['License Date', '100px'],
                    ['Expiry Date', '100px'],
                    ['Allotted Qty', '80px', 'right'],
                    ['Allotted Value', '90px', 'right'],
                    ['Action', '64px'],
                  ].map(([label, minW, align]) => (
                    <th
                      key={String(label)}
                      style={{
                        minWidth: String(minW),
                        whiteSpace: 'nowrap',
                        fontWeight: 600,
                        fontSize: 12,
                        padding: '8px',
                        textAlign: align === 'right' ? 'right' : 'left',
                      }}
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {allotment!.allotment_details.map((detail) => {
                  const ext = detail as AllotmentItem & {
                    current_owner?: string
                    file_transfer_status?: string
                    purchase_status?: string
                  }
                  return (
                    <tr
                      key={detail.id}
                      className="border-b border-border/40 hover:bg-muted/30"
                    >
                      <td className="px-3 py-1.5 font-mono text-[12.5px] font-semibold">
                        {detail.license_number}
                      </td>
                      <td className="px-3 py-1.5 text-[12.5px]">
                        <span className="font-medium">{detail.serial_number}</span>
                        <ConditionBadge type={(detail as AllotmentItem & { condition_type?: string }).condition_type} />
                      </td>
                      <td className="px-3 py-1.5 text-[12.5px]">
                        {detail.product_description}
                      </td>
                      <td className="px-3 py-1.5 font-mono text-[11.5px] text-muted-foreground">
                        {detail.hs_code ?? '-'}
                      </td>
                      <td className="px-3 py-1.5 text-[12.5px]">
                        {detail.exporter}
                      </td>
                      <td className="px-3 py-1.5 text-[12px]">
                        {ext.current_owner && ext.file_transfer_status ? (
                          <div>
                            <div className="font-semibold">{ext.current_owner}</div>
                            <div className="text-muted-foreground text-[11px]">
                              {ext.file_transfer_status}
                            </div>
                          </div>
                        ) : ext.current_owner ? (
                          <div className="font-semibold">{ext.current_owner}</div>
                        ) : ext.file_transfer_status ? (
                          <div className="text-muted-foreground">
                            {ext.file_transfer_status}
                          </div>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </td>
                      <td className="px-3 py-1.5 text-[12px] text-muted-foreground">
                        {detail.license_date}
                      </td>
                      <td className="px-3 py-1.5 text-[12px] text-muted-foreground">
                        {detail.license_expiry}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-[12.5px] font-semibold">
                        {parseInt(detail.qty ?? '0', 10).toLocaleString()}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-[12.5px] font-semibold">
                        {parseFloat(detail.cif_fc ?? '0').toFixed(2)}
                      </td>
                      <td className="px-2 py-1.5 text-center">
                        <button
                          type="button"
                          className="flex size-7 items-center justify-center rounded border border-destructive/30 text-destructive/70 transition-colors hover:border-destructive hover:bg-destructive/10 disabled:opacity-40"
                          onClick={() => handleDeleteAllotment(detail.id)}
                          disabled={
                            deleteMutation.isPending &&
                            deleteMutation.variables === detail.id
                          }
                          title="Remove this allocation"
                        >
                          {deleteMutation.isPending &&
                          deleteMutation.variables === detail.id ? (
                            <span
                              className="inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
                              aria-hidden="true"
                            />
                          ) : (
                            <Trash2 className="size-4" aria-hidden="true" />
                          )}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
              <tfoot>
                <tr
                  style={{
                    background: 'var(--tb-sunken)',
                    borderTop: '2px solid var(--tb-border)',
                  }}
                >
                  <th
                    colSpan={8}
                    className="px-3 py-1.5 text-right text-[11px] font-bold uppercase tracking-wider text-muted-foreground"
                  >
                    Total
                  </th>
                  <th className="px-3 py-1.5 text-right text-[13px] font-extrabold tabular-nums">
                    {parseInt(allotment!.alloted_quantity ?? '0', 10).toLocaleString()}
                  </th>
                  <th className="px-3 py-1.5 text-right text-[13px] font-extrabold tabular-nums">
                    {parseFloat(allotment!.allotted_value ?? '0').toFixed(2)}
                  </th>
                  <th />
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* Transfer Letter */}
      {(allotment?.allotment_details?.length ?? 0) > 0 && (
        <div id="transfer-letter-section">
          <TransferLetterForm
            instanceId={allotmentId!}
            instanceType="allotment"
            items={allotment!.allotment_details.map((d) => ({
              id: d.id,
              license_number: d.license_number ?? '-',
              cif_fc: d.cif_fc ?? 0,
              purchase_status:
                (d as AllotmentItem & { purchase_status?: string }).purchase_status ??
                'N/A',
            }))}
            onSuccess={(msg) => toast.success(msg)}
            onError={(msg) => toast.error(msg)}
          />
        </div>
      )}

      {/* Available Licenses panel */}
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        <div className="flex items-center justify-between border-b border-border/60 px-5 py-3.5">
          <div className="flex items-center gap-2">
            <ListChecks
              className="size-4"
              style={{ color: 'var(--tb-brand)' }}
              aria-hidden="true"
            />
            <span className="text-sm font-bold tracking-tight text-foreground">
              Available License Items
            </span>
            {totalItems > 0 && (
              <span
                className="rounded-full px-2 py-0.5 text-[10px] font-bold"
                style={{
                  background: 'var(--tb-brand-50)',
                  color: 'var(--tb-brand)',
                }}
              >
                {totalItems} items
              </span>
            )}
          </div>
        </div>

        <div className="p-5">
          {/* Status banners */}
          {error && (
            <div
              className="mb-3 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive"
              role="alert"
            >
              <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
              <div className="flex-1">{error}</div>
              <button
                type="button"
                className="ml-auto shrink-0 cursor-pointer opacity-60 hover:opacity-100"
                onClick={() => setError('')}
              >
                <X className="size-3.5" />
              </button>
            </div>
          )}
          {success && (
            <div
              className="mb-3 flex items-start gap-2 rounded-lg border border-green-400/30 bg-green-500/10 px-3.5 py-2.5 text-[13px]"
              style={{ color: 'var(--tb-success-text)' }}
              role="alert"
            >
              <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
              <div className="flex-1">{success}</div>
              <button
                type="button"
                className="ml-auto shrink-0 cursor-pointer opacity-60 hover:opacity-100"
                onClick={() => setSuccess('')}
              >
                <X className="size-3.5" />
              </button>
            </div>
          )}

          {/* Filters */}
          <AllotmentFilters
            filters={filters}
            setFilters={setFilters}
            notificationOptions={notificationOptions}
            availableItemNames={availableItemNames}
          />

          {/* Item cards */}
          <div style={{ maxHeight: 650, overflowY: 'auto', paddingRight: 2 }}>
            {availableItems.map((item) => {
              const maxAllocation = calculateMaxAllocation(item)
              const currentAllocation = allocationData[item.id]
              const qty = parseFloat(item.available_quantity ?? '0')
              const cifFc = parseFloat(item.balance_cif_fc ?? '0')
              const average = qty > 0 ? (cifFc / qty).toFixed(2) : '0.00'
              const isReady =
                !!currentAllocation && parseFloat(currentAllocation.qty) > 0

              return (
                <div
                  key={item.id}
                  style={{
                    display: 'block',
                    background: 'var(--tb-card-bg)',
                    border: `1px solid ${isReady ? 'var(--primary-color, hsl(var(--primary)))' : 'var(--tb-border-soft)'}`,
                    borderLeft: `4px solid ${isReady ? 'var(--primary-color, hsl(var(--primary)))' : 'var(--tb-border-strong)'}`,
                    borderRadius: 'var(--tb-r-md, 8px)',
                    marginBottom: 10,
                    overflow: 'hidden',
                    boxShadow: isReady
                      ? '0 2px 12px rgba(79,70,229,0.12)'
                      : '0 1px 3px rgba(0,0,0,0.06)',
                  }}
                >
                  {/* Row 1: Identity bar */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      gap: 6,
                      padding: '6px 12px',
                      background: 'var(--tb-sunken)',
                      borderBottom: '1px solid var(--tb-border)',
                    }}
                  >
                    <span
                      style={{
                        fontWeight: 700,
                        fontSize: 14,
                        color: 'hsl(var(--primary))',
                        marginRight: 4,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 2,
                      }}
                    >
                      <FileText className="size-4" aria-hidden="true" />
                      {item.license_number}
                    </span>
                    <span
                      style={{
                        background: 'var(--tb-border)',
                        color: 'var(--text-secondary)',
                        borderRadius: 'var(--tb-r-sm, 4px)',
                        padding: '1px 7px',
                        fontSize: 12,
                        fontWeight: 600,
                      }}
                    >
                      #{item.serial_number}
                    </span>
                    <ConditionBadge type={item.condition_type} />
                    {item.hs_code_label && (
                      <span
                        style={{
                          background: 'var(--indigo-50, #EEF2FF)',
                          color: 'var(--primary-dark, hsl(var(--primary)))',
                          border: '1px solid var(--indigo-200, #C7D2FE)',
                          borderRadius: 'var(--tb-r-sm, 4px)',
                          padding: '1px 7px',
                          fontSize: 12,
                        }}
                      >
                        HS: {item.hs_code_label}
                      </span>
                    )}
                    {item.notification_number && (
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                        Notif: {item.notification_number}
                      </span>
                    )}
                    <span
                      style={{
                        marginLeft: 'auto',
                        fontSize: 12,
                        color: 'var(--text-secondary)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      <Calendar className="size-3" aria-hidden="true" />
                      Exp: {item.license_expiry_date ?? '—'}
                    </span>
                    {!item.condition_type && (
                      <span
                        style={{
                          background: 'var(--success-bg, #D1FAE5)',
                          color: 'var(--success-text, #065F46)',
                          border: '1px solid var(--success-border, #A7F3D0)',
                          borderRadius: 4,
                          padding: '0px 6px',
                          fontSize: 11,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 2,
                        }}
                      >
                        <Unlock className="size-3" aria-hidden="true" />
                        Open
                      </span>
                    )}
                  </div>

                  {/* Row 2: Description + exporter + item chips */}
                  <div
                    style={{
                      padding: '5px 12px',
                      borderBottom: '1px solid var(--tb-border-soft)',
                      background: 'var(--tb-card-bg)',
                      display: 'flex',
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      gap: 6,
                    }}
                  >
                    <span
                      style={{
                        fontWeight: 700,
                        fontSize: 13,
                        color: 'var(--tb-text)',
                      }}
                    >
                      {item.description}
                    </span>
                    <span
                      style={{
                        width: 1,
                        height: 12,
                        background: 'var(--tb-border)',
                        flexShrink: 0,
                        display: 'inline-block',
                      }}
                    />
                    <span
                      style={{
                        fontSize: 11.5,
                        color: 'var(--text-secondary)',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 3,
                      }}
                    >
                      <Building2 className="size-3" aria-hidden="true" />
                      {item.exporter_name}
                    </span>
                    {item.items_detail?.map((i, idx) => (
                      <span
                        key={idx}
                        style={{
                          background: 'var(--tb-brand-50)',
                          color: 'var(--tb-brand)',
                          border: '1px solid var(--tb-brand-100)',
                          borderRadius: 4,
                          padding: '0px 6px',
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          lineHeight: '1.6',
                        }}
                      >
                        {i.name}
                      </span>
                    ))}
                  </div>

                  {/* Row 3: Stats + inputs + confirm */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      gap: 0,
                      background: 'var(--tb-sunken)',
                    }}
                  >
                    {/* Availability stats */}
                    <div
                      style={{
                        display: 'flex',
                        gap: 12,
                        padding: '7px 12px',
                        flexShrink: 0,
                      }}
                    >
                      {[
                        { label: 'Avail Qty', value: qty.toFixed(3) },
                        { label: 'CIF FC', value: cifFc.toFixed(2) },
                        { label: 'Avg', value: average },
                      ].map(({ label, value }) => (
                        <div key={label}>
                          <div
                            style={{
                              fontSize: '0.62rem',
                              color: 'var(--text-secondary)',
                              textTransform: 'uppercase',
                              letterSpacing: '0.4px',
                            }}
                          >
                            {label}
                          </div>
                          <div
                            style={{
                              fontWeight: 700,
                              fontSize: 13,
                              color: 'var(--tb-text)',
                              lineHeight: 1.2,
                            }}
                          >
                            {value}
                          </div>
                        </div>
                      ))}
                    </div>

                    <div
                      style={{
                        width: 1,
                        height: 36,
                        background: 'var(--tb-border-soft)',
                        flexShrink: 0,
                      }}
                    />

                    {/* Allocation inputs */}
                    <div
                      style={{
                        display: 'flex',
                        gap: 8,
                        padding: '7px 12px',
                        flexWrap: 'wrap',
                        flex: 1,
                        minWidth: 260,
                      }}
                    >
                      <div style={{ flex: 1, minWidth: 130 }}>
                        <label
                          style={{
                            fontSize: '0.62rem',
                            color: 'var(--text-secondary)',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            letterSpacing: '0.3px',
                            display: 'block',
                            marginBottom: 3,
                          }}
                        >
                          Qty{' '}
                          <span
                            style={{ fontWeight: 400, textTransform: 'none' }}
                          >
                            / max {maxAllocation.qty}
                          </span>
                        </label>
                        <div className="flex">
                          <Input
                            type="number"
                            className="h-8 rounded-r-none"
                            value={currentAllocation?.qty ?? ''}
                            onChange={(e) =>
                              handleQuantityChange(item.id, e.target.value)
                            }
                            placeholder="Qty"
                            step={1}
                            min={0}
                            max={maxAllocation.qty}
                            style={{ fontSize: '0.82rem' }}
                          />
                          <button
                            type="button"
                            onClick={() => handleMaxQuantity(item)}
                            className="flex h-8 items-center rounded-r-md border border-l-0 border-border bg-card px-2 text-xs font-semibold text-muted-foreground hover:bg-muted"
                          >
                            Max
                          </button>
                        </div>
                      </div>

                      <div style={{ flex: 1, minWidth: 130 }}>
                        <label
                          style={{
                            fontSize: '0.62rem',
                            color: 'var(--text-secondary)',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            letterSpacing: '0.3px',
                            display: 'block',
                            marginBottom: 3,
                          }}
                        >
                          Value{' '}
                          <span
                            style={{ fontWeight: 400, textTransform: 'none' }}
                          >
                            / max {maxAllocation.value.toFixed(2)}
                          </span>
                        </label>
                        <div className="flex">
                          <Input
                            type="number"
                            className="h-8 rounded-r-none"
                            value={currentAllocation?.cif_fc ?? ''}
                            onChange={(e) =>
                              handleValueChange(item.id, e.target.value)
                            }
                            placeholder="Value"
                            step={0.01}
                            min={0}
                            style={{ fontSize: '0.82rem' }}
                          />
                          <button
                            type="button"
                            onClick={() => handleMaxQuantity(item)}
                            className="flex h-8 items-center rounded-r-md border border-l-0 border-border bg-card px-2 text-xs font-semibold text-muted-foreground hover:bg-muted"
                          >
                            Max
                          </button>
                        </div>
                      </div>
                    </div>

                    <div
                      style={{
                        width: 1,
                        height: 36,
                        background: 'var(--tb-border-soft)',
                        flexShrink: 0,
                      }}
                    />

                    {/* Confirm */}
                    <div
                      style={{
                        flexShrink: 0,
                        padding: '7px 12px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <button
                        type="button"
                        style={{
                          background: isReady
                            ? 'hsl(var(--primary))'
                            : 'var(--tb-gray-100)',
                          border: 'none',
                          color: isReady ? 'hsl(var(--primary-foreground))' : 'var(--text-secondary)',
                          fontWeight: 600,
                          fontSize: '0.82rem',
                          padding: '10px 16px',
                          borderRadius: 'var(--tb-r-md, 8px)',
                          whiteSpace: 'nowrap',
                          transition: 'all 200ms',
                          cursor: isReady ? 'pointer' : 'not-allowed',
                        }}
                        onClick={() => handleConfirmAllot(item)}
                        disabled={
                          !isReady ||
                          (allocateMutation.isPending &&
                            (allocateMutation.variables as AllocationEntry[] | undefined)?.[0]?.item_id === item.id)
                        }
                      >
                        {allocateMutation.isPending &&
                        (allocateMutation.variables as AllocationEntry[] | undefined)?.[0]?.item_id === item.id ? (
                          <>
                            <span
                              className="mr-1 inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
                              aria-hidden="true"
                            />
                            Saving…
                          </>
                        ) : (
                          <>
                            <CheckCircle2
                              className="mr-1 inline size-4"
                              aria-hidden="true"
                            />
                            Confirm
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Loading overlay */}
          {availableLoading && (
            <div className="flex items-center justify-center gap-2 py-4 text-sm text-muted-foreground">
              <span
                className="inline-block size-4 animate-spin rounded-full border-2 border-primary border-t-transparent"
                aria-hidden="true"
              />
              Loading items…
            </div>
          )}

          {/* Empty state */}
          {!availableLoading && availableItems.length === 0 && (
            <div
              className="py-5 text-center"
              style={{
                border: '2px dashed var(--tb-border)',
                borderRadius: 'var(--tb-r-md, 8px)',
                background: 'var(--tb-card-bg)',
              }}
            >
              <Inbox className="mx-auto mb-2 size-8 text-muted-foreground" aria-hidden="true" />
              <div className="font-semibold text-muted-foreground">
                No available license items found
              </div>
              <small className="text-muted-foreground">
                Try adjusting the filters above
              </small>
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div
              className="mt-3 flex items-center justify-between pt-3"
              style={{ borderTop: '1px solid var(--tb-border)' }}
            >
              <span className="text-sm text-muted-foreground">
                Showing {(currentPage - 1) * PAGE_SIZE + 1} to{' '}
                {Math.min(currentPage * PAGE_SIZE, totalItems)} of {totalItems}{' '}
                items
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage((p) => p - 1)}
                  disabled={currentPage <= 1}
                >
                  Previous
                </Button>
                {/* Windowed page numbers */}
                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter(
                    (n) =>
                      n === 1 ||
                      n === totalPages ||
                      (n >= currentPage - 2 && n <= currentPage + 2),
                  )
                  .reduce<Array<number | 'ellipsis'>>((acc, n, idx, arr) => {
                    if (idx > 0 && n - (arr[idx - 1] as number) > 1)
                      acc.push('ellipsis')
                    acc.push(n)
                    return acc
                  }, [])
                  .map((item, idx) =>
                    item === 'ellipsis' ? (
                      <span key={`e${idx}`} className="px-1 text-muted-foreground">
                        …
                      </span>
                    ) : (
                      <Button
                        key={item}
                        variant={currentPage === item ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setCurrentPage(item as number)}
                      >
                        {item}
                      </Button>
                    ),
                  )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage((p) => p + 1)}
                  disabled={currentPage >= totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Plan gate modal */}
      <LicensePlanningPanel
        show={!!planModal}
        licenseId={planModal?.item.license ?? planModal?.item.license_id}
        licenseNumber={planModal?.item.license_number}
        balanceCif={Number(planModal?.item.balance_cif_fc ?? 0)}
        onHide={() => setPlanModal(null)}
        onSaved={() => {
          const item = planModal?.item
          setPlanModal(null)
          if (item) handleConfirmAllot(item)
        }}
      />
    </div>
  )
}

