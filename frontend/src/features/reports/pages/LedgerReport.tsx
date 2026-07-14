import { useState } from 'react'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { cn } from '@/shared/utils/cn'
import { ReportGenerator } from '../components/ReportGenerator'
import { useGenerateLedgerReport } from '../mutations'
import type { ReportFormat } from '../types'

export default function LedgerReport() {
  const [licenseId, setLicenseId] = useState('')
  const [format, setFormat] = useState<ReportFormat>('json')
  const generate = useGenerateLedgerReport()

  async function handleGenerate(): Promise<string> {
    const result = await generate.mutateAsync({
      license_id: parseInt(licenseId, 10),
      format,
    })
    return result.task_id
  }

  return (
    <div className="p-8">
      <ReportGenerator
        title="Ledger Report"
        description="License transaction ledger."
        onGenerate={handleGenerate}
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="ledger-license-id">License ID</Label>
            <Input
              id="ledger-license-id"
              type="number"
              min="1"
              step="1"
              placeholder="e.g. 42"
              value={licenseId}
              onChange={(e) => setLicenseId(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ledger-format">Format</Label>
            <select
              id="ledger-format"
              value={format}
              onChange={(e) => setFormat(e.target.value as ReportFormat)}
              className={cn(
                'flex h-9 w-40 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm',
                'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
              )}
            >
              <option value="json">JSON</option>
              <option value="excel">Excel</option>
              <option value="pdf">PDF</option>
            </select>
          </div>
        </div>
      </ReportGenerator>
    </div>
  )
}
