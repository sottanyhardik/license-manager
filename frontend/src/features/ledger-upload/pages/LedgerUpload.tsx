/**
 * LedgerUpload — full-featured DGFT ledger upload page.
 *
 * Ported from legacy/frontend/src/pages/LedgerUpload.tsx (445 lines).
 * Features:
 *   - Native drag-and-drop (no react-dropzone)
 *   - Accepts .csv / .htm / .html, max 50 MB per file, multiple files
 *   - Sync mode: sequential per-file upload, shows per-file progress/results
 *   - Async mode: batch upload (20 files/batch), polls task status at 1 s intervals
 *   - Task status modal: per-task progress bar, license badges, failure details
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import {
  FileSpreadsheet,
  CloudUpload,
  Upload,
  FolderOpen,
  Paperclip,
  Trash2,
  X,
  FileText,
  CheckCircle2,
  XCircle,
  Hourglass,
  ListChecks,
  Info,
  Lightbulb,
  Zap,
  Cog,
  Loader2,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/shared/utils/cn'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'

// ── Constants ──────────────────────────────────────────────────────────────────

const UPLOAD_BATCH_SIZE = 20
const POLL_CONCURRENT = 5
const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50 MB
const ACCEPTED_TYPES = '.csv,.htm,.html'

// ── Types ──────────────────────────────────────────────────────────────────────

interface UploadResult {
  fileName: string
  success: boolean
  message?: string
  error?: string
  stats?: { total_licenses?: number }
  licenses?: string[]
  data?: { results?: Array<{ failed?: Array<{ license: string; error: string }> }> }
}

interface FileTask {
  task_id: string
  license: string
}

interface FileTaskGroup {
  file: string
  tasks: FileTask[]
  total: number
}

interface TaskStatus {
  state: 'PENDING' | 'PROGRESS' | 'SUCCESS' | 'FAILURE'
  error?: string
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ── AsyncToggle — inline switch (no shadcn Switch needed) ─────────────────────

interface AsyncToggleProps {
  checked: boolean
  onChange: (v: boolean) => void
  id: string
}

function AsyncToggle({ checked, onChange, id }: AsyncToggleProps) {
  return (
    <button
      type="button"
      id={id}
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent',
        'transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        checked ? 'bg-primary' : 'bg-input',
      )}
    >
      <span
        className={cn(
          'pointer-events-none block size-4 rounded-full bg-background shadow-lg ring-0 transition-transform',
          checked ? 'translate-x-4' : 'translate-x-0',
        )}
      />
    </button>
  )
}

// ── TaskStatusModal ────────────────────────────────────────────────────────────
// Defined outside LedgerUpload to prevent remount on parent re-renders, which
// would destroy the polling intervals.

interface TaskStatusModalProps {
  fileTasks: FileTaskGroup[]
  show: boolean
  onHide: () => void
}

function TaskStatusModal({ fileTasks, show, onHide }: TaskStatusModalProps) {
  const [taskStatuses, setTaskStatuses] = useState<Record<string, TaskStatus>>({})
  const doneRef = useRef(new Set<string>())

  // Reset statuses when the task set changes (new batch uploaded)
  useEffect(() => {
    setTaskStatuses({})
    doneRef.current = new Set()
  }, [fileTasks])

  // Polling loop — runs while modal is visible and tasks remain pending
  useEffect(() => {
    if (!show || fileTasks.length === 0) return

    doneRef.current = new Set()
    const allTaskIds = fileTasks.flatMap((f) => f.tasks.map((t) => t.task_id))

    const interval = setInterval(async () => {
      const pending = allTaskIds.filter((id) => !doneRef.current.has(id))
      if (pending.length === 0) {
        clearInterval(interval)
        return
      }
      const batch = pending.slice(0, POLL_CONCURRENT)
      await Promise.allSettled(
        batch.map(async (task_id) => {
          try {
            const response = await apiClient.get<TaskStatus>(
              ENDPOINTS.LEDGER.TASK_STATUS(task_id),
              { _noDedupe: true } as Parameters<typeof apiClient.get>[1],
            )
            setTaskStatuses((prev) => ({ ...prev, [task_id]: response.data }))
            if (
              response.data.state === 'SUCCESS' ||
              response.data.state === 'FAILURE'
            ) {
              doneRef.current.add(task_id)
            }
          } catch (err) {
            console.error('Error polling task:', task_id, err)
          }
        }),
      )
    }, 1000)

    return () => clearInterval(interval)
  }, [fileTasks, show])

  if (!show) return null

  return (
    // Modal backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="task-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onHide()
      }}
    >
      {/* Modal panel */}
      <div className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border bg-card text-card-foreground shadow-lg">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h2 id="task-modal-title" className="flex items-center gap-2 text-base font-semibold">
            <Cog className="size-4 text-primary" aria-hidden="true" />
            Processing Ledger Files
          </h2>
          <button
            type="button"
            onClick={onHide}
            className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Close"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {fileTasks.map((fileEntry, fi) => {
            const total = fileEntry.total
            const done = fileEntry.tasks.filter(
              (t) => taskStatuses[t.task_id]?.state === 'SUCCESS',
            ).length
            const failed = fileEntry.tasks.filter(
              (t) => taskStatuses[t.task_id]?.state === 'FAILURE',
            ).length
            const pending = total - done - failed
            const pct = total > 0 ? Math.round(((done + failed) / total) * 100) : 0
            const allDone = pending === 0

            return (
              <Card key={fi} className="mb-3">
                <CardContent className="pt-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="flex items-center gap-2 text-sm font-medium">
                      <FileText className="size-4" aria-hidden="true" />
                      {fileEntry.file}
                    </span>
                    <Badge
                      className={cn(
                        allDone && failed > 0
                          ? 'border-amber-500/30 bg-amber-500/15 text-amber-700 dark:text-amber-400'
                          : allDone
                            ? 'border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
                            : '',
                      )}
                      variant={allDone ? 'outline' : 'secondary'}
                    >
                      {allDone ? 'Done' : `Processing ${done + failed}/${total}`}
                    </Badge>
                  </div>

                  {/* Progress bar */}
                  <div className="mb-2 h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn(
                        'h-full rounded-full transition-[width]',
                        allDone && failed === 0
                          ? 'bg-emerald-500'
                          : allDone
                            ? 'bg-amber-500'
                            : 'bg-primary',
                      )}
                      style={{ width: `${pct}%` }}
                      role="progressbar"
                      aria-valuenow={pct}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    />
                  </div>

                  {/* Counts */}
                  <div className="mb-2 flex flex-wrap gap-3 text-xs">
                    <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="size-3.5" aria-hidden="true" />
                      {done} done
                    </span>
                    {failed > 0 && (
                      <span className="flex items-center gap-1 text-destructive">
                        <XCircle className="size-3.5" aria-hidden="true" />
                        {failed} failed
                      </span>
                    )}
                    {pending > 0 && (
                      <span className="flex items-center gap-1 text-muted-foreground">
                        <Hourglass className="size-3.5" aria-hidden="true" />
                        {pending} pending
                      </span>
                    )}
                    <span className="ml-auto text-muted-foreground">{pct}%</span>
                  </div>

                  {/* License badges */}
                  <details>
                    <summary className="cursor-pointer text-xs font-semibold text-muted-foreground">
                      Licenses ({total})
                    </summary>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {fileEntry.tasks.map((task) => {
                        const s = taskStatuses[task.task_id]
                        const isOk = s?.state === 'SUCCESS'
                        const isFail = s?.state === 'FAILURE'
                        return (
                          <Badge
                            key={task.task_id}
                            variant={isFail ? 'destructive' : 'secondary'}
                            title={isFail ? s?.error : isOk ? 'Processed' : 'Pending'}
                            className={cn(
                              isOk &&
                                'border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-400',
                            )}
                          >
                            {task.license}
                          </Badge>
                        )
                      })}
                    </div>
                  </details>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* Footer */}
        <div className="border-t px-6 py-4">
          <Button variant="outline" onClick={onHide}>
            Close
          </Button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function LedgerUpload() {
  const [files, setFiles] = useState<File[]>([])
  const [asyncMode, setAsyncMode] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [results, setResults] = useState<UploadResult[]>([])
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [batchProgress, setBatchProgress] = useState<{ current: number; total: number } | null>(
    null,
  )

  // Async task tracking
  const [asyncFileTasks, setAsyncFileTasks] = useState<FileTaskGroup[]>([])
  const [showTaskModal, setShowTaskModal] = useState(false)

  // Per-file upload progress (sync mode only)
  const [fileProgress, setFileProgress] = useState<
    Record<number, { name: string; progress: number; status: 'uploading' | 'completed' | 'failed' }>
  >({})

  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── File validation ──────────────────────────────────────────────────────────

  function validateFile(file: File): string | null {
    const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
    if (!['csv', 'htm', 'html'].includes(ext)) {
      return `${file.name}: unsupported file type (only .csv, .htm, .html)`
    }
    if (file.size > MAX_FILE_SIZE) {
      return `${file.name}: exceeds 50 MB limit (${formatFileSize(file.size)})`
    }
    return null
  }

  function addFiles(incoming: FileList | File[]) {
    const arr = Array.from(incoming)
    const rejected: string[] = []
    const accepted: File[] = []
    for (const f of arr) {
      const err = validateFile(f)
      if (err) rejected.push(err)
      else accepted.push(f)
    }
    if (rejected.length) {
      toast.error(rejected.join('\n'))
    }
    if (accepted.length) {
      setFiles((prev) => [...prev, ...accepted])
      setResults([])
      setUploadError(null)
    }
  }

  // ── Drag-and-drop handlers (native) ─────────────────────────────────────────

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true)
    else if (e.type === 'dragleave' || e.type === 'drop') setDragActive(false)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setDragActive(false)
      if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files)
    },
    // addFiles is redefined on each render but is pure; deps are stable values
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files?.length) addFiles(e.target.files)
    e.target.value = ''
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  function clearFiles() {
    setFiles([])
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // ── Sync upload ──────────────────────────────────────────────────────────────

  async function handleSyncUpload() {
    setUploading(true)
    setUploadError(null)
    setResults([])
    setFileProgress({})

    const newResults: UploadResult[] = []

    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      setFileProgress((prev) => ({
        ...prev,
        [i]: { name: file.name, progress: 0, status: 'uploading' },
      }))

      try {
        const formData = new FormData()
        formData.append('ledger', file)

        const response = await apiClient.post<{
          results?: Array<{
            file?: string
            message?: string
            stats?: { total_licenses?: number }
            licenses?: string[]
            failed?: Array<{ license: string; error: string }>
          }>
        }>(ENDPOINTS.LEDGER.UPLOAD, formData, {
          params: { async: 'false' },
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (e) => {
            const pct = e.total ? Math.round((e.loaded / e.total) * 100) : 0
            setFileProgress((prev) => ({
              ...prev,
              [i]: { name: file.name, progress: pct, status: 'uploading' },
            }))
          },
        })

        const fileResult = response.data.results?.[0]
        newResults.push({
          fileName: file.name,
          success: true,
          message: fileResult?.message ?? 'Upload successful.',
          stats: fileResult?.stats,
          licenses: fileResult?.licenses,
          data: response.data.results ? { results: response.data.results } : undefined,
        })
        setFileProgress((prev) => ({
          ...prev,
          [i]: { name: file.name, progress: 100, status: 'completed' },
        }))
      } catch (err: unknown) {
        const message =
          (err as { message?: string })?.message ?? 'Upload failed. Please try again.'
        newResults.push({ fileName: file.name, success: false, error: message })
        setFileProgress((prev) => ({
          ...prev,
          [i]: { name: file.name, progress: 100, status: 'failed' },
        }))
        toast.error(`${file.name}: ${message}`)
      }
    }

    setResults(newResults)
    setUploading(false)

    const succeeded = newResults.filter((r) => r.success).length
    if (succeeded > 0) {
      toast.success(`${succeeded}/${files.length} file(s) uploaded successfully.`)
      clearFiles()
    }
  }

  // ── Async upload ─────────────────────────────────────────────────────────────

  async function handleAsyncUpload() {
    setUploading(true)
    setUploadError(null)
    setBatchProgress(null)

    const totalBatches = Math.ceil(files.length / UPLOAD_BATCH_SIZE)
    const allFileTasks: FileTaskGroup[] = []
    const allErrors: string[] = []

    try {
      for (let i = 0; i < files.length; i += UPLOAD_BATCH_SIZE) {
        const batch = files.slice(i, i + UPLOAD_BATCH_SIZE)
        setBatchProgress({ current: Math.floor(i / UPLOAD_BATCH_SIZE) + 1, total: totalBatches })

        const formData = new FormData()
        batch.forEach((f) => formData.append('ledger', f))

        const response = await apiClient.post<{
          file_tasks?: Array<{ file: string; tasks: FileTask[]; total: number }>
          errors?: Array<{ file: string; error: string }>
        }>(ENDPOINTS.LEDGER.UPLOAD, formData, {
          params: { async: 'true' },
          headers: { 'Content-Type': 'multipart/form-data' },
        })

        if (response.data.file_tasks) allFileTasks.push(...response.data.file_tasks)
        if (response.data.errors?.length) {
          allErrors.push(...response.data.errors.map((e) => e.file))
        }
      }

      if (allFileTasks.length > 0) {
        setAsyncFileTasks(allFileTasks)
        setShowTaskModal(true)
        clearFiles()
      }
      if (allErrors.length > 0) {
        const msg = `${allErrors.length} file(s) failed: ${allErrors.join(', ')}`
        setUploadError(msg)
        toast.error(msg)
      }
      if (allFileTasks.length > 0) {
        toast.success('Files queued — tracking progress in the task modal.')
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } }; message?: string }
      const msg =
        axiosErr.response?.data?.error ?? axiosErr.message ?? 'Upload failed. Please try again.'
      setUploadError(msg)
      toast.error(msg)
    } finally {
      setUploading(false)
      setBatchProgress(null)
    }
  }

  function handleUpload() {
    if (files.length === 0) return
    if (asyncMode) handleAsyncUpload()
    else handleSyncUpload()
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div>
      {/* Page header */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-foreground">
            <FileSpreadsheet className="size-6 text-primary" aria-hidden="true" />
            Ledger Upload
          </h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Upload DFIA license ledger files in CSV or HTM/HTML format
          </p>
        </div>
        <label
          htmlFor="asyncModeSwitch"
          className="flex cursor-pointer items-center gap-2.5 text-sm"
        >
          <AsyncToggle
            id="asyncModeSwitch"
            checked={asyncMode}
            onChange={setAsyncMode}
          />
          <span className="flex items-center gap-1 font-medium text-muted-foreground">
            <Zap className="size-3.5 text-amber-500" aria-hidden="true" />
            Async {asyncMode ? '(Parallel)' : '(Sync)'}
          </span>
        </label>
      </div>

      <TaskStatusModal
        fileTasks={asyncFileTasks}
        show={showTaskModal}
        onHide={() => setShowTaskModal(false)}
      />

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {/* ── Upload panel ────────────────────────────────────────────────── */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="border-b pb-4">
              <CardTitle className="flex items-center gap-2 text-sm">
                <CloudUpload className="size-4 text-primary" aria-hidden="true" />
                Upload Files
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-5">
              {/* Drop zone */}
              <label
                htmlFor="file-input"
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={cn(
                  'mb-4 flex min-h-[170px] cursor-pointer flex-col items-center justify-center',
                  'rounded-lg border-2 border-dashed p-9 text-center transition-colors',
                  dragActive
                    ? 'border-primary bg-primary/5'
                    : 'border-border bg-card hover:border-primary/60',
                )}
              >
                <CloudUpload
                  className={cn(
                    'mb-2 size-10',
                    dragActive ? 'text-primary' : 'text-muted-foreground/60',
                  )}
                  aria-hidden="true"
                />
                <p className="mb-1 font-semibold text-foreground">
                  {dragActive ? 'Drop files here' : 'Drag & drop your ledger files'}
                </p>
                <small className="mb-3 text-muted-foreground">or click to browse</small>
                <span
                  className="pointer-events-none inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground"
                  aria-hidden="true"
                >
                  <FolderOpen className="size-3.5" />
                  Browse Files
                </span>
                <small className="mt-3 block text-muted-foreground">
                  CSV or HTM/HTML files · Max 50 MB per file
                </small>
                <input
                  id="file-input"
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPTED_TYPES}
                  multiple
                  onChange={handleFileChange}
                  className="hidden"
                  aria-label="Select ledger files"
                />
              </label>

              {/* Selected files list */}
              {files.length > 0 && (
                <div className="mb-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground">
                      <Paperclip className="size-3.5" aria-hidden="true" />
                      {files.length} file{files.length > 1 ? 's' : ''} selected
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={uploading}
                      onClick={() => {
                        clearFiles()
                        setResults([])
                      }}
                    >
                      <Trash2 className="size-3.5" aria-hidden="true" />
                      Clear All
                    </Button>
                  </div>
                  <div className="flex flex-col gap-2">
                    {files.map((file, index) => (
                      <div
                        key={index}
                        className="flex items-center gap-2 rounded-md border border-border/70 bg-muted/40 px-2.5 py-2"
                      >
                        <FileText
                          className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400"
                          aria-hidden="true"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium">{file.name}</div>
                          <small className="text-muted-foreground">
                            {formatFileSize(file.size)}
                          </small>
                        </div>
                        <Button
                          variant="outline"
                          size="icon"
                          className="size-8 shrink-0 text-destructive hover:bg-destructive/10"
                          disabled={uploading}
                          onClick={() => removeFile(index)}
                          aria-label={`Remove ${file.name}`}
                        >
                          <X className="size-3.5" aria-hidden="true" />
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Error banner */}
              {uploadError && (
                <div className="mb-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive">
                  <XCircle className="size-4 shrink-0" aria-hidden="true" />
                  <div>{uploadError}</div>
                </div>
              )}

              {/* Sync upload progress */}
              {uploading && !asyncMode && Object.keys(fileProgress).length > 0 && (
                <div className="mb-4">
                  <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
                    <CloudUpload className="size-4" aria-hidden="true" />
                    Uploading Files
                  </h3>
                  {Object.entries(fileProgress).map(([idx, fd]) => (
                    <div key={idx} className="mb-3">
                      <div className="mb-1 flex items-center justify-between">
                        <small
                          className="flex items-center gap-1 truncate text-muted-foreground"
                          style={{ maxWidth: '70%' }}
                        >
                          {fd.status === 'completed' ? (
                            <CheckCircle2
                              className="size-3.5 text-emerald-600"
                              aria-hidden="true"
                            />
                          ) : fd.status === 'failed' ? (
                            <XCircle className="size-3.5 text-destructive" aria-hidden="true" />
                          ) : (
                            <Hourglass className="size-3.5 text-primary" aria-hidden="true" />
                          )}
                          {fd.name}
                        </small>
                        <small className="text-muted-foreground">
                          {fd.status === 'completed'
                            ? '✓ Done'
                            : fd.status === 'failed'
                              ? '✗ Failed'
                              : `${fd.progress}%`}
                        </small>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                        <div
                          className={cn(
                            'h-full',
                            fd.status === 'completed'
                              ? 'bg-emerald-500'
                              : fd.status === 'failed'
                                ? 'bg-destructive'
                                : 'bg-primary',
                          )}
                          style={{
                            width: `${fd.status === 'failed' ? 100 : fd.progress}%`,
                          }}
                          role="progressbar"
                          aria-valuenow={fd.progress}
                          aria-valuemin={0}
                          aria-valuemax={100}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Upload button */}
              <Button
                size="lg"
                className="w-full"
                onClick={handleUpload}
                disabled={files.length === 0 || uploading}
              >
                {uploading ? (
                  <>
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                    {batchProgress
                      ? `Uploading batch ${batchProgress.current}/${batchProgress.total}…`
                      : `Uploading ${files.length} file${files.length > 1 ? 's' : ''}…`}
                  </>
                ) : (
                  <>
                    <Upload className="size-4" aria-hidden="true" />
                    Upload & Process
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Sync results */}
          {results.length > 0 && (
            <Card className="mt-3">
              <CardHeader className="border-b pb-4">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <ListChecks
                    className="size-4 text-emerald-600 dark:text-emerald-400"
                    aria-hidden="true"
                  />
                  Upload Results
                  <Badge
                    variant="outline"
                    className="border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
                  >
                    {results.filter((r) => r.success).length}/{results.length} succeeded
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="max-h-[500px] overflow-y-auto pt-4">
                {results.map((result, index) => (
                  <div
                    key={index}
                    className={cn(
                      'mb-2 rounded-lg border px-3.5 py-2.5 text-[13px]',
                      result.success
                        ? 'border-emerald-500/30 bg-emerald-500/10'
                        : 'border-destructive/30 bg-destructive/10',
                    )}
                  >
                    <div className="flex items-start gap-3">
                      {result.success ? (
                        <CheckCircle2
                          className="size-5 shrink-0 text-emerald-600 dark:text-emerald-400"
                          aria-hidden="true"
                        />
                      ) : (
                        <XCircle
                          className="size-5 shrink-0 text-destructive"
                          aria-hidden="true"
                        />
                      )}
                      <div className="flex-1">
                        <h4 className="mb-1.5 font-semibold text-foreground">
                          {result.fileName}
                        </h4>
                        {result.success ? (
                          <>
                            <p className="mb-2">{result.message}</p>
                            {(result.stats?.total_licenses ?? 0) > 0 && (
                              <div className="mb-2 flex flex-wrap gap-2">
                                <Badge
                                  variant="outline"
                                  className="border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
                                >
                                  {result.stats!.total_licenses} Licenses
                                </Badge>
                              </div>
                            )}
                            {(result.licenses?.length ?? 0) > 0 && (
                              <details className="mt-2">
                                <summary className="cursor-pointer text-xs font-semibold">
                                  View License Numbers ({result.licenses!.length})
                                </summary>
                                <div className="mt-2 flex flex-wrap gap-1">
                                  {result.licenses!.map((lic, idx) => (
                                    <Badge
                                      key={idx}
                                      variant="outline"
                                      className="border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
                                    >
                                      {lic}
                                    </Badge>
                                  ))}
                                </div>
                              </details>
                            )}
                            {(result.data?.results?.[0]?.failed?.length ?? 0) > 0 && (
                              <details className="mt-2">
                                <summary className="cursor-pointer text-xs font-semibold text-destructive">
                                  Failed Licenses ({result.data!.results![0].failed!.length})
                                </summary>
                                <div className="mt-2">
                                  {result.data!.results![0].failed!.map((f, idx) => (
                                    <div key={idx} className="mb-1 text-xs text-destructive">
                                      <strong>{f.license}:</strong> {f.error}
                                    </div>
                                  ))}
                                </div>
                              </details>
                            )}
                          </>
                        ) : (
                          <p className="text-destructive">{result.error}</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>

        {/* ── Instructions panel ──────────────────────────────────────────── */}
        <div className="lg:col-span-1">
          <Card>
            <CardHeader className="border-b pb-4">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Info className="size-4 text-primary" aria-hidden="true" />
                File Format Guide
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Required CSV Columns
              </div>
              <div className="mb-3 flex flex-wrap gap-1">
                {[
                  'Regn.No.',
                  'Regn.Date',
                  'Lic.No.',
                  'Lic.Date',
                  'IEC',
                  'Scheme.Cd.',
                  'Port',
                  'Notification',
                ].map((col) => (
                  <code
                    key={col}
                    className="rounded border border-primary/15 bg-primary/10 px-2 py-0.5 text-xs text-primary"
                  >
                    {col}
                  </code>
                ))}
              </div>
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3.5 py-3">
                <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-amber-700 dark:text-amber-400">
                  <Lightbulb className="size-4" aria-hidden="true" />
                  Important Notes
                </div>
                <ul className="ml-4 list-disc text-xs text-muted-foreground">
                  <li className="mb-1">Date format: DD/MM/YYYY</li>
                  <li className="mb-1">License numbers zero-padded to 10 digits</li>
                  <li className="mb-1">Credit and Debit transactions auto-processed</li>
                  <li className="mb-1">Multiple files supported · Max 50 MB</li>
                  <li>
                    <strong>Async mode:</strong> each license runs in parallel
                  </li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
