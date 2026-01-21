import {useEffect, useState} from "react";
import {useNavigate} from "react-router-dom";
import { toast } from 'react-toastify';
import api from "../api/axios";

export default function Settings() {
    const navigate = useNavigate();
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editingUser, setEditingUser] = useState(null);

    const [formData, setFormData] = useState({
        username: "",
        email: "",
        first_name: "",
        last_name: "",
        password: "",
        is_active: true
    });

    useEffect(() => {
        loadUsers();
    }, []);

    const loadUsers = async () => {
        try {
            const response = await api.get("auth/users/");
            setUsers(response.data);
        } catch (error) {
            toast.error("Failed to load users");
        } finally{
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
                is_active: user.is_active
            });
        } else {
            setEditingUser(null);
            setFormData({
                username: "",
                email: "",
                first_name: "",
                last_name: "",
                password: "",
                is_active: true
            });
        }
        setShowModal(true);
    };

    const handleCloseModal = () => {
        setShowModal(false);
        setEditingUser(null);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            if (editingUser) {
                const updateData = {...formData};
                if (!updateData.password) {
                    delete updateData.password;
                }
                await api.put(`auth/users/${editingUser.id}/`, updateData);
                toast.success("User updated successfully");
            } else {
                await api.post("auth/users/", formData);
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
            <div className="container mt-4">
                <div className="text-center">Loading...</div>
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
                <div className="d-flex justify-content-between align-items-center">
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
                            <span style={{ fontSize: '0.9rem' }}>Settings</span>
                        </div>
                        <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '0' }}>
                            <i className="bi bi-gear me-3"></i>
                            Settings
                        </h1>
                    </div>
                </div>
            </div>

            {/* Ledger Upload Section */}
            <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '12px' }}>
                <div className="card-body" style={{ padding: '24px' }}>
                    <div className="d-flex align-items-start">
                        <div style={{
                            width: '56px',
                            height: '56px',
                            borderRadius: '12px',
                            background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            marginRight: '20px',
                            boxShadow: '0 4px 10px rgba(16, 185, 129, 0.3)'
                        }}>
                            <i className="bi bi-file-earmark-spreadsheet text-white" style={{ fontSize: '1.5rem' }}></i>
                        </div>
                        <div style={{ flex: 1 }}>
                            <h5 style={{ fontWeight: '600', marginBottom: '8px', color: '#2c3e50' }}>Ledger Upload</h5>
                            <p className="text-muted mb-3" style={{ fontSize: '0.9rem' }}>Upload license ledger files to update the system</p>
                            <button
                                className="btn btn-success"
                                onClick={() => navigate('/ledger-upload')}
                                style={{ padding: '10px 24px', fontWeight: '500' }}
                            >
                                <i className="bi bi-upload me-2"></i>
                                Go to Ledger Upload
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* User Management Section */}
            <div className="d-flex justify-content-between align-items-center mb-3">
                <h3 style={{ fontWeight: '600', color: '#2c3e50', marginBottom: '0' }}>
                    <i className="bi bi-people me-2"></i>
                    User Management
                </h3>
                <button
                    className="btn btn-primary"
                    onClick={() => handleOpenModal()}
                    style={{
                        padding: '10px 24px',
                        fontWeight: '500',
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        border: 'none'
                    }}
                >
                    <i className="bi bi-plus-circle me-2"></i>
                    Add User
                </button>
            </div>

            <div className="card border-0 shadow-sm" style={{ borderRadius: '12px' }}>
                <div className="card-body" style={{ padding: '24px' }}>
                    <div className="table-responsive">
                        <table className="table table-hover">
                            <thead>
                            <tr>
                                <th>Username</th>
                                <th>Email</th>
                                <th>Name</th>
                                <th>Status</th>
                                <th>Date Joined</th>
                                <th>Actions</th>
                            </tr>
                            </thead>
                            <tbody>
                            {users.map((user) => (
                                <tr key={user.id}>
                                    <td>
                                        {user.username}
                                        {user.is_superuser && (
                                            <span className="badge bg-danger ms-2">Superuser</span>
                                        )}
                                    </td>
                                    <td>{user.email || "-"}</td>
                                    <td>{user.first_name && user.last_name ? `${user.first_name} ${user.last_name}` : "-"}</td>
                                    <td>
                      <span className={`badge ${user.is_active ? 'bg-success' : 'bg-secondary'}`}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                                    </td>
                                    <td>{new Date(user.date_joined).toLocaleDateString()}</td>
                                    <td>
                                        <button
                                            className="btn btn-sm btn-outline-primary me-2"
                                            onClick={() => handleOpenModal(user)}
                                            title="Edit User"
                                        >
                                            <i className="bi bi-pencil"></i>
                                        </button>
                                        <button
                                            className="btn btn-sm btn-outline-danger"
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
                <div className="modal show d-block" style={{backgroundColor: 'rgba(0,0,0,0.5)'}}>
                    <div className="modal-dialog modal-lg">
                        <div className="modal-content">
                            <div className="modal-header">
                                <h5 className="modal-title">{editingUser ? 'Edit User' : 'Add User'}</h5>
                                <button type="button" className="btn-close" onClick={handleCloseModal}></button>
                            </div>
                            <form onSubmit={handleSubmit}>
                                <div className="modal-body">
                                    <div className="row">
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">Username *</label>
                                            <input
                                                type="text"
                                                className="form-control"
                                                value={formData.username}
                                                onChange={(e) => setFormData({...formData, username: e.target.value})}
                                                required
                                                disabled={editingUser !== null}
                                            />
                                        </div>
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">Email</label>
                                            <input
                                                type="email"
                                                className="form-control"
                                                value={formData.email}
                                                onChange={(e) => setFormData({...formData, email: e.target.value})}
                                            />
                                        </div>
                                    </div>
                                    <div className="row">
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">First Name</label>
                                            <input
                                                type="text"
                                                className="form-control"
                                                value={formData.first_name}
                                                onChange={(e) => setFormData({...formData, first_name: e.target.value})}
                                            />
                                        </div>
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">Last Name</label>
                                            <input
                                                type="text"
                                                className="form-control"
                                                value={formData.last_name}
                                                onChange={(e) => setFormData({...formData, last_name: e.target.value})}
                                            />
                                        </div>
                                    </div>
                                    <div className="mb-3">
                                        <label className="form-label">
                                            Password {!editingUser && '*'}
                                            {editingUser &&
                                                <small className="text-muted"> (leave blank to keep current)</small>}
                                        </label>
                                        <input
                                            type="password"
                                            className="form-control"
                                            value={formData.password}
                                            onChange={(e) => setFormData({...formData, password: e.target.value})}
                                            required={!editingUser}
                                        />
                                    </div>
                                    <div className="mb-3 form-check">
                                        <input
                                            type="checkbox"
                                            className="form-check-input"
                                            id="isActive"
                                            checked={formData.is_active}
                                            onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                                        />
                                        <label className="form-check-label" htmlFor="isActive">
                                            Active
                                        </label>
                                    </div>
                                </div>
                                <div className="modal-footer">
                                    <button type="button" className="btn btn-secondary" onClick={handleCloseModal}>
                                        Cancel
                                    </button>
                                    <button type="submit" className="btn btn-primary">
                                        {editingUser ? 'Update' : 'Create'}
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
