// LicenseDocuments — list of uploaded documents for a license.
// Fetches from /api/v1/licenses/{id}/documents/.

import { Download, FileText, Inbox, Loader2 } from 'lucide-react'
import { cn } from '@/shared/utils/cn'
import { Button } from '@/shared/ui/button'
import { useLicenseDocuments } from '../queries'
import type { LicenseDocument } from '../types'

interface LicenseDocumentsProps {
  licenseId: number
  className?: string
}

const TYPE_STYLES: Record<LicenseDocument['type'], string> = {
  'LICENSE COPY': 'bg-blue-500/10 text-blue-700 dark:text-blue-400',
  'TRANSFER LETTER': 'bg-violet-500/10 text-violet-700 dark:text-violet-400',
  OTHER: 'bg-muted text-muted-foreground',
}

function DocumentTypeBadge({ type }: { type: LicenseDocument['type'] }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        TYPE_STYLES[type] ?? TYPE_STYLES.OTHER,
      )}
    >
      {type}
    </span>
  )
}

export function LicenseDocuments({ licenseId, className }: LicenseDocumentsProps) {
  const { data: documents, isLoading, isError } = useLicenseDocuments(licenseId)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        Loading documents…
      </div>
    )
  }

  if (isError) {
    return (
      <div className="py-10 text-center text-sm text-destructive">
        Failed to load documents.
      </div>
    )
  }

  if (!documents || documents.length === 0) {
    return (
      <div
        className={cn(
          'flex flex-col items-center gap-2 py-10 text-center text-muted-foreground',
          className,
        )}
      >
        <Inbox className="size-8 opacity-50" aria-hidden="true" />
        <p className="text-sm">No documents uploaded for this license.</p>
      </div>
    )
  }

  return (
    <div className={cn('space-y-2', className)}>
      {documents.map((doc) => (
        <div
          key={doc.id}
          className="flex items-center justify-between gap-4 rounded-lg border bg-card px-4 py-3"
        >
          <div className="flex items-center gap-3 min-w-0">
            <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <DocumentTypeBadge type={doc.type} />
          </div>
          <Button
            variant="outline"
            size="sm"
            asChild
            className="shrink-0"
          >
            <a
              href={doc.file}
              target="_blank"
              rel="noopener noreferrer"
              download
              aria-label={`Download ${doc.type} document`}
            >
              <Download className="size-3.5" aria-hidden="true" />
              Download
            </a>
          </Button>
        </div>
      ))}
    </div>
  )
}
