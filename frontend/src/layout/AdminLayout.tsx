/**
 * AdminLayout — shell for all authenticated pages.
 *
 * Structure:
 *   <aside> Sidebar (collapsible, fixed height)
 *   <main>
 *     <TopBar /> (breadcrumb + user controls)
 *     <div> {children} / <Outlet /> </div>
 *   </main>
 *
 * Uses react-router's <Outlet /> when rendered as a layout route
 * (no children prop needed), and also accepts an explicit children
 * prop for flexibility.
 */

import { Outlet } from 'react-router-dom'
import { Sidebar } from '@/shared/ui/Sidebar'
import { TopBar } from '@/shared/ui/TopBar'

interface AdminLayoutProps {
  children?: React.ReactNode
}

export function AdminLayout({ children }: AdminLayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar />

        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 overflow-y-auto p-6 focus-visible:outline-none"
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
