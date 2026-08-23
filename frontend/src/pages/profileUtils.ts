import type { AuthUser } from '../types';

export type ProfileFormData = { first_name: string; last_name: string; email: string };
export type ProfilePayload = { first_name: string; last_name: string; email: string | null };

export function getProfileFormData(user: AuthUser | null): ProfileFormData {
    return { first_name: user?.first_name ?? '', last_name: user?.last_name ?? '', email: user?.email ?? '' };
}

export function buildProfilePayload(formData: ProfileFormData): ProfilePayload {
    const email = formData.email.trim();
    return { first_name: formData.first_name.trim(), last_name: formData.last_name.trim(), email: email || null };
}

function getFieldError(data: unknown, field: string): string | null {
    if (!data || typeof data !== 'object' || !(field in data)) return null;
    const value = (data as Record<string, unknown>)[field];
    if (typeof value === 'string') return value.trim() || null;
    if (Array.isArray(value)) return value.find((item): item is string => typeof item === 'string' && item.trim().length > 0)?.trim() ?? null;
    return null;
}

export function getProfileErrorMessage(error: unknown): string {
    const data = error && typeof error === 'object' && 'response' in error ? (error as { response?: { data?: unknown } }).response?.data : null;
    if (data && typeof data === 'object') {
        const detail = getFieldError(data, 'detail');
        if (detail) return detail;
        const fieldError = ['email', 'first_name', 'last_name', 'non_field_errors'].map((field) => getFieldError(data, field)).find((message): message is string => Boolean(message));
        if (fieldError) return fieldError;
    }
    if (error instanceof Error && error.message.trim()) return error.message.trim();
    return 'Failed to update profile.';
}

export function normalizeProfileRoles(roles: unknown): string[] {
    if (!Array.isArray(roles)) return [];
    return Array.from(new Set(roles.filter((role): role is string => typeof role === 'string').map((role) => role.trim()).filter(Boolean)));
}
