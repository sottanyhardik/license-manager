import { QueryClient } from '@tanstack/react-query'

/** Default retry policy: one retry, but never on HTTP 429 (throttled). */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  const status = (error as { response?: { status?: number } } | null)?.response?.status
  if (status === 429) return false
  return failureCount < 1
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000, // 30 s — balanced for compliance data
      retry: shouldRetryQuery,
    },
  },
})
