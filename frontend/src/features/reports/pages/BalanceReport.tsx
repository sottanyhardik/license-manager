import { useState } from 'react'
import { Label } from '@/shared/ui/label'
import { cn } from '@/shared/utils/cn'
import { ReportGenerator } from '../components/ReportGenerator'
import { LicenseSelector } from '../components/LicenseSelector'
import { useGenerateBalanceReport } from '../mutations'
import type { ReportFormat } from '../types'

export default function BalanceReport() {
  const [licenseIds, setLicenseIds] = useState<number[]>([])
  const [format, setFormat] = useState<ReportFormat>('json')
  const generate = useGenerateBalanceReport()

  async function handleGenerate(): Promise<string> {
    const result = await generate.mutateAsync({ license_ids: licenseIds, format })
    return result.task_id
  }

  return (
    <div className="p-8">
      <ReportGenerator
        title="Balance Report"
        description="License balance summary across selected licenses."
        onGenerate={handleGenerate}
      >
        <LicenseSelector value={licenseIds} onChange={setLicenseIds} />

        <div className="space-y-1.5">
          <Label htmlFor="balance-format">Format</Label>
          <select
            id="balance-format"
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
      </ReportGenerator>
    </div>
  )
}
