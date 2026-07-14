// Types for the Tasks feature — shapes match /api/v1/tasks/* DRF responses.

export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'rejected'
export type TaskPriority = 'low' | 'normal' | 'high'

export interface TaskRemark {
  id: number
  task: number
  text: string
  created_by: number | null
  created_by_username: string | null
  created_on: string
}

export interface Task {
  id: number
  title: string
  description: string
  status: TaskStatus
  priority: TaskPriority
  assigned_to: number | null
  assigned_to_username: string | null
  assigned_on: string | null
  due_date: string | null
  completed_on: string | null
  rejected_by: number | null
  rejected_by_username: string | null
  rejection_reason: string
  created_by: number | null
  created_by_username: string | null
  created_on: string
  modified_on: string
  remarks: TaskRemark[]
}

export interface AssignableUser {
  id: number
  username: string
  first_name: string
  last_name: string
}

export interface TaskFormValues {
  title: string
  description?: string
  priority?: TaskPriority
  assigned_to?: number | null
  due_date?: string | null
}

export interface TaskListParams {
  status?: TaskStatus | ''
  priority?: TaskPriority
  assigned_to?: number
  search?: string
  ordering?: string
}
