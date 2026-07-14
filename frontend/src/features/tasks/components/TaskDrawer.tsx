import { useState, useMemo } from 'react'
import { CheckSquare, X } from 'lucide-react'
import { useTasks, useAssignableUsers } from '../queries'
import { useCreateTask } from '../mutations'
import { TaskCard } from './TaskCard'
import type { Task, TaskListParams, TaskStatus } from '../types'

interface Props {
  show: boolean
  onClose: () => void
  currentUserId: number | null
}

const STATUS_FILTERS = [
  { value: 'open', label: 'Open' },
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'rejected', label: 'Rejected' },
]

export function TaskDrawer({ show, onClose, currentUserId }: Props) {
  const [statusFilter, setStatusFilter] = useState<string>('open')
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<number | null>(null)
  const [titleDraft, setTitleDraft] = useState('')

  const queryParams = useMemo<TaskListParams>(() => {
    const p: TaskListParams = {}
    if (search.trim()) p.search = search.trim()
    if (statusFilter && statusFilter !== 'open') p.status = statusFilter as TaskStatus
    return p
  }, [search, statusFilter])

  const { data: rawTasks = [], isLoading, isError } = useTasks(queryParams)
  const { data: users = [] } = useAssignableUsers()
  const createTask = useCreateTask()

  // Client-side "open" filter: pending + in_progress + bounced-back-rejected
  const tasks = useMemo<Task[]>(() => {
    if (statusFilter !== 'open') return rawTasks
    return rawTasks.filter((t) => {
      if (t.status === 'pending' || t.status === 'in_progress') return true
      if (
        t.status === 'rejected' &&
        currentUserId !== null &&
        t.created_by === currentUserId &&
        t.rejected_by !== null &&
        t.rejected_by !== currentUserId
      ) return true
      return false
    })
  }, [rawTasks, statusFilter, currentUserId])

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    const title = titleDraft.trim()
    if (!title) return
    createTask.mutate({ title }, { onSuccess: () => setTitleDraft('') })
  }

  if (!show) return null

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="fixed inset-0 z-[1050] bg-black/30 backdrop-blur-sm"
      />

      {/* Panel */}
      <aside
        role="dialog"
        aria-label="Tasks"
        className="fixed inset-y-0 right-0 z-[1060] flex w-[min(440px,100vw)] flex-col border-l border-border bg-card shadow-xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-lg bg-indigo-50 text-primary">
              <CheckSquare className="size-4" />
            </span>
            <span className="text-base font-semibold">Tasks</span>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="flex size-8 items-center justify-center rounded-lg border border-border hover:bg-muted"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Quick create */}
        <form
          onSubmit={handleCreate}
          className="border-b border-border bg-muted/40 px-5 py-3"
        >
          <div className="flex gap-2">
            <input
              className="h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
              placeholder="New task title…"
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
            />
            <button
              type="submit"
              disabled={createTask.isPending || !titleDraft.trim()}
              className="rounded border border-border bg-card px-3 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
            >
              Add
            </button>
          </div>
        </form>

        {/* Filters */}
        <div className="flex items-center gap-2 border-b border-border px-5 py-2">
          <input
            className="h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
            placeholder="Search…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="h-8 w-32 shrink-0 rounded-md border border-input bg-card px-2 text-sm outline-none"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {STATUS_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="space-y-2 p-5">
              <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
              <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
            </div>
          )}
          {isError && (
            <div className="p-5 text-center text-sm text-destructive" role="alert">
              Failed to load tasks. Please try again.
            </div>
          )}
          {!isLoading && !isError && tasks.length === 0 && (
            <div className="flex flex-col items-center gap-2 p-10 text-center text-muted-foreground">
              <CheckSquare className="size-9 opacity-40" />
              <p className="text-sm font-medium">No tasks yet</p>
              <p className="text-xs">Add one above.</p>
            </div>
          )}
          {!isError && tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              currentUserId={currentUserId}
              isExpanded={expanded === task.id}
              onToggleExpand={() => setExpanded(expanded === task.id ? null : task.id)}
              users={users}
            />
          ))}
        </div>
      </aside>
    </>
  )
}
