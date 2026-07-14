import { Loader2, CheckCircle, XCircle, Download } from 'lucide-react'
import type { ReportTask } from '../types'

interface Props {
  task: ReportTask | undefined
}

export function ReportTaskStatus({ task }: Props) {
  if (!task) return null

  if (task.status === 'pending' || task.status === 'running') {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        <span>{task.status === 'pending' ? 'Queued...' : 'Generating report...'}</span>
      </div>
    )
  }

  if (task.status === 'done' && task.file_url) {
    return (
      <div className="flex items-center gap-2">
        <CheckCircle className="h-4 w-4 text-green-600" aria-hidden="true" />
        <span className="text-green-700">Report ready</span>
        <a
          href={task.file_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          <Download className="h-3.5 w-3.5" aria-hidden="true" />
          Download
        </a>
      </div>
    )
  }

  if (task.status === 'error') {
    return (
      <div className="flex items-center gap-2 text-destructive" role="alert">
        <XCircle className="h-4 w-4" aria-hidden="true" />
        <span>Report generation failed. Please try again.</span>
      </div>
    )
  }

  return null
}
