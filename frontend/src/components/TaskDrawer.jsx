import { useContext, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "react-toastify";
import { AuthContext } from "../context/AuthContext";
import useSpeechRecognition from "../hooks/useSpeechRecognition";
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

    const speech = useSpeechRecognition({
        onSegment: (text) => {
            // Each completed segment becomes a new task auto-saved.
            handleQuickCreate(text);
        },
    });

    const fetchTasks = useMemo(() => async () => {
        setLoading(true);
        try {
            const params = {};
            if (search.trim()) params.search = search.trim();
            if (statusFilter && statusFilter !== "open") params.status = statusFilter;
            const data = await listTasks(params);
            // DRF default pagination returns {results: []} when paginator is global; otherwise array.
            const rows = Array.isArray(data) ? data : (data.results || []);
            const filtered = statusFilter === "open"
                ? rows.filter(t => t.status === TASK_STATUS.PENDING || t.status === TASK_STATUS.IN_PROGRESS)
                : rows;
            setTasks(filtered);
        } catch {
            // axios interceptor already toasts most errors
        } finally {
            setLoading(false);
        }
    }, [search, statusFilter]);

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

    const handleQuickCreate = async (title) => {
        const text = (title || "").trim();
        if (!text) return;
        try {
            const created = await createTask({ title: text, priority: TASK_PRIORITY.NORMAL });
            setTasks(prev => [created, ...prev]);
            toast.success("Task added");
        } catch {
            toast.error("Failed to add task");
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
        } catch {
            toast.error("Failed to create task");
        } finally {
            setSaving(false);
        }
    };

    const handleComplete = async (task) => {
        try {
            const updated = await completeTask(task.id);
            setTasks(prev => prev.map(t => t.id === task.id ? updated : t));
            toast.success("Marked completed");
        } catch {
            toast.error("Failed to update");
        }
    };

    const handleReject = async (task) => {
        const reason = window.prompt("Reason for rejection (optional):", "") || "";
        try {
            const updated = await rejectTask(task.id, reason);
            setTasks(prev => prev.map(t => t.id === task.id ? updated : t));
            toast.success("Task rejected");
        } catch {
            toast.error("Failed to reject");
        }
    };

    const handleReopen = async (task) => {
        try {
            const updated = await reopenTask(task.id);
            setTasks(prev => prev.map(t => t.id === task.id ? updated : t));
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
        if (speech.listening) speech.stop();
        else speech.start();
    };

    if (!show) return null;

    return (
        <>
            <div
                onClick={onClose}
                style={{
                    position: "fixed",
                    inset: 0,
                    background: "rgba(0,0,0,0.35)",
                    zIndex: 1050,
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
                    background: "#fff",
                    zIndex: 1060,
                    display: "flex",
                    flexDirection: "column",
                    boxShadow: "-4px 0 20px rgba(0,0,0,0.15)",
                }}
            >
                {/* Header */}
                <div className="d-flex align-items-center justify-content-between p-3 border-bottom">
                    <div className="d-flex align-items-center gap-2">
                        <i className="bi bi-check2-square fs-5"></i>
                        <strong>Tasks</strong>
                    </div>
                    <button className="btn btn-sm btn-light" onClick={onClose} aria-label="Close">
                        <i className="bi bi-x-lg"></i>
                    </button>
                </div>

                {/* Quick create + voice */}
                <form onSubmit={handleSubmit} className="p-3 border-bottom" style={{ background: "#f8f9fa" }}>
                    <div className="d-flex gap-2 mb-2">
                        <input
                            ref={titleInputRef}
                            className="form-control form-control-sm"
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
                            <i className={`bi ${speech.listening ? "bi-mic-mute-fill" : "bi-mic-fill"}`}></i>
                        </button>
                    </div>

                    {speech.listening && (
                        <div className="small text-muted mb-2" style={{ minHeight: 18 }}>
                            <span className="text-danger">● Listening</span> — say <code>next</code> to start a new task.
                            {speech.interim && <em className="ms-1">"{speech.interim}"</em>}
                        </div>
                    )}

                    <div className="row g-2">
                        <div className="col-6">
                            <select
                                className="form-select form-select-sm"
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
                                className="form-control form-control-sm"
                                value={draft.due_date}
                                onChange={(e) => setDraft(d => ({ ...d, due_date: e.target.value }))}
                            />
                        </div>
                        <div className="col-12">
                            <select
                                className="form-select form-select-sm"
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
                                className="form-control form-control-sm"
                                placeholder="Description (optional)"
                                rows={2}
                                value={draft.description}
                                onChange={(e) => setDraft(d => ({ ...d, description: e.target.value }))}
                            />
                        </div>
                        <div className="col-12 d-flex justify-content-end">
                            <button type="submit" className="btn btn-sm btn-primary" disabled={saving}>
                                {saving ? "Saving..." : "Add task"}
                            </button>
                        </div>
                    </div>
                </form>

                {/* Filters */}
                <div className="px-3 py-2 border-bottom d-flex gap-2 align-items-center" style={{ background: "#fff" }}>
                    <input
                        className="form-control form-control-sm"
                        placeholder="Search…"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && fetchTasks()}
                    />
                    <select
                        className="form-select form-select-sm"
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
                    {loading && <div className="text-center py-4 text-muted small">Loading…</div>}
                    {!loading && tasks.length === 0 && (
                        <div className="text-center py-4 text-muted small">No tasks.</div>
                    )}
                    {tasks.map(task => {
                        const open = expanded === task.id;
                        const mine = user?.id && task.created_by === user.id;
                        const closed = task.status === TASK_STATUS.COMPLETED || task.status === TASK_STATUS.REJECTED;
                        return (
                            <div key={task.id} className="border-bottom px-3 py-2">
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
                                            {task.priority === TASK_PRIORITY.HIGH && (
                                                <span className={`badge ${PRIORITY_BADGE[task.priority]}`} style={{ fontSize: "0.65rem" }}>
                                                    High
                                                </span>
                                            )}
                                        </div>
                                        <div className="small text-muted">
                                            {task.assigned_to_username && <span>→ {task.assigned_to_username} · </span>}
                                            by {task.created_by_username}
                                            {task.due_date && <span> · due {task.due_date}</span>}
                                        </div>
                                    </div>
                                    <div className="btn-group btn-group-sm">
                                        <button
                                            className="btn btn-outline-secondary btn-sm"
                                            onClick={() => setExpanded(open ? null : task.id)}
                                            title="Details"
                                        >
                                            <i className={`bi bi-chevron-${open ? "up" : "down"}`}></i>
                                        </button>
                                        {!closed && (
                                            <button
                                                className="btn btn-outline-warning btn-sm"
                                                onClick={() => handleReject(task)}
                                                title="Reject"
                                            >
                                                <i className="bi bi-x-octagon"></i>
                                            </button>
                                        )}
                                        {mine && (
                                            <button
                                                className="btn btn-outline-danger btn-sm"
                                                onClick={() => handleDelete(task)}
                                                title="Delete"
                                            >
                                                <i className="bi bi-trash"></i>
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {open && (
                                    <div className="mt-2 ps-4">
                                        {/* Inline editable description */}
                                        <textarea
                                            className="form-control form-control-sm mb-2"
                                            placeholder="Description"
                                            rows={2}
                                            defaultValue={task.description}
                                            onBlur={(e) => {
                                                if (e.target.value !== task.description) {
                                                    handleInlineUpdate(task, { description: e.target.value });
                                                }
                                            }}
                                        />
                                        <div className="row g-2 mb-2">
                                            <div className="col-6">
                                                <select
                                                    className="form-select form-select-sm"
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
                                                    className="form-control form-control-sm"
                                                    value={task.due_date || ""}
                                                    onChange={(e) => handleInlineUpdate(task, { due_date: e.target.value || null })}
                                                />
                                            </div>
                                            <div className="col-12">
                                                <select
                                                    className="form-select form-select-sm"
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
                                                    className="form-control form-control-sm"
                                                    placeholder="Add a remark…"
                                                    value={remarkDrafts[task.id] || ""}
                                                    onChange={(e) => setRemarkDrafts(prev => ({ ...prev, [task.id]: e.target.value }))}
                                                    onKeyDown={(e) => e.key === "Enter" && handleAddRemark(task)}
                                                />
                                                <button
                                                    className="btn btn-sm btn-primary"
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
