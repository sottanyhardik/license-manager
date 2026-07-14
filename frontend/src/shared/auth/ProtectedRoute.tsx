import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { Skeleton } from '@/shared/ui/skeleton'

interface ProtectedRouteProps {
  requiredRoles?: string[]
}

export function ProtectedRoute({ requiredRoles }: ProtectedRouteProps) {
  const { user, loading, hasAnyRole } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col gap-4 p-8">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (requiredRoles && requiredRoles.length > 0 && !hasAnyRole(requiredRoles)) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4">
        <h1 className="text-2xl font-bold">Access Denied</h1>
        <p className="text-muted-foreground">You do not have permission to view this page.</p>
      </div>
    )
  }

  return <Outlet />
}
