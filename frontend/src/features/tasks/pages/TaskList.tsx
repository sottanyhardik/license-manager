import { useState } from 'react'
import { TaskDrawer } from '../components/TaskDrawer'

// Placeholder page — the primary UX is the drawer.
// This page exists for direct /tasks routing and could show a table later.
export default function TaskList() {
  const [drawerOpen, setDrawerOpen] = useState(true)

  return (
    <div className="p-8">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tasks</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Track and manage your workflow tasks.
          </p>
        </div>
        <button
          className="rounded border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-muted"
          onClick={() => setDrawerOpen(true)}
        >
          Open Tasks Panel
        </button>
      </div>

      <TaskDrawer
        show={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        currentUserId={null}
      />
    </div>
  )
}
