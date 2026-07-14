// DashboardSkeleton — loading state rendered while any dashboard query is pending.
// Mirrors the exact layout of the real Dashboard page so there is no layout shift
// when data arrives.

import { Skeleton } from '@/shared/ui/skeleton'

function StatCardSkeleton() {
  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-7 w-16" />
        </div>
        <Skeleton className="h-10 w-10 rounded-lg" />
      </div>
    </div>
  )
}

function ChartSkeleton({ title }: { title: string }) {
  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <Skeleton className="mb-4 h-5 w-36" />
      <div className="space-y-2">
        <Skeleton className="h-[260px] w-full rounded-lg" />
      </div>
      <p className="sr-only">{title} chart loading</p>
    </div>
  )
}

function TableSkeleton() {
  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <Skeleton className="mb-4 h-5 w-48" />
      <div className="space-y-3">
        <div className="grid grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-4" />
          ))}
        </div>
        {Array.from({ length: 5 }).map((_, row) => (
          <div key={row} className="grid grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, col) => (
              <Skeleton key={col} className="h-4" />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-6 p-6">
      {/* Page header */}
      <div className="space-y-1">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-8 w-40" />
      </div>

      {/* Row 1 — 3 stat cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <StatCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
      </div>

      {/* Row 2 — 3 stat cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <StatCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
      </div>

      {/* Row 3 — 2 charts */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ChartSkeleton title="License Utilisation" />
        <ChartSkeleton title="Monthly Activity" />
      </div>

      {/* Row 4 — expiring licenses table */}
      <TableSkeleton />
    </div>
  )
}
