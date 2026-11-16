import api from './axios';

// `signal` is optional so older callers retain their exact API behaviour while
// React Query list screens can cancel an obsolete filter request.
export const listUsers = (params, signal) => api.get('auth/users/', {params, signal});
export const getUser = (id) => api.get(`auth/users/${id}/`);
export const createUser = (data) => api.post('auth/users/', data);
export const updateUser = (id, data) => api.put(`auth/users/${id}/`, data);
export const deleteUser = (id) => api.delete(`auth/users/${id}/`);
export const resetPassword = (id, password) =>
    api.post(`auth/users/${id}/reset-password/`, {password});
export const getAvailableRoles = () => api.get('auth/users/available-roles/');
