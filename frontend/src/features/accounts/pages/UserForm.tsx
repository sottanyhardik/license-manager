/**
 * UserForm — create or edit a user.
 *
 * - Create mode: /admin/users/new
 * - Edit mode:   /admin/users/:id/edit
 *
 * Fields: username, email, first_name, last_name, password (create only)
 * Toggles: is_active; is_staff + is_superuser for superusers only
 * Roles: checkbox grid populated from available-roles API
 * Reset Password section: superuser-only inline (OQ-4: no SMTP)
 */

import { useContext, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ArrowLeft, Check, KeyRound, X } from 'lucide-react'

import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { AuthContext } from '@/shared/auth/AuthContext'
import { ROLE_LABELS } from '@/shared/auth/roles'
import { ROUTES } from '@/shared/routes'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { cn } from '@/shared/utils/cn'

import type { ManagedUser, UserFormValues } from '../types'

const EMPTY_FORM: UserFormValues = {
  username: '',
  email: '',
  first_name: '',
  last_name: '',
  password: '',
  is_active: true,
  is_staff: false,
  is_superuser: false,
  roles: [],
}

/** Inline field-level error text. */
function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return <p className="mt-1 text-[11.5px] text-destructive">{message}</p>
}

/**
 * Styled toggle switch built from a native checkbox.
 * Keeps the same visual as the rest of the app without adding a missing Radix package.
 */
function ToggleSwitch({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5 text-sm">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          checked ? 'bg-primary' : 'bg-muted',
        )}
      >
        <span
          className={cn(
            'pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg ring-0 transition-transform',
            checked ? 'translate-x-4' : 'translate-x-0',
          )}
        />
      </button>
      {label}
    </label>
  )
}

export default function UserForm() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user: currentUser } = useContext(AuthContext)
  const isEdit = Boolean(id)

  const [form, setForm] = useState<UserFormValues>(EMPTY_FORM)
  const [availableRoles, setAvailableRoles] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [resettingPw, setResettingPw] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [showPwReset, setShowPwReset] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | undefined>>({})

  useEffect(() => {
    const init = async () => {
      setLoading(true)
      try {
        const { data: roles } = await apiClient.get<string[]>(ENDPOINTS.USERS.AVAILABLE_ROLES)
        setAvailableRoles(Array.isArray(roles) ? roles : [])

        if (isEdit && id) {
          const { data: user } = await apiClient.get<ManagedUser>(ENDPOINTS.USERS.DETAIL(id))
          setForm({
            username: user.username ?? '',
            email: user.email ?? '',
            first_name: user.first_name ?? '',
            last_name: user.last_name ?? '',
            password: '',
            is_active: user.is_active,
            is_staff: user.is_staff ?? false,
            is_superuser: user.is_superuser ?? false,
            roles: user.roles ?? [],
          })
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to load user data'
        toast.error(msg)
      } finally {
        setLoading(false)
      }
    }
    void init()
  }, [id, isEdit])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    setFieldErrors((prev) => ({ ...prev, [name]: undefined }))
  }

  const setFlag = (name: keyof UserFormValues, checked: boolean) => {
    setForm((prev) => ({ ...prev, [name]: checked }))
  }

  const toggleRole = (code: string) => {
    setForm((prev) => ({
      ...prev,
      roles: (prev.roles ?? []).includes(code)
        ? (prev.roles ?? []).filter((r) => r !== code)
        : [...(prev.roles ?? []), code],
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setFieldErrors({})
    try {
      const payload: UserFormValues = { ...form }
      // Don't send blank password on edit
      if (isEdit && !payload.password) {
        delete payload.password
      }
      if (isEdit && id) {
        await apiClient.patch(ENDPOINTS.USERS.DETAIL(id), payload)
        toast.success('User updated')
      } else {
        await apiClient.post(ENDPOINTS.USERS.CREATE, payload)
        toast.success('User created')
      }
      navigate(ROUTES.ADMIN.USERS)
    } catch (err: unknown) {
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        err.response &&
        typeof err.response === 'object' &&
        'data' in err.response &&
        err.response.data &&
        typeof err.response.data === 'object'
      ) {
        setFieldErrors(err.response.data as Record<string, string>)
      }
      const msg = err instanceof Error ? err.message : 'Failed to save user'
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  const handleResetPassword = async () => {
    if (!newPassword || !id) return
    setResettingPw(true)
    try {
      await apiClient.post(ENDPOINTS.USERS.RESET_PASSWORD(id), { new_password: newPassword })
      toast.success('Password reset successfully')
      setShowPwReset(false)
      setNewPassword('')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to reset password'
      toast.error(msg)
    } finally {
      setResettingPw(false)
    }
  }

  if (loading) {
    return <div className="p-8 text-center text-sm text-muted-foreground">Loading…</div>
  }

  return (
    <div className="mx-auto max-w-3xl">
      {/* Back + title */}
      <div className="mb-5 flex items-center gap-3">
        <Button variant="outline" size="sm" onClick={() => navigate(ROUTES.ADMIN.USERS)}>
          <ArrowLeft className="size-4" />
          Back
        </Button>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          {isEdit ? 'Edit User' : 'Create User'}
        </h1>
      </div>

      <form onSubmit={(e) => void handleSubmit(e)} className="flex flex-col gap-4">
        {/* Account details */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-sm">Account Details</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-4 pt-5 sm:grid-cols-2">
            <div>
              <Label className="mb-1.5" htmlFor="username">
                Username <span className="text-destructive">*</span>
              </Label>
              <Input
                id="username"
                name="username"
                value={form.username}
                onChange={handleChange}
                required
                autoComplete="off"
                aria-invalid={!!fieldErrors.username}
              />
              <FieldError message={fieldErrors.username} />
            </div>
            <div>
              <Label className="mb-1.5" htmlFor="email">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                name="email"
                value={form.email}
                onChange={handleChange}
                autoComplete="off"
                aria-invalid={!!fieldErrors.email}
              />
              <FieldError message={fieldErrors.email} />
            </div>
            <div>
              <Label className="mb-1.5" htmlFor="first_name">
                First Name
              </Label>
              <Input
                id="first_name"
                name="first_name"
                value={form.first_name}
                onChange={handleChange}
              />
            </div>
            <div>
              <Label className="mb-1.5" htmlFor="last_name">
                Last Name
              </Label>
              <Input
                id="last_name"
                name="last_name"
                value={form.last_name}
                onChange={handleChange}
              />
            </div>
            {/* Password only on create */}
            {!isEdit && (
              <div>
                <Label className="mb-1.5" htmlFor="password">
                  Password
                </Label>
                <Input
                  id="password"
                  type="password"
                  name="password"
                  value={form.password ?? ''}
                  onChange={handleChange}
                  autoComplete="new-password"
                  aria-invalid={!!fieldErrors.password}
                />
                <FieldError message={fieldErrors.password} />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Access flags */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-sm">Access Flags</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-x-8 gap-y-3 pt-5">
            <ToggleSwitch
              checked={form.is_active}
              onChange={(c) => setFlag('is_active', c)}
              label="Active"
            />
            {currentUser?.is_superuser && (
              <>
                <ToggleSwitch
                  checked={form.is_staff}
                  onChange={(c) => setFlag('is_staff', c)}
                  label="Staff (Django admin)"
                />
                <ToggleSwitch
                  checked={form.is_superuser}
                  onChange={(c) => setFlag('is_superuser', c)}
                  label="Super Admin (bypasses all role checks)"
                />
              </>
            )}
          </CardContent>
        </Card>

        {/* Roles */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-sm">Roles</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-2 pt-5 sm:grid-cols-2 lg:grid-cols-3">
            {availableRoles.map((code) => {
              const checked = (form.roles ?? []).includes(code)
              return (
                <label
                  key={code}
                  className={cn(
                    'flex cursor-pointer items-center gap-2.5 rounded-md border px-3 py-2 text-[13px] transition-colors',
                    checked
                      ? 'border-primary/40 bg-primary/5 text-foreground'
                      : 'border-border text-muted-foreground hover:bg-accent/50',
                  )}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleRole(code)}
                    className="h-4 w-4 rounded border-border accent-primary"
                  />
                  {ROLE_LABELS[code] ?? code}
                </label>
              )
            })}
          </CardContent>
        </Card>

        {/* Form actions */}
        <div className="flex gap-2">
          <Button type="submit" disabled={saving}>
            <Check className="size-4" />
            {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Create User'}
          </Button>
          <Button type="button" variant="outline" onClick={() => navigate(ROUTES.ADMIN.USERS)}>
            <X className="size-4" />
            Cancel
          </Button>
          {isEdit && currentUser?.is_superuser && (
            <Button
              type="button"
              variant="outline"
              className="ml-auto"
              onClick={() => setShowPwReset((v) => !v)}
            >
              <KeyRound className="size-4" />
              Reset Password
            </Button>
          )}
        </div>
      </form>

      {/* Inline password reset (superuser only, OQ-4: no SMTP) */}
      {showPwReset && (
        <Card className="mt-4">
          <CardHeader className="border-b">
            <CardTitle className="text-sm text-warning">Reset Password</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2 pt-5">
            <Input
              type="password"
              className="flex-1"
              placeholder="New password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
            />
            <Button
              onClick={() => void handleResetPassword()}
              disabled={resettingPw || !newPassword}
            >
              <Check className="size-4" />
              {resettingPw ? 'Saving…' : 'Set Password'}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
