import { useState } from 'react'
import { toast } from 'sonner'
import { Download, Loader2, CheckCircle2 } from 'lucide-react'
import apiClient from '@/shared/api/client'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'

interface LicenseExportPanelProps {
  title: string
  description?: string
  daysLabel: string
  helpText: (days: number) => string
  endpoint: string
  filename: (days: number) => string
  features?: string[]
  defaultDays?: number
}

export function LicenseExportPanel({
  title,
  description,
  daysLabel,
  helpText,
  endpoint,
  filename,
  features = [],
  defaultDays = 30,
}: LicenseExportPanelProps) {
  const [days, setDays] = useState(defaultDays)
  const [loading, setLoading] = useState(false)

  const handleExport = async () => {
    setLoading(true)
    try {
      const response = await apiClient.get(endpoint, {
        params: { format: 'excel', days },
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data as BlobPart]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', filename(days))
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      toast.success('Report downloaded successfully.')
    } catch (error: unknown) {
      const msg =
        (error as { response?: { data?: { error?: string } } })?.response?.data?.error ??
        'Failed to download report. Please try again.'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="mb-6">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Reports</p>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-sm">Export Settings</CardTitle>
          </CardHeader>
          <CardContent className="pt-5">
            <div className="mb-4">
              <Label className="mb-1.5" htmlFor="days">
                {daysLabel}
              </Label>
              <Input
                id="days"
                type="number"
                min="1"
                max="365"
                value={days}
                onChange={(e) => setDays(parseInt(e.target.value) || defaultDays)}
              />
              <p className="mt-1.5 text-[11.5px] text-muted-foreground">{helpText(days)}</p>
            </div>
            <Button onClick={handleExport} disabled={loading}>
              {loading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Download className="size-4" />
              )}
              {loading ? 'Generating…' : 'Download Excel Report'}
            </Button>
          </CardContent>
        </Card>

        {features.length > 0 && (
          <Card>
            <CardHeader className="border-b">
              <CardTitle className="text-sm">Report Features</CardTitle>
            </CardHeader>
            <CardContent className="pt-5">
              <ul className="flex flex-col gap-2.5">
                {features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-[13px] text-foreground">
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
                    {f}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
