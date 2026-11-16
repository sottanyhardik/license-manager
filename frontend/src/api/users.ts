import type { AxiosResponse } from 'axios';
import api from './axios';
import type { UserId, UserListParams, UserPayload } from '@/types/api/users';

// `signal` is optional so older callers retain their exact API behaviour while
// React Query list screens can cancel an obsolete filter request.
export const listUsers = (params?: UserListParams, signal?: AbortSignal): Promise<AxiosResponse> =>
    api.get('auth/users/', {params, signal});
export const getUser = (id: UserId): Promise<AxiosResponse> => api.get(`auth/users/${id}/`);
export const createUser = (data: UserPayload): Promise<AxiosResponse> => api.post('auth/users/', data);
export const updateUser = (id: UserId, data: UserPayload): Promise<AxiosResponse> =>
    api.put(`auth/users/${id}/`, data);
export const deleteUser = (id: UserId): Promise<AxiosResponse> => api.delete(`auth/users/${id}/`);
export const resetPassword = (id: UserId, password: string): Promise<AxiosResponse> =>
    api.post(`auth/users/${id}/reset-password/`, {password});
export const getAvailableRoles = (): Promise<AxiosResponse> => api.get('auth/users/available-roles/');
