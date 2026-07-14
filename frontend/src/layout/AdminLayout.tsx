/**
 * AdminLayout — shell for all authenticated pages.
 *
 * Structure:
 *   <aside> Sidebar (collapsible on desktop; mobile drawer with overlay)
 *   <main>
 *     <TopBar /> (breadcrumb + user controls)
 *     <div> {children} / <Outlet /> </div>
 *   </main>
 *
 * Mobile behaviour (< md / 768 px):
 *   - Sidebar is a fixed drawer that slides in from the left.
 *   - A semi-transparent backdrop covers main content while drawer is open.
 *   - Drawer closes on: nav-link click, backdrop click, Escape key, route change.
 *
 * Desktop behaviour (≥ md):
 *   - Sidebar is static (in-flow), respects the user's collapsed preference.
 *
 * Uses react-router's <Outlet /> when rendered as a layout route
 * (no children prop needed), and also accepts an explicit children
 * prop for flexibility.
 */

import { useState, useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { cn } from '@/shared/utils/cn'
import { Sidebar } from '@/shared/ui/Sidebar'
import { TopBar } from '@/shared/ui/TopBar'

interface AdminLayoutProps {
  children?: React.ReactNode
}

export function AdminLayout({ children }: AdminLayoutProps) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  // Close mobile drawer on Escape key
  useEffect(() => {
    if (!mobileOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [mobileOpen])

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Mobile overlay backdrop — sits between sidebar (z-30) and content (z-0) */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 md:hidden"
          aria-hidden="true"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/*
       * Sidebar wrapper:
       *   Mobile  — fixed drawer, slides in/out from left, above backdrop (z-30)
       *   Desktop — static (in-flow), no z-index needed
       */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-30 md:static md:z-auto',
          'transition-transform duration-200 ease-in-out md:transition-none',
          mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
        )}
      >
        <Sidebar
          onLinkClick={() => setMobileOpen(false)}
          forceExpanded={mobileOpen}
        />
      </div>

      {/* Main content column */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        <TopBar
          onMobileMenuToggle={() => setMobileOpen((v) => !v)}
          mobileMenuOpen={mobileOpen}
        />

        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 overflow-y-auto p-4 md:p-6 focus-visible:outline-none"
        >
          {/* ARIA live region for async form validation announcements */}
          <div
            id="form-announcements"
            role="status"
            aria-live="polite"
            aria-atomic="true"
            className="sr-only"
          />
          {children ?? <Outlet />}
        </main>
      </div>
    </div>
  )
}
