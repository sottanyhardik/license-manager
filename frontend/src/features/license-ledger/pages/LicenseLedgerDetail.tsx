/**
 * LicenseLedgerDetail — tally-style ledger detail for a single license.
 *
 * Ported from legacy/frontend/src/pages/LicenseLedgerDetail.tsx.
 * All business logic preserved: company-grouped table, running balance,
 * per-transaction rows (OPENING/PURCHASE/SALE), P/L column, negative-balance
 * warning, DFIA vs Incentive column variance.
 *
 * Export: replaced client-side PDF/Excel generation with backend download links
 * (opened via window.open) since the legacy generatePDF/generateExcel utils
 * are not part of the new frontend. A toast notifies the user.
 */

import { useState, useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { toast } from 'sonner'
import { ArrowLeft, Building2, FileSpreadsheet, FileText, Loader2, TriangleAlert } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { formatDate } from '@/shared/utils/formatters'

// ── Types ──────────────────────────────────────────────────────────────────────

interface Transaction {
  type: 'OPENING' | 'PURCHASE' | 'SALE' | string
  company_id: number | null
  company_name: string | null
  date: string | null
  particular: string | null
  invoice_number: string | null
  items: string | null
  sion_norms: string | null
  debit_cif: number | null
  credit_cif: number | null
  debit_license_value: number | null
  credit_license_value: number | null
  rate: number | null
  debit_amount: number | null
  credit_amount: number | null
  profit_loss: number | null
}

interface LedgerDetail {
  license_number: string
  license_type: string
  license_date: string | null
  expiry_date: string | null
  exporter: string | null
  total_value: number | null
  available_balance: number | null
  transactions: Transaction[]
}

interface CompanyGroup {
  company_id: number | null
  company_name: string
  transactions: Transaction[]
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const TXN_SORT_ORDER: Record<string, number> = { OPENING: 0, PURCHASE: 1, SALE: 2 }

function formatIndianNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null || isNaN(value)) return '0'
  return new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

function formatCurrency(value: number | null | undefined, currency: 'INR' | 'USD' = 'INR'): string {
  if (value == null) return '—'
  const symbol = currency === 'USD' ? '$' : '₹'
  return `${symbol}${formatIndianNumber(value, 2)}`
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function LicenseLedgerDetail() {
  const { id, companyId } = useParams<{ id: string; companyId?: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const [ledger, setLedger] = useState<LedgerDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const queryParams = new URLSearchParams(location.search)
  // license_type from query-param or location.state (for navigation from list)
  const licenseTypeParam =
    queryParams.get('license_type') ||
    (location.state as { license_type?: string } | null)?.license_type ||
    'DFIA'

  useEffect(() => {
    if (!id) return
    let cancelled = false

    const fetchLedger = async () => {
      setLoading(true)
      setError(null)
      try {
        const params = new URLSearchParams()
        if (companyId) params.append('company', companyId)
        const qs = params.toString()
        const url = `${ENDPOINTS.LICENSE_LEDGER.LEDGER_DETAIL(id)}${qs ? `?${qs}` : ''}`
        const { data } = await apiClient.get<LedgerDetail>(url)
        if (!cancelled) setLedger(data)
      } catch (err: unknown) {
        if (!cancelled) {
          const msg =
            (err as { response?: { data?: { error?: string } } })?.response?.data?.error ??
            'Failed to load ledger details'
          setError(msg)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchLedger()
    return () => { cancelled = true }
  }, [id, companyId, licenseTypeParam])

  const handleDownload = (format: 'pdf' | 'excel') => {
    if (!id) return
    const params = new URLSearchParams({ format })
    if (companyId) params.append('company', companyId)
    const url = `${ENDPOINTS.LICENSE_LEDGER.LEDGER_DETAIL(id)}?${params.toString()}`
    toast.info('Preparing download…')
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  // ── Loading / error states ─────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-2">
        <Loader2 className="size-8 animate-spin text-primary" aria-hidden="true" />
        <span className="text-sm text-muted-foreground">Loading…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <div
          className="mb-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive"
          role="alert"
        >
          <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
          {error}
        </div>
        <Button onClick={() => navigate(-1)} variant="outline">
          <ArrowLeft className="size-4" aria-hidden="true" />
          Go Back
        </Button>
      </div>
    )
  }

  if (!ledger) return null

  // ── Data derivations ───────────────────────────────────────────────────────

  const isDFIA = ledger.license_type === 'DFIA'
  const currentBalance = ledger.available_balance ?? 0
  const isNegativeBalance = currentBalance < 0
  const hasPurchases = (ledger.transactions ?? []).some(
    (t) => t.type === 'PURCHASE' || t.type === 'OPENING',
  )
  const showWarning = !hasPurchases || isNegativeBalance

  // Group transactions by company
  const companiesMap = new Map<string | number, CompanyGroup>()
  for (const txn of ledger.transactions ?? []) {
    const key = txn.company_id ?? 'unknown'
    if (!companiesMap.has(key)) {
      companiesMap.set(key, {
        company_id: txn.company_id,
        company_name: txn.company_name ?? 'N/A',
        transactions: [],
      })
    }
    companiesMap.get(key)!.transactions.push(txn)
  }
  const companiesGrouped = Array.from(companiesMap.values())

  // Build SION norms list (DFIA only)
  const allNorms = isDFIA
    ? [
        ...new Set(
          (ledger.transactions ?? [])
            .filter((t) => t.sion_norms)
            .flatMap((t) => t.sion_norms!.split(', ')),
        ),
      ]
    : []

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--tb-sunken)' }}>
      {/* Tally-style header bar */}
      <div
        className="flex items-center justify-between px-5 py-2.5"
        style={{
          backgroundColor: 'var(--tb-text)',
          color: '#fff',
          borderBottom: '2px solid var(--tb-border-strong)',
        }}
      >
        <div className="flex items-center gap-3">
          <Button variant="secondary" size="sm" onClick={() => navigate(-1)}>
            <ArrowLeft className="size-4" aria-hidden="true" />
            Back
          </Button>
          <span className="text-[1.1rem] font-medium">License Ledger</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="destructive"
            size="sm"
            onClick={() => handleDownload('pdf')}
          >
            <FileText className="size-4" aria-hidden="true" />
            Download PDF
          </Button>
          <Button
            size="sm"
            onClick={() => handleDownload('excel')}
            style={{ background: 'var(--tb-success)', color: '#fff' }}
          >
            <FileSpreadsheet className="size-4" aria-hidden="true" />
            Download Excel
          </Button>
          <span className="ml-1 text-sm">{formatDate(new Date())}</span>
        </div>
      </div>

      {/* Warning alert */}
      {showWarning && (
        <div
          className="flex items-center gap-4 px-5 py-4"
          style={{
            backgroundColor: 'var(--warning-bg)',
            border: '1px solid var(--tb-warning)',
            borderLeft: '5px solid var(--tb-warning)',
          }}
          role="alert"
        >
          <TriangleAlert className="size-5 shrink-0" aria-hidden="true" style={{ color: 'var(--warning-text)' }} />
          <div>
            <strong className="block" style={{ color: 'var(--warning-text)', marginBottom: 4 }}>
              Action Required
            </strong>
            <span style={{ color: 'var(--warning-text)' }}>
              {!hasPurchases && isNegativeBalance &&
                'No purchase transactions found and balance is negative. Please add purchase entries to maintain proper accounting.'}
              {!hasPurchases && !isNegativeBalance &&
                'No purchase transactions found. Please add purchase entries for this license.'}
              {hasPurchases && isNegativeBalance &&
                `Balance is negative (${formatCurrency(currentBalance, isDFIA ? 'USD' : 'INR')}). Please add purchase transactions to cover the deficit.`}
            </span>
          </div>
        </div>
      )}

      {/* License summary header */}
      <div
        className="px-8 py-6"
        style={{
          backgroundColor: 'var(--tb-card-bg)',
          border: '1px solid var(--tb-border)',
          borderTop: 'none',
          boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
        }}
      >
        <div className="grid grid-cols-1 items-center gap-6 md:grid-cols-3">
          <div className="md:col-span-2">
            <h2 className="mb-4 flex items-center gap-3 text-xl font-semibold text-foreground">
              {ledger.license_number}
              <span
                className="rounded px-3 py-1 text-xs font-medium text-white"
                style={{
                  backgroundColor: isDFIA ? 'var(--primary-color)' : 'var(--info-color)',
                }}
              >
                {ledger.license_type}
              </span>
            </h2>
            <div className="grid grid-cols-2 gap-3 text-[15px]">
              <MetaRow label="Exporter" value={ledger.exporter ?? 'N/A'} />
              <MetaRow label="License Date" value={formatDate(ledger.license_date)} />
              {isDFIA && (
                <MetaRow
                  label="SION Norms"
                  value={allNorms.length > 0 ? allNorms.join(', ') : 'N/A'}
                  valueStyle={{ color: 'var(--info-color)' }}
                />
              )}
              <MetaRow label="Expiry Date" value={formatDate(ledger.expiry_date)} />
              <MetaRow
                label="Total Value"
                value={formatCurrency(ledger.total_value, isDFIA ? 'USD' : 'INR')}
                valueStyle={{ color: 'var(--primary-color)' }}
              />
            </div>
          </div>

          {/* Current balance box */}
          <div className="text-right">
            <div
              className="inline-block rounded-md px-5 py-5"
              style={{
                backgroundColor: 'var(--tb-sunken)',
                border: '2px solid var(--tb-border)',
              }}
            >
              <div className="mb-2 text-[13.5px] font-medium text-muted-foreground">CURRENT BALANCE</div>
              <div
                className="text-[1.75rem] font-bold"
                style={{
                  color: currentBalance >= 0 ? 'var(--success-color)' : 'var(--danger-color)',
                }}
              >
                {formatCurrency(currentBalance, isDFIA ? 'USD' : 'INR')}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Company-grouped ledger tables */}
      {companiesGrouped.map((company, ci) => {
        const rawTxns = company.transactions
        const txns = [...rawTxns].sort(
          (a, b) => (TXN_SORT_ORDER[a.type] ?? 1) - (TXN_SORT_ORDER[b.type] ?? 1),
        )

        // Per-company running balance
        let companyRunning = 0
        const companyBalMap = new Map<Transaction, number>()
        for (const txn of txns) {
          if (txn.type === 'PURCHASE' || txn.type === 'OPENING') {
            companyRunning += isDFIA ? (txn.debit_cif ?? 0) : (txn.debit_license_value ?? 0)
          } else if (txn.type === 'SALE') {
            companyRunning -= isDFIA ? (txn.credit_cif ?? 0) : (txn.credit_license_value ?? 0)
          }
          companyBalMap.set(txn, companyRunning)
        }

        const totalDebit = txns.reduce((s, t) => s + (t.debit_amount ?? 0), 0)
        const totalCredit = txns.reduce((s, t) => s + (t.credit_amount ?? 0), 0)
        const companyPL = totalCredit - totalDebit

        const isLast = ci === companiesGrouped.length - 1

        return (
          <div
            key={company.company_id ?? ci}
            className="overflow-hidden rounded-md"
            style={{
              backgroundColor: 'var(--tb-card-bg)',
              border: '1px solid var(--tb-border)',
              margin: ci === 0 ? '20px 20px 0' : '12px 20px 0',
              marginBottom: isLast ? 20 : 0,
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            }}
          >
            {/* Company header */}
            <div
              className="flex items-center gap-2 px-5 py-2.5 text-[15px] font-bold text-white"
              style={{ backgroundColor: 'var(--tb-brand-active)' }}
            >
              <Building2 className="size-4 shrink-0" aria-hidden="true" />
              {company.company_name}
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-[0.82rem]" style={{ borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--tb-brand-50)', borderBottom: '2px solid var(--tb-brand-100)' }}>
                    <Th>Date</Th>
                    <Th>Particulars</Th>
                    {isDFIA && <Th>Items</Th>}
                    {isDFIA ? (
                      <>
                        <Th align="right">CIF $ Dr</Th>
                        <Th align="right">CIF $ Cr</Th>
                      </>
                    ) : (
                      <>
                        <Th align="right">Value Dr</Th>
                        <Th align="right">Value Cr</Th>
                      </>
                    )}
                    <Th align="right">Rate</Th>
                    <Th align="right" style={{ color: 'var(--tb-success-text)' }}>Debit (₹)</Th>
                    <Th align="right" style={{ color: 'var(--tb-danger-text)' }}>Credit (₹)</Th>
                    <Th align="right">{isDFIA ? 'Balance ($)' : 'Balance (₹)'}</Th>
                    <Th align="right">P/L</Th>
                  </tr>
                </thead>
                <tbody>
                  {txns.map((txn, ti) => {
                    const isPurchase = txn.type === 'PURCHASE' || txn.type === 'OPENING'
                    const rowBg = isPurchase
                      ? 'var(--tb-success-soft)'
                      : txn.type === 'SALE'
                        ? 'var(--tb-danger-soft)'
                        : 'var(--tb-card-bg)'
                    const rowBorder = isPurchase
                      ? '1px solid var(--tb-success-border)'
                      : txn.type === 'SALE'
                        ? '1px solid var(--tb-danger-border)'
                        : '1px solid var(--tb-border-soft)'
                    const bal = companyBalMap.get(txn) ?? 0

                    return (
                      <tr key={ti} style={{ background: rowBg, borderBottom: rowBorder }}>
                        <Td style={{ whiteSpace: 'nowrap', color: 'var(--tb-text-secondary)' }}>
                          {formatDate(txn.date)}
                        </Td>
                        <Td style={{ color: 'var(--tb-text)' }}>
                          {txn.particular}
                          {txn.invoice_number && (
                            <span style={{ color: 'var(--tb-text-secondary)', fontSize: 12, display: 'block' }}>
                              ({txn.invoice_number})
                            </span>
                          )}
                        </Td>
                        {isDFIA && <Td style={{ color: 'var(--tb-text)' }}>{txn.items ?? '—'}</Td>}
                        {isDFIA ? (
                          <>
                            <Td align="right" style={{ color: 'var(--tb-success-text)' }}>
                              {txn.debit_cif ? formatIndianNumber(txn.debit_cif, 2) : '—'}
                            </Td>
                            <Td align="right" style={{ color: 'var(--tb-danger-text)' }}>
                              {txn.credit_cif ? formatIndianNumber(txn.credit_cif, 2) : '—'}
                            </Td>
                          </>
                        ) : (
                          <>
                            <Td align="right" style={{ color: 'var(--tb-success-text)' }}>
                              {txn.debit_license_value ? formatIndianNumber(txn.debit_license_value, 2) : '—'}
                            </Td>
                            <Td align="right" style={{ color: 'var(--tb-danger-text)' }}>
                              {txn.credit_license_value ? formatIndianNumber(txn.credit_license_value, 2) : '—'}
                            </Td>
                          </>
                        )}
                        <Td align="right" style={{ color: 'var(--tb-text)' }}>
                          {txn.rate ? formatIndianNumber(txn.rate, 2) : '—'}
                        </Td>
                        <Td align="right" style={{ fontWeight: 600, color: 'var(--tb-success-text)' }}>
                          {txn.debit_amount ? `₹${formatIndianNumber(txn.debit_amount, 2)}` : '—'}
                        </Td>
                        <Td align="right" style={{ fontWeight: 600, color: 'var(--tb-danger-text)' }}>
                          {txn.credit_amount ? `₹${formatIndianNumber(txn.credit_amount, 2)}` : '—'}
                        </Td>
                        <Td align="right" style={{ color: bal >= 0 ? 'var(--tb-success-text)' : 'var(--tb-danger-text)' }}>
                          {formatIndianNumber(bal, 2)}
                        </Td>
                        <Td align="right" style={{ color: (txn.profit_loss ?? 0) >= 0 ? 'var(--tb-success-text)' : 'var(--tb-danger-text)' }}>
                          {txn.type === 'SALE' && txn.profit_loss != null
                            ? formatIndianNumber(Math.abs(txn.profit_loss), 2)
                            : '—'}
                        </Td>
                      </tr>
                    )
                  })}

                  {/* Company total row */}
                  <tr style={{ background: 'var(--tb-brand-active)', color: '#fff', fontWeight: 700 }}>
                    <td
                      colSpan={isDFIA ? 6 : 5}
                      style={{ padding: '7px 10px', textAlign: 'right', fontSize: 12.5 }}
                    >
                      Total — {company.company_name}
                    </td>
                    <td style={{ padding: '7px 10px', textAlign: 'right', color: '#86efac' }}>
                      ₹{formatIndianNumber(totalDebit, 2)}
                    </td>
                    <td style={{ padding: '7px 10px', textAlign: 'right', color: '#fca5a5' }}>
                      ₹{formatIndianNumber(totalCredit, 2)}
                    </td>
                    <td style={{ padding: '7px 10px', textAlign: 'right', color: '#fff' }}>
                      {formatIndianNumber(companyRunning, 2)}
                    </td>
                    <td
                      style={{
                        padding: '7px 10px',
                        textAlign: 'right',
                        color: companyPL >= 0 ? '#86efac' : '#fca5a5',
                      }}
                    >
                      {companyPL !== 0
                        ? `${companyPL >= 0 ? '+' : ''}₹${formatIndianNumber(Math.abs(companyPL), 2)}`
                        : '—'}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Tiny table primitives ──────────────────────────────────────────────────────

function Th({
  children,
  align = 'left',
  style,
}: {
  children: React.ReactNode
  align?: 'left' | 'right'
  style?: React.CSSProperties
}) {
  return (
    <th
      style={{
        padding: '7px 10px',
        fontWeight: 700,
        color: 'var(--tb-text)',
        textAlign: align,
        ...style,
      }}
    >
      {children}
    </th>
  )
}

function Td({
  children,
  align = 'left',
  style,
}: {
  children: React.ReactNode
  align?: 'left' | 'right'
  style?: React.CSSProperties
}) {
  return (
    <td style={{ padding: '5px 10px', textAlign: align, ...style }}>
      {children}
    </td>
  )
}

function MetaRow({
  label,
  value,
  valueStyle,
}: {
  label: string
  value: string
  valueStyle?: React.CSSProperties
}) {
  return (
    <div>
      <span style={{ color: 'var(--tb-text-secondary)', marginRight: 10 }}>{label}:</span>
      <strong style={valueStyle}>{value}</strong>
    </div>
  )
}
