/**
 * IncentiveLicenseList — paginated card list of incentive licenses.
 *
 * Features:
 *   - Card per license with left-border color coding by sold status
 *   - Search (debounced 350ms), license_type filter, sold_status filter, is_active filter
 *   - Pagination (StandardPagination envelope: { count, next, previous, results })
 *   - Create → ROUTES.INCENTIVE_LICENSE_NEW
 *   - Edit   → ROUTES.INCENTIVE_LICENSE_EDIT(id)
 *   - Delete: managers only, Radix confirm dialog
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import * as Dialog from '@radix-ui/react-dialog'
import { toast } from 'sonner'
import { FileBadge, Pencil, Plus, Search, Trash2 } from 'lucide-react'

import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { useAuth } from '@/shared/auth/AuthContext'
import { ROLES, ROLE_GROUPS } from '@/shared/auth/roles'
import { ROUTES } from '@/shared/routes'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { cn } from '@/shared/utils/cn'

import type { IncentiveLicense, LicenseType, SoldStatus } from '../types'

// ── Helpers ────────────────────────────────────────────────────────────────────

function formatAmount(value: string): string {
  const n = Number(value)
  if (isNaN(n)) return value
  return n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return value
  }
}

function isExpired(value: string | null): boolean {
  if (!value) return false
  return new Date(value) < new Date()
}

/** Left border color based on sold_status */
function borderClass(status: SoldStatus): string {
  if (status === 'NO') return 'border-l-4 border-l-green-500'
  if (status === 'PARTIAL') return 'border-l-4 border-l-amber-500'
  return 'border-l-4 border-l-red-500'
}

/** Sold status badge variant */
function soldStatusBadge(status: SoldStatus) {
  if (status === 'NO') return { label: 'Available', variant: 'default' as const }
  if (status === 'PARTIAL') return { label: 'Partial', variant: 'secondary' as const }
  return { label: 'Sold', variant: 'destructive' as const }
}

/** License type badge */
function licenseTypeBadge(type: LicenseType) {
  const colors: Record<LicenseType, string> = {
    RODTEP: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200',
    ROSTL: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-200',
    MEIS: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200',
  }
  return colors[type] ?? ''
}

// ── Paginated response shape ───────────────────────────────────────────────────

interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function IncentiveLicenseList() {
  const navigate = useNavigate()
  const { hasAnyRole } = useAuth()
  const canWrite = hasAnyRole([ROLES.INCENTIVE_LICENSE_MANAGER])

  const [licenses, setLicenses] = useState<IncentiveLicense[]>([])
  const [count, setCount] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  // Filters
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [licenseTypeFilter, setLicenseTypeFilter] = useState('')
  const [soldStatusFilter, setSoldStatusFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState('')

  // Delete confirmation
  const [confirmDelete, setConfirmDelete] = useState<IncentiveLicense | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Debounce search
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1)
    }, 350)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [search])

  // Reset page when filters change
  useEffect(() => {
    setPage(1)
  }, [licenseTypeFilter, soldStatusFilter, activeFilter])

  const fetchLicenses = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = { page: String(page) }
      if (debouncedSearch) params.search = debouncedSearch
      if (licenseTypeFilter) params.license_type = licenseTypeFilter
      if (soldStatusFilter) params.sold_status = soldStatusFilter
      if (activeFilter) params.is_active = activeFilter

      const { data } = await apiClient.get<PaginatedResponse<IncentiveLicense> | IncentiveLicense[]>(
        ENDPOINTS.INCENTIVE_LICENSES.LIST,
        { params },
      )

      // Handle both paginated and plain array responses
      if (data && !Array.isArray(data) && 'results' in data) {
        setLicenses(data.results)
        setCount(data.count)
      } else if (Array.isArray(data)) {
        setLicenses(data)
        setCount(data.length)
      } else {
        setLicenses([])
        setCount(0)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load incentive licenses'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch, licenseTypeFilter, soldStatusFilter, activeFilter, page])

  useEffect(() => {
    void fetchLicenses()
  }, [fetchLicenses])

  const handleDelete = async () => {
    if (!confirmDelete) return
    setDeleting(true)
    try {
      await apiClient.delete(ENDPOINTS.INCENTIVE_LICENSES.DETAIL(confirmDelete.id))
      toast.success('Incentive license deleted')
      setConfirmDelete(null)
      void fetchLicenses()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete incentive license'
      toast.error(msg)
    } finally {
      setDeleting(false)
    }
  }

  const PAGE_SIZE = 20
  const totalPages = Math.ceil(count / PAGE_SIZE) || 1

  const selectClass = cn(
    'h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground',
    'focus:outline-none focus:ring-2 focus:ring-ring',
  )

  return (
    <>
      {/* Page header */}
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Incentives
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Incentive Licenses</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Manage RODTEP, ROSTL, and MEIS incentive licenses
          </p>
        </div>
        {canWrite && (
          <Button onClick={() => navigate(ROUTES.INCENTIVE_LICENSE_NEW)}>
            <Plus className="size-4" />
            Create
          </Button>
        )}
      </div>

      {/* Filters */}
      <Card className="mb-3">
        <CardContent className="flex flex-wrap items-center gap-2 py-3">
          <div className="relative min-w-[220px] flex-1">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="h-9 pl-8"
              placeholder="Search by license number…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            value={licenseTypeFilter}
            onChange={(e) => setLicenseTypeFilter(e.target.value)}
            className={selectClass}
          >
            <option value="">All Types</option>
            <option value="RODTEP">RODTEP</option>
            <option value="ROSTL">ROSTL</option>
            <option value="MEIS">MEIS</option>
          </select>
          <select
            value={soldStatusFilter}
            onChange={(e) => setSoldStatusFilter(e.target.value)}
            className={selectClass}
          >
            <option value="">All Statuses</option>
            <option value="NO">Available</option>
            <option value="PARTIAL">Partial</option>
            <option value="YES">Sold</option>
          </select>
          <select
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value)}
            className={selectClass}
          >
            <option value="">All Active</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </CardContent>
      </Card>

      {/* Card list */}
      {loading ? (
        <div className="p-8 text-center text-sm text-muted-foreground">Loading licenses…</div>
      ) : licenses.length === 0 ? (
        <div className="flex flex-col items-center gap-2 p-10 text-center text-muted-foreground">
          <FileBadge className="size-8 opacity-50" />
          <span className="text-sm">No incentive licenses found.</span>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {licenses.map((lic) => {
            const statusBadge = soldStatusBadge(lic.sold_status)
            const expired = isExpired(lic.license_expiry_date)
            const balNum = Number(lic.balance_value)
            const hasBalance = !isNaN(balNum) && balNum > 0

            return (
              <Card
                key={lic.id}
                className={cn('overflow-hidden transition-shadow hover:shadow-md', borderClass(lic.sold_status))}
              >
                <CardContent className="px-4 py-3">
                  {/* Header row */}
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-bold text-foreground">{lic.license_number}</span>

                    {/* License type badge */}
                    <span
                      className={cn(
                        'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold',
                        licenseTypeBadge(lic.license_type),
                      )}
                    >
                      {lic.license_type}
                    </span>

                    {/* Sold status badge */}
                    <Badge variant={statusBadge.variant} className="text-[11px]">
                      {statusBadge.label}
                    </Badge>

                    {/* Active/Inactive */}
                    {!lic.is_active && (
                      <Badge variant="secondary" className="text-[11px]">
                        Inactive
                      </Badge>
                    )}

                    {/* Issue date */}
                    {lic.license_date && (
                      <span className="rounded bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                        Issued: {formatDate(lic.license_date)}
                      </span>
                    )}

                    {/* Expiry date */}
                    {lic.license_expiry_date && (
                      <span
                        className={cn(
                          'rounded px-2 py-0.5 text-[11px]',
                          expired
                            ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                            : 'bg-muted text-muted-foreground',
                        )}
                      >
                        Expires: {formatDate(lic.license_expiry_date)}
                        {expired && ' (Expired)'}
                      </span>
                    )}

                    {/* Port */}
                    {lic.port_display && (
                      <span className="rounded bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                        {lic.port_display}
                      </span>
                    )}

                    {/* Exporter */}
                    {lic.exporter_name && (
                      <span className="rounded bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                        {lic.exporter_name}
                      </span>
                    )}
                  </div>

                  {/* Footer row */}
                  <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap gap-4 text-sm">
                      <span className="text-muted-foreground">
                        License Value:{' '}
                        <strong className="text-foreground">₹{formatAmount(lic.license_value)}</strong>
                      </span>
                      <span className="text-muted-foreground">
                        Sold:{' '}
                        <strong className="text-foreground">₹{formatAmount(lic.sold_value)}</strong>
                      </span>
                      <span className="text-muted-foreground">
                        Balance:{' '}
                        <strong
                          className={hasBalance ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'}
                        >
                          ₹{formatAmount(lic.balance_value)}
                        </strong>
                      </span>
                    </div>

                    {/* Actions */}
                    <div className="flex gap-1.5">
                      {canWrite && (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigate(ROUTES.INCENTIVE_LICENSE_EDIT(lic.id))}
                          >
                            <Pencil className="size-3.5" />
                            Edit
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-destructive hover:bg-destructive/10"
                            onClick={() => setConfirmDelete(lic)}
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {!loading && count > 0 && (
        <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Page {page} of {totalPages} &mdash; {count} total
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Delete confirmation — Radix Dialog */}
      <Dialog.Root open={!!confirmDelete} onOpenChange={(o) => !o && setConfirmDelete(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-background p-6 shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95">
            <Dialog.Title className="text-base font-semibold text-foreground">
              Delete Incentive License
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-muted-foreground">
              Are you sure you want to delete license{' '}
              <strong className="text-foreground">{confirmDelete?.license_number}</strong>? This
              cannot be undone.
            </Dialog.Description>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setConfirmDelete(null)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={deleting}
                onClick={() => void handleDelete()}
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  )
}
