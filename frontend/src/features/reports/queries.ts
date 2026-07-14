import { useQuery } from '@tanstack/react-query'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import type { ReportTask } from './types'

export function useReportTaskStatus(taskId: string | null) {
  return useQuery<ReportTask>({
    queryKey: ['report-task', taskId],
    queryFn: async () => {
      const { data } = await apiClient.get<ReportTask>(
        ENDPOINTS.REPORTS.TASK_STATUS(taskId!),
      )
      return data
    },
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'done' || status === 'error') return false
      return 2000
    },
  })
}
