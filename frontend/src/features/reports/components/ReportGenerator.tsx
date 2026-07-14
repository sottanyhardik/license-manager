import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/shared/ui/button'
import { ReportTaskStatus } from './ReportTaskStatus'
import { useReportTaskStatus } from '../queries'

interface Props {
  title: string
  description?: string
  onGenerate: () => Promise<string> // returns task_id
  children?: React.ReactNode
}

export function ReportGenerator({ title, description, onGenerate, children }: Props) {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)

  const { data: taskData } = useReportTaskStatus(taskId)

  async function handleGenerate() {
    setIsGenerating(true)
    try {
      const id = await onGenerate()
      setTaskId(id)
    } catch {
      toast.error('Failed to start report generation.')
    } finally {
      setIsGenerating(false)
    }
  }

  const isPolling =
    taskData?.status === 'pending' || taskData?.status === 'running'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {description && (
          <p className="text-muted-foreground mt-1">{description}</p>
        )}
      </div>

      <div className="rounded-lg border p-6 space-y-4">
        {children}

        <div className="flex items-center gap-4 pt-2">
          <Button
            onClick={handleGenerate}
            disabled={isGenerating || !!isPolling}
          >
            {isGenerating || isPolling ? 'Generating...' : 'Generate Report'}
          </Button>

          {taskId && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setTaskId(null)}
              disabled={!!isPolling}
            >
              Reset
            </Button>
          )}
        </div>

        {taskData && (
          <ReportTaskStatus task={taskData} />
        )}
      </div>
    </div>
  )
}
