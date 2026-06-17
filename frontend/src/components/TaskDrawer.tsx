import { useContext, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "react-toastify";
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

const STATUS_LABEL = {
    [TASK_STATUS.PENDING]: "Pending",
    [TASK_STATUS.IN_PROGRESS]: "In Progress",
    [TASK_STATUS.COMPLETED]: "Completed",
    [TASK_STATUS.REJECTED]: "Rejected",
};

const STATUS_BADGE = {
    [TASK_STATUS.PENDING]: "bg-warning text-dark",
    [TASK_STATUS.IN_PROGRESS]: "bg-info text-dark",
    [TASK_STATUS.COMPLETED]: "bg-success",
    [TASK_STATUS.REJECTED]: "bg-secondary",
};

const PRIORITY_BADGE = {
    [TASK_PRIORITY.LOW]: "bg-light text-dark border",
    [TASK_PRIORITY.NORMAL]: "bg-light text-dark border",
    [TASK_PRIORITY.HIGH]: "bg-danger",
};

const STATUS_FILTERS = [
    { value: "open", label: "Open" },
    { value: "", label: "All" },
    { value: TASK_STATUS.PENDING, label: "Pending" },
    { value: TASK_STATUS.IN_PROGRESS, label: "In Progress" },
    { value: TASK_STATUS.COMPLETED, label: "Completed" },
    { value: TASK_STATUS.REJECTED, label: "Rejected" },
];

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

export default function TaskDrawer({ show, onClose }) {
    const { user } = useContext(AuthContext) || {};
    const [tasks, setTasks] = useState([]);
    const [loading, setLoading] = useState(false);
    const [statusFilter, setStatusFilter] = useState("open");
    const [search, setSearch] = useState("");
    const [users, setUsers] = useState([]);
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

    // Keep latest users list reachable from speech callback without re-creating the recognizer
    const usersRef = useRef(users);
    useEffect(() => { usersRef.current = users; }, [users]);

    const speech = useSpeechRecognition({
        onSegment: (text) => {
            // Each completed segment becomes a new task auto-saved.
            handleQuickCreate(text);
        },
    });

    // Surface speech errors to the user (the hook itself is silent).
    useEffect(() => {
        if (!speech.error) return;
        toast.error(speech.error.message);
    }, [speech.error]);

    const fetchTasks = useMemo(() => async () => {
        setLoading(true);
        try {
            const params = {};
            if (search.trim()) params.search = search.trim();
            if (statusFilter && statusFilter !== "open") params.status = statusFilter;
            const data = await listTasks(params);
            // DRF default pagination returns {results: []} when paginator is global; otherwise array.
            const rows = Array.isArray(data) ? data : (data.results || []);
            const myId = user?.id;
            const filtered = statusFilter === "open"
                ? rows.filter(t => {
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
                })
                : rows;
            setTasks(filtered);
        } catch {
            // axios interceptor already toasts most errors
        } finally {
            setLoading(false);
        }
    }, [search, statusFilter, user?.id]);

    useEffect(() => {
        if (show) {
            fetchTasks();
            // Lazy load assignable users once per open
            if (users.length === 0) {
                listAssignableUsers().then(setUsers).catch(() => {});
            }
            setTimeout(() => titleInputRef.current?.focus(), 150);
        } else {
            // Stop dictation when closing
            if (speech.listening) speech.stop();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [show, fetchTasks]);

    const handleQuickCreate = async (rawText) => {
        const text = (rawText || "").trim();
        if (!text) return;
        const parsed = parseVoiceCommand(text, usersRef.current);
        const payload = { title: parsed.title, priority: parsed.priority };
        if (parsed.assigned_to) payload.assigned_to = parsed.assigned_to;
        try {
            const created = await createTask(payload);
            setTasks(prev => [created, ...prev]);
            const bits = [`Task added${parsed.priority === TASK_PRIORITY.HIGH ? " (high)" : ""}`];
            if (parsed.assigned_to) {
                const u = usersRef.current.find(x => x.id === parsed.assigned_to);
                if (u) bits.push(`→ ${u.username}`);
            }
            toast.success(bits.join(" "));
        } catch (err) {
            toast.error(extractApiError(err, "Failed to add task"));
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
            const payload = {
                title: draft.title.trim(),
                description: draft.description.trim(),
                priority: draft.priority,
            };
            if (draft.assigned_to) payload.assigned_to = parseInt(draft.assigned_to, 10);
            if (draft.due_date) payload.due_date = draft.due_date;
            const created = await createTask(payload);
            setTasks(prev => [created, ...prev]);
            setDraft({ title: "", description: "", priority: TASK_PRIORITY.NORMAL, assigned_to: "", due_date: "" });
            toast.success("Task created");
        } catch (err) {
            toast.error(extractApiError(err, "Failed to create task"));
        } finally {
            setSaving(false);
        }
    };

    // After an action mutates a task, drop it from the current list if it no longer matches the filter.
    const rowMatchesFilter = (row) => {
        if (statusFilter !== "open") {
            if (!statusFilter) return true;
            return row.status === statusFilter;
        }
        if (row.status === TASK_STATUS.PENDING || row.status === TASK_STATUS.IN_PROGRESS) return true;
        if (
            row.status === TASK_STATUS.REJECTED &&
            user?.id && row.created_by === user.id &&
            row.rejected_by && row.rejected_by !== user.id
        ) return true;
        return false;
    };

    const replaceAndFilter = (updated) =>
        setTasks(prev => prev
            .map(t => t.id === updated.id ? updated : t)
            .filter(rowMatchesFilter)
        );

    const handleComplete = async (task) => {
        try {
            const updated = await completeTask(task.id);
            replaceAndFilter(updated);
            toast.success("Marked completed");
        } catch {
            toast.error("Failed to update");
        }
    };

    const handleReject = async (task) => {
        const reason = window.prompt("Reason for rejection (optional):", "") || "";
        try {
            const updated = await rejectTask(task.id, reason);
            replaceAndFilter(updated);
            toast.success("Task rejected");
        } catch {
            toast.error("Failed to reject");
        }
    };

    const handleReopen = async (task) => {
        try {
            const updated = await reopenTask(task.id);
            replaceAndFilter(updated);
        } catch {
            toast.error("Failed to reopen");
        }
    };

    const handleDelete = async (task) => {
        if (!window.confirm("Delete this task?")) return;
        try {
            await deleteTask(task.id);
            setTasks(prev => prev.filter(t => t.id !== task.id));
            toast.success("Deleted");
        } catch {
            toast.error("Failed to delete");
        }
    };

    const handleAddRemark = async (task) => {
        const text = (remarkDrafts[task.id] || "").trim();
        if (!text) return;
        try {
            const remark = await addRemark(task.id, text);
            setTasks(prev => prev.map(t => (
                t.id === task.id ? { ...t, remarks: [remark, ...(t.remarks || [])] } : t
            )));
            setRemarkDrafts(prev => ({ ...prev, [task.id]: "" }));
        } catch {
            toast.error("Failed to add remark");
        }
    };

    const handleInlineUpdate = async (task, patch) => {
        try {
            const updated = await updateTask(task.id, patch);
            setTasks(prev => prev.map(t => t.id === task.id ? updated : t));
        } catch {
            toast.error("Failed to update");
        }
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
                <div
                    className="d-flex align-items-center justify-content-between"
                    style={{
                        padding: "18px 20px",
                        borderBottom: "1px solid var(--border-subtle)",
                    }}
                >
                    <div className="d-flex align-items-center" style={{ gap: 10 }}>
                        <span
                            aria-hidden="true"
                            style={{
                                display: "inline-flex",
                                alignItems: "center",
                                justifyContent: "center",
                                width: 28,
                                height: 28,
                                borderRadius: 8,
                                background: "var(--indigo-50)",
                                color: "var(--primary-color)",
                            }}
                        >
                            <CheckSquare className="size-4" />
                        </span>
                        <span style={{ fontSize: "1rem", fontWeight: 600, letterSpacing: "-0.01em" }}>Tasks</span>
                    </div>
                    <button
                        className="flex items-center gap-1.5 rounded border border-border bg-muted px-2.5 py-1.5 text-xs font-medium cursor-pointer hover:bg-muted/80"
                        onClick={onClose}
                        aria-label="Close"
                        style={{ width: 32, height: 32, padding: 0, borderRadius: 8 }}
                    >
                        <X className="size-4" />
                    </button>
                </div>

                {/* Quick create + voice */}
                <form
                    onSubmit={handleSubmit}
                    style={{
                        padding: "16px 20px",
                        background: "var(--surface-sunken)",
                        borderBottom: "1px solid var(--border-subtle)",
                    }}
                >
                    <div className="d-flex gap-2 mb-2">
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
                            className={`btn btn-sm ${speech.listening ? "btn-danger" : "btn-outline-primary"}`}
                            title={speech.isSupported ? "Voice input" : "Voice not supported in this browser"}
                            disabled={!speech.isSupported}
                        >
                            {speech.listening ? <span className="size-4">🔇</span> : <span className="size-4">🎤</span>}
                        </button>
                    </div>

                    {speech.listening && (
                        <div
                            className="small mb-2"
                            style={{
                                minHeight: 18,
                                color: "var(--tb-text-secondary)",
                                background: "var(--tb-card-bg)",
                                border: "1px solid var(--tb-border)",
                                borderRadius: 8,
                                padding: "8px 10px",
                                marginTop: 4,
                            }}
                        >
                            <span style={{ color: "var(--tb-danger)", fontWeight: 500 }}>
                                <span
                                    aria-hidden="true"
                                    style={{
                                        display: "inline-block",
                                        width: 8, height: 8, borderRadius: 999,
                                        background: "var(--tb-danger)",
                                        marginRight: 6,
                                        verticalAlign: "middle",
                                        animation: "tb-skel 1.2s ease-in-out infinite",
                                    }}
                                />
                                Listening
                            </span>{" "}— say <code>next</code> to split, <code>assign to NAME</code>, or include <code>urgent</code> for high priority.
                            {speech.interim
                                ? <em className="d-block mt-1" style={{ color: "var(--tb-text-tertiary)" }}>"{speech.interim}"</em>
                                : <span className="d-block mt-1" style={{ color: "var(--tb-text-tertiary)", fontStyle: "italic" }}>
                                      Waiting for audio…
                                  </span>
                            }
                        </div>
                    )}

                    {!speech.listening && speech.error && (
                        <div
                            className="small mb-2 d-flex align-items-start"
                            role="alert"
                            style={{
                                gap: 8,
                                color: "var(--tb-danger-text)",
                                background: "var(--tb-danger-soft)",
                                border: "1px solid var(--tb-danger-border)",
                                borderRadius: 8,
                                padding: "8px 10px",
                                marginTop: 4,
                            }}
                        >
                            <AlertCircle className="size-4" aria-hidden="true" />
                            <div style={{ flex: 1 }}>{speech.error.message}</div>
                            <button
                                type="button"
                                className="btn-close btn-sm"
                                aria-label="Dismiss"
                                onClick={speech.clearError}
                                style={{ fontSize: "0.6rem", marginTop: 2 }}
                            />
                        </div>
                    )}

                    <div className="flex flex-wrap gap-2">
                        <div className="col-6">
                            <select
                                flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring
                                value={draft.priority}
                                onChange={(e) => setDraft(d => ({ ...d, priority: e.target.value }))}
                            >
                                <option value={TASK_PRIORITY.LOW}>Low</option>
                                <option value={TASK_PRIORITY.NORMAL}>Normal</option>
                                <option value={TASK_PRIORITY.HIGH}>High</option>
                            </select>
                        </div>
                        <div className="col-6">
                            <input
                                type="date"
                                className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring "
                                value={draft.due_date}
                                onChange={(e) => setDraft(d => ({ ...d, due_date: e.target.value }))}
                            />
                        </div>
                        <div className="col-12">
                            <select
                                flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring
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
                        <div className="col-12">
                            <textarea
                                className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring "
                                placeholder="Description (optional)"
                                rows={2}
                                value={draft.description}
                                onChange={(e) => setDraft(d => ({ ...d, description: e.target.value }))}
                            />
                        </div>
                        <div className="col-12 d-flex justify-content-end">
                            <button type="submit" className="flex items-center gap-1.5 rounded bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground cursor-pointer hover:bg-primary/90 disabled:opacity-50" disabled={saving}>
                                {saving ? "Saving..." : "Add task"}
                            </button>
                        </div>
                    </div>
                </form>

                {/* Filters */}
                <div
                    className="d-flex align-items-center"
                    style={{
                        padding: "12px 20px",
                        gap: 8,
                        background: "var(--surface-raised)",
                        borderBottom: "1px solid var(--border-subtle)",
                    }}
                >
                    <input
                        className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring "
                        placeholder="Search…"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && fetchTasks()}
                    />
                    <select
                        flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring
                        style={{ width: 130 }}
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                    >
                        {STATUS_FILTERS.map(f => (
                            <option key={f.value} value={f.value}>{f.label}</option>
                        ))}
                    </select>
                </div>

                {/* List */}
                <div className="flex-grow-1" style={{ overflowY: "auto" }}>
                    {loading && (
                        <div style={{ padding: "16px 20px" }}>
                            <div className="skeleton" style={{ height: 14, width: "70%", marginBottom: 10 }} />
                            <div className="skeleton" style={{ height: 12, width: "45%" }} />
                        </div>
                    )}
                    {!loading && tasks.length === 0 && (
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
                                className="task-drawer-row"
                                style={{
                                    padding: "12px 20px",
                                    borderBottom: "1px solid var(--border-subtle)",
                                }}
                            >
                                <div className="d-flex align-items-start gap-2">
                                    <input
                                        type="checkbox"
                                        className="form-check-input mt-1"
                                        checked={task.status === TASK_STATUS.COMPLETED}
                                        onChange={() => task.status === TASK_STATUS.COMPLETED ? handleReopen(task) : handleComplete(task)}
                                        title={task.status === TASK_STATUS.COMPLETED ? "Reopen" : "Mark complete"}
                                    />
                                    <div className="flex-grow-1" style={{ minWidth: 0 }}>
                                        <div className="d-flex align-items-center gap-2 flex-wrap">
                                            <span style={{
                                                textDecoration: task.status === TASK_STATUS.COMPLETED ? "line-through" : "none",
                                                fontWeight: 500,
                                            }}>
                                                {task.title}
                                            </span>
                                            <span className={`badge ${STATUS_BADGE[task.status] || "bg-secondary"}`} style={{ fontSize: "0.65rem" }}>
                                                {STATUS_LABEL[task.status] || task.status}
                                            </span>
                                            {bouncedBack && (
                                                <span className="badge bg-warning text-dark" style={{ fontSize: "0.65rem" }}>
                                                    Bounced back
                                                </span>
                                            )}
                                            {task.priority === TASK_PRIORITY.HIGH && (
                                                <span className={`badge ${PRIORITY_BADGE[task.priority]}`} style={{ fontSize: "0.65rem" }}>
                                                    High
                                                </span>
                                            )}
                                        </div>
                                        <div className="small text-muted">
                                            → <strong>{assigneeIsSelf ? `${assigneeLabel} (you)` : assigneeLabel}</strong>
                                            {task.assigned_on && <span> · assigned {formatDate(task.assigned_on)}</span>}
                                            {!mine && task.created_by_username && (
                                                <span> · by {task.created_by_username}</span>
                                            )}
                                            {task.due_date && <span> · due {task.due_date}</span>}
                                        </div>
                                        {bouncedBack && (
                                            <div
                                                className="small mt-1 p-2 rounded"
                                                style={{ background: "#fff3cd", border: "1px solid #ffeeba" }}
                                            >
                                                <strong>Rejected by {task.rejected_by_username || "assignee"}</strong>
                                                {task.rejection_reason && <span>: {task.rejection_reason}</span>}
                                                {!task.rejection_reason && <span> (no reason given)</span>}
                                                <button
                                                    type="button"
                                                    className="ml-2 cursor-pointer text-xs text-primary underline-offset-2 hover:underline"
                                                    onClick={() => handleReopen(task)}
                                                >
                                                    Reopen
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                    <div className="btn-group btn-group-sm">
                                        <button
                                            className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                                            onClick={() => setExpanded(open ? null : task.id)}
                                            title="Details"
                                        >
                                            <span className="inline-block transition-transform" style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}><ChevronDown className="size-4" /></span>
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
                                        <div className="flex flex-wrap gap-2 mb-2">
                                            <div className="col-6">
                                                <select
                                                    flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring
                                                    value={task.priority}
                                                    onChange={(e) => handleInlineUpdate(task, { priority: e.target.value })}
                                                >
                                                    <option value={TASK_PRIORITY.LOW}>Low</option>
                                                    <option value={TASK_PRIORITY.NORMAL}>Normal</option>
                                                    <option value={TASK_PRIORITY.HIGH}>High</option>
                                                </select>
                                            </div>
                                            <div className="col-6">
                                                <input
                                                    type="date"
                                                    className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring "
                                                    value={task.due_date || ""}
                                                    onChange={(e) => handleInlineUpdate(task, { due_date: e.target.value || null })}
                                                />
                                            </div>
                                            <div className="col-12">
                                                <select
                                                    flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring
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
                                        <div className="border rounded p-2" style={{ background: "#fafbfc" }}>
                                            <div className="small fw-semibold mb-1">Remarks</div>
                                            <div className="d-flex gap-2 mb-2">
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
                                                <div className="small text-muted">No remarks yet.</div>
                                            )}
                                            {(task.remarks || []).map(r => (
                                                <div key={r.id} className="small mb-1">
                                                    <strong>{r.created_by_username}</strong>{" "}
                                                    <span className="text-muted">· {formatDate(r.created_on)}</span>
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
