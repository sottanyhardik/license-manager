// Dashboard page — main KPI overview at /dashboard.
// Shows stat cards, a utilisation bar chart, an activity line chart,
// and a table of licenses expiring soon.

import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Hourglass,
  Network,
  ReceiptText,
  RefreshCw,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { StatCard } from '../components/StatCard'
import { DashboardSkeleton } from '../components/DashboardSkeleton'
import { UtilisationChart } from '../components/UtilisationChart'
import { ActivityChart } from '../components/ActivityChart'
import { ExpiringLicensesTable } from '../components/ExpiringLicensesTable'
import {
  useDashboardStats,
  useUtilisationChart,
  useActivityChart,
  useExpiringLicenses,
} from '../queries'

// ─── Page header ───────────────────────────────────────────────────────────────

interface PageHeaderProps {
  actions?: React.ReactNode
}

function PageHeader({ actions }: PageHeaderProps) {
  const today = new Date().toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })

  return (
    <div className="mb-6">
      <p className="text-sm text-muted-foreground">Overview — {today}</p>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        {actions && <div className="flex gap-2">{actions}</div>}
      </div>
    </div>
  )
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const queryClient = useQueryClient()

  const statsQuery = useDashboardStats()
  const utilisationQuery = useUtilisationChart()
  const activityQuery = useActivityChart()
  const expiringQuery = useExpiringLicenses()

  const isLoading =
    statsQuery.isLoading ||
    utilisationQuery.isLoading ||
    activityQuery.isLoading ||
    expiringQuery.isLoading

  if (isLoading) {
    return <DashboardSkeleton />
  }

  const stats = statsQuery.data
  const utilisationData = utilisationQuery.data ?? []
  const activityData = activityQuery.data ?? []
  const expiringData = expiringQuery.data ?? []

  function handleRefresh() {
    void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
  }

  const totalBalanceFormatted = stats
    ? `$${parseFloat(stats.total_balance_cif).toLocaleString('en-US', { minimumFractionDigits: 2 })}`
    : '—'

  return (
    <div className="p-6">
      <PageHeader
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            className="gap-1.5"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />

      {/* Row 1 — primary license KPIs */}
      <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-3">
        <StatCard
          label="Total Licenses"
          value={stats?.total_licenses ?? '—'}
          icon={FileText}
        />
        <StatCard
          label="Active Licenses"
          value={stats?.active_licenses ?? '—'}
          icon={CheckCircle2}
        />
        <StatCard
          label="Expired Licenses"
          value={stats?.expired_licenses ?? '—'}
          icon={AlertTriangle}
          variant="danger"
        />
      </div>

      {/* Row 2 — secondary KPIs */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-3">
        <StatCard
          label="Expiring Soon"
          value={stats?.expiring_soon ?? '—'}
          icon={Hourglass}
          variant="warning"
        />
        <StatCard
          label="Recent BOEs"
          value={stats?.recent_boes ?? '—'}
          icon={ReceiptText}
        />
        <StatCard
          label="Recent Allotments"
          value={stats?.recent_allotments ?? '—'}
          icon={Network}
        />
      </div>

      {/* Row 3 — charts */}
      <div className="mb-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">License Utilisation</CardTitle>
            <p className="text-xs text-muted-foreground">
              Top 10 licenses by CIF balance
            </p>
          </CardHeader>
          <CardContent>
            <UtilisationChart data={utilisationData} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Monthly Activity</CardTitle>
            <p className="text-xs text-muted-foreground">
              BOE and allotment counts — last 12 months
            </p>
          </CardHeader>
          <CardContent>
            <ActivityChart data={activityData} />
          </CardContent>
        </Card>
      </div>

      {/* Row 4 — expiring licenses table */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Expiring Licenses</CardTitle>
              <p className="text-xs text-muted-foreground">
                Licenses expiring within 30 days
              </p>
            </div>
            {expiringData.length > 0 && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/40 dark:text-amber-400">
                {expiringData.length} license{expiringData.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <ExpiringLicensesTable data={expiringData} />
        </CardContent>
      </Card>

      {/* Hidden total balance — surfaced for screen readers and future stat card */}
      <p className="sr-only">Total CIF Balance: {totalBalanceFormatted}</p>
    </div>
  )
}
