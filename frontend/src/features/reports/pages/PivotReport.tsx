import { useState } from 'react'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { cn } from '@/shared/utils/cn'
import { ReportGenerator } from '../components/ReportGenerator'
import { useGeneratePivotReport } from '../mutations'
import type { ReportFormat, PivotReportParams } from '../types'

export default function PivotReport() {
  const [format, setFormat] = useState<ReportFormat>('json')
  const [sionNorm, setSionNorm] = useState('')
  const [minBalance, setMinBalance] = useState('')
  const generate = useGeneratePivotReport()

  async function handleGenerate(): Promise<string> {
    const params: PivotReportParams = {
      filters: {
        ...(sionNorm.trim() !== '' && { sion_norm: sionNorm.trim() }),
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
        title="Pivot Report"
        description="Items grouped by SION norm class."
        onGenerate={handleGenerate}
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="pivot-sion-norm">SION Norm</Label>
            <Input
              id="pivot-sion-norm"
              type="text"
              placeholder="e.g. A-123"
              value={sionNorm}
              onChange={(e) => setSionNorm(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">Leave blank to include all SION norms</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="pivot-min-balance">Minimum Balance</Label>
            <Input
              id="pivot-min-balance"
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
            <Label htmlFor="pivot-format">Format</Label>
            <select
              id="pivot-format"
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
