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
        role: "accounts",
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
                role: user.role,
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
                role: "accounts",
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
        <div className="container-fluid mt-4 px-4">
            <nav aria-label="breadcrumb" className="mb-3">
                <ol className="breadcrumb">
                    <li className="breadcrumb-item">
                        <a href="/" onClick={(e) => {
                            e.preventDefault();
                            navigate('/');
                        }}>Home</a>
                    </li>
                    <li className="breadcrumb-item active" aria-current="page">Settings</li>
                </ol>
            </nav>

            <h1 className="mb-4">Settings</h1>

            {/* Ledger Upload Section */}
            <div className="card shadow-sm mb-4">
                <div className="card-header bg-primary text-white">
                    <h5 className="mb-0">
                        <i className="bi bi-file-earmark-spreadsheet me-2"></i>
                        Ledger Upload
                    </h5>
                </div>
                <div className="card-body">
                    <p className="text-muted mb-3">Upload license ledger files to update the system</p>
                    <button
                        className="btn btn-primary"
                        onClick={() => navigate('/ledger-upload')}
                    >
                        <i className="bi bi-upload me-2"></i>
                        Go to Ledger Upload
                    </button>
                </div>
            </div>

            {/* User Management Section */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2>User Management</h2>
                <button className="btn btn-primary" onClick={() => handleOpenModal()}>
                    <i className="bi bi-plus-circle me-2"></i>
                    Add User
                </button>
            </div>

            <div className="card shadow-sm">
                <div className="card-body">
                    <div className="table-responsive">
                        <table className="table table-hover">
                            <thead>
                            <tr>
                                <th>Username</th>
                                <th>Email</th>
                                <th>Name</th>
                                <th>Role</th>
                                <th>Status</th>
                                <th>Date Joined</th>
                                <th>Actions</th>
                            </tr>
                            </thead>
                            <tbody>
                            {users.map((user) => (
                                <tr key={user.id}>
                                    <td>{user.username}</td>
                                    <td>{user.email || "-"}</td>
                                    <td>{user.first_name && user.last_name ? `${user.first_name} ${user.last_name}` : "-"}</td>
                                    <td>
                      <span className={`badge ${
                          user.role === 'admin' ? 'bg-danger' :
                              user.role === 'manager' ? 'bg-primary' :
                                  'bg-info'
                      }`}>
                        {user.role}
                      </span>
                                    </td>
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
                                        >
                                            <i className="bi bi-pencil"></i>
                                        </button>
                                        <button
                                            className="btn btn-sm btn-outline-danger"
                                            onClick={() => handleDelete(user.id)}
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

            {showModal && (
                <div className="modal show d-block" style={{backgroundColor: 'rgba(0,0,0,0.5)'}}>
                    <div className="modal-dialog">
                        <div className="modal-content">
                            <div className="modal-header">
                                <h5 className="modal-title">{editingUser ? 'Edit User' : 'Add User'}</h5>
                                <button type="button" className="btn-close" onClick={handleCloseModal}></button>
                            </div>
                            <form onSubmit={handleSubmit}>
                                <div className="modal-body">
                                    <div className="mb-3">
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
                                    <div className="mb-3">
                                        <label className="form-label">Email</label>
                                        <input
                                            type="email"
                                            className="form-control"
                                            value={formData.email}
                                            onChange={(e) => setFormData({...formData, email: e.target.value})}
                                        />
                                    </div>
                                    <div className="mb-3">
                                        <label className="form-label">First Name</label>
                                        <input
                                            type="text"
                                            className="form-control"
                                            value={formData.first_name}
                                            onChange={(e) => setFormData({...formData, first_name: e.target.value})}
                                        />
                                    </div>
                                    <div className="mb-3">
                                        <label className="form-label">Last Name</label>
                                        <input
                                            type="text"
                                            className="form-control"
                                            value={formData.last_name}
                                            onChange={(e) => setFormData({...formData, last_name: e.target.value})}
                                        />
                                    </div>
                                    <div className="mb-3">
                                        <label className="form-label">Role *</label>
                                        <select
                                            className="form-select"
                                            value={formData.role}
                                            onChange={(e) => setFormData({...formData, role: e.target.value})}
                                            required
                                        >
                                            <option value="admin">Admin</option>
                                            <option value="manager">Manager</option>
                                            <option value="accounts">Accounts</option>
                                        </select>
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
