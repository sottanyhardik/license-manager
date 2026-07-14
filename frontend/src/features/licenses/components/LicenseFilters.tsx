// LicenseFilters — filter panel for the license list page.
// Provides: license type chips, company selector, active-only toggle,
// expiry date range, and sort order.
// Non-component constants/helpers live in licenseFilterConstants.ts (fast-refresh compliance).

import { useState } from 'react'
import { Filter, X } from 'lucide-react'
import { cn } from '@/shared/utils/cn'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { MasterSelect } from '@/features/masters/components/MasterSelect'
import { useCompaniesAll } from '@/features/masters/queries'
import type { Company } from '@/features/masters/types'
import { DEFAULT_FILTERS, type LicenseFilterState } from './licenseFilterConstants'

const LICENSE_TYPES = [
  { value: 'ALL', label: 'All' },
  { value: 'DFIA', label: 'DFIA' },
  { value: 'RODTEP', label: 'RODTEP' },
  { value: 'ROSTL', label: 'ROSTL' },
  { value: 'MEIS', label: 'MEIS' },
  { value: 'INCENTIVE', label: 'Incentive' },
]

const SORT_OPTIONS = [
  { value: '-license_date', label: 'Latest First' },
  { value: 'license_date', label: 'Oldest First' },
  { value: 'license_expiry_date', label: 'Expiry Ascending' },
  { value: '-license_expiry_date', label: 'Expiry Descending' },
]

interface LicenseFiltersProps {
  filters: LicenseFilterState
  onChange: (filters: LicenseFilterState) => void
  className?: string
}

export function LicenseFilters({ filters, onChange, className }: LicenseFiltersProps) {
  const [open, setOpen] = useState(true)

  function set<K extends keyof LicenseFilterState>(key: K, value: LicenseFilterState[K]) {
    onChange({ ...filters, [key]: value })
  }

  function hasActiveFilters(): boolean {
    return (
      filters.license_type !== 'ALL' ||
      filters.company !== null ||
      !filters.active_only ||
      filters.expiry_after !== '' ||
      filters.expiry_before !== ''
    )
  }

  function resetFilters() {
    onChange(DEFAULT_FILTERS)
  }

  return (
    <div className={cn('rounded-lg border bg-card', className)}>
      {/* Panel header */}
      <div className="flex items-center justify-between border-b px-4 py-2.5">
        <button
          type="button"
          className="flex items-center gap-2 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded"
          onClick={() => setOpen((prev) => !prev)}
          aria-expanded={open}
        >
          <Filter className="size-4 text-muted-foreground" aria-hidden="true" />
          Filters
          {hasActiveFilters() && (
            <span className="ml-1 rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-bold text-primary-foreground">
              active
            </span>
          )}
        </button>
        {hasActiveFilters() && (
          <Button variant="ghost" size="sm" onClick={resetFilters} className="h-7 gap-1 text-xs">
            <X className="size-3" aria-hidden="true" />
            Reset
          </Button>
        )}
      </div>

      {open && (
        <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* License type chips */}
          <div className="sm:col-span-2 lg:col-span-2">
            <Label className="mb-2 block text-xs font-semibold text-muted-foreground">
              License Type
            </Label>
            <div className="flex flex-wrap gap-1.5">
              {LICENSE_TYPES.map((lt) => (
                <button
                  key={lt.value}
                  type="button"
                  onClick={() => set('license_type', lt.value)}
                  className={cn(
                    'rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors',
                    filters.license_type === lt.value
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border bg-card text-muted-foreground hover:bg-muted',
                  )}
                >
                  {lt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Company */}
          <div>
            <Label className="mb-2 block text-xs font-semibold text-muted-foreground">
              Company
            </Label>
            <MasterSelect<Company>
              queryHook={useCompaniesAll}
              value={filters.company}
              onChange={(id) => set('company', id)}
              getLabel={(c) => c.name}
              placeholder="All companies"
              aria-label="Filter by company"
            />
          </div>

          {/* Sort */}
          <div>
            <Label className="mb-2 block text-xs font-semibold text-muted-foreground">
              Sort By
            </Label>
            <select
              value={filters.ordering}
              onChange={(e) => set('ordering', e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          {/* Expiry from */}
          <div>
            <Label htmlFor="filter-expiry-after" className="mb-2 block text-xs font-semibold text-muted-foreground">
              Expiry From
            </Label>
            <Input
              id="filter-expiry-after"
              type="date"
              value={filters.expiry_after}
              onChange={(e) => set('expiry_after', e.target.value)}
            />
          </div>

          {/* Expiry to */}
          <div>
            <Label htmlFor="filter-expiry-before" className="mb-2 block text-xs font-semibold text-muted-foreground">
              Expiry To
            </Label>
            <Input
              id="filter-expiry-before"
              type="date"
              value={filters.expiry_before}
              onChange={(e) => set('expiry_before', e.target.value)}
            />
          </div>

          {/* Active only toggle */}
          <div className="flex items-end">
            <label className="flex cursor-pointer items-center gap-2 text-sm select-none">
              <input
                type="checkbox"
                checked={filters.active_only}
                onChange={(e) => set('active_only', e.target.checked)}
                className="size-4 rounded border border-input accent-primary"
              />
              <span className="text-xs font-semibold text-muted-foreground">Active only</span>
            </label>
          </div>
        </div>
      )}
    </div>
  )
}
