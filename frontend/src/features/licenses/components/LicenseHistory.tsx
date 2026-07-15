// LicenseHistory — timeline of history events for a license.
// Fetches from /api/v1/licenses/{id}/history/.

import { Loader2 } from 'lucide-react'
import { useLicenseHistory } from '../queries'

interface LicenseHistoryProps {
  licenseId: number
}

export function LicenseHistory({ licenseId }: LicenseHistoryProps) {
  const { data: events, isLoading, isError } = useLicenseHistory(licenseId)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        Loading history…
      </div>
    )
  }

  if (isError) {
    return (
      <div className="py-10 text-center text-sm text-destructive">
        Failed to load history.
      </div>
    )
  }

  if (!events || events.length === 0) {
    return (
      <div className="py-10 text-center text-sm text-muted-foreground">
        No history available.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {events.map((event, idx) => (
        <div key={idx} className="flex gap-3 text-sm">
          <div className="w-32 shrink-0 text-xs text-muted-foreground">
            {event.timestamp
              ? new Date(event.timestamp).toLocaleDateString('en-GB')
              : '—'}
          </div>
          <div>
            <span className="font-medium capitalize">{event.event_type}</span>
            {event.description && (
              <span className="ml-2 text-muted-foreground">{event.description}</span>
            )}
            {event.user && (
              <span className="ml-2 text-xs text-muted-foreground">by {event.user}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
