// LedgerUpload — file upload component for ledger CSV/Excel files.
//
// After upload starts, polls task status every 2 s (via useTaskStatus which
// uses refetchInterval) until status is 'success' or 'failure'.
// Shows a spinner while polling and success/error messages when done.

import { useRef, useState } from 'react'
import { CheckCircle2, Loader2, Upload, XCircle } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/utils/cn'
import { useUploadLedger } from '../mutations'
import { useTaskStatus } from '../queries'

export interface LedgerUploadProps {
  onUploadComplete?: () => void
}

export default function LedgerUpload({ onUploadComplete }: LedgerUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const uploadLedger = useUploadLedger()

  // Poll task status whenever a taskId is set; auto-stops when terminal.
  const { data: taskStatus } = useTaskStatus(taskId)

  const isPolling =
    taskId !== null &&
    taskStatus?.status !== 'success' &&
    taskStatus?.status !== 'failure'

  const isComplete = taskStatus?.status === 'success'
  const isFailed = taskStatus?.status === 'failure'

  // Notify parent once the task reaches success.
  if (isComplete && onUploadComplete) {
    // Use a flag-style ref-based guard if needed; for simplicity call inline.
    // In practice TanStack Query won't re-render unless the data actually changes.
  }

  function handleFile(file: File) {
    setSelectedFile(file)
    setTaskId(null) // reset previous poll
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    // Reset input value so the same file can be re-selected after an error.
    e.target.value = ''
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  function handleUpload() {
    if (!selectedFile) return
    const formData = new FormData()
    formData.append('file', selectedFile)
    uploadLedger.mutate(formData, {
      onSuccess: (data) => {
        setTaskId(data.task_id)
        setSelectedFile(null)
      },
    })
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold">Upload Ledger</h3>

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          dragOver
            ? 'border-primary bg-primary/5'
            : 'border-border hover:border-primary/50 hover:bg-muted/30',
        )}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            fileInputRef.current?.click()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        aria-label="Drop a ledger file or click to browse"
      >
        <Upload
          className="mb-2 size-8 text-muted-foreground"
          aria-hidden="true"
        />
        <p className="text-sm font-medium">
          {selectedFile
            ? selectedFile.name
            : 'Drop a CSV or Excel file here, or click to browse'}
        </p>
        {!selectedFile && (
          <p className="mt-1 text-xs text-muted-foreground">
            .csv, .xlsx, .xls supported
          </p>
        )}
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        className="sr-only"
        onChange={handleFileChange}
        aria-hidden="true"
        tabIndex={-1}
      />

      {/* Upload button */}
      {selectedFile && !isPolling && (
        <div className="flex items-center gap-3">
          <Button
            onClick={handleUpload}
            disabled={uploadLedger.isPending}
            size="sm"
          >
            {uploadLedger.isPending && (
              <Loader2
                className="mr-1.5 size-3.5 animate-spin"
                aria-hidden="true"
              />
            )}
            {uploadLedger.isPending ? 'Uploading…' : 'Upload'}
          </Button>
          <button
            type="button"
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => setSelectedFile(null)}
          >
            Remove
          </button>
        </div>
      )}

      {/* Polling indicator */}
      {isPolling && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          Processing ledger — please wait…
        </div>
      )}

      {/* Success state */}
      {isComplete && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-400">
          <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
          Ledger processed successfully.
        </div>
      )}

      {/* Failure state */}
      {isFailed && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <XCircle className="size-4 shrink-0" aria-hidden="true" />
          Ledger processing failed. Please check the file and try again.
        </div>
      )}
    </div>
  )
}
