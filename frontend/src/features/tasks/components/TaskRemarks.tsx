import { useState } from 'react'
import { useAddRemark } from '../mutations'
import type { Task } from '../types'

interface Props {
  task: Task
  currentUserId: number | null
}

export function TaskRemarks({ task }: Props) {
  const [draft, setDraft] = useState('')
  const addRemark = useAddRemark(task.id)

  const handleSubmit = () => {
    const text = draft.trim()
    if (!text) return
    addRemark.mutate(text, { onSuccess: () => setDraft('') })
  }

  return (
    <div className="rounded border border-border bg-muted/40 p-3">
      <p className="mb-2 text-xs font-semibold text-muted-foreground">Remarks</p>

      {/* Add remark */}
      <div className="mb-3 flex gap-2">
        <input
          className="h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
          placeholder="Add a remark…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }}
        />
        <button
          type="button"
          className="rounded border border-border bg-card px-3 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
          onClick={handleSubmit}
          disabled={addRemark.isPending || !draft.trim()}
        >
          Add
        </button>
      </div>

      {/* Thread */}
      {task.remarks.length === 0 && (
        <p className="text-xs text-muted-foreground">No remarks yet.</p>
      )}
      <div className="flex flex-col gap-2">
        {task.remarks.map((r) => (
          <div key={r.id} className="rounded bg-card px-3 py-2 text-sm">
            <p>{r.text}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {r.created_by_username ?? 'Unknown'} · {new Date(r.created_on).toLocaleString()}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
