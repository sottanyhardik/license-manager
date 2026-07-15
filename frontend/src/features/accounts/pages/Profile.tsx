// Profile — self-service user profile page.
//
// Sections:
//   1. Current profile display (username, email, roles)
//   2. Edit profile form: first_name, last_name, email
//   3. Change password form: current_password, new_password, confirm_password
//
// Data:
//   - Reads current user from AuthContext (already fetched on session start).
//   - PATCH /api/v1/auth/me/ for profile updates.
//   - POST /api/v1/auth/change-password/ for password changes.

import { useState } from 'react'
import { Eye, EyeOff, Loader2, Lock, User } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Card, CardContent, CardHeader } from '@/shared/ui/card'
import { Badge } from '@/shared/ui/badge'
import { cn } from '@/shared/utils/cn'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { normaliseApiErrorString } from '@/shared/utils/errors'
import { useAuth } from '@/shared/auth/AuthContext'
import { ROLE_LABELS } from '@/shared/auth/roles'

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-3 border-b pb-1 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </h2>
  )
}

function FormField({
  label,
  htmlFor,
  children,
}: {
  label: string
  htmlFor?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={htmlFor} className="text-xs text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  )
}

// ─── Password visibility toggle ───────────────────────────────────────────────

function PasswordInput({
  id,
  value,
  onChange,
  placeholder,
  autoComplete,
}: {
  id: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  autoComplete?: string
}) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <Input
        id={id}
        type={show ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        className="pr-9"
      />
      <button
        type="button"
        className={cn(
          'absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground',
          'hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded',
        )}
        onClick={() => setShow((v) => !v)}
        aria-label={show ? 'Hide password' : 'Show password'}
      >
        {show ? (
          <EyeOff className="size-4" aria-hidden="true" />
        ) : (
          <Eye className="size-4" aria-hidden="true" />
        )}
      </button>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function Profile() {
  const { user, loginSuccess } = useAuth()

  // Profile edit form state
  const [profileForm, setProfileForm] = useState({
    first_name: user?.first_name ?? '',
    last_name: user?.last_name ?? '',
    email: user?.email ?? '',
  })
  const [profileSaving, setProfileSaving] = useState(false)

  // Password change form state
  const [pwForm, setPwForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })
  const [pwSaving, setPwSaving] = useState(false)

  function patchProfile<K extends keyof typeof profileForm>(
    key: K,
    value: string,
  ) {
    setProfileForm((prev) => ({ ...prev, [key]: value }))
  }

  function patchPw<K extends keyof typeof pwForm>(key: K, value: string) {
    setPwForm((prev) => ({ ...prev, [key]: value }))
  }

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault()
    setProfileSaving(true)
    try {
      const { data } = await apiClient.patch(ENDPOINTS.AUTH.UPDATE_PROFILE, profileForm)
      // Refresh the stored user in context so the sidebar/header reflect changes
      // The /me endpoint returns a full AuthUser; merge access/refresh tokens we already have.
      if (data && user) {
        const merged = { ...user, ...profileForm }
        loginSuccess({
          access: localStorage.getItem('access') ?? '',
          refresh: localStorage.getItem('refresh') ?? '',
          user: merged,
        })
      }
      toast.success('Profile updated successfully.')
    } catch (err) {
      toast.error(normaliseApiErrorString(err))
    } finally {
      setProfileSaving(false)
    }
  }

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault()
    if (pwForm.new_password !== pwForm.confirm_password) {
      toast.error('New password and confirmation do not match.')
      return
    }
    if (pwForm.new_password.length < 8) {
      toast.error('New password must be at least 8 characters.')
      return
    }
    setPwSaving(true)
    try {
      await apiClient.post(ENDPOINTS.AUTH.CHANGE_PASSWORD, {
        current_password: pwForm.current_password,
        new_password: pwForm.new_password,
      })
      toast.success('Password changed successfully.')
      setPwForm({ current_password: '', new_password: '', confirm_password: '' })
    } catch (err) {
      toast.error(normaliseApiErrorString(err))
    } finally {
      setPwSaving(false)
    }
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" aria-hidden="true" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Page header */}
      <div className="border-b bg-card px-6 py-4">
        <div className="flex items-center gap-3">
          <User className="size-5 text-muted-foreground" aria-hidden="true" />
          <div>
            <h1 className="text-lg font-semibold">Profile</h1>
            <p className="text-sm text-muted-foreground">
              Manage your account details
            </p>
          </div>
        </div>
      </div>

      <div className="flex-1 space-y-6 p-6">
        {/* Current user overview */}
        <Card>
          <CardHeader className="pb-2">
            <SectionHeading>Account Overview</SectionHeading>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary text-lg font-bold text-primary-foreground">
                {user.username[0].toUpperCase()}
              </div>
              <div>
                <p className="font-semibold">
                  {[user.first_name, user.last_name].filter(Boolean).join(' ') ||
                    user.username}
                </p>
                <p className="text-sm text-muted-foreground">@{user.username}</p>
                <p className="text-sm text-muted-foreground">{user.email}</p>
              </div>
            </div>

            {/* Roles */}
            {(user.is_superuser || user.roles.length > 0) && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Roles
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {user.is_superuser && (
                    <Badge variant="default" className="text-xs">
                      Super Admin
                    </Badge>
                  )}
                  {user.roles.map((role) => (
                    <Badge key={role} variant="secondary" className="text-xs">
                      {ROLE_LABELS[role] ?? role}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Edit profile */}
        <Card>
          <CardHeader className="pb-2">
            <SectionHeading>Edit Profile</SectionHeading>
          </CardHeader>
          <CardContent>
            <form
              id="profile-form"
              onSubmit={(e) => void handleProfileSave(e)}
              className="grid grid-cols-1 gap-4 sm:grid-cols-2"
              noValidate
            >
              <FormField label="First Name" htmlFor="first-name">
                <Input
                  id="first-name"
                  type="text"
                  value={profileForm.first_name}
                  onChange={(e) => patchProfile('first_name', e.target.value)}
                  placeholder="First name"
                  autoComplete="given-name"
                />
              </FormField>

              <FormField label="Last Name" htmlFor="last-name">
                <Input
                  id="last-name"
                  type="text"
                  value={profileForm.last_name}
                  onChange={(e) => patchProfile('last_name', e.target.value)}
                  placeholder="Last name"
                  autoComplete="family-name"
                />
              </FormField>

              <FormField label="Email" htmlFor="email">
                <Input
                  id="email"
                  type="email"
                  value={profileForm.email}
                  onChange={(e) => patchProfile('email', e.target.value)}
                  placeholder="your@email.com"
                  autoComplete="email"
                  required
                />
              </FormField>

              <div className="flex items-end sm:col-span-2">
                <Button
                  type="submit"
                  size="sm"
                  disabled={profileSaving}
                  form="profile-form"
                >
                  {profileSaving && (
                    <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" />
                  )}
                  Save Profile
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* Change password */}
        <Card>
          <CardHeader className="pb-2">
            <SectionHeading>Change Password</SectionHeading>
          </CardHeader>
          <CardContent>
            <form
              id="pw-form"
              onSubmit={(e) => void handlePasswordChange(e)}
              className="grid grid-cols-1 gap-4 sm:grid-cols-2"
              noValidate
            >
              <FormField label="Current Password" htmlFor="cur-pw">
                <PasswordInput
                  id="cur-pw"
                  value={pwForm.current_password}
                  onChange={(v) => patchPw('current_password', v)}
                  placeholder="Current password"
                  autoComplete="current-password"
                />
              </FormField>

              <div className="hidden sm:block" aria-hidden="true" />

              <FormField label="New Password" htmlFor="new-pw">
                <PasswordInput
                  id="new-pw"
                  value={pwForm.new_password}
                  onChange={(v) => patchPw('new_password', v)}
                  placeholder="At least 8 characters"
                  autoComplete="new-password"
                />
              </FormField>

              <FormField label="Confirm New Password" htmlFor="conf-pw">
                <PasswordInput
                  id="conf-pw"
                  value={pwForm.confirm_password}
                  onChange={(v) => patchPw('confirm_password', v)}
                  placeholder="Repeat new password"
                  autoComplete="new-password"
                />
              </FormField>

              <div className="flex items-end sm:col-span-2">
                <Button
                  type="submit"
                  size="sm"
                  variant="outline"
                  disabled={pwSaving || !pwForm.current_password || !pwForm.new_password}
                  form="pw-form"
                >
                  {pwSaving ? (
                    <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Lock className="mr-2 size-4" aria-hidden="true" />
                  )}
                  Change Password
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default Profile
