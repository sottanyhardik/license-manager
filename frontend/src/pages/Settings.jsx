import {useContext, useEffect, useState} from "react";
import {Navigate} from "react-router-dom";
import { toast } from 'react-toastify';
import api from "../api/axios";
import {AuthContext} from "../context/AuthContext";
import {ROLE_LABELS, getRoleBadgeProps} from "../utils/roleConstants";

function fmtDate(val) {
    if (!val) return '—';
    const d = new Date(val);
    if (isNaN(d.getTime())) return '—';
    return `${String(d.getDate()).padStart(2, '0')}-${String(d.getMonth() + 1).padStart(2, '0')}-${d.getFullYear()}`;
}

export default function Settings() {
    const {user: currentUser} = useContext(AuthContext);
    const [users, setUsers] = useState([]);
    const [availableRoles, setAvailableRoles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editingUser, setEditingUser] = useState(null);

    // Guard: superusers only — hooks must all be declared before this
    if (currentUser && !currentUser.is_superuser) {
        return <Navigate to="/403" replace />;
    }

    const [formData, setFormData] = useState({
        username: "",
        email: "",
        first_name: "",
        last_name: "",
        password: "",
        is_active: true,
        roles: [],
    });

    useEffect(() => {
        loadUsers();
        api.get("auth/users/available-roles/")
            .then(r => setAvailableRoles(r.data))
            .catch(() => {});
    }, []);

    const loadUsers = async () => {
        try {
            const response = await api.get("auth/users/");
            const usersData = Array.isArray(response.data)
                ? response.data
                : response.data.results || [];
            setUsers(usersData);
        } catch (error) {
            toast.error("Failed to load users");
            setUsers([]);
        } finally {
            setLoading(false);
        }
    };

    const handleOpenModal = (user = null) => {
        if (user) {
            setEditingUser(user);
            setFormData({
                username: user.username,
                email: user.email || "",
                first_name: user.first_name || "",
                last_name: user.last_name || "",
                password: "",
                is_active: user.is_active,
                roles: user.roles || [],
            });
        } else {
            setEditingUser(null);
            setFormData({
                username: "",
                email: "",
                first_name: "",
                last_name: "",
                password: "",
                is_active: true,
                roles: [],
            });
        }
        setShowModal(true);
    };

    const toggleRole = (code) => {
        setFormData(prev => ({
            ...prev,
            roles: prev.roles.includes(code)
                ? prev.roles.filter(r => r !== code)
                : [...prev.roles, code],
        }));
    };

    const handleCloseModal = () => {
        setShowModal(false);
        setEditingUser(null);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const payload = {...formData};
            if (editingUser && !payload.password) delete payload.password;

            if (editingUser) {
                await api.put(`auth/users/${editingUser.id}/`, payload);
                toast.success("User updated successfully");
            } else {
                await api.post("auth/users/", payload);
                toast.success("User created successfully");
            }
            handleCloseModal();
            loadUsers();
        } catch (error) {
            toast.error(error.response?.data?.detail || "Failed to save user");
        }
    };

    const handleDelete = async (userId) => {
        if (!window.confirm("Are you sure you want to delete this user?")) return;
        try {
            await api.delete(`auth/users/${userId}/`);
            toast.success("User deleted successfully");
            loadUsers();
        } catch (error) {
            toast.error("Failed to delete user");
        }
    };

    if (loading) {
        return (
            <div className="container-fluid" style={{ backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh', padding: '24px' }}>
                <div className="d-flex justify-content-between align-items-center mb-4">
                    <div>
                        <div className="placeholder-glow mb-1"><span className="placeholder col-3 rounded" style={{ height: 24 }}></span></div>
                        <div className="placeholder-glow"><span className="placeholder col-5 rounded" style={{ height: 14 }}></span></div>
                    </div>
                </div>
                <div className="card border-0 shadow-sm">
                    <div className="card-body p-4 placeholder-glow">
                        {[...Array(4)].map((_, i) => (
                            <span key={i} className="placeholder col-12 rounded d-block mb-3" style={{ height: 40 }}></span>
                        ))}
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="container-fluid" style={{ backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh', padding: '20px 24px' }}>
            {/* Compact Header */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h4 className="mb-0 fw-bold" style={{color: 'var(--text-dark)'}}>
                        <i className="bi bi-shield-lock me-2" style={{color: 'var(--primary-color)'}}></i>
                        Users &amp; Roles
                    </h4>
                    <small className="text-muted">Manage users and assign roles — visible to superusers only</small>
                </div>
            </div>

            {/* User Management Card */}
            <div className="card border-0 shadow-sm" style={{ borderRadius: '12px' }}>
                <div className="card-header bg-white border-bottom d-flex justify-content-between align-items-center py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                    <h6 className="mb-0 fw-semibold">
                        <i className="bi bi-people me-2" style={{ color: '#4F46E5' }}></i>
                        User Management
                        <span className="badge ms-2" style={{ backgroundColor: '#4F46E522', color: '#4F46E5', fontSize: '0.7rem' }}>
                            {users.length}
                        </span>
                    </h6>
                    <button
                        className="btn btn-sm btn-primary"
                        onClick={() => handleOpenModal()}
                        style={{ background: 'linear-gradient(135deg, #4F46E5, #4338CA)', border: 'none' }}
                    >
                        <i className="bi bi-plus-lg me-1"></i>Add User
                    </button>
                </div>
                <div className="card-body p-0">
                    <div className="table-responsive">
                        <table className="table table-hover table-sm mb-0">
                            <thead className="table-light">
                            <tr>
                                <th className="ps-3">Username</th>
                                <th>Email</th>
                                <th>Name</th>
                                <th>Roles</th>
                                <th>Status</th>
                                <th>Joined</th>
                                <th className="text-end pe-3">Actions</th>
                            </tr>
                            </thead>
                            <tbody>
                            {users.map((user) => (
                                <tr key={user.id}>
                                    <td className="ps-3">
                                        <div className="d-flex align-items-center gap-2">
                                            <div style={{
                                                width: 30, height: 30, borderRadius: '50%',
                                                background: 'linear-gradient(135deg,#4F46E5,#6366F1)',
                                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                color: 'white', fontSize: '0.7rem', fontWeight: '700', flexShrink: 0
                                            }}>
                                                {user.username[0].toUpperCase()}
                                            </div>
                                            <div>
                                                <div className="fw-medium small">{user.username}</div>
                                                {user.is_superuser && (
                                                    <span className="badge bg-danger" style={{fontSize: '0.65rem'}}>Superuser</span>
                                                )}
                                            </div>
                                        </div>
                                    </td>
                                    <td className="small text-muted">{user.email || '—'}</td>
                                    <td className="small">{user.first_name || user.last_name ? `${user.first_name || ''} ${user.last_name || ''}`.trim() : '—'}</td>
                                    <td>
                                        {(user.roles ?? []).length === 0
                                            ? <span className="text-muted small">—</span>
                                            : (user.roles ?? []).map(r => {
                                                const bp = getRoleBadgeProps(r);
                                                return (
                                                    <span key={r}
                                                          className={`${bp.className} me-1 mb-1`}
                                                          style={{fontSize: '0.65rem', ...bp.style}}>
                                                        {ROLE_LABELS[r] ?? r}
                                                    </span>
                                                );
                                            })
                                        }
                                    </td>
                                    <td>
                                        <span className={`badge ${user.is_active ? 'bg-success' : 'bg-secondary'}`}
                                              style={{fontSize: '0.7rem'}}>
                                            {user.is_active ? 'Active' : 'Inactive'}
                                        </span>
                                    </td>
                                    <td className="small text-muted">{fmtDate(user.date_joined)}</td>
                                    <td className="text-end pe-3">
                                        <button
                                            className="btn btn-sm btn-outline-secondary me-1"
                                            onClick={() => handleOpenModal(user)}
                                            title="Edit User"
                                        >
                                            <i className="bi bi-pencil"></i>
                                        </button>
                                        <button
                                            className="btn btn-sm btn-outline-secondary"
                                            onClick={() => handleDelete(user.id)}
                                            title="Delete User"
                                        >
                                            <i className="bi bi-trash"></i>
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* User Create/Edit Modal */}
            {showModal && (
                <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.6)' }}>
                    <div className="modal-dialog modal-lg">
                        <div className="modal-content" style={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 40px rgba(0,0,0,0.2)' }}>
                            <div className="modal-header" style={{
                                background: 'linear-gradient(135deg, #4F46E5 0%, #4338CA 100%)',
                                color: 'white',
                                borderRadius: '12px 12px 0 0',
                                padding: '1.25rem 1.5rem',
                                borderBottom: 'none'
                            }}>
                                <h5 className="modal-title fw-semibold">
                                    <i className={`bi bi-${editingUser ? 'pencil-square' : 'person-plus'} me-2`}></i>
                                    {editingUser ? 'Edit User' : 'Add User'}
                                </h5>
                                <button type="button" className="btn-close btn-close-white" onClick={handleCloseModal}></button>
                            </div>
                            <form onSubmit={handleSubmit}>
                                <div className="modal-body" style={{ padding: '1.5rem', backgroundColor: 'var(--bs-gray-50)' }}>
                                    <div className="d-flex flex-column gap-3">
                                        {/* Account Credentials */}
                                        <div style={{ background: 'white', borderRadius: '10px', padding: '16px 20px', borderLeft: '3px solid #4F46E5' }}>
                                            <div style={{ fontSize: '0.68rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#4F46E5', marginBottom: '14px' }}>
                                                <i className="bi bi-shield-lock me-1"></i> Account Credentials
                                            </div>
                                            <div className="row g-3">
                                                <div className="col-md-6">
                                                    <label className="form-label" style={{ fontSize: '0.8rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>
                                                        Username <span className="text-danger">*</span>
                                                    </label>
                                                    <input
                                                        type="text"
                                                        className="form-control"
                                                        value={formData.username}
                                                        onChange={(e) => setFormData({...formData, username: e.target.value})}
                                                        required
                                                        disabled={editingUser !== null}
                                                        placeholder="Enter username"
                                                    />
                                                    {editingUser && <small className="text-muted" style={{ fontSize: '0.75rem' }}><i className="bi bi-info-circle me-1"></i>Username cannot be changed</small>}
                                                </div>
                                                <div className="col-md-6">
                                                    <label className="form-label" style={{ fontSize: '0.8rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>
                                                        Password {!editingUser && <span className="text-danger">*</span>}
                                                    </label>
                                                    <input
                                                        type="password"
                                                        className="form-control"
                                                        value={formData.password}
                                                        onChange={(e) => setFormData({...formData, password: e.target.value})}
                                                        required={!editingUser}
                                                        placeholder={editingUser ? 'Leave blank to keep current' : 'Enter password'}
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                        {/* Personal Info */}
                                        <div style={{ background: 'white', borderRadius: '10px', padding: '16px 20px', borderLeft: '3px solid #10b981' }}>
                                            <div style={{ fontSize: '0.68rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#10b981', marginBottom: '14px' }}>
                                                <i className="bi bi-person me-1"></i> Personal Information
                                            </div>
                                            <div className="row g-3">
                                                <div className="col-md-4">
                                                    <label className="form-label" style={{ fontSize: '0.8rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>First Name</label>
                                                    <input
                                                        type="text"
                                                        className="form-control"
                                                        value={formData.first_name}
                                                        onChange={(e) => setFormData({...formData, first_name: e.target.value})}
                                                        placeholder="First name"
                                                    />
                                                </div>
                                                <div className="col-md-4">
                                                    <label className="form-label" style={{ fontSize: '0.8rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Last Name</label>
                                                    <input
                                                        type="text"
                                                        className="form-control"
                                                        value={formData.last_name}
                                                        onChange={(e) => setFormData({...formData, last_name: e.target.value})}
                                                        placeholder="Last name"
                                                    />
                                                </div>
                                                <div className="col-md-4">
                                                    <label className="form-label" style={{ fontSize: '0.8rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Email</label>
                                                    <input
                                                        type="email"
                                                        className="form-control"
                                                        value={formData.email}
                                                        onChange={(e) => setFormData({...formData, email: e.target.value})}
                                                        placeholder="email@example.com"
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                        {/* Roles */}
                                        {availableRoles.length > 0 && (
                                            <div style={{background: 'white', borderRadius: '10px', padding: '16px 20px', borderLeft: '3px solid #8b5cf6'}}>
                                                <div style={{fontSize: '0.68rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8b5cf6', marginBottom: '14px'}}>
                                                    <i className="bi bi-shield-check me-1"></i> Roles
                                                </div>
                                                <div className="row g-2">
                                                    {availableRoles.map(code => (
                                                        <div className="col-md-4" key={code}>
                                                            <div
                                                                className={`form-check border rounded p-2 ${formData.roles.includes(code) ? 'border-primary bg-primary bg-opacity-10' : 'border-light'}`}
                                                                style={{cursor: 'pointer'}}
                                                                onClick={() => toggleRole(code)}
                                                            >
                                                                <input
                                                                    className="form-check-input"
                                                                    type="checkbox"
                                                                    id={`role-${code}`}
                                                                    checked={formData.roles.includes(code)}
                                                                    onChange={() => toggleRole(code)}
                                                                    onClick={e => e.stopPropagation()}
                                                                />
                                                                <label className="form-check-label small" htmlFor={`role-${code}`} style={{cursor: 'pointer'}}>
                                                                    {ROLE_LABELS[code] ?? code}
                                                                </label>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {/* Status */}
                                        <div style={{background: 'white', borderRadius: '10px', padding: '14px 20px', borderLeft: '3px solid #6366F1'}}>
                                            <div className="form-check form-switch">
                                                <input
                                                    type="checkbox"
                                                    className="form-check-input"
                                                    role="switch"
                                                    id="isActive"
                                                    checked={formData.is_active}
                                                    onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                                                />
                                                <label className="form-check-label" htmlFor="isActive" style={{fontWeight: '500'}}>
                                                    Active User
                                                    <small className="text-muted ms-2">Allow this user to log in</small>
                                                </label>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div className="modal-footer" style={{ backgroundColor: 'var(--bs-gray-50)', borderTop: '1px solid #dee2e6', padding: '1rem 1.5rem', borderRadius: '0 0 12px 12px' }}>
                                    <button type="button" className="btn btn-outline-secondary" onClick={handleCloseModal}>
                                        <i className="bi bi-x-lg me-1"></i>Cancel
                                    </button>
                                    <button type="submit" className="btn btn-primary" style={{ background: 'linear-gradient(135deg, #4F46E5, #4338CA)', border: 'none' }}>
                                        <i className={`bi bi-${editingUser ? 'check-circle' : 'person-plus'} me-1`}></i>
                                        {editingUser ? 'Update User' : 'Create User'}
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            )}

        </div>
    );
}
