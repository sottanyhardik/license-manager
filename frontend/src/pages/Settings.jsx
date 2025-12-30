import {useEffect, useState} from "react";
import {useNavigate} from "react-router-dom";
import { toast } from 'react-toastify';
import api from "../api/axios";

export default function Settings() {
    const navigate = useNavigate();
    const [users, setUsers] = useState([]);
    const [roles, setRoles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [showRoleModal, setShowRoleModal] = useState(false);
    const [editingUser, setEditingUser] = useState(null);
    const [selectedUserForRoles, setSelectedUserForRoles] = useState(null);
    const [selectedRoles, setSelectedRoles] = useState([]);

    const [formData, setFormData] = useState({
        username: "",
        email: "",
        first_name: "",
        last_name: "",
        role_ids: [],
        password: "",
        is_active: true
    });

    useEffect(() => {
        loadUsers();
        loadRoles();
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

    const loadRoles = async () => {
        try {
            const response = await api.get("auth/roles/");
            setRoles(response.data);
        } catch (error) {
            toast.error("Failed to load roles");
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
                role_ids: user.roles ? user.roles.map(r => r.id) : [],
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
                role_ids: [],
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

    const handleOpenRoleModal = (user) => {
        setSelectedUserForRoles(user);
        setSelectedRoles(user.roles ? user.roles.map(r => r.id) : []);
        setShowRoleModal(true);
    };

    const handleCloseRoleModal = () => {
        setShowRoleModal(false);
        setSelectedUserForRoles(null);
        setSelectedRoles([]);
    };

    const handleToggleRole = (roleId) => {
        setSelectedRoles(prev =>
            prev.includes(roleId)
                ? prev.filter(id => id !== roleId)
                : [...prev, roleId]
        );
    };

    const handleSaveRoles = async () => {
        try {
            await api.post(`auth/users/${selectedUserForRoles.id}/assign-roles/`, {
                role_ids: selectedRoles
            });
            toast.success("Roles updated successfully");
            handleCloseRoleModal();
            loadUsers();
        } catch (error) {
            toast.error(error.response?.data?.detail || "Failed to update roles");
        }
    };

    const handleToggleFormRole = (roleId) => {
        setFormData(prev => ({
            ...prev,
            role_ids: prev.role_ids.includes(roleId)
                ? prev.role_ids.filter(id => id !== roleId)
                : [...prev.role_ids, roleId]
        }));
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
                                <th>Roles</th>
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
                                        {user.is_superuser ? (
                                            <span className="badge bg-danger">All Permissions</span>
                                        ) : user.roles && user.roles.length > 0 ? (
                                            <>
                                                {user.roles.slice(0, 2).map((role, idx) => (
                                                    <span key={idx} className="badge bg-info me-1 mb-1">
                                                        {role.name}
                                                    </span>
                                                ))}
                                                {user.roles.length > 2 && (
                                                    <span className="badge bg-secondary">
                                                        +{user.roles.length - 2} more
                                                    </span>
                                                )}
                                            </>
                                        ) : (
                                            <span className="text-muted">No roles</span>
                                        )}
                                    </td>
                                    <td>
                      <span className={`badge ${user.is_active ? 'bg-success' : 'bg-secondary'}`}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                                    </td>
                                    <td>{new Date(user.date_joined).toLocaleDateString()}</td>
                                    <td>
                                        <button
                                            className="btn btn-sm btn-outline-info me-2"
                                            onClick={() => handleOpenRoleModal(user)}
                                            title="Manage Roles"
                                        >
                                            <i className="bi bi-person-badge"></i>
                                        </button>
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
                                    <div className="mb-3">
                                        <label className="form-label">Roles</label>
                                        <div className="border rounded p-3" style={{maxHeight: '200px', overflowY: 'auto'}}>
                                            {roles.map(role => (
                                                <div key={role.id} className="form-check mb-2">
                                                    <input
                                                        type="checkbox"
                                                        className="form-check-input"
                                                        id={`role-${role.id}`}
                                                        checked={formData.role_ids.includes(role.id)}
                                                        onChange={() => handleToggleFormRole(role.id)}
                                                    />
                                                    <label className="form-check-label" htmlFor={`role-${role.id}`}>
                                                        <strong>{role.name}</strong>
                                                        <br/>
                                                        <small className="text-muted">{role.description}</small>
                                                    </label>
                                                </div>
                                            ))}
                                        </div>
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

            {/* Role Assignment Modal */}
            {showRoleModal && selectedUserForRoles && (
                <div className="modal show d-block" style={{backgroundColor: 'rgba(0,0,0,0.5)'}}>
                    <div className="modal-dialog modal-lg">
                        <div className="modal-content">
                            <div className="modal-header bg-dark text-white">
                                <h5 className="modal-title">
                                    <i className="bi bi-person-badge me-2"></i>
                                    Chosen roles
                                    {selectedUserForRoles.is_superuser && (
                                        <span className="badge bg-danger ms-2">Superuser</span>
                                    )}
                                </h5>
                                <button type="button" className="btn-close btn-close-white" onClick={handleCloseRoleModal}></button>
                            </div>
                            <div className="modal-body">
                                <div className="mb-3">
                                    <input
                                        type="text"
                                        className="form-control"
                                        placeholder="Filter"
                                    />
                                </div>
                                <div style={{maxHeight: '400px', overflowY: 'auto'}}>
                                    {roles.map(role => (
                                        <div
                                            key={role.id}
                                            className={`p-3 mb-2 border rounded cursor-pointer ${
                                                selectedRoles.includes(role.id) ? 'bg-light' : ''
                                            }`}
                                            style={{cursor: 'pointer'}}
                                            onClick={() => handleToggleRole(role.id)}
                                        >
                                            <div className="d-flex align-items-center">
                                                <input
                                                    type="checkbox"
                                                    className="form-check-input me-3"
                                                    checked={selectedRoles.includes(role.id)}
                                                    onChange={() => {}}
                                                    style={{cursor: 'pointer'}}
                                                />
                                                <div>
                                                    <strong>{role.name}</strong>
                                                    <br/>
                                                    <small className="text-muted">{role.description}</small>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                                <div className="text-center mt-3">
                                    <button
                                        className="btn btn-link text-danger"
                                        onClick={() => setSelectedRoles([])}
                                    >
                                        <i className="bi bi-x-circle me-1"></i>
                                        Remove all
                                    </button>
                                </div>
                            </div>
                            <div className="modal-footer">
                                <button type="button" className="btn btn-secondary" onClick={handleCloseRoleModal}>
                                    Cancel
                                </button>
                                <button type="button" className="btn btn-primary" onClick={handleSaveRoles}>
                                    Save Changes
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
