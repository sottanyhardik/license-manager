// TanStack Query hooks for the tasks feature.
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import type { Task, AssignableUser, TaskListParams } from './types'

export const TASKS_KEY = (params?: TaskListParams) => ['tasks', params] as const
export const ASSIGNABLE_USERS_KEY = ['tasks-assignable-users'] as const

export function useTasks(params?: TaskListParams): UseQueryResult<Task[]> {
  return useQuery({
    queryKey: TASKS_KEY(params),
    queryFn: async () => {
      const { data } = await apiClient.get<Task[]>(ENDPOINTS.TASKS.LIST, { params })
      return Array.isArray(data) ? data : (data as { results?: Task[] }).results ?? []
    },
  })
}

export function useTask(id: number | null): UseQueryResult<Task> {
  return useQuery({
    queryKey: ['tasks', id],
    queryFn: async () => {
      const { data } = await apiClient.get<Task>(ENDPOINTS.TASKS.DETAIL(id!))
      return data
    },
    enabled: !!id,
  })
}

export function useAssignableUsers(): UseQueryResult<AssignableUser[]> {
  return useQuery({
    queryKey: ASSIGNABLE_USERS_KEY,
    queryFn: async () => {
      const { data } = await apiClient.get<AssignableUser[]>(ENDPOINTS.TASKS.ASSIGNABLE_USERS)
      return data
    },
    staleTime: Infinity,
  })
}
