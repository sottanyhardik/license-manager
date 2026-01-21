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

    return (
        <div className="container-fluid" style={{ backgroundColor: '#f8f9fa', minHeight: '100vh', padding: '24px' }}>
            {/* Professional Header with Gradient */}
            <div style={{
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                padding: '32px',
                borderRadius: '12px',
                boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
                color: 'white',
                marginBottom: '24px'
            }}>
                <div className="d-flex justify-content-between align-items-center flex-wrap">
                    <div>
                        <div style={{ marginBottom: '12px', opacity: '0.9' }}>
                            <a
                                href="/"
                                onClick={(e) => { e.preventDefault(); navigate('/'); }}
                                style={{ color: 'white', textDecoration: 'none', fontSize: '0.9rem' }}
                            >
                                <i className="bi bi-house-door me-2"></i>Home
                            </a>
                            <span className="mx-2">/</span>
                            <span style={{ fontSize: '0.9rem' }}>Profile</span>
                        </div>
                        <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '0' }}>
                            <i className="bi bi-person-circle me-3"></i>
                            My Profile
                        </h1>
                    </div>
                    {!editing && (
                        <button
                            className="btn"
                            onClick={handleEdit}
                            style={{
                                backgroundColor: 'white',
                                border: '2px solid white',
                                color: '#667eea',
                                fontWeight: '600',
                                padding: '10px 24px',
                                boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                                marginTop: '12px'
                            }}
                        >
                            <i className="bi bi-pencil me-2"></i>
                            Edit Profile
                        </button>
                    )}
                </div>
            </div>

            <div className="row">
                <div className="col-lg-8 mx-auto">
                    <div className="card border-0 shadow-sm" style={{ borderRadius: '12px' }}>
                        <div className="card-body" style={{ padding: '32px' }}>
                            {error && (
                                <div className="alert alert-danger alert-dismissible fade show">
                                    {error}
                                    <button
                                        type="button"
                                        className="btn-close"
                                        onClick={() => setError("")}
                                    ></button>
                                </div>
                            )}

                            {success && (
                                <div className="alert alert-success alert-dismissible fade show">
                                    {success}
                                    <button
                                        type="button"
                                        className="btn-close"
                                        onClick={() => setSuccess("")}
                                    ></button>
                                </div>
                            )}

                            <div className="mb-4">
                                <label className="form-label" style={{ fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
                                    <i className="bi bi-person-badge me-2"></i>
                                    Username
                                </label>
                                <div className="form-control" style={{ backgroundColor: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '12px' }}>
                                    {user.username}
                                </div>
                                <small className="text-muted" style={{ fontSize: '0.8rem', marginTop: '4px', display: 'block' }}>
                                    <i className="bi bi-info-circle me-1"></i>
                                    Username cannot be changed
                                </small>
                            </div>

                            <div className="mb-4">
                                <label className="form-label" style={{ fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
                                    <i className="bi bi-person me-2"></i>
                                    First Name
                                </label>
                                {editing ? (
                                    <input
                                        type="text"
                                        className="form-control"
                                        name="first_name"
                                        value={formData.first_name}
                                        onChange={handleChange}
                                        placeholder="Enter first name"
                                        style={{ borderRadius: '8px', padding: '12px', border: '1px solid #d1d5db' }}
                                    />
                                ) : (
                                    <div className="form-control" style={{ backgroundColor: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '12px' }}>
                                        {user.first_name || <em className="text-muted">Not set</em>}
                                    </div>
                                )}
                            </div>

                            <div className="mb-4">
                                <label className="form-label" style={{ fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
                                    <i className="bi bi-person me-2"></i>
                                    Last Name
                                </label>
                                {editing ? (
                                    <input
                                        type="text"
                                        className="form-control"
                                        name="last_name"
                                        value={formData.last_name}
                                        onChange={handleChange}
                                        placeholder="Enter last name"
                                        style={{ borderRadius: '8px', padding: '12px', border: '1px solid #d1d5db' }}
                                    />
                                ) : (
                                    <div className="form-control" style={{ backgroundColor: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '12px' }}>
                                        {user.last_name || <em className="text-muted">Not set</em>}
                                    </div>
                                )}
                            </div>

                            <div className="mb-4">
                                <label className="form-label" style={{ fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
                                    <i className="bi bi-envelope me-2"></i>
                                    Email
                                </label>
                                {editing ? (
                                    <input
                                        type="email"
                                        className="form-control"
                                        name="email"
                                        value={formData.email}
                                        onChange={handleChange}
                                        placeholder="Enter email"
                                        style={{ borderRadius: '8px', padding: '12px', border: '1px solid #d1d5db' }}
                                    />
                                ) : (
                                    <div className="form-control" style={{ backgroundColor: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '12px' }}>
                                        {user.email || <em className="text-muted">Not set</em>}
                                    </div>
                                )}
                            </div>

                            {editing && (
                                <div className="mt-4 pt-3" style={{ borderTop: '1px solid #e5e7eb' }}>
                                    <button
                                        className="btn btn-primary me-2"
                                        onClick={handleSave}
                                        disabled={saving}
                                        style={{
                                            padding: '12px 32px',
                                            fontWeight: '600',
                                            fontSize: '1rem',
                                            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                            border: 'none',
                                            borderRadius: '8px'
                                        }}
                                    >
                                        {saving ? (
                                            <>
                                                <span className="spinner-border spinner-border-sm me-2"></span>
                                                Saving...
                                            </>
                                        ) : (
                                            <>
                                                <i className="bi bi-check-circle me-2"></i>
                                                Save Changes
                                            </>
                                        )}
                                    </button>
                                    <button
                                        className="btn btn-outline-secondary"
                                        onClick={handleCancel}
                                        disabled={saving}
                                        style={{
                                            padding: '12px 24px',
                                            fontWeight: '500',
                                            borderRadius: '8px'
                                        }}
                                    >
                                        <i className="bi bi-x-circle me-2"></i>
                                        Cancel
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
