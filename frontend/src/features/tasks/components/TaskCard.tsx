import { useState, useRef, useEffect } from 'react'
import { Check, ChevronDown, MessageSquare, OctagonX, RotateCcw, Trash2 } from 'lucide-react'
import { cn } from '@/shared/utils/cn'
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

// ── Inline reject modal ─────────────────────────────────────────────────────
// Uses a fixed overlay so it stacks correctly inside the drawer (z-[1070]).
interface RejectModalProps {
  taskTitle: string
  onConfirm: (reason: string) => void
  onCancel: () => void
  isPending: boolean
}

function RejectModal({ taskTitle, onConfirm, onCancel, isPending }: RejectModalProps) {
  const [reason, setReason] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onCancel])

  return (
    <div
      className="fixed inset-0 z-[1070] flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onCancel() }}
      role="dialog"
      aria-modal="true"
      aria-label="Reject task"
    >
      <div className="w-[min(400px,90vw)] rounded-lg border border-border bg-card p-5 shadow-xl">
        <h2 className="mb-1 text-base font-semibold">Reject task</h2>
        <p className="mb-3 text-sm text-muted-foreground line-clamp-2">{taskTitle}</p>

        <label htmlFor="reject-reason" className="mb-1.5 block text-xs font-medium text-muted-foreground">
          Reason <span className="text-muted-foreground">(optional)</span>
        </label>
        <textarea
          id="reject-reason"
          ref={textareaRef}
          className="h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
          placeholder="Explain why this task is being rejected…"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />

        <div className="mt-3 flex justify-end gap-2">
          <button
            type="button"
            className="rounded border border-border bg-card px-3 py-1.5 text-sm font-medium hover:bg-muted"
            onClick={onCancel}
            disabled={isPending}
          >
            Cancel
          </button>
          <button
            type="button"
            className="rounded border border-destructive/40 bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
            onClick={() => onConfirm(reason)}
            disabled={isPending}
          >
            {isPending ? 'Rejecting…' : 'Reject task'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── TaskCard ────────────────────────────────────────────────────────────────
export function TaskCard({ task, currentUserId, isExpanded, onToggleExpand, users }: Props) {
  const [rejectModalOpen, setRejectModalOpen] = useState(false)

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

  // Checkbox quick-toggle (keep existing UX shortcut)
  const handleCheckboxToggle = () => {
    if (task.status === 'completed') {
      reopen.mutate(task.id)
    } else {
      complete.mutate(task.id)
    }
  }

  // Explicit Complete button with confirm
  const handleComplete = () => {
    if (!window.confirm('Mark this task as complete?')) return
    complete.mutate(task.id)
  }

  // Reject via modal
  const handleRejectConfirm = (reason: string) => {
    reject.mutate(
      { id: task.id, reason },
      { onSuccess: () => setRejectModalOpen(false) },
    )
  }

  const handleDelete = () => {
    if (!window.confirm('Delete this task?')) return
    del.mutate(task.id)
  }

  const remarksCount = task.remarks.length

  const assigneeLabel = task.assigned_to_username ?? task.created_by_username ?? 'self'
  const assigneeIsSelf = task.assigned_to === currentUserId || (!task.assigned_to && isMine)

  return (
    <>
      {rejectModalOpen && (
        <RejectModal
          taskTitle={task.title}
          onConfirm={handleRejectConfirm}
          onCancel={() => setRejectModalOpen(false)}
          isPending={reject.isPending}
        />
      )}

      <div className="border-b border-border px-5 py-3">
        <div className="flex items-start gap-2">
          {/* Completion checkbox — quick toggle */}
          <input
            type="checkbox"
            className="mt-1 shrink-0 cursor-pointer"
            checked={task.status === 'completed'}
            onChange={handleCheckboxToggle}
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
          <div className="flex shrink-0 flex-wrap gap-1">
            {/* Remarks badge */}
            <button
              type="button"
              className={cn(
                'relative rounded border border-border bg-card p-1.5 hover:bg-muted',
                isExpanded && remarksCount > 0 && 'border-indigo-300 bg-indigo-50 text-indigo-700',
              )}
              onClick={onToggleExpand}
              title={remarksCount > 0 ? `${remarksCount} remark${remarksCount !== 1 ? 's' : ''}` : 'Remarks'}
              aria-label={`Remarks${remarksCount > 0 ? ` (${remarksCount})` : ''}`}
            >
              <MessageSquare className="size-4" />
              {remarksCount > 0 && (
                <span className="absolute -right-1.5 -top-1.5 flex size-4 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-semibold leading-none text-white">
                  {remarksCount > 9 ? '9+' : remarksCount}
                </span>
              )}
            </button>

            {/* Expand/collapse chevron */}
            <button
              type="button"
              className="rounded border border-border bg-card p-1.5 hover:bg-muted"
              onClick={onToggleExpand}
              title="Details"
              aria-label={isExpanded ? 'Collapse' : 'Expand'}
              aria-expanded={isExpanded}
            >
              <ChevronDown
                className={cn('size-4 transition-transform', isExpanded && 'rotate-180')}
              />
            </button>

            {/* Complete button — shown for non-completed tasks */}
            {task.status !== 'completed' && (
              <button
                type="button"
                className="rounded border border-green-300 bg-green-50 p-1.5 text-green-700 hover:bg-green-100 disabled:opacity-50"
                onClick={handleComplete}
                disabled={complete.isPending}
                title="Mark complete"
                aria-label="Mark task complete"
              >
                <Check className="size-4" />
              </button>
            )}

            {/* Reject button — shown for open tasks */}
            {!isClosed && (
              <button
                type="button"
                className="rounded border border-yellow-300 bg-yellow-50 p-1.5 text-yellow-700 hover:bg-yellow-100 disabled:opacity-50"
                onClick={() => setRejectModalOpen(true)}
                disabled={reject.isPending}
                title="Reject"
                aria-label="Reject task"
              >
                <OctagonX className="size-4" />
              </button>
            )}

            {/* Reopen button — shown for completed/rejected tasks */}
            {isClosed && (
              <button
                type="button"
                className="rounded border border-amber-300 bg-amber-50 p-1.5 text-amber-700 hover:bg-amber-100 disabled:opacity-50"
                onClick={() => reopen.mutate(task.id)}
                disabled={reopen.isPending}
                title="Reopen"
                aria-label="Reopen task"
              >
                <RotateCcw className="size-4" />
              </button>
            )}

            {/* Delete button — only task creator */}
            {isMine && (
              <button
                type="button"
                className="rounded border border-destructive/30 bg-destructive/10 p-1.5 text-destructive hover:bg-destructive/20 disabled:opacity-50"
                onClick={handleDelete}
                disabled={del.isPending}
                title="Delete"
                aria-label="Delete task"
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

            <TaskRemarks task={task} />
          </div>
        )}
      </div>
    </>
  )
}
