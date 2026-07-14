// Re-export master endpoint constants for convenient import within this feature.
// All actual HTTP calls are made through apiClient in queries.ts — never raw
// string URLs in components.
export { ENDPOINTS } from '@/shared/api/endpoints'
