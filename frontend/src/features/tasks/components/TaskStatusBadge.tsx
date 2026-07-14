import type { TaskStatus } from '../types'

const LABEL: Record<TaskStatus, string> = {
  pending: 'Pending',
  in_progress: 'In Progress',
  completed: 'Completed',
  rejected: 'Rejected',
}

const CLASS: Record<TaskStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  in_progress: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  rejected: 'bg-gray-100 text-gray-600',
}

interface Props {
  status: TaskStatus
}

export function TaskStatusBadge({ status }: Props) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${CLASS[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {LABEL[status] ?? status}
    </span>
  )
}
