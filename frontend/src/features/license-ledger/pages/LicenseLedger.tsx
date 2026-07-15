/**
 * LicenseLedger — list + company-wise ledger view for DFIA and Incentive licenses.
 *
 * Ported from legacy/frontend/src/pages/LicenseLedger.tsx.
 * All business logic preserved: financial year calculation, filters, company-wise
 * ledger, license-wise sub-component, running balance, P/L.
 *
 * Export (PDF / Excel): replaced client-side generation with a backend download
 * endpoint (GET /api/v1/license-ledger/export/all/) triggered as a URL open so
 * the browser streams the file directly. A toast is shown if no data is available.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import {
  ArrowDownCircle,
  ArrowUpCircle,
  BookOpen,
  Building2,
  Calendar,
  CalendarCheck,
  CalendarRange,
  CalendarX,
  FileSpreadsheet,
  FileText,
  Filter,
  Globe,
  Inbox,
  Loader2,
  Trophy,
  XCircle,
} from 'lucide-react'
import { cn } from '@/shared/utils/cn'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'

// ── Types ──────────────────────────────────────────────────────────────────────

interface LicenseTypeOption {
  value: string
  label: string
}

interface Filters {
  license_type: string
  min_balance: string
  search: string
  company: { value: string | number; label: string } | null
  active_only: boolean
  ordering: string
  purchase_date_from: string
  purchase_date_to: string
  no_purchases?: boolean
}

interface SummarySection {
  total_licenses: number
  total_value_usd?: number
  balance_value_usd?: number
  total_value_inr?: number
  balance_value_inr?: number
  purchase_amount_inr: number
  profit_loss_inr: number
}

interface Summary {
  dfia: SummarySection
  incentive: SummarySection
}

interface TradeRow {
  trade_id: number
  invoice_date: string
  amount: number
}

interface LicenseCompany {
  company_id: number
  company_name: string
  purchases: TradeRow[]
  sales: TradeRow[]
  purchase_total: number
  sale_total: number
  profit_loss: number
}

interface LicenseEntry {
  license_id: number
  license_number: string
  license_date: string
  license_type: string
  companies: LicenseCompany[]
}

interface LicenseWiseData {
  licenses: LicenseEntry[]
}

// ── Financial year helpers ─────────────────────────────────────────────────────

function getCurrentFinancialYear() {
  const today = new Date()
  const currentYear = today.getFullYear()
  const currentMonth = today.getMonth() // 0-11
  const fyStartYear = currentMonth <= 2 ? currentYear - 1 : currentYear
  return {
    fyStart: `${fyStartYear}-04-01`,
    fyEnd: `${fyStartYear + 1}-03-31`,
  }
}

function getPreviousFinancialYear() {
  const today = new Date()
  const currentYear = today.getFullYear()
  const currentMonth = today.getMonth()
  const fyStartYear = currentMonth <= 2 ? currentYear - 2 : currentYear - 1
  return {
    fyStart: `${fyStartYear}-04-01`,
    fyEnd: `${fyStartYear + 1}-03-31`,
  }
}

// ── formatIndianNumber shim ────────────────────────────────────────────────────
// Uses en-IN Intl.NumberFormat to match legacy formatting.
function formatIndianNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null || isNaN(value)) return '0'
  return new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

// ── License-wise sub-component ────────────────────────────────────────────────

interface LicenseWiseLedgerProps {
  data: LicenseWiseData
  navigate: ReturnType<typeof useNavigate>
}

function LicenseWiseLedger({ data, navigate }: LicenseWiseLedgerProps) {
  const { licenses } = data
  const fmt = (v: number) => `₹${formatIndianNumber(v, 2)}`
  const plColor = (v: number) => (v >= 0 ? 'var(--tb-success)' : 'var(--tb-danger)')

  if (licenses.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
        <Inbox className="size-8" aria-hidden="true" />
        <p className="mt-1 text-sm">No trades found</p>
      </div>
    )
  }

  return (
    <div className="p-2">
      {licenses.map((lic) => (
        <div
          key={lic.license_id}
          className="mb-6 overflow-hidden rounded-md border border-border"
        >
          {/* License header */}
          <div
            className="flex flex-wrap items-center gap-6 px-4 py-2.5"
            style={{ background: 'var(--tb-brand-active)', color: '#fff' }}
          >
            <span className="flex items-center gap-1.5 text-sm font-bold">
              <FileText className="size-3.5 shrink-0" aria-hidden="true" />
              {lic.license_number}
            </span>
            <span className="flex items-center gap-1 text-xs" style={{ color: 'rgba(255,255,255,0.75)' }}>
              <Calendar className="size-3.5 shrink-0" aria-hidden="true" />
              {lic.license_date}
            </span>
            <span
              className="rounded px-2 py-0.5 text-[11px] font-bold"
              style={{
                background:
                  lic.license_type === 'DFIA' ? 'var(--tb-info)' : 'var(--accent-color)',
                color: '#fff',
              }}
            >
              {lic.license_type}
            </span>
            <button
              type="button"
              onClick={() => navigate(`/license-ledger/${lic.license_id}`)}
              className="ml-auto flex items-center gap-1 rounded px-2.5 py-0.5 text-xs font-semibold transition-colors"
              style={{
                background: 'rgba(255,255,255,0.15)',
                border: '1px solid rgba(255,255,255,0.3)',
                color: '#fff',
              }}
            >
              <BookOpen className="size-3.5 shrink-0" aria-hidden="true" />
              View Ledger
            </button>
          </div>

          {/* Companies table */}
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--tb-sunken)', borderBottom: '2px solid var(--tb-border)' }}>
                  <th className="px-3 py-1.5 text-left font-bold text-foreground" style={{ width: '30%' }}>Company</th>
                  <th className="px-3 py-1.5 text-left font-bold text-foreground" style={{ width: '15%' }}>Type</th>
                  <th className="px-3 py-1.5 text-left font-bold text-foreground" style={{ width: '15%' }}>Date</th>
                  <th className="px-3 py-1.5 text-right font-bold" style={{ width: '20%', color: 'var(--tb-success-text)' }}>Purchase (₹)</th>
                  <th className="px-3 py-1.5 text-right font-bold" style={{ width: '20%', color: 'var(--tb-danger-text)' }}>Sale (₹)</th>
                </tr>
              </thead>
              <tbody>
                {lic.companies.map((company, ci) => (
                  <>
                    {/* Company name row */}
                    <tr
                      key={`company-${company.company_id}`}
                      style={{
                        background: ci % 2 === 0 ? 'var(--tb-brand-50)' : 'var(--tb-sunken)',
                        borderTop: ci > 0 ? '2px solid var(--tb-border)' : 'none',
                      }}
                    >
                      <td colSpan={5} className="flex items-center gap-1 px-3 py-1.5 text-[0.82rem] font-bold text-foreground">
                        <Building2 className="size-3.5 shrink-0" aria-hidden="true" />
                        {company.company_name}
                      </td>
                    </tr>

                    {/* Purchase rows */}
                    {company.purchases.map((row) => (
                      <tr
                        key={`p-${row.trade_id}`}
                        style={{
                          background: 'var(--tb-success-soft)',
                          borderBottom: '1px solid var(--tb-success-border)',
                        }}
                      >
                        <td className="flex items-center gap-1 px-3 py-1 pl-6 text-foreground">
                          <ArrowDownCircle className="size-3.5 shrink-0" aria-hidden="true" />
                          Purchase
                        </td>
                        <td className="px-3 py-1 text-muted-foreground">{lic.license_type}</td>
                        <td className="px-3 py-1 text-muted-foreground">{row.invoice_date}</td>
                        <td className="px-3 py-1 text-right font-semibold" style={{ color: 'var(--tb-success-text)' }}>{fmt(row.amount)}</td>
                        <td className="px-3 py-1" />
                      </tr>
                    ))}

                    {/* Sale rows */}
                    {company.sales.map((row) => (
                      <tr
                        key={`s-${row.trade_id}`}
                        style={{
                          background: 'var(--tb-danger-soft)',
                          borderBottom: '1px solid var(--tb-danger-border)',
                        }}
                      >
                        <td className="flex items-center gap-1 px-3 py-1 pl-6 text-foreground">
                          <ArrowUpCircle className="size-3.5 shrink-0" aria-hidden="true" />
                          Sale
                        </td>
                        <td className="px-3 py-1 text-muted-foreground">{lic.license_type}</td>
                        <td className="px-3 py-1 text-muted-foreground">{row.invoice_date}</td>
                        <td className="px-3 py-1" />
                        <td className="px-3 py-1 text-right font-semibold" style={{ color: 'var(--tb-danger-text)' }}>{fmt(row.amount)}</td>
                      </tr>
                    ))}

                    {/* Company total row */}
                    <tr
                      key={`total-${company.company_id}`}
                      className="font-bold"
                      style={{ background: 'var(--tb-brand-active)', color: '#fff' }}
                    >
                      <td colSpan={3} className="px-3 py-1.5 text-right text-xs">
                        Total — {company.company_name}
                      </td>
                      <td className="px-3 py-1.5 text-right" style={{ color: '#86efac' }}>{fmt(company.purchase_total)}</td>
                      <td className="px-3 py-1.5 text-right" style={{ color: '#fca5a5' }}>
                        {fmt(company.sale_total)}
                        <span className="ml-2 text-[11px]" style={{ color: plColor(company.profit_loss) }}>
                          P/L: {company.profit_loss >= 0 ? '+' : ''}{fmt(company.profit_loss)}
                        </span>
                      </td>
                    </tr>
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Debounced input ────────────────────────────────────────────────────────────

interface DebouncedInputProps {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  delay?: number
}

function DebouncedInput({ value, onChange, placeholder, delay = 350 }: DebouncedInputProps) {
  const [local, setLocal] = useState(value)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Keep local in sync when parent resets the value
  useEffect(() => {
    setLocal(value)
  }, [value])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value
    setLocal(v)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => onChange(v), delay)
  }

  return <Input value={local} onChange={handleChange} placeholder={placeholder} />
}

// ── Company autocomplete ───────────────────────────────────────────────────────

interface CompanyOption {
  value: number
  label: string
}

interface CompanySelectProps {
  value: { value: string | number; label: string } | null
  onChange: (v: { value: string | number; label: string } | null) => void
}

function CompanySelect({ value, onChange }: CompanySelectProps) {
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState<CompanyOption[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const search = useCallback(async (q: string) => {
    setLoading(true)
    try {
      const { data } = await apiClient.get<
        Array<{ id: number; name: string }> | { results?: Array<{ id: number; name: string }> }
      >(ENDPOINTS.MASTERS.COMPANIES, { params: { search: q, page_size: 20 } })
      const list = Array.isArray(data) ? data : (data as { results?: Array<{ id: number; name: string }> }).results ?? []
      setOptions(
        list.map((c) => ({
          value: c.id,
          label: c.name,
        })),
      )
    } catch {
      setOptions([])
    } finally {
      setLoading(false)
    }
  }, [])

  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const q = e.target.value
    setQuery(q)
    setOpen(true)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => search(q), 300)
  }

  const handleFocus = () => {
    setOpen(true)
    if (!options.length) search('')
  }

  const select = (opt: CompanyOption) => {
    onChange({ value: opt.value, label: opt.label })
    setQuery(opt.label)
    setOpen(false)
  }

  // Sync display when parent clears the value
  useEffect(() => {
    if (!value) setQuery('')
    else setQuery(value.label)
  }, [value])

  return (
    <div ref={wrapperRef} className="relative">
      <Input
        value={query}
        onChange={handleInput}
        onFocus={handleFocus}
        placeholder="Select company to view their ledger..."
        autoComplete="off"
      />
      {open && (
        <div className="absolute z-50 mt-1 max-h-52 w-full overflow-auto rounded-md border border-border bg-card shadow-md">
          {loading && (
            <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              Searching…
            </div>
          )}
          {!loading && options.length === 0 && (
            <div className="px-3 py-2 text-sm text-muted-foreground">No companies found</div>
          )}
          {!loading &&
            options.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className="flex w-full items-center px-3 py-1.5 text-left text-sm hover:bg-accent hover:text-accent-foreground focus-visible:bg-accent focus-visible:outline-none"
                onMouseDown={() => select(opt)}
              >
                {opt.label}
              </button>
            ))}
        </div>
      )}
    </div>
  )
}

// ── Toggle (replaces shadcn Switch which is not in shared/ui) ─────────────────

interface ToggleProps {
  id: string
  checked: boolean
  onCheckedChange: (v: boolean) => void
  label: string
}

function Toggle({ id, checked, onCheckedChange, label }: ToggleProps) {
  return (
    <label
      htmlFor={id}
      className="flex cursor-pointer items-center gap-2.5 text-sm"
    >
      <button
        type="button"
        id={id}
        role="switch"
        aria-checked={checked}
        onClick={() => onCheckedChange(!checked)}
        className={cn(
          'relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          checked ? 'bg-primary' : 'bg-input',
        )}
      >
        <span
          className={cn(
            'pointer-events-none inline-block size-4 rounded-full bg-background shadow-lg transition-transform',
            checked ? 'translate-x-4' : 'translate-x-0',
          )}
        />
      </button>
      <span className="text-xs font-semibold text-muted-foreground">{label}</span>
    </label>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

const LICENSE_TYPE_OPTIONS: LicenseTypeOption[] = [
  { value: 'ALL', label: 'All Licenses' },
  { value: 'DFIA', label: 'DFIA Only' },
  { value: 'INCENTIVE', label: 'All Incentive' },
  { value: 'RODTEP', label: 'RODTEP' },
  { value: 'ROSTL', label: 'ROSTL' },
  { value: 'MEIS', label: 'MEIS' },
]

const { fyStart: CURRENT_FY_START, fyEnd: CURRENT_FY_END } = getCurrentFinancialYear()

export default function LicenseLedger() {
  const navigate = useNavigate()
  const [summary, setSummary] = useState<Summary | null>(null)
  const [companyWiseData, setCompanyWiseData] = useState<LicenseWiseData | null>(null)
  const [companyWiseLoading, setCompanyWiseLoading] = useState(false)
  const [bulkExporting, setBulkExporting] = useState(false)

  const [filters, setFilters] = useState<Filters>({
    license_type: 'ALL',
    min_balance: '',
    search: '',
    company: null,
    active_only: true,
    ordering: '-license_date',
    purchase_date_from: CURRENT_FY_START,
    purchase_date_to: CURRENT_FY_END,
  })

  // Build URLSearchParams from current filters
  const buildFilterParams = useCallback(
    (overrides: Partial<Filters> = {}) => {
      const f = { ...filters, ...overrides }
      const params = new URLSearchParams()
      if (f.license_type) params.append('license_type', f.license_type)
      if (f.min_balance) params.append('min_balance', f.min_balance)
      if (f.search) params.append('search', f.search)
      if (f.company) params.append('company', String(f.company.value))
      if (f.ordering) params.append('ordering', f.ordering)
      if (f.purchase_date_from) params.append('purchase_date_from', f.purchase_date_from)
      if (f.purchase_date_to) params.append('purchase_date_to', f.purchase_date_to)
      params.append('active_only', String(f.active_only))
      if (f.no_purchases) params.append('no_purchases', 'true')
      return params
    },
    [filters],
  )

  const fetchSummary = useCallback(async () => {
    if (!filters.company) { setSummary(null); return }
    try {
      const params = buildFilterParams()
      const { data } = await apiClient.get<Summary>(`${ENDPOINTS.LICENSE_LEDGER.SUMMARY}?${params.toString()}`)
      setSummary(data)
    } catch {
      toast.error('Failed to load summary data.')
    }
  }, [filters.company, buildFilterParams])

  const fetchCompanyWise = useCallback(async () => {
    setCompanyWiseLoading(true)
    try {
      const params = buildFilterParams()
      params.delete('company')
      const { data } = await apiClient.get<LicenseWiseData>(
        `${ENDPOINTS.LICENSE_LEDGER.LICENSE_WISE}?${params.toString()}`,
      )
      setCompanyWiseData(data)
    } catch {
      toast.error('Failed to load license-wise ledger.')
      setCompanyWiseData(null)
    } finally {
      setCompanyWiseLoading(false)
    }
  }, [buildFilterParams])

  useEffect(() => {
    if (filters.company) {
      fetchSummary()
    } else {
      setSummary(null)
      fetchCompanyWise()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    filters.license_type,
    filters.min_balance,
    filters.search,
    filters.company,
    filters.active_only,
    filters.ordering,
    filters.purchase_date_from,
    filters.purchase_date_to,
  ])

  const handleFilterChange = <K extends keyof Filters>(field: K, value: Filters[K]) => {
    setFilters((prev) => ({ ...prev, [field]: value }))
  }

  const setCurrentFY = () => {
    const { fyStart, fyEnd } = getCurrentFinancialYear()
    setFilters((prev) => ({ ...prev, purchase_date_from: fyStart, purchase_date_to: fyEnd }))
  }

  const setPreviousFY = () => {
    const { fyStart, fyEnd } = getPreviousFinancialYear()
    setFilters((prev) => ({ ...prev, purchase_date_from: fyStart, purchase_date_to: fyEnd }))
  }

  const clearDateFilter = () => {
    setFilters((prev) => ({ ...prev, purchase_date_from: '', purchase_date_to: '' }))
  }

  // Export — open backend endpoint as a download link
  const handleBulkExport = async (format: 'pdf' | 'excel') => {
    if (!companyWiseData?.licenses?.length) {
      toast.error('No data to export')
      return
    }
    setBulkExporting(true)
    try {
      const params = buildFilterParams()
      params.append('format', format)
      const url = `${ENDPOINTS.LICENSE_LEDGER.EXPORT_ALL}?${params.toString()}`
      toast.info('Export started — download will begin shortly.')
      window.open(url, '_blank', 'noopener,noreferrer')
    } finally {
      setBulkExporting(false)
    }
  }

  const fmt = (v: number) => `₹${formatIndianNumber(v, 0)}`

  return (
    <div className="min-h-screen p-4 md:p-6" style={{ background: 'var(--tb-body-bg)' }}>
      {/* Page header */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold text-foreground">
            <BookOpen className="size-5 shrink-0" aria-hidden="true" />
            License Ledger
          </h1>
          <p className="text-sm text-muted-foreground">
            Track available balance for DFIA and Incentive licenses
          </p>
        </div>
        {companyWiseData?.licenses?.length ? (
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => handleBulkExport('pdf')} disabled={bulkExporting}>
              {bulkExporting ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <FileText className="size-3.5" aria-hidden="true" />
              )}
              Export PDF
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleBulkExport('excel')} disabled={bulkExporting}>
              {bulkExporting ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <FileSpreadsheet className="size-3.5" aria-hidden="true" />
              )}
              Export Excel
            </Button>
          </div>
        ) : null}
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="mb-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
          {/* DFIA */}
          <div className="rounded-lg border border-border bg-card" style={{ borderLeft: '3px solid var(--tb-brand)' }}>
            <div className="flex items-center gap-2 border-b border-border px-3 py-2">
              <Globe className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="text-sm font-semibold">DFIA Licenses</span>
              <span className="ml-auto rounded px-2 py-0.5 text-[11px] font-bold text-white" style={{ background: 'var(--tb-brand)' }}>
                {summary.dfia.total_licenses} active
              </span>
            </div>
            <div className="grid grid-cols-4 divide-x divide-border px-3 py-2 text-center">
              <StatCell label="Total Value" value={`$ ${formatIndianNumber(summary.dfia.total_value_usd, 2)}`} className="text-primary" />
              <StatCell label="Balance" value={`$ ${formatIndianNumber(summary.dfia.balance_value_usd, 2)}`} className="text-green-600" />
              <StatCell label="Purchase" value={fmt(summary.dfia.purchase_amount_inr)} className="text-yellow-600" />
              <StatCell
                label="P / L"
                value={`${summary.dfia.profit_loss_inr >= 0 ? '+' : ''}₹${formatIndianNumber(Math.abs(summary.dfia.profit_loss_inr), 0)}`}
                style={{ color: summary.dfia.profit_loss_inr >= 0 ? 'var(--tb-success)' : 'var(--tb-danger)' }}
              />
            </div>
          </div>

          {/* Incentive */}
          <div className="rounded-lg border border-border bg-card" style={{ borderLeft: '3px solid var(--tb-info)' }}>
            <div className="flex items-center gap-2 border-b border-border px-3 py-2">
              <Trophy className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="text-sm font-semibold">Incentive Licenses</span>
              <span className="ml-auto rounded px-2 py-0.5 text-[11px] font-bold text-white" style={{ background: 'var(--tb-info)' }}>
                {summary.incentive.total_licenses} active
              </span>
            </div>
            <div className="grid grid-cols-4 divide-x divide-border px-3 py-2 text-center">
              <StatCell label="Total Value" value={`₹${formatIndianNumber(summary.incentive.total_value_inr, 2)}`} className="text-primary" />
              <StatCell label="Balance" value={`₹${formatIndianNumber(summary.incentive.balance_value_inr, 2)}`} className="text-green-600" />
              <StatCell label="Purchase" value={fmt(summary.incentive.purchase_amount_inr)} className="text-yellow-600" />
              <StatCell
                label="P / L"
                value={`${summary.incentive.profit_loss_inr >= 0 ? '+' : ''}₹${formatIndianNumber(Math.abs(summary.incentive.profit_loss_inr), 0)}`}
                style={{ color: summary.incentive.profit_loss_inr >= 0 ? 'var(--tb-success)' : 'var(--tb-danger)' }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="mb-3 rounded-lg border border-border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3 py-2">
          <div className="flex items-center gap-2">
            <Filter className="size-4 text-muted-foreground" aria-hidden="true" />
            <h2 className="text-sm font-semibold">Filters &amp; Search</h2>
            {filters.company && (
              <span className="flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-semibold text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                <Building2 className="size-3 shrink-0" aria-hidden="true" />
                {filters.company.label}
              </span>
            )}
          </div>
          {filters.company && (
            <Button size="sm" variant="outline" onClick={() => handleFilterChange('company', null)}>
              <XCircle className="size-3.5" aria-hidden="true" />
              Clear Company
            </Button>
          )}
        </div>

        <div className="p-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-6">
            <div className="lg:col-span-2">
              <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">
                <Building2 className="mr-1 inline size-3.5" aria-hidden="true" />
                Company Filter
              </label>
              <CompanySelect
                value={filters.company}
                onChange={(v) => handleFilterChange('company', v)}
              />
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                Filter by trades with specific company
              </p>
            </div>

            <div className="lg:col-span-2">
              <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">
                License Type
              </label>
              <div className="flex flex-wrap gap-1">
                {LICENSE_TYPE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => handleFilterChange('license_type', opt.value)}
                    className={cn(
                      'cursor-pointer rounded-full border px-2.5 py-1 text-xs font-semibold transition-colors',
                      filters.license_type === opt.value
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border bg-card text-muted-foreground hover:bg-muted',
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label htmlFor="min-balance" className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">
                Min Balance
              </label>
              <Input
                id="min-balance"
                type="number"
                value={filters.min_balance}
                onChange={(e) => handleFilterChange('min_balance', e.target.value)}
                placeholder="0"
                step="100"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">
                Search
              </label>
              <DebouncedInput
                value={filters.search}
                onChange={(v) => handleFilterChange('search', v)}
                placeholder="License # or exporter..."
              />
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label htmlFor="sort-by" className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">
                Sort By
              </label>
              <select
                id="sort-by"
                className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                value={filters.ordering}
                onChange={(e) => handleFilterChange('ordering', e.target.value)}
              >
                <option value="-license_date">Latest First</option>
                <option value="license_date">Oldest First</option>
                <option value="-balance_value">Highest Balance</option>
                <option value="balance_value">Lowest Balance</option>
              </select>
            </div>
            <div className="flex items-end">
              <Toggle
                id="active-only"
                checked={filters.active_only}
                onCheckedChange={(v) => handleFilterChange('active_only', v)}
                label="Active Only"
              />
            </div>
          </div>

          {/* Purchase date range */}
          <div className="mt-3 border-t border-border/60 pt-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-[12px] font-semibold text-muted-foreground">
                <CalendarRange className="size-3.5 shrink-0" aria-hidden="true" />
                Purchase Date Range
                <span className="text-[11.5px] font-normal">(Defaults to current FY: Apr–Mar)</span>
              </div>
              <div className="flex gap-1">
                <Button size="sm" variant="outline" onClick={setCurrentFY}>
                  <CalendarCheck className="size-3.5" aria-hidden="true" />
                  Current FY
                </Button>
                <Button size="sm" variant="outline" onClick={setPreviousFY}>
                  <Calendar className="size-3.5" aria-hidden="true" />
                  Previous FY
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="text-destructive hover:bg-destructive/10"
                  onClick={clearDateFilter}
                  disabled={!filters.purchase_date_from && !filters.purchase_date_to}
                >
                  <XCircle className="size-3.5" aria-hidden="true" />
                  Clear
                </Button>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <label htmlFor="date-from" className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">
                  <CalendarCheck className="mr-1 inline size-3.5" aria-hidden="true" />
                  From Date
                </label>
                <Input
                  id="date-from"
                  type="date"
                  value={filters.purchase_date_from}
                  onChange={(e) => handleFilterChange('purchase_date_from', e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="date-to" className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">
                  <CalendarX className="mr-1 inline size-3.5" aria-hidden="true" />
                  To Date
                </label>
                <Input
                  id="date-to"
                  type="date"
                  value={filters.purchase_date_to}
                  onChange={(e) => handleFilterChange('purchase_date_to', e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* License-wise ledger table */}
      <div className="rounded-lg border border-border bg-card">
        {companyWiseLoading ? (
          <div className="flex flex-col items-center gap-2 py-10 text-center">
            <span
              className="inline-block size-8 animate-spin rounded-full border-2 border-primary border-t-transparent"
              aria-hidden="true"
            />
            <p className="text-sm text-muted-foreground">Loading license-wise ledger…</p>
          </div>
        ) : companyWiseData ? (
          <LicenseWiseLedger data={companyWiseData} navigate={navigate} />
        ) : (
          <div className="flex flex-col items-center gap-2 py-10 text-center">
            <Building2 className="size-8 text-muted-foreground" aria-hidden="true" />
            <p className="font-semibold text-foreground">No Data</p>
            <p className="text-sm text-muted-foreground">No trades found</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Small helper ───────────────────────────────────────────────────────────────

interface StatCellProps {
  label: string
  value: string | undefined
  className?: string
  style?: React.CSSProperties
}

function StatCell({ label, value, className, style }: StatCellProps) {
  return (
    <div className="py-2">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={cn('text-sm font-bold', className)} style={style}>{value ?? '—'}</div>
    </div>
  )
}

