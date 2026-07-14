import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { useAuth } from '@/shared/auth/AuthContext'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import type { LoginResponse } from '@/shared/auth/AuthContext'
import { normaliseApiErrorString } from '@/shared/utils/errors'

export default function Login() {
  const { loginSuccess } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reason = searchParams.get('reason')
  // Guard against open-redirect: only allow same-origin relative paths.
  // A redirect value starting with '//' or a scheme like 'javascript:' would
  // be dangerous when passed to navigate(), so we validate it here.
  const rawRedirect = searchParams.get('redirect') ?? '/dashboard'
  const redirect = /^\/[^/]/.test(rawRedirect) || rawRedirect === '/' ? rawRedirect : '/dashboard'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Client-side validation before hitting the network
    if (!username.trim()) {
      setError('Username is required.')
      return
    }
    if (!password) {
      setError('Password is required.')
      return
    }

    setIsLoading(true)
    try {
      const { data } = await apiClient.post<LoginResponse>(ENDPOINTS.AUTH.LOGIN, {
        username: username.trim(),
        password,
      })
      loginSuccess(data)
      navigate(redirect, { replace: true })
    } catch (err) {
      const msg = normaliseApiErrorString(err)
      setError(msg)
      toast.error(msg)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900 p-4">
      <div className="w-full max-w-sm">
        {/* App brand mark above card */}
        <div className="mb-6 text-center">
          <div className="inline-flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground text-xl font-bold mb-3">
            LM
          </div>
          <p className="text-xs text-muted-foreground uppercase tracking-widest font-medium">
            DGFT License Manager
          </p>
        </div>

        <Card className="shadow-lg border-border/50">
          <CardHeader className="pb-4">
            <CardTitle className="text-xl">Sign in</CardTitle>
            <CardDescription>
              {reason === 'idle' && 'You were signed out due to inactivity.'}
              {reason === 'session_expired' && 'Your session expired. Please sign in again.'}
              {!reason && 'Enter your credentials to access the dashboard.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => { void handleSubmit(e) }}
              noValidate
              className="flex flex-col gap-4"
            >
              {/* Inline error banner — shown instead of (or alongside) toast */}
              {error && (
                <div
                  role="alert"
                  className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
                >
                  {error}
                </div>
              )}

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  name="username"
                  type="text"
                  autoComplete="username"
                  autoFocus
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value)
                    if (error) setError(null)
                  }}
                  disabled={isLoading}
                  aria-invalid={error !== null ? 'true' : undefined}
                  placeholder="Enter your username"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value)
                      if (error) setError(null)
                    }}
                    disabled={isLoading}
                    aria-invalid={error !== null ? 'true' : undefined}
                    placeholder="Enter your password"
                    className="pr-10"
                  />
                  <button
                    type="button"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute inset-y-0 right-0 flex items-center px-3 text-muted-foreground hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-r-md"
                  >
                    {showPassword ? (
                      <EyeOff className="size-4" aria-hidden="true" />
                    ) : (
                      <Eye className="size-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                className="w-full mt-1"
                disabled={isLoading}
                size="lg"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" />
                    Signing in…
                  </>
                ) : (
                  'Sign in'
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          For access, contact your system administrator.
        </p>
      </div>
    </div>
  )
}
