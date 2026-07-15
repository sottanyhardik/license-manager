import { useState } from 'react'
import { toast } from 'sonner'
import {
  ScanBarcode,
  Filter,
  FileSpreadsheet,
  Loader2,
  Info,
  CircleCheck,
  TriangleAlert,
  CheckCircle2,
} from 'lucide-react'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Textarea } from '@/shared/ui/textarea'
import { Badge } from '@/shared/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active Licenses', Icon: CircleCheck, tone: 'success' },
  { value: 'expiring', label: 'Expiring Soon', Icon: TriangleAlert, tone: 'warning' },
] as const

const EXCEL_INCLUDES = [
  'License number, date, expiry, exporter',
  'BOE & Allotment summary per license',
  'Balance quantity per item (HSN, description)',
  'Restriction percentage and CIF values',
  'Unit price and CIF FC calculations',
  'Each license in its own named sheet',
]

interface LicenseListResponse {
  licenses: Array<{ license_number: string }>
}

export default function DownloadLicense() {
  const [licenseStatus, setLicenseStatus] = useState<'active' | 'expiring'>('active')
  const [days, setDays] = useState(365)
  const [loading, setLoading] = useState(false)
  const [bulkInput, setBulkInput] = useState('')
  const [bulkLoading, setBulkLoading] = useState(false)

  const handleDownload = async () => {
    setLoading(true)
    try {
      const url =
        licenseStatus === 'expiring'
          ? ENDPOINTS.LICENSES.EXPIRING_LICENSES_REPORT
          : ENDPOINTS.LICENSES.ACTIVE_LICENSES_REPORT
      const jsonResponse = await apiClient.get<LicenseListResponse>(url, {
        params: { days },
      })
      const licenseNumbers = jsonResponse.data.licenses.map((l) => l.license_number)
      if (licenseNumbers.length === 0) {
        toast.error('No licenses found for the selected criteria.')
        return
      }
      const response = await apiClient.post(
        ENDPOINTS.LICENSES.BULK_BALANCE_EXCEL,
        { license_numbers: licenseNumbers },
        { responseType: 'blob' },
      )
      const link = document.createElement('a')
      link.href = window.URL.createObjectURL(new Blob([response.data as BlobPart]))
      link.setAttribute('download', `licenses_${licenseStatus}_${days}days.xlsx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(link.href)
      toast.success(`Downloaded Excel for ${licenseNumbers.length} license(s)`)
    } catch (error: unknown) {
      const msg =
        (error as { response?: { data?: { error?: string } } })?.response?.data?.error ??
        'Failed to download. Please try again.'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleBulkDownload = async () => {
    const numbers = bulkInput
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean)
    if (numbers.length === 0) {
      toast.error('Please enter at least one license number.')
      return
    }
    setBulkLoading(true)
    try {
      const response = await apiClient.post(
        ENDPOINTS.LICENSES.BULK_BALANCE_EXCEL,
        { license_numbers: numbers },
        { responseType: 'blob' },
      )
      const link = document.createElement('a')
      link.href = window.URL.createObjectURL(new Blob([response.data as BlobPart]))
      link.setAttribute('download', `bulk_license_summary_${numbers.length}_licenses.xlsx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(link.href)
      toast.success(`Downloaded Excel for ${numbers.length} license(s)`)
    } catch (error: unknown) {
      const msg =
        (error as { response?: { data?: { error?: string } } })?.response?.data?.error ??
        'Failed to download. Please try again.'
      toast.error(msg)
    } finally {
      setBulkLoading(false)
    }
  }

  const parsedCount = bulkInput
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean).length

  return (
    <>
      <div className="mb-6">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Reports / Download License
        </p>
        <h1 className="text-2xl font-bold tracking-tight">Download License</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Export per-license balance summaries as Excel
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Bulk by numbers */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="flex items-center gap-2 text-sm">
              <ScanBarcode className="size-4 text-primary" />
              Download by License Numbers
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col pt-5">
            <p className="mb-3 text-[13px] text-muted-foreground">
              Enter DFIA license numbers separated by commas or new lines. Each license gets its own
              sheet.
            </p>
            <div className="mb-3 flex-1">
              <Label className="mb-1.5 flex items-center gap-2">
                License Numbers
                {parsedCount > 0 && <Badge>{parsedCount} entered</Badge>}
              </Label>
              <Textarea
                rows={5}
                className="font-mono"
                placeholder={'e.g. 3011007415, 3011007018, 3011008321\nor one per line'}
                value={bulkInput}
                onChange={(e) => setBulkInput(e.target.value)}
              />
              <p className="mt-1.5 text-[11.5px] text-muted-foreground">
                Comma- or newline-separated. Each license = one sheet named after the license
                number.
              </p>
            </div>
            <Button
              className="w-full"
              onClick={handleBulkDownload}
              disabled={bulkLoading || parsedCount === 0}
            >
              {bulkLoading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FileSpreadsheet className="size-4" />
              )}
              {bulkLoading
                ? 'Generating…'
                : `Download Excel (${parsedCount} license${parsedCount !== 1 ? 's' : ''})`}
            </Button>
          </CardContent>
        </Card>

        {/* By status */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Filter className="size-4 text-success" />
              Download by Status
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col pt-5">
            <p className="mb-3 text-[13px] text-muted-foreground">
              Export all active or expiring licenses filtered by date range.
            </p>

            <div className="mb-3">
              <Label className="mb-1.5">License Status</Label>
              <div className="flex flex-wrap gap-2">
                {STATUS_OPTIONS.map(({ value, label, Icon, tone }) => {
                  const active = licenseStatus === value
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setLicenseStatus(value)}
                      className={`flex min-w-[140px] flex-1 cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-[13px] font-medium transition-colors ${
                        active
                          ? tone === 'success'
                            ? 'border-success/40 bg-success/10 text-success'
                            : 'border-warning/40 bg-warning/10 text-warning'
                          : 'border-border text-muted-foreground hover:bg-accent/50'
                      }`}
                    >
                      <Icon className="size-4" />
                      {label}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="mb-4">
              <Label className="mb-1.5" htmlFor="days">
                {licenseStatus === 'expiring' ? 'Expiring within (days)' : 'Look-back period (days)'}
              </Label>
              <Input
                id="days"
                type="number"
                min="1"
                max="3650"
                value={days}
                onChange={(e) => setDays(parseInt(e.target.value) || 365)}
              />
              <p className="mt-1.5 text-[11.5px] text-muted-foreground">
                {licenseStatus === 'expiring'
                  ? `Licenses expiring within the next ${days} days`
                  : `Active licenses from ${days} days ago through future dates`}
              </p>
            </div>

            <Button className="mt-auto w-full" onClick={handleDownload} disabled={loading}>
              {loading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FileSpreadsheet className="size-4" />
              )}
              {loading ? 'Generating…' : 'Download Excel'}
            </Button>
          </CardContent>
        </Card>

        {/* Info */}
        <Card className="lg:col-span-2">
          <CardContent className="pt-5">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
              <Info className="size-4 text-primary" />
              Excel Report Includes
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {EXCEL_INCLUDES.map((f, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
                  <CheckCircle2 className="size-4 shrink-0 text-success" />
                  {f}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
