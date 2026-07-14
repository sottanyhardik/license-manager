// UtilisationChart — top-10 licenses by balance_cif as a horizontal bar chart.
// Uses Recharts BarChart wrapped in ResponsiveContainer.

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import type { UtilisationItem } from '../types'

interface Props {
  data: UtilisationItem[]
}

function formatUSDCompact(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`
  return `$${value}`
}

function tooltipFormatter(value: unknown): [string, string] {
  return [`$${Number(value).toLocaleString('en-US', { minimumFractionDigits: 2 })}`, 'Balance CIF']
}

export function UtilisationChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">
        No utilisation data available.
      </div>
    )
  }

  // Convert string decimals to numbers for Recharts
  const chartData = data.map((item) => ({
    license_number: item.license_number,
    balance_cif: parseFloat(item.balance_cif),
  }))

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={chartData} margin={{ top: 4, right: 12, left: 8, bottom: 4 }}>
        <XAxis
          dataKey="license_number"
          tick={{ fontSize: 11 }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tickFormatter={formatUSDCompact}
          tick={{ fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={52}
        />
        <Tooltip
          formatter={tooltipFormatter}
          contentStyle={{
            borderRadius: '8px',
            fontSize: '12px',
          }}
        />
        <Bar dataKey="balance_cif" radius={[4, 4, 0, 0]}>
          {chartData.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={entry.balance_cif > 100_000 ? '#f59e0b' : '#3b82f6'}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
