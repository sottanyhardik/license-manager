/**
 * Sidebar — collapsible left-nav for the AdminLayout.
 *
 * Collapse state is persisted in localStorage so the preference survives
 * page refreshes. In icon-only mode the sidebar shrinks to 64px and labels
 * are hidden; tooltips are NOT added here to keep the component lean —
 * add them later if the UX review asks for it.
 *
 * RBAC: items are hidden (not just disabled) when the user lacks the role.
 * Superusers bypass all role checks via `hasAnyRole` in AuthContext.
 */

import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  BarChart3,
  BookOpen,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ClipboardList,
  Database,
  FileBadge,
  FileBarChart2,
  FileText,
  LayoutDashboard,
  Package,
  ScrollText,
  Settings,
  ShoppingCart,
  Truck,
  Upload,
  User,
  Users,
} from 'lucide-react'
import { cn } from '@/shared/utils/cn'
import { useAuth } from '@/shared/auth/AuthContext'
import { ROLE_GROUPS, ROLES } from '@/shared/auth/roles'
import { ROUTES } from '@/shared/routes'

// ── Nav item shape ─────────────────────────────────────────────────────────────

interface NavItem {
  label: string
  path: string
  icon: React.ElementType
  /** If provided, item is hidden unless user hasAnyRole(roles) */
  roles?: string[]
}

interface NavGroup {
  label: string
  icon: React.ElementType
  /** Path prefix — used to determine active state for the group button */
  prefix: string
  items: NavItem[]
  roles?: string[]
}

// ── Route definitions ──────────────────────────────────────────────────────────

const TOP_NAV: NavItem[] = [
  { label: 'Dashboard', path: ROUTES.DASHBOARD, icon: LayoutDashboard },
  {
    label: 'Licenses',
    path: ROUTES.LICENSES,
    icon: FileText,
    roles: ROLE_GROUPS.LICENSE_ANY,
  },
  {
    label: 'Incentive Licenses',
    path: ROUTES.INCENTIVE_LICENSES,
    icon: FileBadge,
    roles: ROLE_GROUPS.INCENTIVE_ANY,
  },
  {
    label: 'Allotments',
    path: ROUTES.ALLOTMENTS,
    icon: Package,
    roles: ROLE_GROUPS.ALLOTMENT_ANY,
  },
  {
    label: 'Bill of Entry',
    path: ROUTES.BOE,
    icon: ClipboardList,
    roles: ROLE_GROUPS.BOE_ANY,
  },
  {
    label: 'Trade',
    path: ROUTES.TRADE,
    icon: ShoppingCart,
    roles: ROLE_GROUPS.TRADE_ANY,
  },
  {
    label: 'Ledger Upload',
    path: ROUTES.LEDGER_UPLOAD,
    icon: Upload,
    roles: ROLE_GROUPS.BOE_ANY,
  },
  {
    label: 'Ledger',
    path: ROUTES.LICENSE_LEDGER,
    icon: BookOpen,
    roles: [ROLES.TRADE_VIEWER, ROLES.TRADE_MANAGER, ROLES.LICENSE_MANAGER, ROLES.LEDGER_MANAGER],
  },
  {
    label: 'Users',
    path: ROUTES.ADMIN.USERS,
    icon: Users,
    roles: [ROLES.USER_MANAGER],
  },
]

const REPORT_ITEMS: NavItem[] = [
  {
    label: 'Balance Report',
    path: ROUTES.REPORTS.BALANCE,
    icon: BarChart3,
    roles: ROLE_GROUPS.CAN_VIEW_REPORTS,
  },
  {
    label: 'Item Report',
    path: ROUTES.REPORTS.ITEMS,
    icon: FileBarChart2,
    roles: ROLE_GROUPS.CAN_VIEW_REPORTS,
  },
  {
    label: 'Pivot Report',
    path: ROUTES.REPORTS.PIVOT,
    icon: FileBadge,
    roles: ROLE_GROUPS.CAN_VIEW_REPORTS,
  },
  {
    label: 'Ledger Report',
    path: ROUTES.REPORTS.LEDGER,
    icon: BookOpen,
    roles: ROLE_GROUPS.CAN_VIEW_REPORTS,
  },
]

const MASTER_ITEMS: NavItem[] = [
  { label: 'Companies', path: ROUTES.MASTERS.COMPANIES, icon: Database },
  { label: 'Ports', path: ROUTES.MASTERS.PORTS, icon: Truck },
  { label: 'HS Codes', path: ROUTES.MASTERS.HS_CODES, icon: Package },
  { label: 'Item Groups', path: ROUTES.MASTERS.ITEM_GROUPS, icon: Package },
  { label: 'Item Names', path: ROUTES.MASTERS.ITEM_NAMES, icon: Package },
  {
    label: 'SION Norm Classes',
    path: ROUTES.MASTERS.SION_NORM_CLASSES,
    icon: Package,
  },
  {
    label: 'Exchange Rates',
    path: ROUTES.MASTERS.EXCHANGE_RATES,
    icon: FileBarChart2,
  },
]

const GROUPS: NavGroup[] = [
  {
    label: 'Reports',
    icon: BarChart3,
    prefix: '/reports',
    items: REPORT_ITEMS,
    roles: ROLE_GROUPS.CAN_VIEW_REPORTS,
  },
  {
    label: 'Masters',
    icon: Database,
    prefix: '/masters',
    items: MASTER_ITEMS,
    // Masters are readable by all authenticated users; write is gated server-side
  },
]

const TASKS_ITEM: NavItem = {
  label: 'Tasks',
  path: ROUTES.TASKS,
  icon: ClipboardList,
}

// ── Helpers ────────────────────────────────────────────────────────────────────

/** Returns true if the current route matches this nav item's path. */
function useIsActive(path: string): boolean {
  const { pathname } = useLocation()
  if (path === ROUTES.DASHBOARD) return pathname === '/'
  return pathname === path || pathname.startsWith(path + '/')
}

// ── Sub-components ─────────────────────────────────────────────────────────────

interface SidebarLinkProps {
  item: NavItem
  collapsed: boolean
  onLinkClick?: () => void
}

function SidebarLink({ item, collapsed, onLinkClick }: SidebarLinkProps) {
  const { hasAnyRole } = useAuth()
  const active = useIsActive(item.path)

  // Hide gated items when user lacks the required role
  if (item.roles && !hasAnyRole(item.roles)) return null

  const Icon = item.icon

  return (
    <li>
      <Link
        to={item.path}
        aria-current={active ? 'page' : undefined}
        onClick={onLinkClick}
        className={cn(
          'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          active
            ? 'bg-primary text-primary-foreground'
            : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
          collapsed && 'justify-center px-2',
        )}
        title={collapsed ? item.label : undefined}
      >
        <Icon className="size-4 shrink-0" aria-hidden="true" />
        {!collapsed && <span className="truncate">{item.label}</span>}
      </Link>
    </li>
  )
}

interface CollapsibleGroupProps {
  group: NavGroup
  collapsed: boolean
  onLinkClick?: () => void
}

function CollapsibleGroup({ group, collapsed, onLinkClick }: CollapsibleGroupProps) {
  const { pathname } = useLocation()
  const { hasAnyRole } = useAuth()
  const isGroupActive = pathname.startsWith(group.prefix)
  const [open, setOpen] = useState(isGroupActive)

  // Hide group when user lacks all required roles
  if (group.roles && !hasAnyRole(group.roles)) return null

  const Icon = group.icon
  const ChevronIcon = open ? ChevronUp : ChevronDown

  // In collapsed sidebar mode the group button just links to the prefix
  if (collapsed) {
    return (
      <li>
        <Link
          to={group.prefix}
          aria-label={group.label}
          title={group.label}
          onClick={onLinkClick}
          className={cn(
            'flex justify-center rounded-lg px-2 py-2 text-sm font-medium transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            isGroupActive
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
          )}
        >
          <Icon className="size-4 shrink-0" aria-hidden="true" />
        </Link>
      </li>
    )
  }

  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={cn(
          'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          isGroupActive
            ? 'bg-primary text-primary-foreground'
            : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
        )}
      >
        <Icon className="size-4 shrink-0" aria-hidden="true" />
        <span className="flex-1 truncate text-left">{group.label}</span>
        <ChevronIcon className="size-3.5 shrink-0" aria-hidden="true" />
      </button>

      {open && (
        <ul className="mt-1 space-y-0.5 pl-6">
          {group.items.map((item) => (
            <SidebarLink key={item.path} item={item} collapsed={false} onLinkClick={onLinkClick} />
          ))}
        </ul>
      )}
    </li>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

interface SidebarProps {
  /** Called when any nav link is clicked — used by the mobile drawer to close itself. */
  onLinkClick?: () => void
  /**
   * When true, forces the sidebar to render fully expanded regardless of the
   * persisted collapsed preference. Used by AdminLayout on mobile so the drawer
   * always shows labels, not just icons.
   */
  forceExpanded?: boolean
}

export function Sidebar({ onLinkClick, forceExpanded = false }: SidebarProps) {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('sidebar-collapsed') === 'true'
    } catch {
      return false
    }
  })

  // On mobile the drawer always shows the full (non-collapsed) view so that
  // icon-only mode on a 375 px screen is not the user experience.
  const effectiveCollapsed = forceExpanded ? false : collapsed

  const toggleCollapsed = () => {
    setCollapsed((v) => {
      const next = !v
      try {
        localStorage.setItem('sidebar-collapsed', String(next))
      } catch {
        // ignore storage errors
      }
      return next
    })
  }

  return (
    <aside
      id="main-nav"
      aria-label="Main navigation"
      className={cn(
        'flex h-full flex-col border-r border-border bg-card transition-[width] duration-200',
        effectiveCollapsed ? 'w-16' : 'w-60',
      )}
    >
      {/* Brand header */}
      <div
        className={cn(
          'flex h-14 items-center border-b border-border px-3',
          effectiveCollapsed ? 'justify-center' : 'justify-between',
        )}
      >
        {!effectiveCollapsed && (
          <span className="text-sm font-bold tracking-tight text-foreground">
            License Manager
          </span>
        )}
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label={effectiveCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={cn(
            'flex size-7 items-center justify-center rounded-md text-muted-foreground',
            'transition-colors hover:bg-accent hover:text-accent-foreground',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          )}
        >
          {effectiveCollapsed ? (
            <ChevronRight className="size-4" aria-hidden="true" />
          ) : (
            <ChevronLeft className="size-4" aria-hidden="true" />
          )}
        </button>
      </div>

      {/* Primary nav */}
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        <ul className="space-y-0.5">
          {TOP_NAV.map((item) => (
            <SidebarLink key={item.path} item={item} collapsed={effectiveCollapsed} onLinkClick={onLinkClick} />
          ))}

          {/* Divider before groups */}
          <li aria-hidden="true" className="my-2 border-t border-border" />

          {GROUPS.map((group) => (
            <CollapsibleGroup key={group.prefix} group={group} collapsed={effectiveCollapsed} onLinkClick={onLinkClick} />
          ))}

          {/* Divider before Tasks */}
          <li aria-hidden="true" className="my-2 border-t border-border" />

          <SidebarLink item={TASKS_ITEM} collapsed={effectiveCollapsed} onLinkClick={onLinkClick} />
        </ul>
      </nav>

      {/* Bottom: Settings */}
      <div className="border-t border-border px-2 py-3">
        <ul className="space-y-0.5">
          <SidebarLink
            item={{ label: 'Settings', path: ROUTES.SETTINGS, icon: Settings }}
            collapsed={effectiveCollapsed}
            onLinkClick={onLinkClick}
          />
        </ul>
      </div>
    </aside>
  )
}
