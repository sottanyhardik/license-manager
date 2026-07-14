import { Suspense, lazy, Component } from 'react'
import type { ReactNode, ErrorInfo } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ProtectedRoute } from '@/shared/auth/ProtectedRoute'
import { AdminLayout } from '@/layout/AdminLayout'
import { Skeleton } from '@/shared/ui/skeleton'

const Login = lazy(() => import('@/pages/Login'))
const NotFound = lazy(() => import('@/pages/NotFound'))

// Masters — lazy-loaded chunks per page.
// CompanyList and PortList have dedicated pages for possible entity-specific
// customisation; all other masters fall through to the generic MasterList.
const CompanyList = lazy(() => import('@/features/masters/pages/CompanyList'))
const PortList = lazy(() => import('@/features/masters/pages/PortList'))
const MasterList = lazy(() => import('@/features/masters/pages/MasterList'))

// Allotments
const AllotmentList = lazy(() => import('@/features/allotments/pages/AllotmentList'))

// Licenses
const LicenseList = lazy(() => import('@/features/licenses/pages/LicenseList'))
const LicenseDetail = lazy(() => import('@/features/licenses/pages/LicenseDetail'))

// Bill of Entry
const BOEList = lazy(() => import('@/features/bill-of-entry/pages/BOEList'))
const BOEDetail = lazy(() => import('@/features/bill-of-entry/pages/BOEDetail'))

// Dashboard
const Dashboard = lazy(() => import('@/features/dashboard/pages/Dashboard'))

// Trades
const TradeList = lazy(() =>
  import('@/features/trade/pages/TradeList').then((m) => ({ default: m.TradeList })),
)
const TradeForm = lazy(() =>
  import('@/features/trade/pages/TradeForm').then((m) => ({ default: m.TradeForm })),
)

// Tasks
const TaskList = lazy(() => import('@/features/tasks/pages/TaskList'))

// Reports
const ReportsIndex = lazy(() => import('@/features/reports/pages/ReportsIndex'))
const BalanceReport = lazy(() => import('@/features/reports/pages/BalanceReport'))
const ItemReport = lazy(() => import('@/features/reports/pages/ItemReport'))
const PivotReport = lazy(() => import('@/features/reports/pages/PivotReport'))
const LedgerReport = lazy(() => import('@/features/reports/pages/LedgerReport'))

// Settings — named export, re-wrapped for lazy()
const Settings = lazy(() =>
  import('@/pages/settings/Settings').then((m) => ({ default: m.Settings })),
)

function PageLoader() {
  return (
    <div className="flex min-h-screen flex-col gap-4 p-8">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}

// ── Per-route error boundary ──────────────────────────────────────────────────
// Catches render errors thrown by individual page components so a single
// broken page does not crash the entire app (which the root boundary in
// main.tsx would also catch, but this gives a recoverable in-layout fallback).

interface PageErrorBoundaryState {
  hasError: boolean
  message: string
}

class PageErrorBoundary extends Component<
  { children: ReactNode },
  PageErrorBoundaryState
> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error: unknown): PageErrorBoundaryState {
    return {
      hasError: true,
      message: error instanceof Error ? error.message : 'An unexpected error occurred.',
    }
  }

  componentDidCatch(_error: Error, info: ErrorInfo) {
    // In production you would forward this to an error-tracking service.
    if (import.meta.env.DEV) {
      console.error('[PageErrorBoundary]', _error, info.componentStack)
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8">
          <p className="text-lg font-semibold text-destructive">This page failed to load.</p>
          <p className="text-sm text-muted-foreground">{this.state.message}</p>
          <button
            type="button"
            className="rounded bg-primary px-4 py-2 text-sm text-primary-foreground"
            onClick={() => this.setState({ hasError: false, message: '' })}
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <PageErrorBoundary>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />

          {/* Protected routes — all authenticated pages are wrapped in AdminLayout */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AdminLayout />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />

              {/* Settings */}
              <Route path="/settings" element={<Settings />} />

              {/* Masters routes — superuser write access; any authenticated user can read */}
              <Route path="/masters/companies" element={<CompanyList />} />
              <Route path="/masters/ports" element={<PortList />} />
              {/* Generic master list catches hs-codes, item-groups, item-names,
                  sion-norm-classes, exchange-rates and any future entity */}
              <Route path="/masters/:entity" element={<MasterList />} />

              {/* Allotments */}
              <Route path="/allotments" element={<AllotmentList />} />

              {/* Licenses */}
              <Route path="/licenses" element={<LicenseList />} />
              <Route path="/licenses/:id" element={<LicenseDetail />} />

              {/* Bill of Entry */}
              <Route path="/boe" element={<BOEList />} />
              <Route path="/boe/:id" element={<BOEDetail />} />

              {/* Trades */}
              <Route path="/trades" element={<TradeList />} />
              <Route path="/trades/new" element={<TradeForm />} />
              <Route path="/trades/:id" element={<TradeForm />} />

              {/* Tasks */}
              <Route path="/tasks" element={<TaskList />} />

              {/* Reports */}
              <Route path="/reports" element={<ReportsIndex />} />
              <Route path="/reports/balance" element={<BalanceReport />} />
              <Route path="/reports/items" element={<ItemReport />} />
              <Route path="/reports/pivot" element={<PivotReport />} />
              <Route path="/reports/ledger" element={<LedgerReport />} />
            </Route>
          </Route>

          {/* 404 */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
      </PageErrorBoundary>
    </BrowserRouter>
  )
}
