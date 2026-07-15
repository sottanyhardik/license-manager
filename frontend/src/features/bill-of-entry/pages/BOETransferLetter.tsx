// BOETransferLetter — generate a transfer letter for a specific BOE.
//
// Per OQ-5: user selects a template, previews, then generates/downloads.
//
// The backend endpoint (POST /api/v1/bill-of-entries/{id}/generate-transfer-letter/)
// currently returns HTTP 501 while the transfer_letter utility is being ported
// from the legacy system. This page displays a clear notice and shows what the
// form will look like once the utility is available.

import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, FileDown, Info, Loader2, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { normaliseApiErrorString } from '@/shared/utils/errors'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Skeleton } from '@/shared/ui/skeleton'
import { useBOE } from '../queries'

// ── Transfer Letter form values ───────────────────────────────────────────────

interface TransferLetterFormValues {
  company_name: string
  address_line1: string
  address_line2: string
  template_id: string
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function BOETransferLetter() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const boeId = id ? parseInt(id, 10) : null
  const { data: boe, isLoading, isError } = useBOE(boeId)

  const [form, setForm] = useState<TransferLetterFormValues>({
    company_name: '',
    address_line1: '',
    address_line2: '',
    template_id: '1',
  })
  const [isGenerating, setIsGenerating] = useState(false)
  const [backendError, setBackendError] = useState<string | null>(null)
  const [isNotImplemented, setIsNotImplemented] = useState(false)

  // Pre-fill company name from BOE once loaded
  if (boe && !form.company_name && boe.company_name) {
    setForm((prev) => ({ ...prev, company_name: boe.company_name ?? '' }))
  }

  function handleChange(field: keyof TransferLetterFormValues) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }))
    }
  }

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault()
    if (!boeId) return

    setBackendError(null)
    setIsNotImplemented(false)
    setIsGenerating(true)

    try {
      const response = await apiClient.post(
        ENDPOINTS.BILL_OF_ENTRY.GENERATE_TRANSFER_LETTER(boeId),
        {
          company_name: form.company_name || undefined,
          address_line1: form.address_line1 || undefined,
          address_line2: form.address_line2 || undefined,
          template_id: parseInt(form.template_id, 10) || 1,
        },
        { responseType: 'blob', validateStatus: (s) => s < 600 },
      )

      // 501 means not yet implemented — show a friendly notice
      if (response.status === 501) {
        setIsNotImplemented(true)
        return
      }

      if (response.status >= 400) {
        const msg = normaliseApiErrorString(new Error(`HTTP ${response.status}`))
        setBackendError(msg)
        return
      }

      // Success — trigger file download
      const blob = new Blob([response.data as BlobPart], {
        type: 'application/pdf',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `transfer-letter-boe-${boeId}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('Transfer letter downloaded.')
    } catch (err) {
      const msg = normaliseApiErrorString(err)
      setBackendError(msg)
      toast.error(msg)
    } finally {
      setIsGenerating(false)
    }
  }

  // ── Guard: invalid id ────────────────────────────────────────────────────────

  if (!boeId || isNaN(boeId)) {
    return (
      <div className="p-6 text-center text-destructive">Invalid Bill of Entry ID.</div>
    )
  }

  // ── Loading / error states ────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full max-w-lg" />
      </div>
    )
  }

  if (isError || !boe) {
    return (
      <div className="p-6">
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
          Failed to load Bill of Entry.
        </div>
        <Button variant="outline" onClick={() => navigate(-1)}>
          <ArrowLeft className="size-4" aria-hidden="true" />
          Go Back
        </Button>
      </div>
    )
  }

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b bg-card px-6 py-4">
        <div className="mb-3 flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/boe/${boeId}`)}
            className="gap-1"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            Back to BOE
          </Button>
        </div>
        <h1 className="text-lg font-semibold">Generate Transfer Letter</h1>
        <p className="text-sm text-muted-foreground">
          BOE: <span className="font-mono font-semibold">{boe.bill_of_entry_number}</span>
          {boe.company_name && (
            <span className="ml-2 text-muted-foreground">— {boe.company_name}</span>
          )}
        </p>
      </div>

      <div className="p-6">
        {/* 501 Notice */}
        {isNotImplemented && (
          <div className="mb-6 flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700/50 dark:bg-amber-900/20 dark:text-amber-300">
            <Info className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-semibold">Transfer letter generation is not yet available</p>
              <p className="mt-0.5">
                The transfer letter utility is being ported from the legacy system. Until it is
                ready, please use the legacy application to generate transfer letters.
              </p>
            </div>
          </div>
        )}

        {/* General error */}
        {backendError && !isNotImplemented && (
          <div className="mb-6 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
            {backendError}
          </div>
        )}

        {/* Form */}
        <form
          onSubmit={(e) => void handleGenerate(e)}
          className="max-w-lg space-y-4"
          aria-label="Transfer letter form"
        >
          {/* Template selection */}
          <div className="space-y-1">
            <label htmlFor="template_id" className="text-sm font-medium">
              Template
            </label>
            <select
              id="template_id"
              value={form.template_id}
              onChange={handleChange('template_id')}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              aria-label="Transfer letter template"
            >
              <option value="1">Standard Template</option>
              <option value="2">Short Form Template</option>
              <option value="3">Custom Template</option>
            </select>
          </div>

          {/* Company name override */}
          <div className="space-y-1">
            <label htmlFor="company_name" className="text-sm font-medium">
              Company Name
              <span className="ml-1 text-xs font-normal text-muted-foreground">(optional — defaults to BOE company)</span>
            </label>
            <Input
              id="company_name"
              placeholder={boe.company_name ?? 'Company name'}
              value={form.company_name}
              onChange={handleChange('company_name')}
            />
          </div>

          {/* Address lines */}
          <div className="space-y-1">
            <label htmlFor="address_line1" className="text-sm font-medium">
              Address Line 1
            </label>
            <Input
              id="address_line1"
              placeholder="Street address"
              value={form.address_line1}
              onChange={handleChange('address_line1')}
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="address_line2" className="text-sm font-medium">
              Address Line 2
            </label>
            <Input
              id="address_line2"
              placeholder="City, State, PIN"
              value={form.address_line2}
              onChange={handleChange('address_line2')}
            />
          </div>

          {/* Submit */}
          <Button type="submit" disabled={isGenerating} className="w-full sm:w-auto">
            {isGenerating ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" />
                Generating…
              </>
            ) : (
              <>
                <FileDown className="mr-2 size-4" aria-hidden="true" />
                Generate &amp; Download
              </>
            )}
          </Button>
        </form>
      </div>
    </div>
  )
}
