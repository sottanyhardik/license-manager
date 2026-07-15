// BoeParsePanel — upload an ICEGATE BOE PDF and receive prefill data
// for the BOE create form.
//
// The backend endpoint returns:
//   parsed:               raw extracted fields from the PDF
//   prefill:              mapped form values (company_id, port_id, exchange_rate, …)
//   licences:             matched licence rows (matched_license_id, match_status, …)
//   matched_allotment_id: allotment matched by invoice number, or null
//
// The parent passes onParsed(result) and uses the data to prefill its form.

import { useRef, useState } from 'react'
import { FileText, Loader2, TriangleAlert, Upload, X } from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { normaliseApiErrorString } from '@/shared/utils/errors'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/utils/cn'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface BoeParsedLicenceRow {
  licence_number: string | null
  licence_slno: number | null
  licence_date: string | null
  uqc: string | null
  qty: string | null
  cif_inr: string | null
  cif_fc: string | null
  matched_license_id: number | null
  matched_license_number: string | null
  matched_item_id: number | null
  matched_item_description: string | null
  /** 'matched' | 'license_only' | 'license_missing' | 'no_data' */
  match_status: string
}

export interface BoeParsePrefill {
  company_id: number | null
  company_name: string | null
  company_created: boolean
  port_id: number | null
  port_code: string | null
  invoice: string | null
  exchange_rate: string | null
  item_name: string | null
  required_quantity: string | null
  cif_inr: string | null
  cif_fc: string | null
  is_boe: boolean
}

export interface BoeParsedResult {
  parsed: Record<string, unknown>
  prefill: BoeParsePrefill
  matched_allotment_id: number | null
  matched_company_id: number | null
  company_created: boolean
  matched_port_id: number | null
  licences: BoeParsedLicenceRow[]
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface BoeParsePanelProps {
  /** Called with the parsed result so the parent can prefill its form */
  onParsed: (result: BoeParsedResult) => void
  /** Optional CSS override on the outer container */
  className?: string
}

// ── Match status badge ────────────────────────────────────────────────────────

function MatchBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; className: string }> = {
    matched: { label: 'Matched', className: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' },
    license_only: { label: 'License only', className: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300' },
    license_missing: { label: 'Not found', className: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' },
    no_data: { label: 'No data', className: 'bg-muted text-muted-foreground' },
  }
  const badge = map[status] ?? map['no_data']
  return (
    <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', badge.className)}>
      {badge.label}
    </span>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function BoeParsePanel({ onParsed, className }: BoeParsePanelProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isParsing, setIsParsing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BoeParsedResult | null>(null)

  async function handleFile(file: File) {
    setError(null)
    setResult(null)
    setIsParsing(true)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const { data } = await apiClient.post<BoeParsedResult>(
        ENDPOINTS.BILL_OF_ENTRY.PARSE_PDF,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
      setResult(data)
      onParsed(data)
      toast.success('PDF parsed — form prefilled from BOE data.')
    } catch (err) {
      const msg = normaliseApiErrorString(err)
      setError(msg)
      toast.error(msg)
    } finally {
      setIsParsing(false)
    }
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) void handleFile(file)
    // reset so the same file can be re-uploaded
    e.target.value = ''
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file) void handleFile(file)
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
  }

  function handleClear() {
    setResult(null)
    setError(null)
  }

  // ── Upload zone ────────────────────────────────────────────────────────────

  return (
    <div className={cn('space-y-3', className)}>
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload BOE PDF to prefill form"
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors',
          'hover:border-primary/60 hover:bg-accent/30',
          isParsing && 'pointer-events-none opacity-60',
        )}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          className="sr-only"
          onChange={handleInputChange}
          aria-hidden="true"
        />

        {isParsing ? (
          <>
            <Loader2 className="mb-2 size-8 animate-spin text-primary" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">Parsing PDF…</p>
          </>
        ) : (
          <>
            <Upload className="mb-2 size-8 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm font-medium">Upload BOE PDF</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Drag and drop or click to select an ICEGATE BOE PDF
            </p>
          </>
        )}
      </div>

      {/* Error message */}
      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {/* Parsed result summary */}
      {result && (
        <div className="rounded-lg border bg-card p-4 text-sm">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2 font-medium">
              <FileText className="size-4 text-primary" aria-hidden="true" />
              Parsed successfully
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClear}
              aria-label="Clear parsed result"
            >
              <X className="size-4" aria-hidden="true" />
              Clear
            </Button>
          </div>

          {/* Key extracted fields */}
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-3">
            {result.parsed.be_number && (
              <>
                <dt className="text-muted-foreground">BOE Number</dt>
                <dd className="font-mono font-semibold sm:col-span-2">
                  {String(result.parsed.be_number)}
                </dd>
              </>
            )}
            {result.parsed.be_date && (
              <>
                <dt className="text-muted-foreground">BOE Date</dt>
                <dd className="sm:col-span-2">{String(result.parsed.be_date)}</dd>
              </>
            )}
            {result.prefill.company_name && (
              <>
                <dt className="text-muted-foreground">Company</dt>
                <dd className="sm:col-span-2">
                  {result.prefill.company_name}
                  {result.company_created && (
                    <span className="ml-1 text-xs text-amber-600">(created)</span>
                  )}
                </dd>
              </>
            )}
            {result.prefill.port_code && (
              <>
                <dt className="text-muted-foreground">Port</dt>
                <dd className="sm:col-span-2">{result.prefill.port_code}</dd>
              </>
            )}
            {result.prefill.exchange_rate && (
              <>
                <dt className="text-muted-foreground">Exchange Rate</dt>
                <dd className="font-mono sm:col-span-2">{result.prefill.exchange_rate}</dd>
              </>
            )}
            {result.prefill.invoice && (
              <>
                <dt className="text-muted-foreground">Invoice</dt>
                <dd className="font-mono sm:col-span-2">{result.prefill.invoice}</dd>
              </>
            )}
          </dl>

          {/* Licence rows table */}
          {result.licences.length > 0 && (
            <div className="mt-3">
              <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                Licence rows ({result.licences.length})
              </p>
              <div className="overflow-x-auto rounded border">
                <table className="w-full text-xs">
                  <thead className="border-b bg-muted/40">
                    <tr>
                      {['License No', 'Sl No', 'Qty', 'CIF INR', 'Status'].map((h) => (
                        <th
                          key={h}
                          className="px-3 py-1.5 text-left font-semibold text-muted-foreground"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.licences.map((row, idx) => (
                      <tr
                        key={idx}
                        className={cn('border-b last:border-0', idx % 2 === 1 && 'bg-muted/20')}
                      >
                        <td className="px-3 py-1.5 font-mono">
                          {row.matched_license_number ?? row.licence_number ?? '—'}
                        </td>
                        <td className="px-3 py-1.5">{row.licence_slno ?? '—'}</td>
                        <td className="px-3 py-1.5 tabular-nums">
                          {row.qty ? parseFloat(row.qty).toFixed(3) : '—'}
                        </td>
                        <td className="px-3 py-1.5 tabular-nums">
                          {row.cif_inr ? parseFloat(row.cif_inr).toFixed(2) : '—'}
                        </td>
                        <td className="px-3 py-1.5">
                          <MatchBadge status={row.match_status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result.matched_allotment_id && (
            <p className="mt-2 text-xs text-muted-foreground">
              Allotment matched by invoice:{' '}
              <span className="font-semibold text-foreground">#{result.matched_allotment_id}</span>
            </p>
          )}
        </div>
      )}
    </div>
  )
}
