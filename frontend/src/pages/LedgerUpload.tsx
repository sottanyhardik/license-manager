import React, { useCallback, useEffect, useRef, useState } from "react";
import {
    CloudUpload, Upload, FolderOpen, Trash2, X, RefreshCw,
    FileText, CheckCircle2, XCircle, Hourglass, ListChecks, Info, Lightbulb, Zap, Cog, Loader2,
} from "lucide-react";

import { useFileUpload } from "../hooks";
import api from "../api/axios";
import { WorkspaceToolbar, WorkspaceTitle } from "@/components/workspace";
import { InlineError, StatusBadge, EmptyState } from "@/components/shared";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
    Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
    LEDGER_ACCEPT, LEDGER_ACCEPTED_EXTENSIONS, LEDGER_MAX_FILE_BYTES, LEDGER_MAX_FILE_MB,
    buildAsyncUploadErrorMessage, getFailedLicenses, getLedgerUploadErrorMessage,
    normalizeLedgerFileTasks, normalizeLedgerUploadErrors, normalizeProgressValue,
    summarizeLedgerResults,
    type LedgerFileTask, type LedgerSyncResult, type LedgerUploadError,
} from "./ledgerUploadHelpers";

const UPLOAD_BATCH_SIZE = 20;
const POLL_CONCURRENT = 5; // simultaneous status requests per tick

type TaskStatus = {
    state?: string;
    error?: string;
};

type BatchProgress = {
    current: number;
    total: number;
};

type TaskStatusModalProps = {
    fileTasks: LedgerFileTask[];
    show: boolean;
    onHide: () => void;
};

type FileProgressEntry = { name: string; progress?: number; status?: string };

// Defined outside LedgerUpload so React doesn't remount it on every parent render,
// which would destroy polling intervals.
const TaskStatusModal = ({ fileTasks, show, onHide }: TaskStatusModalProps) => {
    const [taskStatuses, setTaskStatuses] = useState<Record<string, TaskStatus>>({});
    const doneRef = useRef<Set<string>>(new Set());

    useEffect(() => {
        if (!show || fileTasks.length === 0) return;

        doneRef.current = new Set();
        const allTaskIds = fileTasks.flatMap((f) => f.tasks.map((t) => t.task_id));

        const interval = setInterval(async () => {
            const pending = allTaskIds.filter((id) => !doneRef.current.has(id));
            if (pending.length === 0) {
                clearInterval(interval);
                return;
            }
            const batch = pending.slice(0, POLL_CONCURRENT);
            await Promise.allSettled(batch.map(async (task_id) => {
                try {
                    const response = await api.get(`ledger-task-status/${task_id}/`);
                    setTaskStatuses((prev) => ({ ...prev, [task_id]: response.data }));
                    if (response.data.state === "SUCCESS" || response.data.state === "FAILURE") {
                        doneRef.current.add(task_id);
                    }
                } catch (err) {
                    setTaskStatuses((prev) => ({
                        ...prev,
                        [task_id]: { state: "FAILURE", error: getLedgerUploadErrorMessage(err) },
                    }));
                    doneRef.current.add(task_id);
                }
            }));
        }, 1000);

        return () => clearInterval(interval);
    }, [fileTasks, show]);

    useEffect(() => {
        setTaskStatuses({});
        doneRef.current = new Set();
    }, [fileTasks]);

    return (
        <Dialog open={show} onOpenChange={(o) => !o && onHide()}>
            <DialogContent className="max-h-[85vh] max-w-2xl overflow-hidden">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Cog className="size-4 text-primary" />
                        Processing Ledger Files
                    </DialogTitle>
                    <DialogDescription className="sr-only">
                        Per-license processing progress for uploaded ledger files.
                    </DialogDescription>
                </DialogHeader>

                <div className="max-h-[60vh] overflow-y-auto pr-1">
                    {fileTasks.map((fileEntry, fi) => {
                        const total = fileEntry.total;
                        const done = fileEntry.tasks.filter((t) => taskStatuses[t.task_id]?.state === "SUCCESS").length;
                        const failed = fileEntry.tasks.filter((t) => taskStatuses[t.task_id]?.state === "FAILURE").length;
                        const pending = total - done - failed;
                        const pct = total > 0 ? Math.round(((done + failed) / total) * 100) : 0;
                        const allDone = pending === 0;

                        return (
                            <Card key={`${fileEntry.file}-${fi}`} className="mb-3">
                                <CardContent className="pt-4">
                                    <div className="mb-2 flex items-center justify-between">
                                        <span className="flex min-w-0 items-center gap-2 text-sm font-medium">
                                            <FileText className="size-4 shrink-0" />
                                            <span className="truncate" title={fileEntry.file}>{fileEntry.file}</span>
                                        </span>
                                        <Badge variant={allDone ? (failed > 0 ? "warning" : "success") : "default"}>
                                            {allDone ? "Done" : `Processing ${done + failed}/${total}`}
                                        </Badge>
                                    </div>

                                    <div
                                        className="mb-2 h-2 overflow-hidden rounded-full bg-muted"
                                        role="progressbar"
                                        aria-label={`${fileEntry.file} processing progress`}
                                        aria-valuemin={0}
                                        aria-valuemax={100}
                                        aria-valuenow={pct}
                                    >
                                        <div
                                            className={`h-full rounded-full transition-[width] ${allDone ? (failed === 0 ? "bg-success" : "bg-warning") : "bg-primary"}`}
                                            style={{ width: `${pct}%` }}
                                        />
                                    </div>

                                    <div className="mb-2 flex flex-wrap gap-3 text-xs">
                                        <span className="flex items-center gap-1 text-success"><CheckCircle2 className="size-3.5" />{done} done</span>
                                        {failed > 0 && <span className="flex items-center gap-1 text-destructive"><XCircle className="size-3.5" />{failed} failed</span>}
                                        {pending > 0 && <span className="flex items-center gap-1 text-muted-foreground"><Hourglass className="size-3.5" />{pending} pending</span>}
                                        <span className="ml-auto text-muted-foreground">{pct}%</span>
                                    </div>

                                    <details>
                                        <summary className="cursor-pointer text-xs font-semibold text-muted-foreground">Licenses ({total})</summary>
                                        <div className="mt-2 flex flex-wrap gap-1">
                                            {fileEntry.tasks.map((task) => {
                                                const s = taskStatuses[task.task_id];
                                                const isOk = s?.state === "SUCCESS";
                                                const isFail = s?.state === "FAILURE";
                                                return (
                                                    <Badge
                                                        key={task.task_id}
                                                        variant={isOk ? "success" : isFail ? "destructive" : "secondary"}
                                                        title={isFail ? s?.error : isOk ? "Processed" : "Pending"}
                                                    >
                                                        {task.license}
                                                    </Badge>
                                                );
                                            })}
                                        </div>
                                    </details>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={onHide}>Close</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
function UploadProgressList({ fileProgress }: { fileProgress: Record<string, FileProgressEntry> }) {
    return (
        <div className="mb-4" role="status" aria-live="polite">
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><CloudUpload className="size-4" aria-hidden="true" />Uploading Files</h3>
            {Object.entries(fileProgress).map(([index, fileData]) => {
                const progressValue = fileData.status === "failed" ? 100 : normalizeProgressValue(fileData.progress);
                return (
                    <div key={index} className="mb-3">
                        <div className="mb-1 flex items-center justify-between gap-2">
                            <small className="flex min-w-0 items-center gap-1 text-muted-foreground" title={fileData.name}>
                                {fileData.status === "completed" ? <CheckCircle2 className="size-3.5 shrink-0 text-success" aria-hidden="true" />
                                    : fileData.status === "failed" ? <XCircle className="size-3.5 shrink-0 text-destructive" aria-hidden="true" />
                                    : <Hourglass className="size-3.5 shrink-0 text-primary" aria-hidden="true" />}
                                <span className="truncate">{fileData.name}</span>
                            </small>
                            <small className="shrink-0 text-muted-foreground">
                                {fileData.status === "completed" ? "Done" : fileData.status === "failed" ? "Failed" : `${progressValue}%`}
                            </small>
                        </div>
                        <div
                            className="h-1.5 overflow-hidden rounded-full bg-muted"
                            role="progressbar"
                            aria-label={`${fileData.name} upload progress`}
                            aria-valuemin={0}
                            aria-valuemax={100}
                            aria-valuenow={progressValue}
                        >
                            <div
                                className={`h-full ${fileData.status === "completed" ? "bg-success" : fileData.status === "failed" ? "bg-destructive" : "bg-primary"}`}
                                style={{ width: `${progressValue}%` }}
                            />
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

function FileDetails({ result }: { result: LedgerSyncResult }) {
    const failed = getFailedLicenses(result);
    const licenses = result.licenses ?? [];
    if (licenses.length === 0 && failed.length === 0) return null;
    return (
        <div className="space-y-2">
            {licenses.length > 0 && (
                <details>
                    <summary className="cursor-pointer text-xs font-semibold">View License Numbers ({licenses.length})</summary>
                    <div className="mt-2 flex max-h-40 flex-wrap gap-1 overflow-y-auto">
                        {licenses.map((license, idx) => <StatusBadge key={`${license}-${idx}`} tone="success" label={String(license)} />)}
                    </div>
                </details>
            )}
            {failed.length > 0 && (
                <details>
                    <summary className="cursor-pointer text-xs font-semibold text-destructive">Failed Licenses ({failed.length})</summary>
                    <Table className="text-xs" containerClassName="mt-2">
                        <TableHeader>
                            <TableRow><TableHead>License</TableHead><TableHead>Reason reported by server</TableHead></TableRow>
                        </TableHeader>
                        <TableBody>
                            {failed.map((f, idx) => (
                                <TableRow key={`${f.license}-${idx}`}>
                                    <TableCell className="font-medium">{f.license}</TableCell>
                                    <TableCell className="whitespace-normal break-words text-destructive">{f.error}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </details>
            )}
        </div>
    );
}

function SyncResults({ results }: { results: LedgerSyncResult[] }) {
    const summary = summarizeLedgerResults(results);
    return (
        <Card className="mt-3" role="region" aria-label="Upload results">
            <CardHeader className="border-b py-3">
                <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                    <ListChecks className="size-4 text-success" aria-hidden="true" />
                    Upload Results
                    <StatusBadge tone={summary.filesFailed === 0 ? "success" : "warning"} label={`${summary.filesSucceeded}/${summary.files} succeeded`} />
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-3">
                <div className="flex flex-wrap gap-2" aria-label="Result summary">
                    <StatusBadge tone="success" icon={CheckCircle2} label={`${summary.licensesImported} licenses imported`} />
                    <StatusBadge tone={summary.licensesFailed > 0 ? "danger" : "neutral"} icon={XCircle} label={`${summary.licensesFailed} licenses failed`} />
                    <StatusBadge tone={summary.filesFailed > 0 ? "danger" : "neutral"} icon={FileText} label={`${summary.filesFailed} files rejected`} />
                </div>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>File</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead className="text-right">Imported</TableHead>
                            <TableHead className="text-right">Failed</TableHead>
                            <TableHead>Details</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {results.map((result, index) => {
                            const failed = getFailedLicenses(result);
                            return (
                                <TableRow key={`${result.fileName}-${index}`} className="align-top">
                                    <TableCell className="max-w-[16rem] whitespace-normal break-words font-medium">{result.fileName || "Ledger file"}</TableCell>
                                    <TableCell>
                                        <StatusBadge
                                            tone={result.success ? (failed.length > 0 ? "warning" : "success") : "danger"}
                                            icon={result.success ? CheckCircle2 : XCircle}
                                            label={result.success ? (failed.length > 0 ? "Partly imported" : "Imported") : "Rejected"}
                                        />
                                    </TableCell>
                                    <TableCell className="text-right tabular-nums">{result.success ? (result.licenses?.length ?? 0) : "-"}</TableCell>
                                    <TableCell className="text-right tabular-nums">{result.success ? failed.length : "-"}</TableCell>
                                    <TableCell className="min-w-[12rem] whitespace-normal break-words">
                                        {result.success ? (
                                            <div className="space-y-2">
                                                <p>{result.message}</p>
                                                <FileDetails result={result} />
                                            </div>
                                        ) : (
                                            <p className="text-destructive">{result.error}</p>
                                        )}
                                    </TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    );
}

function QueuedSummary({ fileTasks, onView }: { fileTasks: LedgerFileTask[]; onView: () => void }) {
    const queued = fileTasks.reduce((n, f) => n + f.total, 0);
    return (
        <Card className="mt-3" role="region" aria-label="Queued for processing">
            <CardHeader className="border-b py-3">
                <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                    <Cog className="size-4 text-primary" aria-hidden="true" />
                    Queued for Processing
                    <StatusBadge tone="info" label={`${queued} licenses queued`} />
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-3">
                <Table>
                    <TableHeader>
                        <TableRow><TableHead>File</TableHead><TableHead className="text-right">Licenses queued</TableHead></TableRow>
                    </TableHeader>
                    <TableBody>
                        {fileTasks.map((f, i) => (
                            <TableRow key={`${f.file}-${i}`}>
                                <TableCell className="whitespace-normal break-words font-medium">{f.file}</TableCell>
                                <TableCell className="text-right tabular-nums">{f.total}</TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
                <Button type="button" variant="outline" size="sm" onClick={onView}>View processing status</Button>
            </CardContent>
        </Card>
    );
}

const LedgerUpload = () => {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [asyncFileTasks, setAsyncFileTasks] = useState<LedgerFileTask[]>([]);
    const [showTaskModal, setShowTaskModal] = useState(false);
    const [useAsyncMode, setUseAsyncMode] = useState(true);
    const [asyncError, setAsyncError] = useState<string | null>(null);
    const [asyncUploading, setAsyncUploading] = useState(false);
    const [batchProgress, setBatchProgress] = useState<BatchProgress | null>(null);
    // State does not change synchronously, so it cannot by itself protect two
    // click events arriving in the same render frame.
    const uploadInFlightRef = useRef(false);

    const resetFileInput = useCallback(() => {
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    }, []);

    const {
        files, uploading, results, error, dragActive, fileProgress,
        handleDrag, handleDrop, handleFileChange, handleUpload: originalHandleUpload,
        formatFileSize, removeFile, clearFiles,
    } = useFileUpload({
        endpoint: "upload-ledger/",
        fileFieldName: "ledger",
        uploadMode: "sequential",
        multiple: true,
        accept: LEDGER_ACCEPT,
        maxFileSize: LEDGER_MAX_FILE_BYTES,
        timeout: 300000,
        onSuccess: (uploadResults) => {
            if (uploadResults.some((r) => r.success)) {
                resetFileInput();
            }
        },
    });

    const handleAsyncUpload = async () => {
        if (files.length === 0 || uploadInFlightRef.current) return;
        uploadInFlightRef.current = true;
        setAsyncError(null);
        setAsyncUploading(true);

        const totalBatches = Math.ceil(files.length / UPLOAD_BATCH_SIZE);
        setBatchProgress({ current: 0, total: totalBatches });

        const allFileTasks: LedgerFileTask[] = [];
        const allErrors: LedgerUploadError[] = [];

        try {
            for (let i = 0; i < files.length; i += UPLOAD_BATCH_SIZE) {
                const batch = files.slice(i, i + UPLOAD_BATCH_SIZE);
                setBatchProgress({ current: Math.floor(i / UPLOAD_BATCH_SIZE) + 1, total: totalBatches });

                const formData = new FormData();
                batch.forEach((file) => formData.append("ledger", file));
                formData.append("async", "true");
                const operationId = crypto.randomUUID();

                const response = await api.post("upload-ledger/", formData, {
                    headers: {
                        "Content-Type": "multipart/form-data",
                        "X-Upload-Operation-Id": operationId,
                    },
                });

                allFileTasks.push(...normalizeLedgerFileTasks(response.data?.file_tasks));
                allErrors.push(...normalizeLedgerUploadErrors(response.data?.errors));
            }

            if (allFileTasks.length > 0) {
                setAsyncFileTasks(allFileTasks);
                setShowTaskModal(true);
                clearFiles();
                resetFileInput();
            }
            if (allErrors.length > 0) {
                setAsyncError(buildAsyncUploadErrorMessage(allErrors));
            }
        } catch (err) {
            setAsyncError(getLedgerUploadErrorMessage(err));
        } finally {
            setAsyncUploading(false);
            setBatchProgress(null);
            uploadInFlightRef.current = false;
        }
    };

    const handleUpload = () => {
        if (uploadInFlightRef.current) return;
        if (useAsyncMode) void handleAsyncUpload();
        else {
            uploadInFlightRef.current = true;
            void originalHandleUpload().finally(() => {
                uploadInFlightRef.current = false;
            });
        }
    };

    const busy = uploading || asyncUploading;
    const progressEntries = fileProgress as Record<string, FileProgressEntry>;
    const fileCountLabel = `${files.length} file${files.length > 1 ? "s" : ""}`;

    return (
        <div className="ledger-upload-page min-w-0 space-y-3">
            <WorkspaceToolbar
                start={<WorkspaceTitle title="Ledger Upload" breadcrumbs={[{ label: "Home", to: "/" }]} />}
                actions={
                    <label className="flex cursor-pointer items-center gap-2.5 text-sm" htmlFor="asyncModeSwitch">
                        <Switch id="asyncModeSwitch" checked={useAsyncMode} onCheckedChange={setUseAsyncMode} disabled={busy} />
                        <span className="flex items-center gap-1 font-medium text-muted-foreground">
                            <Zap className="size-3.5 text-warning" aria-hidden="true" />
                            Async {useAsyncMode ? "(Parallel)" : "(Sync)"}
                        </span>
                    </label>
                }
            />

            <TaskStatusModal fileTasks={asyncFileTasks} show={showTaskModal} onHide={() => setShowTaskModal(false)} />

            <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                <div className="min-w-0 lg:col-span-2">
                    <Card className="overflow-hidden border-border/80 shadow-sm">
                        <CardHeader className="border-b py-3">
                            <CardTitle className="flex items-center gap-2 text-sm">
                                <CloudUpload className="size-4 text-primary" aria-hidden="true" />Upload Files
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-3">
                            {/* Drop zone */}
                            <label
                                htmlFor="file-input"
                                onDragEnter={handleDrag}
                                onDragLeave={handleDrag}
                                onDragOver={handleDrag}
                                onDrop={handleDrop}
                                className={cn(
                                    "mb-3 flex min-h-[132px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-5 text-center transition-colors duration-200 focus-within:ring-2 focus-within:ring-ring",
                                    dragActive ? "border-primary bg-primary/5" : "border-border bg-card hover:border-primary/60",
                                    busy && "pointer-events-none opacity-60",
                                )}
                            >
                                <CloudUpload className={`mb-1.5 size-8 ${dragActive ? "text-primary" : "text-muted-foreground/60"}`} aria-hidden="true" />
                                <p className="mb-0.5 text-sm font-semibold text-foreground">{dragActive ? "Drop files here" : "Drag & drop ledger files"}</p>
                                <small className="mb-2 text-xs text-muted-foreground">or click to browse</small>
                                <span className="pointer-events-none inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground">
                                    <FolderOpen className="size-3.5" aria-hidden="true" />Browse Files
                                </span>
                                <small className="mt-2 block text-xs text-muted-foreground">
                                    Accepted: {LEDGER_ACCEPTED_EXTENSIONS.join(", ")} · Max {LEDGER_MAX_FILE_MB}MB per file
                                </small>
                                <input
                                    ref={fileInputRef}
                                    id="file-input"
                                    type="file"
                                    accept={LEDGER_ACCEPT}
                                    multiple
                                    disabled={busy}
                                    aria-label="Ledger files"
                                    aria-describedby="ledger-file-hint"
                                    onChange={handleFileChange}
                                    className="sr-only"
                                />
                            </label>
                            <p id="ledger-file-hint" className="sr-only">
                                Accepted file types {LEDGER_ACCEPTED_EXTENSIONS.join(", ")}, maximum {LEDGER_MAX_FILE_MB} megabytes per file. Choosing files replaces the current selection.
                            </p>

                            {/* Client-side rejection (file type / size) */}
                            {error && (
                                <div className="mb-4">
                                    <InlineError title="File not accepted" error={{ message: error }} />
                                </div>
                            )}

                            {/* Selected files */}
                            {files.length > 0 && (
                                <div className="mb-4">
                                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                                        <span className="text-sm font-semibold text-muted-foreground">{fileCountLabel} selected</span>
                                        <div className="flex items-center gap-2">
                                            <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => fileInputRef.current?.click()}>
                                                <RefreshCw className="size-3.5" aria-hidden="true" />Replace
                                            </Button>
                                            <Button
                                                type="button"
                                                variant="outline"
                                                size="sm"
                                                disabled={busy}
                                                onClick={() => { clearFiles(); resetFileInput(); setAsyncError(null); }}
                                            >
                                                <Trash2 className="size-3.5" aria-hidden="true" />Clear All
                                            </Button>
                                        </div>
                                    </div>
                                    <ul className="flex flex-col gap-2">
                                        {files.map((file, index) => (
                                            <li key={`${file.name}-${file.lastModified}-${file.size}`} className="flex items-center gap-2 rounded-md border border-border/70 bg-muted/40 px-2.5 py-2">
                                                <FileText className="size-4 shrink-0 text-success" aria-hidden="true" />
                                                <div className="min-w-0 flex-1">
                                                    <div className="truncate text-sm font-medium" title={file.name}>{file.name}</div>
                                                    <small className="text-muted-foreground">{formatFileSize(file.size)}</small>
                                                </div>
                                                <Button
                                                    type="button"
                                                    variant="outline"
                                                    size="icon"
                                                    className="size-8 shrink-0 text-destructive hover:bg-destructive/10"
                                                    disabled={busy}
                                                    onClick={() => removeFile(index)}
                                                    aria-label={`Remove ${file.name}`}
                                                >
                                                    <X className="size-3.5" aria-hidden="true" />
                                                </Button>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* Async submission error (request failed, or the server rejected files) */}
                            {asyncError && (
                                <div className="mb-4">
                                    <InlineError title="Upload problem" error={{ message: asyncError }} />
                                </div>
                            )}

                            {/* Progress */}
                            {uploading && Object.keys(progressEntries).length > 0 && <UploadProgressList fileProgress={progressEntries} />}
                            {asyncUploading && (
                                <div role="status" aria-live="polite" className="mb-4 space-y-1.5">
                                    <div className="text-sm text-muted-foreground">
                                        {batchProgress ? `Uploading batch ${batchProgress.current} of ${batchProgress.total}…` : "Processing…"}
                                    </div>
                                    <div className="h-1.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label="Upload in progress">
                                        <div className="h-full w-1/3 animate-pulse rounded-full bg-primary motion-reduce:animate-none" />
                                    </div>
                                </div>
                            )}

                            {/* Upload button */}
                            <Button type="button" className="w-full sm:w-auto" onClick={handleUpload} disabled={files.length === 0 || busy} aria-busy={busy}>
                                {busy ? (
                                    <>
                                        <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        {batchProgress ? `Uploading batch ${batchProgress.current}/${batchProgress.total}…` : `Uploading ${fileCountLabel}…`}
                                    </>
                                ) : (
                                    <><Upload className="size-4" aria-hidden="true" />Upload & Process</>
                                )}
                            </Button>
                        </CardContent>
                    </Card>

                    {results.length > 0
                        ? <SyncResults results={results as LedgerSyncResult[]} />
                        : asyncFileTasks.length > 0
                            ? <QueuedSummary fileTasks={asyncFileTasks} onView={() => setShowTaskModal(true)} />
                            : !busy && !error && files.length === 0 && (
                                <Card className="mt-3">
                                    <CardContent>
                                        <EmptyState icon={ListChecks} title="No uploads yet" description="Results of your next upload will appear here." />
                                    </CardContent>
                                </Card>
                            )}
                </div>

                {/* Instructions */}
                <div className="min-w-0 lg:col-span-1">
                    <Card className="lg:sticky lg:top-3">
                        <CardHeader className="border-b py-3">
                            <CardTitle className="flex items-center gap-2 text-sm">
                                <Info className="size-4 text-primary" aria-hidden="true" />File Format Guide
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-3">
                            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Supported files</div>
                            <div className="mb-3 flex flex-wrap items-center gap-1">
                                {LEDGER_ACCEPTED_EXTENSIONS.map((ext) => <Badge key={ext} variant="secondary">{ext}</Badge>)}
                                <span className="text-xs text-muted-foreground">up to {LEDGER_MAX_FILE_MB}MB each</span>
                            </div>
                            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Required CSV Columns</div>
                            <div className="mb-3 flex flex-wrap gap-1">
                                {["Regn.No.", "Regn.Date", "Lic.No.", "Lic.Date", "IEC", "Scheme.Cd.", "Port", "Notification"].map((col) => (
                                    <code key={col} className="rounded border border-primary/15 bg-primary/10 px-2 py-0.5 text-xs text-primary">{col}</code>
                                ))}
                            </div>
                            <div className="rounded-lg border border-warning/30 bg-warning/10 px-3.5 py-3">
                                <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-[var(--tb-warning-text)]">
                                    <Lightbulb className="size-4" aria-hidden="true" />Important Notes
                                </div>
                                <ul className="ml-4 list-disc text-xs text-muted-foreground">
                                    <li className="mb-1">Date format: DD/MM/YYYY</li>
                                    <li className="mb-1">License numbers zero-padded to 10 digits</li>
                                    <li className="mb-1">Credit and Debit transactions auto-processed</li>
                                    <li className="mb-1">Multiple files supported · Max {LEDGER_MAX_FILE_MB}MB</li>
                                    <li><strong>Async mode:</strong> each license runs in parallel</li>
                                </ul>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
};

export default LedgerUpload;
