// LicenseList — main license list page.
// Features: debounced search, filter panel, paginated table, skeleton loaders,
// near-expiry badges, "New License" button (role-gated to LICENSE_MANAGER).

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Loader2, Plus, Search } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Skeleton } from '@/shared/ui/skeleton'
import { cn } from '@/shared/utils/cn'
import { formatDate } from '@/shared/utils/formatters'
import { useDebounce } from '@/shared/hooks/useDebounce'
import { useAuth } from '@/shared/auth/AuthContext'
import { ROLES } from '@/shared/auth/roles'
import { useLicenses } from '../queries'
import { LicenseStatusBadge } from '../components/LicenseStatusBadge'
import { LicenseFilters } from '../components/LicenseFilters'
import {
  DEFAULT_FILTERS,
  filtersToParams,
  type LicenseFilterState,
} from '../components/licenseFilterConstants'
import { LicenseFormModal } from '../components/LicenseFormModal'

// ── Table skeleton ─────────────────────────────────────────────────────────────

function TableSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <Skeleton className="h-9 w-1/4" />
          <Skeleton className="h-9 w-1/6" />
          <Skeleton className="h-9 w-1/4" />
          <Skeleton className="h-9 w-1/6" />
          <Skeleton className="h-9 w-1/6" />
          <Skeleton className="h-9 w-20" />
        </div>
      ))}
    </div>
  )
}

// ── Pagination controls ───────────────────────────────────────────────────────

interface PaginationProps {
  page: number
  totalCount: number
  pageSize: number
  onPageChange: (page: number) => void
}

function Pagination({ page, totalCount, pageSize, onPageChange }: PaginationProps) {
  const totalPages = Math.ceil(totalCount / pageSize)
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center justify-between border-t px-4 py-3 text-sm">
      <span className="text-muted-foreground">
        Page {page} of {totalPages} ({totalCount} results)
      </span>
      <div className="flex gap-1">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
        >
          Next
        </Button>
      </div>
    </div>
  )
}

// ── License type chip ─────────────────────────────────────────────────────────

const TYPE_STYLES: Record<string, string> = {
  DFIA: 'bg-blue-500/10 text-blue-700 dark:text-blue-400',
  RODTEP: 'bg-violet-500/10 text-violet-700 dark:text-violet-400',
  ROSTL: 'bg-teal-500/10 text-teal-700 dark:text-teal-400',
  MEIS: 'bg-orange-500/10 text-orange-700 dark:text-orange-400',
  INCENTIVE: 'bg-pink-500/10 text-pink-700 dark:text-pink-400',
}

/** Derive the displayable license type from available fields.
 *  Priority: scheme_code_display → license_type → license_number prefix.
 */
function deriveLicenseType(lic: { scheme_code_display?: string | null; license_type?: string; license_number: string }): string | null {
  if (lic.scheme_code_display) return lic.scheme_code_display
  if (lic.license_type) return lic.license_type
  // Parse from license number prefix (e.g. "DFIA/2024/0001" → "DFIA")
  const m = lic.license_number.match(/^(DFIA|RODTEP|ROSTL|MEIS|INCENTIVE)/i)
  return m ? m[1].toUpperCase() : null
}

function LicenseTypePill({ type }: { type: string | null | undefined }) {
  if (!type) return <span className="text-muted-foreground">—</span>
  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5 text-xs font-semibold',
        TYPE_STYLES[type] ?? 'bg-muted text-muted-foreground',
      )}
    >
      {type}
    </span>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

const PAGE_SIZE = 25

export default function LicenseList() {
  const navigate = useNavigate()
  const { hasRole, isSuperAdmin } = useAuth()
  const canCreate = hasRole(ROLES.LICENSE_MANAGER) || isSuperAdmin()

  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 350)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<LicenseFilterState>(DEFAULT_FILTERS)
  const [formOpen, setFormOpen] = useState(false)

  // Reset to page 1 when any filter/search changes.
  function handleFiltersChange(next: LicenseFilterState) {
    setFilters(next)
    setPage(1)
  }

  function handleSearchChange(value: string) {
    setSearch(value)
    setPage(1)
  }

  const queryParams = {
    ...filtersToParams(filters),
    search: debouncedSearch || undefined,
    page,
    page_size: PAGE_SIZE,
  }

  const { data, isLoading, isFetching, isError } = useLicenses(queryParams)

  // After the envelope interceptor in client.ts, data is PaginatedResponse<License>:
  // { data: License[], pagination: { count, next, previous, page_size, total_pages } }
  const results = data?.data ?? []
  const totalCount = data?.pagination?.count ?? 0

  // Use the License type directly — useLicenses() already returns License[].
  // The list serializer returns a subset; optional fields will be undefined.
  const licenses = results

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Page header */}
      <div className="border-b bg-card px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <FileText className="size-5 text-muted-foreground" aria-hidden="true" />
            <div>
              <h1 className="text-lg font-semibold">Licenses</h1>
              <p className="text-sm text-muted-foreground">
                DFIA, RODTEP, ROSTL and Incentive licenses
              </p>
            </div>
          </div>
          {canCreate && (
            <Button onClick={() => setFormOpen(true)} size="sm">
              <Plus className="size-4" aria-hidden="true" />
              New License
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 space-y-4 p-6">
        {/* Search */}
        <div className="relative max-w-sm">
          <Search
            className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            placeholder="Search license number or exporter…"
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-9"
            aria-label="Search licenses"
          />
        </div>

        {/* Filters */}
        <LicenseFilters filters={filters} onChange={handleFiltersChange} />

        {/* Table */}
        <div className="rounded-lg border bg-card shadow-sm">
          {/* Table header */}
          <div className="flex items-center justify-between border-b px-4 py-2.5">
            <span className="text-sm text-muted-foreground">
              {isFetching && !isLoading && (
                <Loader2
                  className="mr-2 inline size-3.5 animate-spin"
                  aria-hidden="true"
                />
              )}
              {isLoading ? 'Loading…' : `${totalCount} license${totalCount !== 1 ? 's' : ''}`}
            </span>
          </div>

          {isError ? (
            <div className="px-4 py-8 text-center text-sm text-destructive">
              Failed to load licenses. Please try again.
            </div>
          ) : isLoading ? (
            <TableSkeleton />
          ) : licenses.length === 0 ? (
            <div className="px-4 py-12 text-center">
              <FileText
                className="mx-auto mb-3 size-10 text-muted-foreground opacity-40"
                aria-hidden="true"
              />
              <p className="text-sm text-muted-foreground">No licenses found.</p>
              {(search || filters.license_type !== 'ALL' || filters.company) && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Try clearing the filters.
                </p>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    {[
                      'License Number',
                      'Type',
                      'Company',
                      'Issue Date',
                      'Expiry Date',
                      'Balance CIF',
                      'Status',
                    ].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {licenses.map((lic, idx) => (
                    <tr
                      key={lic.id}
                      className={cn(
                        'cursor-pointer border-b transition-colors hover:bg-accent/40',
                        idx % 2 === 1 && 'bg-muted/20',
                      )}
                      onClick={() => navigate(`/licenses/${lic.id}`)}
                      tabIndex={0}
                      role="row"
                      aria-label={`View license ${lic.license_number}`}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          navigate(`/licenses/${lic.id}`)
                        }
                      }}
                    >
                      <td className="px-4 py-2.5 font-mono font-semibold">
                        {lic.license_number}
                      </td>
                      <td className="px-4 py-2.5">
                        <LicenseTypePill type={deriveLicenseType(lic)} />
                      </td>
                      <td className="max-w-[200px] truncate px-4 py-2.5 text-muted-foreground">
                        {lic.exporter_name ?? lic.company_label ?? '—'}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {formatDate(lic.license_date)}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {formatDate(lic.license_expiry_date)}
                      </td>
                      <td className="px-4 py-2.5 tabular-nums font-semibold text-emerald-700 dark:text-emerald-400">
                        {lic.balance_cif != null
                          ? parseFloat(lic.balance_cif).toFixed(2)
                          : '—'}
                      </td>
                      <td className="px-4 py-2.5">
                        <LicenseStatusBadge
                          isExpired={lic.is_expired ?? false}
                          expiryDate={lic.license_expiry_date ?? ''}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {!isLoading && !isError && (
            <Pagination
              page={page}
              totalCount={totalCount}
              pageSize={PAGE_SIZE}
              onPageChange={setPage}
            />
          )}
        </div>
      </div>

      {/* Create modal */}
      <LicenseFormModal open={formOpen} onOpenChange={setFormOpen} />
    </div>
  )
}
