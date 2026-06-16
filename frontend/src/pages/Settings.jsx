import { useContext, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "react-toastify";
import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import { ROLE_LABELS, getRoleBadgeProps } from "../utils/roleConstants";
import { PageHeader, Button, Skeleton } from "../components/ui";

function fmtDate(val) {
    if (!val) return "—";
    const d = new Date(val);
    if (isNaN(d.getTime())) return "—";
    return `${String(d.getDate()).padStart(2, "0")}-${String(d.getMonth() + 1).padStart(2, "0")}-${d.getFullYear()}`;
}

const EMPTY_FORM = {
    username: "", email: "", first_name: "", last_name: "",
    password: "", is_active: true, roles: [],
};

function SectionBox({ icon, label, tone = "primary", children }) {
    const toneColors = {
        primary: { border: "var(--tb-brand)",         label: "var(--tb-brand)" },
        success: { border: "var(--tb-success)",        label: "var(--tb-success-text)" },
        info:    { border: "var(--tb-info)",           label: "var(--tb-info-text)" },
        neutral: { border: "var(--tb-border-strong)",  label: "var(--tb-text-secondary)" },
    };
    const c = toneColors[tone] || toneColors.primary;
    return (
        <div
            style={{
                background: "var(--tb-card-bg)",
                borderRadius: "var(--tb-r-md)",
                padding: "14px 16px",
                border: "1px solid var(--tb-border)",
                borderLeftWidth: 3,
                borderLeftColor: c.border,
            }}
        >
            <div style={{ fontSize: 10.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: c.label, marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
                <i className={`bi bi-${icon}`} aria-hidden="true" />{label}
            </div>
            {children}
        </div>
    );
}

export default function Settings() {
    const { user: currentUser } = useContext(AuthContext);
    const [users, setUsers] = useState([]);
    const [availableRoles, setAvailableRoles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editingUser, setEditingUser] = useState(null);
    const [saving, setSaving] = useState(false);
    const [formData, setFormData] = useState(EMPTY_FORM);

    useEffect(() => {
        if (!currentUser?.is_superuser) { setLoading(false); return; }
        loadUsers();
        api.get("auth/users/available-roles/").then(r => setAvailableRoles(r.data)).catch(() => {});
    }, [currentUser?.is_superuser]);

    const loadUsers = async () => {
        try {
            const { data } = await api.get("auth/users/");
            setUsers(Array.isArray(data) ? data : data.results || []);
        } catch { toast.error("Failed to load users"); setUsers([]); }
        finally { setLoading(false); }
    };

    const handleOpenModal = (user = null) => {
        if (user) {
            setEditingUser(user);
            setFormData({ username: user.username, email: user.email || "", first_name: user.first_name || "", last_name: user.last_name || "", password: "", is_active: user.is_active, roles: user.roles || [] });
        } else {
            setEditingUser(null);
            setFormData(EMPTY_FORM);
        }
        setShowModal(true);
    };

    const toggleRole = (code) => setFormData(prev => ({
        ...prev,
        roles: prev.roles.includes(code) ? prev.roles.filter(r => r !== code) : [...prev.roles, code],
    }));

    const handleCloseModal = () => { setShowModal(false); setEditingUser(null); };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            const payload = { ...formData };
            if (editingUser && !payload.password) delete payload.password;
            if (editingUser) { await api.put(`auth/users/${editingUser.id}/`, payload); toast.success("User updated"); }
            else { await api.post("auth/users/", payload); toast.success("User created"); }
            handleCloseModal(); loadUsers();
        } catch (err) { toast.error(err.response?.data?.detail || "Failed to save user"); }
        finally { setSaving(false); }
    };

    const handleDelete = async (userId) => {
        if (!window.confirm("Are you sure you want to delete this user?")) return;
        try { await api.delete(`auth/users/${userId}/`); toast.success("User deleted"); loadUsers(); }
        catch { toast.error("Failed to delete user"); }
    };

    if (currentUser && !currentUser.is_superuser) return <Navigate to="/403" replace />;

    if (loading) {
        return (
            <>
                <PageHeader pretitle="Admin" title="Users & Roles" />
                <div className="card">
                    <div className="card-body">
                        {[...Array(5)].map((_, i) => <div key={i} style={{ marginBottom: 10 }}><Skeleton variant="text" width="100%" height={36} /></div>)}
                    </div>
                </div>
            </>
        );
    }

    return (
        <>
            <PageHeader
                pretitle="Admin"
                title="Users & Roles"
                description="Manage users and assign roles — visible to superusers only"
                actions={<Button variant="primary" size="sm" icon="plus-lg" onClick={() => handleOpenModal()}>Add User</Button>}
            />

            <div className="card">
                <div className="card-header" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <i className="bi bi-people" style={{ color: "var(--tb-brand)", fontSize: 15 }} aria-hidden="true" />
                    <span style={{ fontSize: 13.5, fontWeight: 600 }}>User Management</span>
                    <span style={{ fontSize: 11, background: "var(--tb-brand-50)", color: "var(--tb-brand-active)", border: "1px solid var(--tb-brand-100)", borderRadius: "var(--tb-r-pill)", padding: "1px 8px", fontWeight: 500, marginLeft: 4 }}>
                        {users.length}
                    </span>
                </div>
                <div className="card-body p-0">
                    <div className="table-responsive">
                        <table className="table table-hover mb-0">
                            <thead>
                                <tr>
                                    <th style={{ paddingLeft: 16 }}>User</th>
                                    <th>Email</th>
                                    <th>Name</th>
                                    <th>Roles</th>
                                    <th>Status</th>
                                    <th>Joined</th>
                                    <th className="text-end" style={{ paddingRight: 16 }}>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map(user => (
                                    <tr key={user.id}>
                                        <td style={{ paddingLeft: 16 }}>
                                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                                <div style={{ width: 30, height: 30, borderRadius: "50%", background: "linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 12, fontWeight: 700, flexShrink: 0 }} aria-hidden="true">
                                                    {user.username[0].toUpperCase()}
                                                </div>
                                                <div>
                                                    <div style={{ fontSize: 13, fontWeight: 500 }}>{user.username}</div>
                                                    {user.is_superuser && <span className="badge bg-danger" style={{ fontSize: 10 }}>Superuser</span>}
                                                </div>
                                            </div>
                                        </td>
                                        <td style={{ fontSize: 12.5, color: "var(--tb-text-secondary)" }}>{user.email || "—"}</td>
                                        <td style={{ fontSize: 12.5 }}>{user.first_name || user.last_name ? `${user.first_name || ""} ${user.last_name || ""}`.trim() : "—"}</td>
                                        <td>
                                            {(user.roles ?? []).length === 0 ? (
                                                <span style={{ color: "var(--tb-text-muted)", fontSize: 12 }}>—</span>
                                            ) : (
                                                <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                                                    {(user.roles ?? []).map(r => {
                                                        const bp = getRoleBadgeProps(r);
                                                        return <span key={r} className={bp.className} style={{ fontSize: 10, ...bp.style }}>{ROLE_LABELS[r] ?? r}</span>;
                                                    })}
                                                </div>
                                            )}
                                        </td>
                                        <td><span className={`badge ${user.is_active ? "bg-success" : "bg-secondary"}`} style={{ fontSize: 10.5 }}>{user.is_active ? "Active" : "Inactive"}</span></td>
                                        <td style={{ fontSize: 12, color: "var(--tb-text-secondary)", whiteSpace: "nowrap" }}>{fmtDate(user.date_joined)}</td>
                                        <td className="text-end" style={{ paddingRight: 16 }}>
                                            <div style={{ display: "inline-flex", gap: 4 }}>
                                                <button className="btn btn-sm btn-outline-secondary" onClick={() => handleOpenModal(user)} title="Edit" aria-label={`Edit ${user.username}`} style={{ padding: "3px 8px" }}><i className="bi bi-pencil" aria-hidden="true" /></button>
                                                <button className="btn btn-sm btn-outline-danger" onClick={() => handleDelete(user.id)} title="Delete" aria-label={`Delete ${user.username}`} style={{ padding: "3px 8px" }}><i className="bi bi-trash" aria-hidden="true" /></button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                                {users.length === 0 && (
                                    <tr><td colSpan={7} style={{ textAlign: "center", padding: "48px 24px", color: "var(--tb-text-tertiary)" }}><i className="bi bi-people" style={{ fontSize: 28, display: "block", marginBottom: 8, color: "var(--tb-text-muted)" }} />No users found</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {showModal && (
                <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.48)", zIndex: 1050, display: "flex", alignItems: "center", justifyContent: "center", padding: 16, backdropFilter: "blur(2px)", animation: "tb-fade-in 120ms ease both" }} onClick={e => { if (e.target === e.currentTarget) handleCloseModal(); }} role="dialog" aria-modal="true" aria-labelledby="user-modal-title">
                    <div style={{ background: "var(--tb-card-bg)", border: "1px solid var(--tb-border)", borderRadius: "var(--tb-r-xl)", boxShadow: "var(--tb-shadow-overlay)", width: "100%", maxWidth: 640, maxHeight: "90vh", overflow: "hidden", display: "flex", flexDirection: "column", animation: "tb-panel-enter 160ms var(--tb-ease) both" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 20px", borderBottom: "1px solid var(--tb-border)", flexShrink: 0 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <div style={{ width: 32, height: 32, borderRadius: "var(--tb-r-md)", background: "var(--tb-brand-50)", border: "1px solid var(--tb-brand-100)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--tb-brand)", fontSize: 15 }}>
                                    <i className={`bi bi-${editingUser ? "pencil-square" : "person-plus"}`} aria-hidden="true" />
                                </div>
                                <h5 id="user-modal-title" style={{ margin: 0, fontSize: 15, fontWeight: 600, letterSpacing: "-0.01em" }}>{editingUser ? "Edit User" : "Add New User"}</h5>
                            </div>
                            <button type="button" onClick={handleCloseModal} aria-label="Close" style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--tb-text-tertiary)", fontSize: 20, lineHeight: 1, padding: 4, borderRadius: "var(--tb-r-sm)" }}><i className="bi bi-x" aria-hidden="true" /></button>
                        </div>
                        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
                            <div style={{ padding: "20px", overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
                                <SectionBox icon="shield-lock" label="Account Credentials" tone="primary">
                                    <div className="row g-3">
                                        <div className="col-md-6">
                                            <label className="form-label required" htmlFor="modal-username">Username</label>
                                            <input id="modal-username" type="text" className="form-control" value={formData.username} onChange={e => setFormData({ ...formData, username: e.target.value })} required disabled={!!editingUser} placeholder="Enter username" autoComplete="off" />
                                            {editingUser && <div className="form-text">Username cannot be changed.</div>}
                                        </div>
                                        <div className="col-md-6">
                                            <label className="form-label" htmlFor="modal-password">Password {!editingUser && <span style={{ color: "var(--tb-danger)" }}>*</span>}</label>
                                            <input id="modal-password" type="password" className="form-control" value={formData.password} onChange={e => setFormData({ ...formData, password: e.target.value })} required={!editingUser} placeholder={editingUser ? "Leave blank to keep current" : "Enter password"} autoComplete="new-password" />
                                        </div>
                                    </div>
                                </SectionBox>
                                <SectionBox icon="person" label="Personal Information" tone="success">
                                    <div className="row g-3">
                                        <div className="col-md-4"><label className="form-label" htmlFor="modal-fname">First Name</label><input id="modal-fname" type="text" className="form-control" value={formData.first_name} onChange={e => setFormData({ ...formData, first_name: e.target.value })} placeholder="First name" /></div>
                                        <div className="col-md-4"><label className="form-label" htmlFor="modal-lname">Last Name</label><input id="modal-lname" type="text" className="form-control" value={formData.last_name} onChange={e => setFormData({ ...formData, last_name: e.target.value })} placeholder="Last name" /></div>
                                        <div className="col-md-4"><label className="form-label" htmlFor="modal-email">Email</label><input id="modal-email" type="email" className="form-control" value={formData.email} onChange={e => setFormData({ ...formData, email: e.target.value })} placeholder="email@example.com" /></div>
                                    </div>
                                </SectionBox>
                                {availableRoles.length > 0 && (
                                    <SectionBox icon="shield-check" label="Roles" tone="info">
                                        <div className="row g-2">
                                            {availableRoles.map(code => {
                                                const checked = formData.roles.includes(code);
                                                return (
                                                    <div className="col-md-4 col-6" key={code}>
                                                        <div onClick={() => toggleRole(code)} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 10px", borderRadius: "var(--tb-r-sm)", border: `1px solid ${checked ? "var(--tb-brand-200)" : "var(--tb-border)"}`, background: checked ? "var(--tb-brand-50)" : "var(--tb-card-bg)", cursor: "pointer", transition: "all var(--tb-tx-fast)" }}>
                                                            <input type="checkbox" className="form-check-input" id={`role-${code}`} checked={checked} onChange={() => toggleRole(code)} onClick={e => e.stopPropagation()} style={{ margin: 0, flexShrink: 0 }} />
                                                            <label htmlFor={`role-${code}`} style={{ fontSize: 11.5, cursor: "pointer", color: checked ? "var(--tb-brand-active)" : "var(--tb-text-secondary)", fontWeight: checked ? 500 : 400, margin: 0 }}>{ROLE_LABELS[code] ?? code}</label>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </SectionBox>
                                )}
                                <SectionBox icon="toggle-on" label="Account Status" tone="neutral">
                                    <div className="form-check form-switch">
                                        <input type="checkbox" className="form-check-input" role="switch" id="modal-is-active" checked={formData.is_active} onChange={e => setFormData({ ...formData, is_active: e.target.checked })} />
                                        <label className="form-check-label" htmlFor="modal-is-active">Active — allow this user to log in</label>
                                    </div>
                                </SectionBox>
                            </div>
                            <div style={{ padding: "12px 20px", borderTop: "1px solid var(--tb-border-soft)", background: "var(--tb-sunken)", display: "flex", gap: 8, justifyContent: "flex-end", flexShrink: 0 }}>
                                <Button variant="outline-secondary" size="sm" onClick={handleCloseModal} disabled={saving}>Cancel</Button>
                                <Button type="submit" variant="primary" size="sm" loading={saving} icon={saving ? null : (editingUser ? "check-lg" : "person-plus")}>
                                    {saving ? "Saving…" : editingUser ? "Update User" : "Create User"}
                                </Button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </>
    );
}
