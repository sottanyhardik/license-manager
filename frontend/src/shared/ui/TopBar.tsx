/**
 * TopBar — page header bar with breadcrumb, theme toggle, and user menu.
 *
 * Breadcrumb is derived automatically from the current pathname.
 * User menu (dropdown) uses the existing @radix-ui/react-dropdown-menu
 * that is already installed.
 */

import { Link, useLocation } from 'react-router-dom'
import {
  ChevronRight,
  LogOut,
  Menu,
  Moon,
  Sun,
  User,
} from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { cn } from '@/shared/utils/cn'
import { useAuth } from '@/shared/auth/AuthContext'
import { useTheme } from '@/shared/ui/ThemeProvider'
import { ROUTES } from '@/shared/routes'

// ── Breadcrumb ──────────────────────────────────────────────────────────────────

/** Convert a URL pathname into human-readable breadcrumb segments. */
function buildCrumbs(pathname: string): { label: string; path: string }[] {
  const segments = pathname.split('/').filter(Boolean)
  if (segments.length === 0) return [{ label: 'Dashboard', path: '/' }]

  const LABELS: Record<string, string> = {
    licenses: 'Licenses',
    allotments: 'Allotments',
    boe: 'Bill of Entry',
    trade: 'Trade',
    reports: 'Reports',
    balance: 'Balance Report',
    items: 'Item Report',
    pivot: 'Pivot Report',
    ledger: 'Ledger Report',
    masters: 'Masters',
    companies: 'Companies',
    ports: 'Ports',
    'hs-codes': 'HS Codes',
    'item-groups': 'Item Groups',
    'item-names': 'Item Names',
    'sion-norm-classes': 'SION Norm Classes',
    'exchange-rates': 'Exchange Rates',
    tasks: 'Tasks',
    settings: 'Settings',
  }

  const crumbs: { label: string; path: string }[] = [
    { label: 'Dashboard', path: '/' },
  ]

  let accumulated = ''
  for (const seg of segments) {
    accumulated += `/${seg}`
    // Numeric segments are record IDs (e.g. /licenses/2348).
    // Show "Detail" instead of the raw number — the page h1 already shows
    // the human-readable identifier (license number, BOE number, etc.)
    const isNumericId = /^\d+$/.test(seg)
    crumbs.push({
      label: isNumericId
        ? 'Detail'
        : (LABELS[seg] ?? seg.charAt(0).toUpperCase() + seg.slice(1)),
      path: accumulated,
    })
  }

  return crumbs
}

// ── User menu ──────────────────────────────────────────────────────────────────

function UserMenu() {
  const { user, logout } = useAuth()

  const initials =
    user
      ? `${user.first_name.charAt(0)}${user.last_name.charAt(0)}`.toUpperCase() ||
        user.username.charAt(0).toUpperCase()
      : '?'

  const displayName =
    user
      ? [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username
      : 'User'

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label="User menu"
          className={cn(
            'flex size-8 items-center justify-center rounded-full',
            'bg-primary text-primary-foreground text-xs font-semibold',
            'transition-opacity hover:opacity-80',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          )}
        >
          {initials}
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className={cn(
            'z-50 min-w-48 rounded-lg border border-border bg-popover p-1 shadow-lg',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
          )}
        >
          {/* User info header */}
          <div className="px-3 py-2">
            <p className="text-sm font-medium text-foreground">{displayName}</p>
            {user?.email && (
              <p className="truncate text-xs text-muted-foreground">{user.email}</p>
            )}
          </div>

          <DropdownMenu.Separator className="my-1 h-px bg-border" />

          <DropdownMenu.Item asChild>
            <Link
              to={ROUTES.SETTINGS}
              className={cn(
                'flex cursor-pointer items-center gap-2 rounded-md px-3 py-1.5 text-sm',
                'text-foreground outline-none transition-colors',
                'hover:bg-accent hover:text-accent-foreground',
                'focus:bg-accent focus:text-accent-foreground',
              )}
            >
              <User className="size-3.5" aria-hidden="true" />
              Profile
            </Link>
          </DropdownMenu.Item>

          <DropdownMenu.Separator className="my-1 h-px bg-border" />

          <DropdownMenu.Item
            onSelect={() => void logout()}
            className={cn(
              'flex cursor-pointer items-center gap-2 rounded-md px-3 py-1.5 text-sm',
              'text-destructive outline-none transition-colors',
              'hover:bg-destructive hover:text-destructive-foreground',
              'focus:bg-destructive focus:text-destructive-foreground',
            )}
          >
            <LogOut className="size-3.5" aria-hidden="true" />
            Logout
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

interface TopBarProps {
  /** Called when the mobile hamburger button is pressed. */
  onMobileMenuToggle: () => void
  /** Whether the mobile sidebar drawer is currently open. */
  mobileMenuOpen: boolean
}

export function TopBar({ onMobileMenuToggle, mobileMenuOpen }: TopBarProps) {
  const { pathname } = useLocation()
  const { theme, toggleTheme } = useTheme()
  const crumbs = buildCrumbs(pathname)

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background px-4">
      {/* Mobile hamburger — visible only below md breakpoint */}
      <button
        type="button"
        aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
        aria-expanded={mobileMenuOpen}
        aria-controls="main-nav"
        onClick={onMobileMenuToggle}
        className={cn(
          'flex md:hidden size-8 items-center justify-center rounded-md',
          'text-muted-foreground transition-colors',
          'hover:bg-accent hover:text-accent-foreground',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        )}
      >
        <Menu className="size-4" aria-hidden="true" />
      </button>

      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="flex flex-1 items-center gap-1 overflow-hidden">
        {crumbs.map((crumb, idx) => {
          const isLast = idx === crumbs.length - 1
          return (
            <span key={crumb.path} className="flex items-center gap-1 overflow-hidden">
              {idx > 0 && (
                <ChevronRight
                  className="size-3.5 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
              )}
              {isLast ? (
                <span className="truncate text-sm font-semibold text-foreground">
                  {crumb.label}
                </span>
              ) : (
                <Link
                  to={crumb.path}
                  className={cn(
                    'truncate text-sm text-muted-foreground',
                    'transition-colors hover:text-foreground',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded',
                  )}
                >
                  {crumb.label}
                </Link>
              )}
            </span>
          )
        })}
      </nav>

      {/* Right controls */}
      <div className="flex items-center gap-2">
        {/* Theme toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          className={cn(
            'flex size-8 items-center justify-center rounded-md',
            'text-muted-foreground transition-colors',
            'hover:bg-accent hover:text-accent-foreground',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          )}
        >
          {theme === 'dark' ? (
            <Sun className="size-4" aria-hidden="true" />
          ) : (
            <Moon className="size-4" aria-hidden="true" />
          )}
        </button>

        {/* User menu */}
        <UserMenu />
      </div>
    </header>
  )
}
