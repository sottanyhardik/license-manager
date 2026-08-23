import { useContext, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AuthContext } from "../context/AuthContext";
import useSpeechRecognition from "../hooks/useSpeechRecognition";
import { AlertCircle, Check, CheckSquare, ChevronDown, ClipboardCheck, OctagonX, Trash2, X } from "lucide-react";
import {
    TASK_PRIORITY,
    TASK_STATUS,
    addRemark,
    completeTask,
    createTask,
    deleteTask,
    listAssignableUsers,
    listTasks,
    rejectTask,
    reopenTask,
    updateTask,
} from "../api/tasks";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_LABEL = {
    [TASK_STATUS.PENDING]: "Pending",
    [TASK_STATUS.IN_PROGRESS]: "In Progress",
    [TASK_STATUS.COMPLETED]: "Completed",
    [TASK_STATUS.REJECTED]: "Rejected",
};

// Tailwind semantic classes — no Bootstrap dependency
const STATUS_BADGE: Record<string, string> = {
    [TASK_STATUS.PENDING]:     "bg-warning/15 text-warning border border-warning/25",
    [TASK_STATUS.IN_PROGRESS]: "bg-info/15 text-info border border-info/25",
    [TASK_STATUS.COMPLETED]:   "bg-success/15 text-success border border-success/25",
    [TASK_STATUS.REJECTED]:    "bg-muted text-muted-foreground border border-border",
};

const PRIORITY_BADGE: Record<string, string> = {
    [TASK_PRIORITY.LOW]:    "bg-muted text-muted-foreground border border-border",
    [TASK_PRIORITY.NORMAL]: "bg-primary/10 text-primary border border-primary/20",
    [TASK_PRIORITY.HIGH]:   "bg-destructive/15 text-destructive border border-destructive/25",
};

const STATUS_FILTERS = [
    { value: "open", label: "Open" },
    { value: "", label: "All" },
    { value: TASK_STATUS.PENDING, label: "Pending" },
    { value: TASK_STATUS.IN_PROGRESS, label: "In Progress" },
    { value: TASK_STATUS.COMPLETED, label: "Completed" },
    { value: TASK_STATUS.REJECTED, label: "Rejected" },
];

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

const TASKS_KEY = (params: Record<string, string>) => ["tasks", params] as const;
const USERS_KEY = ["tasks-assignable-users"] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(value) {
    if (!value) return "";
    try {
        return new Date(value).toLocaleString();
    } catch {
        return value;
    }
}

const URGENT_RX = /\b(urgent|asap|high\s*priority)\b/i;
const ASSIGN_RX = /\bassign(?:\s+(?:this\s+)?task)?\s+to\s+([a-z][a-z0-9 ._-]{0,40}?)(?=\s*(?:,|\.|;|:|$|\bplease\b|\bto\b))/i;

// Pull the most useful error string out of an axios error response.
function extractApiError(err, fallback = "Request failed") {
    if (!err) return fallback;
    if (err.response) {
        const data = err.response.data;
        if (typeof data === "string" && data) return data;
        if (data?.detail) return data.detail;
        if (data && typeof data === "object") {
            // DRF field-validation error shape: { field: ["msg"] }
            const firstKey = Object.keys(data)[0];
            const firstVal = firstKey ? data[firstKey] : null;
            const msg = Array.isArray(firstVal) ? firstVal[0] : firstVal;
            if (msg) return firstKey === "non_field_errors" ? msg : `${firstKey}: ${msg}`;
        }
        return `${fallback} (HTTP ${err.response.status})`;
    }
    if (err.message) return err.message;
    return fallback;
}

function fuzzyMatchUser(name, users) {
    if (!name || !users || users.length === 0) return null;
    const lower = name.trim().toLowerCase();
    const candidates = users.map(u => ({
        u,
        username: (u.username || "").toLowerCase(),
        first: (u.first_name || "").toLowerCase(),
        last: (u.last_name || "").toLowerCase(),
        full: `${u.first_name || ""} ${u.last_name || ""}`.trim().toLowerCase(),
    }));
    // Exact matches first
    let hit = candidates.find(c => c.username === lower || c.first === lower || c.full === lower);
    if (hit) return hit.u;
    // First-token match (e.g. "ankit sharma" → matches "ankit")
    const firstToken = lower.split(/\s+/)[0];
    hit = candidates.find(c => c.username === firstToken || c.first === firstToken);
    if (hit) return hit.u;
    // Contains
    hit = candidates.find(c =>
        c.username.includes(lower) || c.first.includes(lower) || c.full.includes(lower)
    );
    return hit ? hit.u : null;
}

/**
 * Parse a voice segment into a task payload.
 * Recognises "assign (task) to NAME" and "urgent"/"asap"/"high priority".
 */
function parseVoiceCommand(rawText, users) {
    let title = (rawText || "").trim();
    let priority = TASK_PRIORITY.NORMAL;
    let assignedTo = null;

    if (URGENT_RX.test(title)) {
        priority = TASK_PRIORITY.HIGH;
    }

    const assignMatch = title.match(ASSIGN_RX);
    if (assignMatch) {
        const candidate = assignMatch[1].trim();
        const match = fuzzyMatchUser(candidate, users);
        if (match) {
            assignedTo = match.id;
            // Strip "assign (task) to NAME" from the title
            title = title.replace(assignMatch[0], " ").replace(/\s+/g, " ").trim();
        }
    }

    // If, after stripping, the title is empty, fall back to the original text
    if (!title) title = (rawText || "").trim();
    return { title, priority, assigned_to: assignedTo };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function TaskDrawer({ show, onClose }) {
    const { user } = useContext(AuthContext) || {};
    const qc = useQueryClient();

    const [statusFilter, setStatusFilter] = useState("open");
    const [search, setSearch] = useState("");
    const [expanded, setExpanded] = useState(null);
    const [remarkDrafts, setRemarkDrafts] = useState({});

    // Create form state
    const [draft, setDraft] = useState({
        title: "",
        description: "",
        priority: TASK_PRIORITY.NORMAL,
        assigned_to: "",
        due_date: "",
    });
    const [saving, setSaving] = useState(false);
    const titleInputRef = useRef(null);

    // Build API params — used both for the query key and the fetch call
    const queryParams = useMemo<Record<string, string>>(() => {
        const p: Record<string, string> = {};
        if (search.trim()) p.search = search.trim();
        if (statusFilter && statusFilter !== "open") p.status = statusFilter;
        return p;
    }, [search, statusFilter]);

    // ---------------------------------------------------------------------------
    // Queries
    // ---------------------------------------------------------------------------

    const { data: rawTaskData, isLoading } = useQuery({
        queryKey: TASKS_KEY(queryParams),
        queryFn: () => listTasks(queryParams),
        enabled: show,
    });

    const { data: users = [] } = useQuery({
        queryKey: USERS_KEY,
        queryFn: listAssignableUsers,
        enabled: show,
        staleTime: Infinity, // assignable users don't change mid-session
    });

    // Derive the filtered task list from raw server data (client-side "open" filter)
    const tasks = useMemo(() => {
        const rows = Array.isArray(rawTaskData)
            ? rawTaskData
            : (rawTaskData?.results || []);
        if (statusFilter !== "open") return rows;
        const myId = user?.id;
        return rows.filter(t => {
            if (t.status === TASK_STATUS.PENDING || t.status === TASK_STATUS.IN_PROGRESS) return true;
            // Bounced-back: rejected by someone else, I'm the creator → still "open" for me
            if (
                t.status === TASK_STATUS.REJECTED &&
                myId &&
                t.created_by === myId &&
                t.rejected_by &&
                t.rejected_by !== myId
            ) return true;
            return false;
        });
    }, [rawTaskData, statusFilter, user?.id]);

    // ---------------------------------------------------------------------------
    // Mutations — all invalidate ['tasks'] on success so the list refreshes
    // ---------------------------------------------------------------------------

    const invalidateTasks = () => qc.invalidateQueries({ queryKey: ["tasks"] });

    const createMutation = useMutation({
        mutationFn: createTask,
        onSuccess: () => { invalidateTasks(); },
        onError: (err) => toast.error(extractApiError(err, "Failed to create task")),
    });

    const completeMutation = useMutation({
        mutationFn: (id: number) => completeTask(id),
        onSuccess: () => { invalidateTasks(); toast.success("Marked completed"); },
        onError: () => toast.error("Failed to update"),
    });

    const rejectMutation = useMutation({
        mutationFn: ({ id, reason }: { id: number; reason: string }) => rejectTask(id, reason),
        onSuccess: () => { invalidateTasks(); toast.success("Task rejected"); },
        onError: () => toast.error("Failed to reject"),
    });

    const reopenMutation = useMutation({
        mutationFn: (id: number) => reopenTask(id),
        onSuccess: () => { invalidateTasks(); },
        onError: () => toast.error("Failed to reopen"),
    });

    const deleteMutation = useMutation({
        mutationFn: (id: number) => deleteTask(id),
        onSuccess: () => { invalidateTasks(); toast.success("Deleted"); },
        onError: () => toast.error("Failed to delete"),
    });

    const remarkMutation = useMutation({
        mutationFn: ({ id, text }: { id: number; text: string }) => addRemark(id, text),
        onSuccess: (_data, { id }) => {
            invalidateTasks();
            setRemarkDrafts(prev => ({ ...prev, [id]: "" }));
        },
        onError: () => toast.error("Failed to add remark"),
    });

    const updateMutation = useMutation({
        mutationFn: ({ id, patch }: { id: number; patch: Record<string, unknown> }) =>
            updateTask(id, patch),
        onSuccess: () => { invalidateTasks(); },
        onError: () => toast.error("Failed to update"),
    });

    // ---------------------------------------------------------------------------
    // Speech / voice
    // ---------------------------------------------------------------------------

    // Keep latest users list reachable from speech callback without re-creating the recognizer
    const usersRef = useRef(users);
    useEffect(() => { usersRef.current = users; }, [users]);

    const speech = useSpeechRecognition({
        onSegment: (text) => {
            handleQuickCreate(text);
        },
    });

    // Surface speech errors to the user (the hook itself is silent).
    useEffect(() => {
        if (!speech.error) return;
        toast.error(speech.error.message);
    }, [speech.error]);

    // Focus and stop speech on drawer open/close
    useEffect(() => {
        if (show) {
            setTimeout(() => titleInputRef.current?.focus(), 150);
        } else {
            if (speech.listening) speech.stop();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [show]);

    // ---------------------------------------------------------------------------
    // Handlers
    // ---------------------------------------------------------------------------

    const handleQuickCreate = async (rawText) => {
        const text = (rawText || "").trim();
        if (!text) return;
        const parsed = parseVoiceCommand(text, usersRef.current);
        const payload: Record<string, any> = { title: parsed.title, priority: parsed.priority };
        if (parsed.assigned_to) payload.assigned_to = parsed.assigned_to;
        try {
            await createMutation.mutateAsync(payload);
            const bits = [`Task added${parsed.priority === TASK_PRIORITY.HIGH ? " (high)" : ""}`];
            if (parsed.assigned_to) {
                const u = usersRef.current.find(x => x.id === parsed.assigned_to);
                if (u) bits.push(`→ ${u.username}`);
            }
            toast.success(bits.join(" "));
        } catch (err) {
            // error already handled by mutation onError
        }
    };

    const handleSubmit = async (e) => {
        e?.preventDefault?.();
        if (!draft.title.trim()) {
            toast.error("Title is required");
            return;
        }
        setSaving(true);
        try {
            const payload: Record<string, any> = {
                title: draft.title.trim(),
                description: draft.description.trim(),
                priority: draft.priority,
            };
            if (draft.assigned_to) payload.assigned_to = parseInt(draft.assigned_to, 10);
            if (draft.due_date) payload.due_date = draft.due_date;
            await createMutation.mutateAsync(payload);
            setDraft({ title: "", description: "", priority: TASK_PRIORITY.NORMAL, assigned_to: "", due_date: "" });
            toast.success("Task created");
        } catch {
            // error already handled by mutation onError
        } finally {
            setSaving(false);
        }
    };

    const handleComplete = (task) => {
        if (task.status === TASK_STATUS.COMPLETED) {
            reopenMutation.mutate(task.id);
        } else {
            completeMutation.mutate(task.id);
        }
    };

    const handleReject = (task) => {
        const reason = window.prompt("Reason for rejection (optional):", "") || "";
        rejectMutation.mutate({ id: task.id, reason });
    };

    const handleDelete = (task) => {
        if (!window.confirm("Delete this task?")) return;
        deleteMutation.mutate(task.id);
    };

    const handleAddRemark = (task) => {
        const text = (remarkDrafts[task.id] || "").trim();
        if (!text) return;
        remarkMutation.mutate({ id: task.id, text });
    };

    const handleInlineUpdate = (task, patch) => {
        updateMutation.mutate({ id: task.id, patch });
    };

    const toggleSpeech = () => {
        if (!speech.isSupported) {
            toast.error("Voice input is not supported in this browser. Use Chrome or Edge.");
            return;
        }
        if (speech.listening) {
            speech.stop();
        } else {
            speech.clearError();
            speech.start();
        }
    };

    if (!show) return null;

    return (
        <>
            <div
                onClick={onClose}
                style={{
                    position: "fixed",
                    inset: 0,
                    background: "var(--surface-overlay)",
                    backdropFilter: "blur(2px)",
                    WebkitBackdropFilter: "blur(2px)",
                    zIndex: 1050,
                    transition: "opacity 180ms cubic-bezier(0.16,1,0.3,1)",
                }}
            />
            <aside
                role="dialog"
                aria-label="Tasks"
                style={{
                    position: "fixed",
                    top: 0,
                    right: 0,
                    bottom: 0,
                    width: "min(440px, 100vw)",
                    background: "var(--surface-raised)",
                    zIndex: 1060,
                    display: "flex",
                    flexDirection: "column",
                    boxShadow: "var(--elevation-overlay)",
                    borderLeft: "1px solid var(--border-subtle)",
                }}
            >
                {/* Header */}
                <div className="flex items-center justify-between border-b border-border px-5 py-[18px]">
                    <div className="flex items-center gap-2.5">
                        <span
                            aria-hidden="true"
                            className="inline-flex size-7 items-center justify-center rounded-lg bg-indigo-50 text-primary"
                        >
                            <CheckSquare className="size-4" />
                        </span>
                        <span className="text-base font-semibold tracking-tight">Tasks</span>
                    </div>
                    <button
                        className="inline-flex size-8 cursor-pointer items-center justify-center rounded-lg border border-border bg-muted text-muted-foreground hover:bg-muted/80"
                        onClick={onClose}
                        aria-label="Close"
                        type="button"
                    >
                        <X className="size-4" />
                    </button>
                </div>

                {/* Quick create + voice */}
                <form
                    onSubmit={handleSubmit}
                    className="border-b border-border bg-muted/40 px-5 py-4"
                >
                    <div className="flex gap-2 mb-2">
                        <input
                            ref={titleInputRef}
                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring "
                            placeholder='New task title (or click mic and say "next" to split)'
                            value={draft.title}
                            onChange={(e) => setDraft(d => ({ ...d, title: e.target.value }))}
                        />
                        <button
                            type="button"
                            onClick={toggleSpeech}
                            className={`inline-flex size-8 shrink-0 items-center justify-center rounded-md border text-sm transition-colors ${speech.listening ? "border-destructive/40 bg-destructive/10 text-destructive hover:bg-destructive/20" : "border-primary/30 bg-primary/5 text-primary hover:bg-primary/10"}`}
                            title={speech.isSupported ? "Voice input" : "Voice not supported in this browser"}
                            disabled={!speech.isSupported}
                        >
                            {speech.listening ? <span className="size-4">🔇</span> : <span className="size-4">🎤</span>}
                        </button>
                    </div>

                    {speech.listening && (
                        <div className="mb-2 mt-1 min-h-[18px] rounded-lg border border-border bg-card px-2.5 py-2 text-sm text-muted-foreground">
                            <span className="font-medium text-destructive">
                                <span
                                    aria-hidden="true"
                                    className="mr-1.5 inline-block size-2 rounded-full bg-destructive align-middle"
                                    style={{ animation: "tb-skel 1.2s ease-in-out infinite" }}
                                />
                                Listening
                            </span>{" "}— say <code>next</code> to split, <code>assign to NAME</code>, or include <code>urgent</code> for high priority.
                            {speech.interim
                                ? <em className="mt-1 block" style={{ color: "var(--tb-text-tertiary)" }}>"{speech.interim}"</em>
                                : <span className="mt-1 block italic" style={{ color: "var(--tb-text-tertiary)" }}>
                                      Waiting for audio…
                                  </span>
                            }
                        </div>
                    )}

                    {!speech.listening && speech.error && (
                        <div
                            className="mb-2 mt-1 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-2.5 py-2 text-sm text-destructive"
                            role="alert"
                        >
                            <AlertCircle className="size-4" aria-hidden="true" />
                            <div className="flex-1">{speech.error.message}</div>
                            <button
                                type="button"
                                className="mt-0.5 inline-flex size-4 shrink-0 cursor-pointer items-center justify-center rounded text-current opacity-60 hover:opacity-100"
                                aria-label="Dismiss"
                                onClick={speech.clearError}
                            >
                                <X className="size-3" />
                            </button>
                        </div>
                    )}

                    <div className="flex flex-wrap gap-2">
                        <div className="flex-1 min-w-0">
                            <select
                                className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                value={draft.priority}
                                onChange={(e) => setDraft(d => ({ ...d, priority: e.target.value }))}
                            >
                                <option value={TASK_PRIORITY.LOW}>Low</option>
                                <option value={TASK_PRIORITY.NORMAL}>Normal</option>
                                <option value={TASK_PRIORITY.HIGH}>High</option>
                            </select>
                        </div>
                        <div className="flex-1 min-w-0">
                            <input
                                type="date"
                                className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                value={draft.due_date}
                                onChange={(e) => setDraft(d => ({ ...d, due_date: e.target.value }))}
                            />
                        </div>
                        <div className="w-full">
                            <select
                                className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                value={draft.assigned_to}
                                onChange={(e) => setDraft(d => ({ ...d, assigned_to: e.target.value }))}
                            >
                                <option value="">Assign to (myself)</option>
                                {users.map(u => (
                                    <option key={u.id} value={u.id}>
                                        {u.username}{u.first_name || u.last_name ? ` — ${u.first_name} ${u.last_name}`.trim() : ""}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="w-full">
                            <textarea
                                className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring "
                                placeholder="Description (optional)"
                                rows={2}
                                value={draft.description}
                                onChange={(e) => setDraft(d => ({ ...d, description: e.target.value }))}
                            />
                        </div>
                        <div className="flex justify-end">
                            <button type="submit" className="flex items-center gap-1.5 rounded bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground cursor-pointer hover:bg-primary/90 disabled:opacity-50" disabled={saving}>
                                {saving ? "Saving..." : "Add task"}
                            </button>
                        </div>
                    </div>
                </form>

                {/* Filters */}
                <div className="flex items-center gap-2 border-b border-border bg-card px-5 py-3">
                    <input
                        className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring "
                        placeholder="Search…"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                    <select
                        className="flex h-8 w-[130px] shrink-0 rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                    >
                        {STATUS_FILTERS.map(f => (
                            <option key={f.value} value={f.value}>{f.label}</option>
                        ))}
                    </select>
                </div>

                {/* List */}
                <div className="flex-grow overflow-y-auto">
                    {isLoading && (
                        <div className="px-5 py-4">
                            <div className="skeleton mb-2.5 h-[14px] w-[70%]" />
                            <div className="skeleton h-3 w-[45%]" />
                        </div>
                    )}
                    {!isLoading && tasks.length === 0 && (
                        <div className="empty-state">
                            <div className="empty-icon"><ClipboardCheck className="size-9" /></div>
                            <div className="empty-title">No tasks yet</div>
                            <div className="empty-sub">Add one above or hold the mic and dictate.</div>
                        </div>
                    )}
                    {tasks.map(task => {
                        const open = expanded === task.id;
                        const mine = user?.id && task.created_by === user.id;
                        const closed = task.status === TASK_STATUS.COMPLETED || task.status === TASK_STATUS.REJECTED;
                        const bouncedBack =
                            task.status === TASK_STATUS.REJECTED &&
                            mine && task.rejected_by && task.rejected_by !== user.id;
                        const assigneeLabel = task.assigned_to_username || task.created_by_username || "self";
                        const assigneeIsSelf = task.assigned_to === user?.id || (!task.assigned_to && mine);
                        return (
                            <div
                                key={task.id}
                                className="border-b border-border px-5 py-3"
                            >
                                <div className="flex items-start gap-2">
                                    <input
                                        type="checkbox"
                                        className="mt-1 size-4 shrink-0 cursor-pointer rounded accent-primary"
                                        checked={task.status === TASK_STATUS.COMPLETED}
                                        onChange={() => handleComplete(task)}
                                        title={task.status === TASK_STATUS.COMPLETED ? "Reopen" : "Mark complete"}
                                    />
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <span className={`font-medium ${task.status === TASK_STATUS.COMPLETED ? "line-through" : ""}`}>
                                                {task.title}
                                            </span>
                                            <span className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${STATUS_BADGE[task.status] || "bg-muted text-muted-foreground border border-border"}`}>
                                                {STATUS_LABEL[task.status] || task.status}
                                            </span>
                                            {bouncedBack && (
                                                <span className="inline-flex items-center rounded-full border border-warning/25 bg-warning/15 px-1.5 py-0.5 text-[10px] font-semibold text-warning">
                                                    Bounced back
                                                </span>
                                            )}
                                            {task.priority === TASK_PRIORITY.HIGH && (
                                                <span className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${PRIORITY_BADGE[task.priority]}`}>
                                                    High
                                                </span>
                                            )}
                                        </div>
                                        <div className="text-sm text-muted-foreground">
                                            → <strong>{assigneeIsSelf ? `${assigneeLabel} (you)` : assigneeLabel}</strong>
                                            {task.assigned_on && <span> · assigned {formatDate(task.assigned_on)}</span>}
                                            {!mine && task.created_by_username && (
                                                <span> · by {task.created_by_username}</span>
                                            )}
                                            {task.due_date && <span> · due {task.due_date}</span>}
                                        </div>
                                        {bouncedBack && (
                                            <div className="mt-1 rounded bg-amber-50 border border-amber-200 p-2 text-sm">
                                                <strong>Rejected by {task.rejected_by_username || "assignee"}</strong>
                                                {task.rejection_reason && <span>: {task.rejection_reason}</span>}
                                                {!task.rejection_reason && <span> (no reason given)</span>}
                                                <button
                                                    type="button"
                                                    className="ml-2 cursor-pointer text-xs text-primary underline-offset-2 hover:underline"
                                                    onClick={() => reopenMutation.mutate(task.id)}
                                                >
                                                    Reopen
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-1">
                                        <button
                                            className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                                            onClick={() => setExpanded(open ? null : task.id)}
                                            title="Details"
                                        >
                                            <ChevronDown className={`size-4 transition-transform ${open ? 'rotate-180' : ''}`} />
                                        </button>
                                        {!closed && (
                                            <button
                                                className="flex items-center gap-1.5 rounded border border-warning/30 bg-warning/10 px-2.5 py-1.5 text-xs font-medium text-warning cursor-pointer hover:bg-warning/20"
                                                onClick={() => handleReject(task)}
                                                title="Reject"
                                            >
                                                <OctagonX className="size-4" />
                                            </button>
                                        )}
                                        {mine && (
                                            <button
                                                className="flex items-center gap-1.5 rounded border border-destructive/30 bg-destructive/10 px-2.5 py-1.5 text-xs font-medium text-destructive cursor-pointer hover:bg-destructive/20"
                                                onClick={() => handleDelete(task)}
                                                title="Delete"
                                            >
                                                <Trash2 className="size-4" />
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {open && (
                                    <div className="mt-2 ps-4">
                                        {/* Inline editable description */}
                                        <textarea
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm mb-2 outline-none focus-visible:border-ring"
                                            placeholder="Description"
                                            rows={2}
                                            defaultValue={task.description}
                                            onBlur={(e) => {
                                                if (e.target.value !== task.description) {
                                                    handleInlineUpdate(task, { description: e.target.value });
                                                }
                                            }}
                                        />
                                        <div className="mb-2 flex flex-wrap gap-2">
                                            <div className="flex-1 min-w-0">
                                                <select
                                                    className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                    value={task.priority}
                                                    onChange={(e) => handleInlineUpdate(task, { priority: e.target.value })}
                                                >
                                                    <option value={TASK_PRIORITY.LOW}>Low</option>
                                                    <option value={TASK_PRIORITY.NORMAL}>Normal</option>
                                                    <option value={TASK_PRIORITY.HIGH}>High</option>
                                                </select>
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <input
                                                    type="date"
                                                    className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                    value={task.due_date || ""}
                                                    onChange={(e) => handleInlineUpdate(task, { due_date: e.target.value || null })}
                                                />
                                            </div>
                                            <div className="w-full">
                                                <select
                                                    className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                    value={task.assigned_to || ""}
                                                    onChange={(e) => handleInlineUpdate(task, { assigned_to: e.target.value ? parseInt(e.target.value, 10) : null })}
                                                >
                                                    <option value="">Unassigned (myself)</option>
                                                    {users.map(u => (
                                                        <option key={u.id} value={u.id}>{u.username}</option>
                                                    ))}
                                                </select>
                                            </div>
                                        </div>

                                        {/* Remarks */}
                                        <div className="rounded border border-border bg-muted/40 p-2">
                                            <div className="mb-1 text-xs font-semibold">Remarks</div>
                                            <div className="flex gap-2 mb-2">
                                                <input
                                                    className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring "
                                                    placeholder="Add a remark…"
                                                    value={remarkDrafts[task.id] || ""}
                                                    onChange={(e) => setRemarkDrafts(prev => ({ ...prev, [task.id]: e.target.value }))}
                                                    onKeyDown={(e) => e.key === "Enter" && handleAddRemark(task)}
                                                />
                                                <button
                                                    className="flex items-center gap-1.5 rounded bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground cursor-pointer hover:bg-primary/90"
                                                    onClick={() => handleAddRemark(task)}
                                                    type="button"
                                                >
                                                    Add
                                                </button>
                                            </div>
                                            {(task.remarks || []).length === 0 && (
                                                <div className="text-xs text-muted-foreground">No remarks yet.</div>
                                            )}
                                            {(task.remarks || []).map(r => (
                                                <div key={r.id} className="mb-1 text-xs">
                                                    <strong>{r.created_by_username}</strong>{" "}
                                                    <span className="text-muted-foreground">· {formatDate(r.created_on)}</span>
                                                    <div>{r.text}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </aside>
        </>
    );
}
