// ActivityLog — paginated activity log for admin users.
// Ported from legacy/frontend/src/pages/admin/ActivityLog.tsx.
//
// Differences from legacy:
//   - Uses apiClient (authenticated) instead of raw axios.
//   - Fully typed with TypeScript.
//   - Pagination added (server-side, 50 per page).
//   - TanStack Query for data fetching + automatic refetch on filter change.
//   - Sonner toasts on error.

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Download,
  Eye,
  FileDown,
  FileX,
  LogIn,
  LogOut,
  Pencil,
  PlusCircle,
  RefreshCw,
  ScrollText,
  Search,
  Trash2,
  Upload,
} from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Card, CardContent } from '@/shared/ui/card'
import { Skeleton } from '@/shared/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/ui/select'
import { cn } from '@/shared/utils/cn'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { normaliseApiErrorString } from '@/shared/utils/errors'
import { useAuth } from '@/shared/auth/AuthContext'

// ─── Types ────────────────────────────────────────────────────────────────────

type ActionType =
  | 'LOGIN'
  | 'LOGOUT'
  | 'VIEW'
  | 'CREATE'
  | 'UPDATE'
  | 'DELETE'
  | 'DOWNLOAD'
  | 'UPLOAD'
  | 'EXPORT'
  | 'SEARCH'

interface ActivityLogEntry {
  id: number
  timestamp: string
  username?: string | null
  action: ActionType
  module?: string | null
  resource_id?: number | null
  description?: string | null
  endpoint?: string | null
  status_code?: number | null
  ip_address?: string | null
}

interface PaginatedLogs {
  count: number
  results: ActivityLogEntry[]
}

interface LogFilters {
  username: string
  action: string
  module: string
  date_from: string
  date_to: string
  search: string
}

// ─── Constants ────────────────────────────────────────────────────────────────

type ActionMeta = {
  bg: string
  color: string
  Icon: React.ElementType
}

const ACTION_META: Record<string, ActionMeta> = {
  LOGIN:    { bg: 'var(--tb-success-soft,  #dcfce7)', color: 'var(--tb-success-text,  #166534)', Icon: LogIn },
  LOGOUT:   { bg: 'var(--tb-danger-soft,   #fee2e2)', color: 'var(--tb-danger-text,   #991b1b)', Icon: LogOut },
  VIEW:     { bg: 'var(--tb-info-soft,     #dbeafe)', color: 'var(--tb-info-text,     #1e40af)', Icon: Eye },
  CREATE:   { bg: 'var(--tb-success-soft,  #dcfce7)', color: 'var(--tb-success-text,  #166534)', Icon: PlusCircle },
  UPDATE:   { bg: 'var(--tb-warning-soft,  #fef9c3)', color: 'var(--tb-warning-text,  #854d0e)', Icon: Pencil },
  DELETE:   { bg: 'var(--tb-danger-soft,   #fee2e2)', color: 'var(--tb-danger-text,   #991b1b)', Icon: Trash2 },
  DOWNLOAD: { bg: 'var(--muted)',                     color: 'var(--muted-foreground)', Icon: Download },
  UPLOAD:   { bg: 'var(--muted)',                     color: 'var(--muted-foreground)', Icon: Upload },
  EXPORT:   { bg: 'var(--tb-success-soft,  #dcfce7)', color: 'var(--tb-success-text,  #166534)', Icon: FileDown },
  SEARCH:   { bg: 'var(--muted)',                     color: 'var(--muted-foreground)', Icon: Search },
}

const ACTIONS: ActionType[] = [
  'LOGIN', 'LOGOUT', 'VIEW', 'CREATE', 'UPDATE', 'DELETE', 'DOWNLOAD', 'UPLOAD', 'EXPORT', 'SEARCH',
]

const PAGE_SIZE = 50
const ALL_VALUE = '__all__'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(ts: string | null | undefined): string {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function TableSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <Skeleton className="h-8 w-1/6" />
          <Skeleton className="h-8 w-1/8" />
          <Skeleton className="h-8 w-1/8" />
          <Skeleton className="h-8 w-1/6" />
          <Skeleton className="h-8 flex-1" />
        </div>
      ))}
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function ActivityLog() {
  const { user } = useAuth()
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<LogFilters>({
    username: '',
    action: '',
    module: '',
    date_from: '',
    date_to: '',
    search: '',
  })

  function handleFilter<K extends keyof LogFilters>(key: K, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }))
    setPage(1)
  }

  function clearFilters() {
    setFilters({ username: '', action: '', module: '', date_from: '', date_to: '', search: '' })
    setPage(1)
  }

  const queryKey = ['activity-logs', filters, page]

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey,
    queryFn: async () => {
      const params: Record<string, string | number> = { page, limit: PAGE_SIZE }
      if (filters.username) params.username = filters.username
      if (filters.action)   params.action   = filters.action
      if (filters.module)   params.module   = filters.module
      if (filters.date_from) params.date_from = filters.date_from
      if (filters.date_to)   params.date_to   = filters.date_to
      if (filters.search)    params.search    = filters.search

      const { data: res } = await apiClient.get<PaginatedLogs | ActivityLogEntry[]>(
        ENDPOINTS.MASTERS.ACTIVITY_LOGS,
        { params },
      )
      // Backend may return paginated or plain array
      if (Array.isArray(res)) return { count: res.length, results: res }
      return res
    },
    staleTime: 30_000,
  })

  // Report fetch errors as toasts only once per new error object
  if (isError && error) {
    toast.error(normaliseApiErrorString(error))
  }

  const logs = data?.results ?? []
  const totalCount = data?.count ?? 0
  const totalPages = Math.ceil(totalCount / PAGE_SIZE)

  // Stat chips: only show actions present in current result page
  const presentActions = ACTIONS.filter((a) => logs.some((l) => l.action === a))

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Page header */}
      <div className="border-b bg-card px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <ScrollText className="size-5 text-muted-foreground" aria-hidden="true" />
            <div>
              <h1 className="text-lg font-semibold">Activity Log</h1>
              <p className="text-sm text-muted-foreground">
                {user?.is_superuser
                  ? 'All user actions across the system'
                  : 'Your recent activity'}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void refetch()}
            disabled={isLoading || isFetching}
          >
            <RefreshCw
              className={cn('size-4', (isLoading || isFetching) && 'animate-spin')}
              aria-hidden="true"
            />
            Refresh
          </Button>
        </div>
      </div>

      <div className="flex-1 space-y-4 p-6">
        {/* Filters */}
        <Card>
          <CardContent className="grid grid-cols-2 gap-3 py-3 md:grid-cols-3 lg:grid-cols-6">
            {user?.is_superuser && (
              <div>
                <Label className="mb-1 block text-xs" htmlFor="f-user">Username</Label>
                <Input
                  id="f-user"
                  className="h-8"
                  placeholder="Search user…"
                  value={filters.username}
                  onChange={(e) => handleFilter('username', e.target.value)}
                />
              </div>
            )}
            <div>
              <Label className="mb-1 block text-xs">Action</Label>
              <Select
                value={filters.action || ALL_VALUE}
                onValueChange={(v) => handleFilter('action', v === ALL_VALUE ? '' : v)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="All Actions" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL_VALUE}>All Actions</SelectItem>
                  {ACTIONS.map((a) => (
                    <SelectItem key={a} value={a}>{a}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-1 block text-xs" htmlFor="f-module">Module</Label>
              <Input
                id="f-module"
                className="h-8"
                placeholder="e.g. licenses"
                value={filters.module}
                onChange={(e) => handleFilter('module', e.target.value)}
              />
            </div>
            <div>
              <Label className="mb-1 block text-xs" htmlFor="f-from">From</Label>
              <Input
                id="f-from"
                type="date"
                className="h-8"
                value={filters.date_from}
                onChange={(e) => handleFilter('date_from', e.target.value)}
              />
            </div>
            <div>
              <Label className="mb-1 block text-xs" htmlFor="f-to">To</Label>
              <Input
                id="f-to"
                type="date"
                className="h-8"
                value={filters.date_to}
                onChange={(e) => handleFilter('date_to', e.target.value)}
              />
            </div>
            <div>
              <Label className="mb-1 block text-xs" htmlFor="f-search">Search</Label>
              <Input
                id="f-search"
                className="h-8"
                placeholder="IP, description…"
                value={filters.search}
                onChange={(e) => handleFilter('search', e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        {/* Action summary chips — shown when there are results */}
        {!isLoading && logs.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {presentActions.map((a) => {
              const m = ACTION_META[a]
              const count = logs.filter((l) => l.action === a).length
              const Icon = m?.Icon ?? ScrollText
              return (
                <button
                  key={a}
                  type="button"
                  onClick={() => handleFilter('action', filters.action === a ? '' : a)}
                  className="inline-flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-opacity hover:opacity-80"
                  style={{ background: m?.bg, color: m?.color }}
                  aria-pressed={filters.action === a}
                >
                  <Icon className="size-3.5" aria-hidden="true" />
                  {a} <strong>{count}</strong>
                </button>
              )
            })}
            {(filters.action || filters.username || filters.module || filters.search || filters.date_from || filters.date_to) && (
              <button
                type="button"
                className="ml-auto cursor-pointer text-xs text-muted-foreground hover:text-foreground"
                onClick={clearFilters}
              >
                Clear filters
              </button>
            )}
          </div>
        )}

        {/* Table */}
        <div className="rounded-lg border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b px-4 py-2.5">
            <span className="text-sm text-muted-foreground">
              {isFetching && !isLoading && (
                <RefreshCw className="mr-2 inline size-3.5 animate-spin" aria-hidden="true" />
              )}
              {isLoading ? 'Loading…' : `${totalCount} record${totalCount !== 1 ? 's' : ''}`}
            </span>
          </div>

          {isError ? (
            <div className="px-4 py-8 text-center text-sm text-destructive">
              Failed to load activity log. Please try again.
            </div>
          ) : isLoading ? (
            <TableSkeleton />
          ) : logs.length === 0 ? (
            <div className="flex flex-col items-center gap-2 p-12 text-center text-muted-foreground">
              <FileX className="size-8 opacity-50" aria-hidden="true" />
              <span>No activity records found</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground" style={{ width: 170 }}>
                      Time
                    </th>
                    {user?.is_superuser && (
                      <th className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground">
                        User
                      </th>
                    )}
                    <th className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground" style={{ width: 120 }}>
                      Action
                    </th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground">
                      Module
                    </th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground">
                      Description
                    </th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground" style={{ width: 70 }}>
                      Status
                    </th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground" style={{ width: 130 }}>
                      IP
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => {
                    const m = ACTION_META[log.action] ?? {
                      bg: 'var(--muted)',
                      color: 'var(--muted-foreground)',
                      Icon: ScrollText,
                    }
                    const Icon = m.Icon
                    const isErrRow = log.status_code != null && log.status_code >= 400
                    return (
                      <tr
                        key={log.id}
                        className="border-b border-border/60 transition-colors"
                        style={isErrRow ? { background: 'var(--tb-danger-soft, #fee2e2)' } : undefined}
                      >
                        <td className="whitespace-nowrap px-3 py-2 text-xs text-muted-foreground">
                          {fmtDate(log.timestamp)}
                        </td>
                        {user?.is_superuser && (
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-2">
                              <div
                                className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground"
                              >
                                {(log.username ?? '?')[0].toUpperCase()}
                              </div>
                              <span className="text-[13px] font-medium">
                                {log.username ?? '—'}
                              </span>
                            </div>
                          </td>
                        )}
                        <td className="px-3 py-2">
                          <span
                            className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium"
                            style={{ background: m.bg, color: m.color }}
                          >
                            <Icon className="size-3" aria-hidden="true" />
                            {log.action}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-xs text-muted-foreground">
                          {log.module ?? '—'}
                          {log.resource_id != null && (
                            <span className="ml-1 text-muted-foreground/70">
                              #{log.resource_id}
                            </span>
                          )}
                        </td>
                        <td className="max-w-[300px] px-3 py-2 text-xs">
                          <span
                            className="block truncate"
                            title={log.description ?? log.endpoint ?? undefined}
                          >
                            {log.description ?? log.endpoint ?? '—'}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          {log.status_code != null ? (
                            <span
                              className={cn(
                                'rounded px-1.5 py-0.5 text-[10.5px] font-medium',
                                isErrRow
                                  ? 'bg-destructive/15 text-destructive'
                                  : 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400',
                              )}
                            >
                              {log.status_code}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="px-3 py-2 text-xs text-muted-foreground">
                          {log.ip_address ?? '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Footer: count + pagination */}
          {!isLoading && !isError && logs.length > 0 && (
            <div className="flex items-center justify-between border-t border-border/60 px-4 py-2.5 text-xs text-muted-foreground">
              <span>
                Showing {logs.length} of {totalCount} records
              </span>
              {totalPages > 1 && (
                <div className="flex gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p - 1)}
                    disabled={page <= 1}
                  >
                    Previous
                  </Button>
                  <span className="flex items-center px-2">
                    {page} / {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={page >= totalPages}
                  >
                    Next
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ActivityLog
