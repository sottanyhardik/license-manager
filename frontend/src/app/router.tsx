import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ProtectedRoute } from '@/shared/auth/ProtectedRoute'
import { Skeleton } from '@/shared/ui/skeleton'

const Login = lazy(() => import('@/pages/Login'))
const NotFound = lazy(() => import('@/pages/NotFound'))

// Masters — lazy-loaded chunks per page.
// CompanyList and PortList have dedicated pages for possible entity-specific
// customisation; all other masters fall through to the generic MasterList.
const CompanyList = lazy(() => import('@/features/masters/pages/CompanyList'))
const PortList = lazy(() => import('@/features/masters/pages/PortList'))
const MasterList = lazy(() => import('@/features/masters/pages/MasterList'))

function PageLoader() {
  return (
    <div className="flex min-h-screen flex-col gap-4 p-8">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />

          {/* Protected routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<div className="p-8"><h1 className="text-2xl font-bold">Dashboard</h1><p className="text-muted-foreground mt-2">Welcome to License Manager.</p></div>} />

            {/* Masters routes — superuser write access; any authenticated user can read */}
            <Route path="/masters/companies" element={<CompanyList />} />
            <Route path="/masters/ports" element={<PortList />} />
            {/* Generic master list catches hs-codes, item-groups, item-names,
                sion-norm-classes, exchange-rates and any future entity */}
            <Route path="/masters/:entity" element={<MasterList />} />
          </Route>

          {/* 404 */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
