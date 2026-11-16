import type { ApiId, ApiParams, ApiRecord, PaginatedResponse } from "./common";

export type TaskListParams = ApiParams;
/** Create/patch body; fields as sent by TaskDrawer (title, description, priority, assigned_to, due_date, ...). */
export type TaskPayload = ApiRecord;
export type TaskId = ApiId;

export interface TaskRemark {
    id: number;
    text: string;
    created_by_username?: string;
    created_on?: string;
}

/** Task row as consumed by TaskDrawer (fields not listed are passed through untouched). */
export interface Task {
    id: number;
    title: string;
    description?: string | null;
    status: string;
    priority: string;
    due_date?: string | null;
    created_by?: number | null;
    created_by_username?: string | null;
    assigned_to?: number | null;
    assigned_to_username?: string | null;
    assigned_on?: string | null;
    rejected_by?: number | null;
    rejected_by_username?: string | null;
    rejection_reason?: string | null;
    remarks?: TaskRemark[];
}

export interface AssignableUser {
    id: number;
    username: string;
    first_name?: string;
    last_name?: string;
}

/** `GET tasks/` may return a bare list or a DRF page envelope. */
export type TaskListResponse = Task[] | PaginatedResponse<Task>;
