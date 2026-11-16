import api from "./axios";

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

export const listTasks = (params = {}) =>
    api.get("tasks/", { params }).then(r => r.data);

export const createTask = (payload) =>
    api.post("tasks/", payload).then(r => r.data);

export const updateTask = (id, payload) =>
    api.patch(`tasks/${id}/`, payload).then(r => r.data);

export const deleteTask = (id) =>
    api.delete(`tasks/${id}/`);

export const completeTask = (id) =>
    api.post(`tasks/${id}/complete/`).then(r => r.data);

export const rejectTask = (id, reason = "") =>
    api.post(`tasks/${id}/reject/`, { reason }).then(r => r.data);

export const reopenTask = (id) =>
    api.post(`tasks/${id}/reopen/`).then(r => r.data);

export const addRemark = (id, text) =>
    api.post(`tasks/${id}/remarks/`, { text }).then(r => r.data);

export const listRemarks = (id) =>
    api.get(`tasks/${id}/remarks/`).then(r => r.data);

export const listAssignableUsers = () =>
    api.get("tasks/assignable-users/").then(r => r.data);
