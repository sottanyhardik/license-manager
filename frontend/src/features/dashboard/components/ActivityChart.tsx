// ActivityChart — BOE + allotment counts per month over 12 months.
// Two lines: boe_count (blue) and allotment_count (green).

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import type { ActivityItem } from '../types'

interface Props {
  data: ActivityItem[]
}

export function ActivityChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">
        No activity data available.
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 4, right: 12, left: 0, bottom: 4 }}>
        <XAxis
          dataKey="month"
          tick={{ fontSize: 11 }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tick={{ fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
          width={32}
        />
        <Tooltip
          contentStyle={{
            borderRadius: '8px',
            fontSize: '12px',
          }}
        />
        <Legend
          wrapperStyle={{ fontSize: '12px' }}
          formatter={(value) =>
            value === 'boe_count' ? 'Bills of Entry' : 'Allotments'
          }
        />
        <Line
          type="monotone"
          dataKey="boe_count"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={{ r: 3 }}
          activeDot={{ r: 5 }}
        />
        <Line
          type="monotone"
          dataKey="allotment_count"
          stroke="#22c55e"
          strokeWidth={2}
          dot={{ r: 3 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
