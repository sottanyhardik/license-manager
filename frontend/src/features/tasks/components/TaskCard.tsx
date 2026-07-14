import { ChevronDown, OctagonX, Trash2 } from 'lucide-react'
import { TaskStatusBadge } from './TaskStatusBadge'
import { TaskRemarks } from './TaskRemarks'
import { useCompleteTask, useRejectTask, useReopenTask, useDeleteTask, useUpdateTask } from '../mutations'
import type { Task, AssignableUser } from '../types'

interface Props {
  task: Task
  currentUserId: number | null
  isExpanded: boolean
  onToggleExpand: () => void
  users: AssignableUser[]
}

function formatDate(value: string | null | undefined) {
  if (!value) return ''
  try { return new Date(value).toLocaleString() } catch { return value }
}

export function TaskCard({ task, currentUserId, isExpanded, onToggleExpand, users }: Props) {
  const complete = useCompleteTask()
  const reject = useRejectTask()
  const reopen = useReopenTask()
  const del = useDeleteTask()
  const update = useUpdateTask(task.id)

  const isMine = currentUserId !== null && task.created_by === currentUserId
  const isClosed = task.status === 'completed' || task.status === 'rejected'
  const isBouncedBack =
    task.status === 'rejected' &&
    isMine &&
    task.rejected_by !== null &&
    task.rejected_by !== currentUserId

  const handleComplete = () => {
    if (task.status === 'completed') {
      reopen.mutate(task.id)
    } else {
      complete.mutate(task.id)
    }
  }

  const handleReject = () => {
    const reason = window.prompt('Reason for rejection (optional):', '') ?? ''
    reject.mutate({ id: task.id, reason })
  }

  const handleDelete = () => {
    if (!window.confirm('Delete this task?')) return
    del.mutate(task.id)
  }

  const assigneeLabel = task.assigned_to_username ?? task.created_by_username ?? 'self'
  const assigneeIsSelf = task.assigned_to === currentUserId || (!task.assigned_to && isMine)

  return (
    <div className="border-b border-border px-5 py-3">
      <div className="flex items-start gap-2">
        {/* Completion checkbox */}
        <input
          type="checkbox"
          className="mt-1 shrink-0 cursor-pointer"
          checked={task.status === 'completed'}
          onChange={handleComplete}
          title={task.status === 'completed' ? 'Reopen' : 'Mark complete'}
        />

        <div className="min-w-0 flex-1">
          {/* Title row */}
          <div className="flex flex-wrap items-center gap-2">
            <span
              className="font-medium"
              style={{ textDecoration: task.status === 'completed' ? 'line-through' : 'none' }}
            >
              {task.title}
            </span>
            <TaskStatusBadge status={task.status} />
            {isBouncedBack && (
              <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800">
                Bounced back
              </span>
            )}
            {task.priority === 'high' && (
              <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                High
              </span>
            )}
          </div>

          {/* Meta line */}
          <p className="mt-0.5 text-xs text-muted-foreground">
            {'->'} <strong>{assigneeIsSelf ? `${assigneeLabel} (you)` : assigneeLabel}</strong>
            {task.assigned_on && <span> · assigned {formatDate(task.assigned_on)}</span>}
            {!isMine && task.created_by_username && <span> · by {task.created_by_username}</span>}
            {task.due_date && <span> · due {task.due_date}</span>}
          </p>

          {/* Bounced-back callout */}
          {isBouncedBack && (
            <div className="mt-1 rounded border border-yellow-300 bg-yellow-50 p-2 text-xs">
              <strong>Rejected by {task.rejected_by_username ?? 'assignee'}</strong>
              {task.rejection_reason
                ? <span>: {task.rejection_reason}</span>
                : <span> (no reason given)</span>
              }
              <button
                type="button"
                className="ml-2 cursor-pointer text-xs text-primary underline-offset-2 hover:underline"
                onClick={() => reopen.mutate(task.id)}
              >
                Reopen
              </button>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex shrink-0 gap-1">
          <button
            className="rounded border border-border bg-card p-1.5 hover:bg-muted"
            onClick={onToggleExpand}
            title="Details"
          >
            <ChevronDown
              className="size-4 transition-transform"
              style={{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
            />
          </button>
          {!isClosed && (
            <button
              className="rounded border border-yellow-300 bg-yellow-50 p-1.5 text-yellow-700 hover:bg-yellow-100"
              onClick={handleReject}
              title="Reject"
            >
              <OctagonX className="size-4" />
            </button>
          )}
          {isMine && (
            <button
              className="rounded border border-destructive/30 bg-destructive/10 p-1.5 text-destructive hover:bg-destructive/20"
              onClick={handleDelete}
              title="Delete"
            >
              <Trash2 className="size-4" />
            </button>
          )}
        </div>
      </div>

      {/* Expanded detail panel */}
      {isExpanded && (
        <div className="ml-6 mt-3 space-y-3">
          <textarea
            className="h-16 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
            placeholder="Description"
            defaultValue={task.description}
            onBlur={(e) => {
              if (e.target.value !== task.description) {
                update.mutate({ description: e.target.value })
              }
            }}
          />

          <div className="flex flex-wrap gap-2">
            <select
              className="h-8 flex-1 rounded-md border border-input bg-card px-2 text-sm outline-none"
              value={task.priority}
              onChange={(e) => update.mutate({ priority: e.target.value as 'low' | 'normal' | 'high' })}
            >
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
            </select>

            <input
              type="date"
              className="h-8 flex-1 rounded-md border border-input bg-card px-2 text-sm outline-none"
              value={task.due_date ?? ''}
              onChange={(e) => update.mutate({ due_date: e.target.value || null })}
            />

            <select
              className="h-8 w-full rounded-md border border-input bg-card px-2 text-sm outline-none"
              value={task.assigned_to ?? ''}
              onChange={(e) => update.mutate({ assigned_to: e.target.value ? parseInt(e.target.value, 10) : null })}
            >
              <option value="">Unassigned (myself)</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.username}</option>
              ))}
            </select>
          </div>

          <TaskRemarks task={task} currentUserId={currentUserId} />
        </div>
      )}
    </div>
  )
}
