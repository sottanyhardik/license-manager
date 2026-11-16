import api from "./axios";
import type { AxiosResponse } from "axios";
import type { AssignableUser, Task, TaskId, TaskListParams, TaskListResponse, TaskPayload, TaskRemark } from "@/types/api/tasks";

export const TASK_STATUS = {
    PENDING: "pending",
    IN_PROGRESS: "in_progress",
    COMPLETED: "completed",
    REJECTED: "rejected",
};

export const TASK_PRIORITY = {
    LOW: "low",
    NORMAL: "normal",
    HIGH: "high",
};

export const listTasks = (params: TaskListParams = {}): Promise<TaskListResponse> =>
    api.get("tasks/", { params }).then(r => r.data);

export const createTask = (payload: TaskPayload): Promise<Task> =>
    api.post("tasks/", payload).then(r => r.data);

export const updateTask = (id: TaskId, payload: TaskPayload): Promise<Task> =>
    api.patch(`tasks/${id}/`, payload).then(r => r.data);

export const deleteTask = (id: TaskId): Promise<AxiosResponse> =>
    api.delete(`tasks/${id}/`);

export const completeTask = (id: TaskId): Promise<Task> =>
    api.post(`tasks/${id}/complete/`).then(r => r.data);

export const rejectTask = (id: TaskId, reason = ""): Promise<Task> =>
    api.post(`tasks/${id}/reject/`, { reason }).then(r => r.data);

export const reopenTask = (id: TaskId): Promise<Task> =>
    api.post(`tasks/${id}/reopen/`).then(r => r.data);

export const addRemark = (id: TaskId, text: string): Promise<TaskRemark> =>
    api.post(`tasks/${id}/remarks/`, { text }).then(r => r.data);

export const listRemarks = (id: TaskId): Promise<TaskRemark[]> =>
    api.get(`tasks/${id}/remarks/`).then(r => r.data);

export const listAssignableUsers = (): Promise<AssignableUser[]> =>
    api.get("tasks/assignable-users/").then(r => r.data);
