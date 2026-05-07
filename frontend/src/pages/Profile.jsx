import {useContext, useState} from "react";
import {useNavigate} from "react-router-dom";
import {AuthContext} from "../context/AuthContext";
import api from "../api/axios";

export default function Profile() {
    const {user, loginSuccess} = useContext(AuthContext);
    const navigate = useNavigate();
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    const [formData, setFormData] = useState({
        first_name: user?.first_name || "",
        last_name: user?.last_name || "",
        email: user?.email || "",
    });

    const handleEdit = () => {
        setEditing(true);
        setError("");
        setSuccess("");
    };

    const handleCancel = () => {
        setEditing(false);
        setFormData({
            first_name: user?.first_name || "",
            last_name: user?.last_name || "",
            email: user?.email || "",
        });
        setError("");
        setSuccess("");
    };

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value,
        });
    };

    const handleSave = async () => {
        setSaving(true);
        setError("");
        setSuccess("");

        try {
            const {data} = await api.patch("/auth/me/", formData);

            // Update user in context and localStorage
            loginSuccess({
                access: localStorage.getItem("access"),
                refresh: localStorage.getItem("refresh"),
                user: data,
            });

            setSuccess("Profile updated successfully!");
            setEditing(false);
        } catch (err) {
            setError(
                err.response?.data?.detail ||
                err.response?.data?.email?.[0] ||
                "Failed to update profile"
            );
        } finally {
            setSaving(false);
        }
    };

    if (!user) {
        return (
            <div className="container mt-4">
                <div className="alert alert-warning">Loading user data...</div>
            </div>
        );
    }

    const initials = ((user.first_name?.[0] || '') + (user.last_name?.[0] || '') || user.username?.[0] || '?').toUpperCase();

    return (
        <div className="container-fluid" style={{ backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh', padding: '20px 24px' }}>
            {/* Compact Header */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h4 className="mb-0 fw-bold" style={{ color: 'var(--text-dark)' }}>
                        <i className="bi bi-person-circle me-2" style={{ color: 'var(--primary-color)' }}></i>
                        My Profile
                    </h4>
                    <small className="text-muted">Manage your account information</small>
                </div>
                {!editing && (
                    <button className="btn btn-sm btn-outline-primary" onClick={handleEdit}>
                        <i className="bi bi-pencil me-1"></i>Edit Profile
                    </button>
                )}
            </div>

            {error && (
                <div className="alert alert-danger alert-dismissible fade show d-flex align-items-center gap-2 mb-3">
                    <i className="bi bi-exclamation-circle-fill flex-shrink-0"></i>
                    <span>{error}</span>
                    <button type="button" className="btn-close ms-auto" onClick={() => setError("")}></button>
                </div>
            )}
            {success && (
                <div className="alert alert-success alert-dismissible fade show d-flex align-items-center gap-2 mb-3">
                    <i className="bi bi-check-circle-fill flex-shrink-0"></i>
                    <span>{success}</span>
                    <button type="button" className="btn-close ms-auto" onClick={() => setSuccess("")}></button>
                </div>
            )}

            <div className="row g-3">
                {/* Avatar card */}
                <div className="col-lg-3">
                    <div className="card border-0 shadow-sm text-center" style={{ borderRadius: '12px' }}>
                        <div className="card-body py-4">
                            <div style={{
                                width: 80, height: 80, borderRadius: '50%',
                                background: 'linear-gradient(135deg, #4F46E5, #6366F1)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: '1.75rem', fontWeight: '700', color: 'white',
                                margin: '0 auto 16px'
                            }}>
                                {initials}
                            </div>
                            <h6 className="fw-bold mb-1">
                                {user.first_name || user.last_name
                                    ? `${user.first_name || ''} ${user.last_name || ''}`.trim()
                                    : user.username}
                            </h6>
                            <small className="text-muted">@{user.username}</small>
                            <div className="mt-2">
                                <span className="badge bg-success" style={{ fontSize: '0.7rem' }}>Active</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Form card */}
                <div className="col-lg-9">
                    <div className="card border-0 shadow-sm" style={{ borderRadius: '12px' }}>
                        <div className="card-header bg-white border-bottom py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                            <h6 className="mb-0 fw-semibold">
                                <i className="bi bi-person me-2" style={{ color: '#4F46E5' }}></i>
                                Account Details
                            </h6>
                        </div>
                        <div className="card-body p-4">
                            <div className="d-flex flex-column gap-3">
                                {/* Account info section */}
                                <div style={{ background: 'var(--bs-gray-50)', borderRadius: '10px', padding: '16px 20px', borderLeft: '3px solid #6b7280' }}>
                                    <div style={{ fontSize: '0.68rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#6b7280', marginBottom: '14px' }}>
                                        <i className="bi bi-shield-lock me-1"></i> Account
                                    </div>
                                    <div>
                                        <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Username</label>
                                        <div className="form-control" style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', color: 'var(--text-secondary)', cursor: 'not-allowed' }}>
                                            {user.username}
                                        </div>
                                        <small className="text-muted" style={{ fontSize: '0.73rem' }}>
                                            <i className="bi bi-info-circle me-1"></i>Username cannot be changed
                                        </small>
                                    </div>
                                </div>

                                {/* Personal info section */}
                                <div style={{ background: editing ? 'white' : 'var(--bs-gray-50)', borderRadius: '10px', padding: '16px 20px', borderLeft: '3px solid #4F46E5', border: editing ? '1px solid #e0e7ff' : undefined }}>
                                    <div style={{ fontSize: '0.68rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#4F46E5', marginBottom: '14px' }}>
                                        <i className="bi bi-person me-1"></i> Personal Information
                                        {editing && <span className="badge ms-2" style={{ backgroundColor: '#4F46E522', color: '#4F46E5', fontSize: '0.6rem' }}>Editing</span>}
                                    </div>
                                    <div className="row g-3">
                                        <div className="col-md-6">
                                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>First Name</label>
                                            {editing ? (
                                                <input type="text" className="form-control" name="first_name" value={formData.first_name} onChange={handleChange} placeholder="First name" />
                                            ) : (
                                                <div className="form-control" style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
                                                    {user.first_name || <em className="text-muted small">Not set</em>}
                                                </div>
                                            )}
                                        </div>
                                        <div className="col-md-6">
                                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Last Name</label>
                                            {editing ? (
                                                <input type="text" className="form-control" name="last_name" value={formData.last_name} onChange={handleChange} placeholder="Last name" />
                                            ) : (
                                                <div className="form-control" style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
                                                    {user.last_name || <em className="text-muted small">Not set</em>}
                                                </div>
                                            )}
                                        </div>
                                        <div className="col-12">
                                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Email</label>
                                            {editing ? (
                                                <input type="email" className="form-control" name="email" value={formData.email} onChange={handleChange} placeholder="email@example.com" />
                                            ) : (
                                                <div className="form-control" style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
                                                    {user.email || <em className="text-muted small">Not set</em>}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {editing && (
                                <div className="d-flex gap-2 mt-4 pt-3" style={{ borderTop: '1px solid #e5e7eb' }}>
                                    <button
                                        className="btn btn-primary"
                                        onClick={handleSave}
                                        disabled={saving}
                                        style={{ padding: '10px 28px', fontWeight: '600', background: 'linear-gradient(135deg, #4F46E5, #4338CA)', border: 'none', borderRadius: '8px' }}
                                    >
                                        {saving ? (
                                            <><span className="spinner-border spinner-border-sm me-2"></span>Saving...</>
                                        ) : (
                                            <><i className="bi bi-check-circle me-2"></i>Save Changes</>
                                        )}
                                    </button>
                                    <button className="btn btn-outline-secondary" onClick={handleCancel} disabled={saving} style={{ padding: '10px 20px', borderRadius: '8px' }}>
                                        <i className="bi bi-x-lg me-2"></i>Cancel
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
