import {useContext, useState} from "react";
import {AuthContext} from "../context/AuthContext";
import api from "../api/axios";

export default function Profile() {
    const {user, loginSuccess} = useContext(AuthContext);
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
        <div className="container mt-4">
            <div className="row">
                <div className="col-lg-8 mx-auto">
                    <div className="card shadow-sm">
                        <div className="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                            <h4 className="mb-0">My Profile</h4>
                            {!editing && (
                                <button
                                    className="btn btn-sm btn-light"
                                    onClick={handleEdit}
                                >
                                    <i className="bi bi-pencil me-2"></i>
                                    Edit
                                </button>
                            )}
                        </div>

                        <div className="card-body">
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

                            <div className="row mb-3">
                                <div className="col-md-4">
                                    <strong>Username:</strong>
                                </div>
                                <div className="col-md-8">
                                    <span className="text-muted">{user.username}</span>
                                    <small className="text-muted d-block">
                                        (Username cannot be changed)
                                    </small>
                                </div>
                            </div>

                            <div className="row mb-3">
                                <div className="col-md-4">
                                    <strong>First Name:</strong>
                                </div>
                                <div className="col-md-8">
                                    {editing ? (
                                        <input
                                            type="text"
                                            className="form-control"
                                            name="first_name"
                                            value={formData.first_name}
                                            onChange={handleChange}
                                            placeholder="Enter first name"
                                        />
                                    ) : (
                                        <span>{user.first_name || <em className="text-muted">Not set</em>}</span>
                                    )}
                                </div>
                            </div>

                            <div className="row mb-3">
                                <div className="col-md-4">
                                    <strong>Last Name:</strong>
                                </div>
                                <div className="col-md-8">
                                    {editing ? (
                                        <input
                                            type="text"
                                            className="form-control"
                                            name="last_name"
                                            value={formData.last_name}
                                            onChange={handleChange}
                                            placeholder="Enter last name"
                                        />
                                    ) : (
                                        <span>{user.last_name || <em className="text-muted">Not set</em>}</span>
                                    )}
                                </div>
                            </div>

                            <div className="row mb-3">
                                <div className="col-md-4">
                                    <strong>Email:</strong>
                                </div>
                                <div className="col-md-8">
                                    {editing ? (
                                        <input
                                            type="email"
                                            className="form-control"
                                            name="email"
                                            value={formData.email}
                                            onChange={handleChange}
                                            placeholder="Enter email"
                                        />
                                    ) : (
                                        <span>{user.email || <em className="text-muted">Not set</em>}</span>
                                    )}
                                </div>
                            </div>

                            <div className="row mb-3">
                                <div className="col-md-4">
                                    <strong>Role:</strong>
                                </div>
                                <div className="col-md-8">
                                    <span className="badge bg-info text-capitalize">
                                        {user.role || "viewer"}
                                    </span>
                                </div>
                            </div>

                            {editing && (
                                <div className="row mt-4">
                                    <div className="col-md-8 offset-md-4">
                                        <button
                                            className="btn btn-primary me-2"
                                            onClick={handleSave}
                                            disabled={saving}
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
                                            className="btn btn-secondary"
                                            onClick={handleCancel}
                                            disabled={saving}
                                        >
                                            Cancel
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
