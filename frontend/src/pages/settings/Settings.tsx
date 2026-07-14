/**
 * Settings page — Profile, Security, and Preferences tabs.
 *
 * Profile:     update display name and email (PATCH /api/v1/auth/me/)
 * Security:    change password (POST /api/v1/auth/change-password/)
 * Preferences: theme (light / dark / system) + items-per-page stored in localStorage
 *
 * Forms use React Hook Form + Zod. API calls go through the shared apiClient
 * so Authorization headers are injected automatically.
 */

import { useState, useId } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, Moon, Sun, Monitor } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/shared/utils/cn'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { useAuth } from '@/shared/auth/AuthContext'
import { useTheme } from '@/shared/ui/ThemeProvider'
import { ENDPOINTS } from '@/shared/api/endpoints'
import apiClient from '@/shared/api/client'

// ── Tab management ─────────────────────────────────────────────────────────────

type TabId = 'profile' | 'security' | 'preferences'

const TABS: { id: TabId; label: string }[] = [
  { id: 'profile', label: 'Profile' },
  { id: 'security', label: 'Security' },
  { id: 'preferences', label: 'Preferences' },
]

// ── Schemas ────────────────────────────────────────────────────────────────────

const profileSchema = z.object({
  first_name: z.string().min(1, 'First name is required'),
  last_name: z.string().min(1, 'Last name is required'),
  email: z.string().email('Invalid email address'),
})

type ProfileFormData = z.infer<typeof profileSchema>

const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Current password is required'),
    new_password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .regex(/[A-Z]/, 'Must contain at least one uppercase letter')
      .regex(/[0-9]/, 'Must contain at least one number'),
    confirm_password: z.string().min(1, 'Please confirm your new password'),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })

type PasswordFormData = z.infer<typeof passwordSchema>

// ── Profile tab ────────────────────────────────────────────────────────────────

function ProfileTab() {
  const { user, loginSuccess } = useAuth()
  const uid = useId()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      first_name: user?.first_name ?? '',
      last_name: user?.last_name ?? '',
      email: user?.email ?? '',
    },
  })

  const onSubmit = async (data: ProfileFormData) => {
    try {
      const response = await apiClient.patch<{
        access: string
        refresh: string
        user: typeof user
      }>(ENDPOINTS.AUTH.UPDATE_PROFILE, data)
      // If the API returns updated user data, update the local session
      if (response.data.user && response.data.access) {
        loginSuccess(response.data as Parameters<typeof loginSuccess>[0])
      }
      toast.success('Profile updated successfully')
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: Record<string, string[]> } }
      const fieldErrors = apiErr?.response?.data
      if (fieldErrors) {
        for (const [field, messages] of Object.entries(fieldErrors)) {
          if (field in profileSchema.shape) {
            setError(field as keyof ProfileFormData, {
              message: Array.isArray(messages) ? messages[0] : String(messages),
            })
          }
        }
      } else {
        toast.error('Failed to update profile. Please try again.')
      }
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5 max-w-md">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor={`${uid}-first-name`}>First name</Label>
          <Input
            id={`${uid}-first-name`}
            {...register('first_name')}
            aria-invalid={!!errors.first_name}
            aria-describedby={errors.first_name ? `${uid}-first-name-err` : undefined}
          />
          {errors.first_name && (
            <p id={`${uid}-first-name-err`} role="alert" className="text-xs text-destructive">
              {errors.first_name.message}
            </p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={`${uid}-last-name`}>Last name</Label>
          <Input
            id={`${uid}-last-name`}
            {...register('last_name')}
            aria-invalid={!!errors.last_name}
            aria-describedby={errors.last_name ? `${uid}-last-name-err` : undefined}
          />
          {errors.last_name && (
            <p id={`${uid}-last-name-err`} role="alert" className="text-xs text-destructive">
              {errors.last_name.message}
            </p>
          )}
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${uid}-email`}>Email address</Label>
        <Input
          id={`${uid}-email`}
          type="email"
          autoComplete="email"
          {...register('email')}
          aria-invalid={!!errors.email}
          aria-describedby={errors.email ? `${uid}-email-err` : undefined}
        />
        {errors.email && (
          <p id={`${uid}-email-err`} role="alert" className="text-xs text-destructive">
            {errors.email.message}
          </p>
        )}
      </div>

      <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
        {isSubmitting && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
        Save changes
      </Button>
    </form>
  )
}

// ── Security tab ───────────────────────────────────────────────────────────────

function SecurityTab() {
  const uid = useId()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<PasswordFormData>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: '', new_password: '', confirm_password: '' },
  })

  const onSubmit = async (data: PasswordFormData) => {
    try {
      await apiClient.post(ENDPOINTS.AUTH.CHANGE_PASSWORD, {
        current_password: data.current_password,
        new_password: data.new_password,
      })
      toast.success('Password changed successfully')
      reset()
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: Record<string, string[]> | { detail?: string } } }
      const body = apiErr?.response?.data
      if (body && 'current_password' in body) {
        setError('current_password', {
          message: Array.isArray(body.current_password)
            ? body.current_password[0]
            : String(body.current_password),
        })
      } else if (body && 'detail' in body) {
        toast.error((body as { detail: string }).detail)
      } else {
        toast.error('Failed to change password. Please try again.')
      }
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5 max-w-md">
      <div className="space-y-1.5">
        <Label htmlFor={`${uid}-current-pw`}>Current password</Label>
        <Input
          id={`${uid}-current-pw`}
          type="password"
          autoComplete="current-password"
          {...register('current_password')}
          aria-invalid={!!errors.current_password}
          aria-describedby={errors.current_password ? `${uid}-current-pw-err` : undefined}
        />
        {errors.current_password && (
          <p id={`${uid}-current-pw-err`} role="alert" className="text-xs text-destructive">
            {errors.current_password.message}
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${uid}-new-pw`}>New password</Label>
        <Input
          id={`${uid}-new-pw`}
          type="password"
          autoComplete="new-password"
          {...register('new_password')}
          aria-invalid={!!errors.new_password}
          aria-describedby={errors.new_password ? `${uid}-new-pw-err` : undefined}
        />
        {errors.new_password && (
          <p id={`${uid}-new-pw-err`} role="alert" className="text-xs text-destructive">
            {errors.new_password.message}
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${uid}-confirm-pw`}>Confirm new password</Label>
        <Input
          id={`${uid}-confirm-pw`}
          type="password"
          autoComplete="new-password"
          {...register('confirm_password')}
          aria-invalid={!!errors.confirm_password}
          aria-describedby={errors.confirm_password ? `${uid}-confirm-pw-err` : undefined}
        />
        {errors.confirm_password && (
          <p id={`${uid}-confirm-pw-err`} role="alert" className="text-xs text-destructive">
            {errors.confirm_password.message}
          </p>
        )}
      </div>

      <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
        {isSubmitting && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
        Change password
      </Button>
    </form>
  )
}

// ── Preferences tab ────────────────────────────────────────────────────────────

const ITEMS_PER_PAGE_OPTIONS = [10, 25, 50, 100] as const
const ITEMS_PER_PAGE_KEY = 'pref-items-per-page'

type ThemeChoice = 'light' | 'dark' | 'system'

function PreferencesTab() {
  const { theme, setTheme } = useTheme()
  const uid = useId()

  const [itemsPerPage, setItemsPerPage] = useState<number>(() => {
    const stored = localStorage.getItem(ITEMS_PER_PAGE_KEY)
    return stored ? parseInt(stored, 10) : 25
  })

  const handleThemeChange = (choice: ThemeChoice) => {
    if (choice === 'system') {
      const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      setTheme(systemDark ? 'dark' : 'light')
    } else {
      setTheme(choice)
    }
    toast.success('Theme updated')
  }

  const handleItemsPerPageChange = (value: number) => {
    setItemsPerPage(value)
    localStorage.setItem(ITEMS_PER_PAGE_KEY, String(value))
    toast.success('Preference saved')
  }

  const themeOptions: { id: ThemeChoice; label: string; icon: React.ElementType }[] = [
    { id: 'light', label: 'Light', icon: Sun },
    { id: 'dark', label: 'Dark', icon: Moon },
    { id: 'system', label: 'System', icon: Monitor },
  ]

  return (
    <div className="space-y-8 max-w-md">
      {/* Theme */}
      <fieldset>
        <legend className="text-sm font-medium text-foreground">Theme</legend>
        <p className="mt-0.5 text-xs text-muted-foreground">Choose how the app looks for you.</p>
        <div className="mt-3 flex gap-3">
          {themeOptions.map(({ id, label, icon: Icon }) => {
            const isSelected =
              id === 'system'
                ? false // system doesn't persist as a stored value
                : theme === id
            return (
              <button
                key={id}
                type="button"
                onClick={() => handleThemeChange(id)}
                aria-pressed={isSelected}
                className={cn(
                  'flex flex-col items-center gap-1.5 rounded-lg border px-4 py-3 text-xs font-medium transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  isSelected
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                )}
              >
                <Icon className="size-4" aria-hidden="true" />
                {label}
              </button>
            )
          })}
        </div>
      </fieldset>

      {/* Items per page */}
      <div className="space-y-1.5">
        <Label htmlFor={`${uid}-ipp`}>Items per page</Label>
        <p className="text-xs text-muted-foreground">
          Controls the default page size for lists and tables.
        </p>
        <select
          id={`${uid}-ipp`}
          value={itemsPerPage}
          onChange={(e) => handleItemsPerPageChange(Number(e.target.value))}
          className={cn(
            'mt-1 block rounded-md border border-input bg-background px-3 py-2 text-sm',
            'text-foreground shadow-sm',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          )}
        >
          {ITEMS_PER_PAGE_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}

// ── Settings page ──────────────────────────────────────────────────────────────

export function Settings() {
  const [activeTab, setActiveTab] = useState<TabId>('profile')
  const panelId = useId()

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage your account, security, and preferences.
        </p>
      </div>

      {/* Tab list */}
      <div
        role="tablist"
        aria-label="Settings sections"
        className="mb-6 flex gap-1 border-b border-border"
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            type="button"
            id={`tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`${panelId}-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'px-4 py-2 text-sm font-medium transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-t-md',
              activeTab === tab.id
                ? 'border-b-2 border-primary text-primary'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab panels */}
      {TABS.map((tab) => (
        <div
          key={tab.id}
          role="tabpanel"
          id={`${panelId}-${tab.id}`}
          aria-labelledby={`tab-${tab.id}`}
          hidden={activeTab !== tab.id}
        >
          {activeTab === tab.id && (
            <>
              {tab.id === 'profile' && <ProfileTab />}
              {tab.id === 'security' && <SecurityTab />}
              {tab.id === 'preferences' && <PreferencesTab />}
            </>
          )}
        </div>
      ))}
    </div>
  )
}
