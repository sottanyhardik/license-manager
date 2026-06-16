import React, { useState, useEffect, useRef } from "react";
import {
    FileSpreadsheet, CloudUpload, Upload, FolderOpen, Paperclip, Trash2, X,
    FileText, CheckCircle2, XCircle, Hourglass, ListChecks, Info, Lightbulb, Zap, Cog, Loader2,
} from "lucide-react";

import { useFileUpload } from "../hooks";
import api from "../api/axios";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";

const UPLOAD_BATCH_SIZE = 20;
const POLL_CONCURRENT = 5; // simultaneous status requests per tick

// Defined outside LedgerUpload so React doesn't remount it on every parent render,
// which would destroy polling intervals.
const TaskStatusModal = ({ fileTasks, show, onHide }) => {
    const [taskStatuses, setTaskStatuses] = useState({});
    const doneRef = useRef(new Set());

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
                    console.error("Error polling task:", task_id, err);
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
                            <Card key={fi} className="mb-3">
                                <CardContent className="pt-4">
                                    <div className="mb-2 flex items-center justify-between">
                                        <span className="flex items-center gap-2 text-sm font-medium">
                                            <FileText className="size-4" />{fileEntry.file}
                                        </span>
                                        <Badge variant={allDone ? (failed > 0 ? "warning" : "success") : "default"}>
                                            {allDone ? "Done" : `Processing ${done + failed}/${total}`}
                                        </Badge>
                                    </div>

                                    <div className="mb-2 h-2 overflow-hidden rounded-full bg-muted">
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

const LedgerUpload = () => {
    const [asyncFileTasks, setAsyncFileTasks] = useState([]);
    const [showTaskModal, setShowTaskModal] = useState(false);
    const [useAsyncMode, setUseAsyncMode] = useState(true);
    const [asyncError, setAsyncError] = useState(null);
    const [asyncUploading, setAsyncUploading] = useState(false);
    const [batchProgress, setBatchProgress] = useState(null);

    const {
        files, uploading, results, error, dragActive, fileProgress,
        handleDrag, handleDrop, handleFileChange, handleUpload: originalHandleUpload,
        formatFileSize, removeFile, clearFiles,
    } = useFileUpload({
        endpoint: "upload-ledger/",
        fileFieldName: "ledger",
        uploadMode: "sequential",
        multiple: true,
        accept: ".csv,.htm,.html",
        maxFileSize: 50 * 1024 * 1024,
        timeout: 300000,
        onSuccess: (results) => {
            const fileInput = document.getElementById("file-input");
            if (fileInput && results.some((r) => r.success)) fileInput.value = "";
        },
    });

    const handleAsyncUpload = async () => {
        if (files.length === 0) return;
        setAsyncError(null);
        setAsyncUploading(true);

        const totalBatches = Math.ceil(files.length / UPLOAD_BATCH_SIZE);
        setBatchProgress({ current: 0, total: totalBatches });

        const allFileTasks = [];
        const allErrors = [];

        try {
            for (let i = 0; i < files.length; i += UPLOAD_BATCH_SIZE) {
                const batch = files.slice(i, i + UPLOAD_BATCH_SIZE);
                setBatchProgress({ current: Math.floor(i / UPLOAD_BATCH_SIZE) + 1, total: totalBatches });

                const formData = new FormData();
                batch.forEach((file) => formData.append("ledger", file));
                formData.append("async", "true");

                const response = await api.post("upload-ledger/", formData, {
                    headers: { "Content-Type": "multipart/form-data" },
                });

                if (response.data.file_tasks) allFileTasks.push(...response.data.file_tasks);
                if (response.data.errors?.length) allErrors.push(...response.data.errors);
            }

            if (allFileTasks.length > 0) {
                setAsyncFileTasks(allFileTasks);
                setShowTaskModal(true);
                clearFiles();
                document.getElementById("file-input").value = "";
            }
            if (allErrors.length > 0) {
                setAsyncError(`${allErrors.length} file(s) failed: ${allErrors.map((e) => e.file).join(", ")}`);
            }
        } catch (err) {
            console.error("Upload error:", err);
            setAsyncError(err.response?.data?.error || err.message || "Upload failed. Please try again.");
        } finally {
            setAsyncUploading(false);
            setBatchProgress(null);
        }
    };

    const handleUpload = () => {
        if (useAsyncMode) handleAsyncUpload();
        else originalHandleUpload();
    };

    const busy = uploading || asyncUploading;

    return (
        <div>
            {/* Header */}
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-foreground">
                        <FileSpreadsheet className="size-6 text-primary" />
                        Ledger Upload
                    </h1>
                    <p className="mt-0.5 text-sm text-muted-foreground">Upload DFIA license ledger files in CSV or HTM/HTML format</p>
                </div>
                <label className="flex cursor-pointer items-center gap-2.5 text-sm" htmlFor="asyncModeSwitch">
                    <Switch id="asyncModeSwitch" checked={useAsyncMode} onCheckedChange={setUseAsyncMode} />
                    <span className="flex items-center gap-1 font-medium text-muted-foreground">
                        <Zap className="size-3.5 text-warning" />
                        Async {useAsyncMode ? "(Parallel)" : "(Sync)"}
                    </span>
                </label>
            </div>

            <TaskStatusModal fileTasks={asyncFileTasks} show={showTaskModal} onHide={() => setShowTaskModal(false)} />

            <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                {/* Main upload */}
                <div className="lg:col-span-2">
                    <Card>
                        <CardHeader className="border-b">
                            <CardTitle className="flex items-center gap-2 text-sm">
                                <CloudUpload className="size-4 text-primary" />Upload Files
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
                                className={`mb-4 flex min-h-[170px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-9 text-center transition-colors ${
                                    dragActive ? "border-primary bg-primary/5" : "border-border bg-card hover:border-primary/60"
                                }`}
                            >
                                <CloudUpload className={`mb-2 size-10 ${dragActive ? "text-primary" : "text-muted-foreground/60"}`} />
                                <p className="mb-1 font-semibold text-foreground">{dragActive ? "Drop files here" : "Drag & drop your ledger files"}</p>
                                <small className="mb-3 text-muted-foreground">or click to browse</small>
                                <span className="pointer-events-none inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-semibold text-primary-foreground" style={{ background: "linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))" }}>
                                    <FolderOpen className="size-3.5" />Browse Files
                                </span>
                                <small className="mt-3 block text-muted-foreground">CSV or HTM/HTML files · Max 50MB per file</small>
                                <input id="file-input" type="file" accept=".csv,.htm,.html" multiple onChange={handleFileChange} className="hidden" />
                            </label>

                            {/* Selected files */}
                            {files.length > 0 && (
                                <div className="mb-4">
                                    <div className="mb-2 flex items-center justify-between">
                                        <span className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground">
                                            <Paperclip className="size-3.5" />{files.length} file{files.length > 1 ? "s" : ""} selected
                                        </span>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            disabled={uploading}
                                            onClick={() => { clearFiles(); document.getElementById("file-input").value = ""; }}
                                        >
                                            <Trash2 className="size-3.5" />Clear All
                                        </Button>
                                    </div>
                                    <div className="flex flex-col gap-2">
                                        {files.map((file, index) => (
                                            <div key={index} className="flex items-center gap-2 rounded-md border border-border/70 bg-muted/40 px-2.5 py-2">
                                                <FileText className="size-4 shrink-0 text-success" />
                                                <div className="min-w-0 flex-1">
                                                    <div className="truncate text-sm font-medium">{file.name}</div>
                                                    <small className="text-muted-foreground">{formatFileSize(file.size)}</small>
                                                </div>
                                                <Button variant="outline" size="icon" className="size-8 shrink-0 text-destructive hover:bg-destructive/10" disabled={uploading} onClick={() => removeFile(index)}>
                                                    <X className="size-3.5" />
                                                </Button>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Error */}
                            {(error || asyncError) && (
                                <div className="mb-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive">
                                    <XCircle className="size-4 shrink-0" />
                                    <div>{error || asyncError}</div>
                                </div>
                            )}

                            {/* Sync progress */}
                            {uploading && Object.keys(fileProgress).length > 0 && (
                                <div className="mb-4">
                                    <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><CloudUpload className="size-4" />Uploading Files</h3>
                                    {Object.entries(fileProgress).map(([index, fileData]) => (
                                        <div key={index} className="mb-3">
                                            <div className="mb-1 flex items-center justify-between">
                                                <small className="flex items-center gap-1 truncate text-muted-foreground" style={{ maxWidth: "70%" }}>
                                                    {fileData.status === "completed" ? <CheckCircle2 className="size-3.5 text-success" />
                                                        : fileData.status === "failed" ? <XCircle className="size-3.5 text-destructive" />
                                                        : <Hourglass className="size-3.5 text-primary" />}
                                                    {fileData.name}
                                                </small>
                                                <small className="text-muted-foreground">
                                                    {fileData.status === "completed" ? "✓ Done" : fileData.status === "failed" ? "✗ Failed" : `${fileData.progress}%`}
                                                </small>
                                            </div>
                                            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                                                <div
                                                    className={`h-full ${fileData.status === "completed" ? "bg-success" : fileData.status === "failed" ? "bg-destructive" : "bg-primary"}`}
                                                    style={{ width: `${fileData.status === "failed" ? 100 : fileData.progress}%` }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Upload button */}
                            <Button size="lg" className="w-full" onClick={handleUpload} disabled={files.length === 0 || busy}>
                                {busy ? (
                                    <>
                                        <Loader2 className="size-4 animate-spin" />
                                        {batchProgress ? `Uploading batch ${batchProgress.current}/${batchProgress.total}…` : `Uploading ${files.length} file${files.length > 1 ? "s" : ""}…`}
                                    </>
                                ) : (
                                    <><Upload className="size-4" />Upload & Process</>
                                )}
                            </Button>
                        </CardContent>
                    </Card>

                    {/* Sync results */}
                    {results.length > 0 && (
                        <Card className="mt-3">
                            <CardHeader className="border-b">
                                <CardTitle className="flex items-center gap-2 text-sm">
                                    <ListChecks className="size-4 text-success" />
                                    Upload Results
                                    <Badge variant="success">{results.filter((r) => r.success).length}/{results.length} succeeded</Badge>
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="max-h-[500px] overflow-y-auto pt-4">
                                {results.map((result, index) => (
                                    <div key={index} className={`mb-2 rounded-lg border px-3.5 py-2.5 text-[13px] ${result.success ? "border-success/30 bg-success/10" : "border-destructive/30 bg-destructive/10"}`}>
                                        <div className="flex items-start gap-3">
                                            {result.success ? <CheckCircle2 className="size-5 shrink-0 text-success" /> : <XCircle className="size-5 shrink-0 text-destructive" />}
                                            <div className="flex-1">
                                                <h4 className="mb-1.5 font-semibold text-foreground">{result.fileName}</h4>
                                                {result.success ? (
                                                    <>
                                                        <p className="mb-2">{result.message}</p>
                                                        {result.stats?.total_licenses > 0 && (
                                                            <div className="mb-2 flex flex-wrap gap-2">
                                                                <Badge variant="success">{result.stats.total_licenses} Licenses</Badge>
                                                            </div>
                                                        )}
                                                        {result.licenses?.length > 0 && (
                                                            <details className="mt-2">
                                                                <summary className="cursor-pointer text-xs font-semibold">View License Numbers ({result.licenses.length})</summary>
                                                                <div className="mt-2 flex flex-wrap gap-1">
                                                                    {result.licenses.map((license, idx) => <Badge key={idx} variant="success">{license}</Badge>)}
                                                                </div>
                                                            </details>
                                                        )}
                                                        {result.data?.results?.[0]?.failed?.length > 0 && (
                                                            <details className="mt-2">
                                                                <summary className="cursor-pointer text-xs font-semibold text-destructive">Failed Licenses ({result.data.results[0].failed.length})</summary>
                                                                <div className="mt-2">
                                                                    {result.data.results[0].failed.map((f, idx) => (
                                                                        <div key={idx} className="mb-1 text-xs text-destructive"><strong>{f.license}:</strong> {f.error}</div>
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

                {/* Instructions */}
                <div className="lg:col-span-1">
                    <Card>
                        <CardHeader className="border-b">
                            <CardTitle className="flex items-center gap-2 text-sm">
                                <Info className="size-4 text-primary" />File Format Guide
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-4">
                            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Required CSV Columns</div>
                            <div className="mb-3 flex flex-wrap gap-1">
                                {["Regn.No.", "Regn.Date", "Lic.No.", "Lic.Date", "IEC", "Scheme.Cd.", "Port", "Notification"].map((col) => (
                                    <code key={col} className="rounded border border-primary/15 bg-primary/10 px-2 py-0.5 text-xs text-primary">{col}</code>
                                ))}
                            </div>
                            <div className="rounded-lg border border-warning/30 bg-warning/10 px-3.5 py-3">
                                <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-warning">
                                    <Lightbulb className="size-4" />Important Notes
                                </div>
                                <ul className="ml-4 list-disc text-xs text-muted-foreground">
                                    <li className="mb-1">Date format: DD/MM/YYYY</li>
                                    <li className="mb-1">License numbers zero-padded to 10 digits</li>
                                    <li className="mb-1">Credit and Debit transactions auto-processed</li>
                                    <li className="mb-1">Multiple files supported · Max 50MB</li>
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
