import { useState } from 'react'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { cn } from '@/shared/utils/cn'
import { ReportGenerator } from '../components/ReportGenerator'
import { useGenerateItemReport } from '../mutations'
import type { ReportFormat, ItemReportParams } from '../types'

export default function ItemReport() {
  const [format, setFormat] = useState<ReportFormat>('json')
  const [minBalance, setMinBalance] = useState('')
  const [licenseStatus, setLicenseStatus] = useState<'active' | 'all'>('active')
  const generate = useGenerateItemReport()

  async function handleGenerate(): Promise<string> {
    const params: ItemReportParams = {
      filters: {
        license_status: licenseStatus,
        ...(minBalance !== '' && { min_balance: parseFloat(minBalance) }),
      },
      format,
    }
    const result = await generate.mutateAsync(params)
    return result.task_id
  }

  return (
    <div className="p-8">
      <ReportGenerator
        title="Item Report"
        description="Per-item utilisation across licenses."
        onGenerate={handleGenerate}
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="item-min-balance">Minimum Balance</Label>
            <Input
              id="item-min-balance"
              type="number"
              min="0"
              step="0.01"
              placeholder="e.g. 100"
              value={minBalance}
              onChange={(e) => setMinBalance(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">Leave blank to include all balances</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="item-license-status">License Status</Label>
            <select
              id="item-license-status"
              value={licenseStatus}
              onChange={(e) => setLicenseStatus(e.target.value as 'active' | 'all')}
              className={cn(
                'flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm',
                'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
              )}
            >
              <option value="active">Active only</option>
              <option value="all">All</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="item-format">Format</Label>
            <select
              id="item-format"
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
