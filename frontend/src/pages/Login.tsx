import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
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
  const [isLoading, setIsLoading] = useState(false)

  const reason = searchParams.get('reason')
  const redirect = searchParams.get('redirect') ?? '/dashboard'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      const { data } = await apiClient.post<LoginResponse>(ENDPOINTS.AUTH.LOGIN, {
        username,
        password,
      })
      loginSuccess(data)
      navigate(redirect, { replace: true })
    } catch (err) {
      toast.error(normaliseApiErrorString(err))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">License Manager</CardTitle>
          <CardDescription>
            {reason === 'idle' && 'You were logged out due to inactivity.'}
            {reason === 'session_expired' && 'Your session expired. Please log in again.'}
            {!reason && 'Sign in to your account'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={(e) => { void handleSubmit(e) }} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
