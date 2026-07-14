// TanStack Query mutation hooks for the tasks feature.
import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { toast } from 'sonner'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { normaliseApiErrorString } from '@/shared/utils/errors'
import type { Task, TaskRemark, TaskFormValues } from './types'

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ['tasks'] })
}

export function useCreateTask(): UseMutationResult<Task, Error, TaskFormValues> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (values) => {
      const { data } = await apiClient.post<Task>(ENDPOINTS.TASKS.LIST, values)
      return data
    },
    onSuccess: () => { invalidate(qc); toast.success('Task created.') },
    onError: (err) => { toast.error(normaliseApiErrorString(err)) },
  })
}

export function useUpdateTask(id: number): UseMutationResult<Task, Error, Partial<TaskFormValues>> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (values) => {
      const { data } = await apiClient.patch<Task>(ENDPOINTS.TASKS.DETAIL(id), values)
      return data
    },
    onSuccess: () => { invalidate(qc) },
    onError: (err) => { toast.error(normaliseApiErrorString(err)) },
  })
}

export function useDeleteTask(): UseMutationResult<void, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => { await apiClient.delete(ENDPOINTS.TASKS.DETAIL(id)) },
    onSuccess: () => { invalidate(qc); toast.success('Task deleted.') },
    onError: (err) => { toast.error(normaliseApiErrorString(err)) },
  })
}

export function useCompleteTask(): UseMutationResult<Task, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => {
      const { data } = await apiClient.post<Task>(ENDPOINTS.TASKS.COMPLETE(id))
      return data
    },
    onSuccess: () => { invalidate(qc); toast.success('Task completed.') },
    onError: (err) => { toast.error(normaliseApiErrorString(err)) },
  })
}

export function useRejectTask(): UseMutationResult<Task, Error, { id: number; reason: string }> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, reason }) => {
      const { data } = await apiClient.post<Task>(ENDPOINTS.TASKS.REJECT(id), { reason })
      return data
    },
    onSuccess: () => { invalidate(qc); toast.success('Task rejected.') },
    onError: (err) => { toast.error(normaliseApiErrorString(err)) },
  })
}

export function useReopenTask(): UseMutationResult<Task, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => {
      const { data } = await apiClient.post<Task>(ENDPOINTS.TASKS.REOPEN(id))
      return data
    },
    onSuccess: () => { invalidate(qc); toast.success('Task reopened.') },
    onError: (err) => { toast.error(normaliseApiErrorString(err)) },
  })
}

export function useAddRemark(taskId: number): UseMutationResult<TaskRemark, Error, string> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (text) => {
      const { data } = await apiClient.post<TaskRemark>(ENDPOINTS.TASKS.REMARKS(taskId), { text })
      return data
    },
    onSuccess: () => { invalidate(qc) },
    onError: (err) => { toast.error(normaliseApiErrorString(err)) },
  })
}
