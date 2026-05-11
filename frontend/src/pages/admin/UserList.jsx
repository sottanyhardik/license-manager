import {useCallback, useContext, useEffect, useState} from 'react';
import {Link, useNavigate} from 'react-router-dom';
import {toast} from 'react-toastify';
import {deleteUser, listUsers} from '../../api/users';
import {AuthContext} from '../../context/AuthContext';
import {getErrorMessage} from '../../utils/errorUtils';
import {ROLE_LABELS, getRoleBadgeProps} from '../../utils/roleConstants';

export default function UserList() {
    const navigate = useNavigate();
    const {user: currentUser} = useContext(AuthContext);

    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [roleFilter, setRoleFilter] = useState('');
    const [activeFilter, setActiveFilter] = useState('');
    const [confirmDelete, setConfirmDelete] = useState(null);

    const fetchUsers = useCallback(async () => {
        setLoading(true);
        try {
            const params = {};
            if (search) params.search = search;
            if (roleFilter) params.role = roleFilter;
            if (activeFilter !== '') params.is_active = activeFilter;
            const {data} = await listUsers(params);
            setUsers(Array.isArray(data) ? data : data.results ?? []);
        } catch (err) {
            toast.error(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    }, [search, roleFilter, activeFilter]);

    useEffect(() => {
        fetchUsers();
    }, [fetchUsers]);

    const handleDelete = async (userId) => {
        try {
            await deleteUser(userId);
            toast.success('User deleted');
            setConfirmDelete(null);
            fetchUsers();
        } catch (err) {
            toast.error(getErrorMessage(err));
        }
    };

    return (
        <div className="container-fluid py-4">
            {/* Header */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h4 className="fw-bold mb-0">User Management</h4>
                    <small className="text-muted">Manage users, roles and access</small>
                </div>
                <Link to="/admin/users/create" className="btn btn-primary">
                    + Add User
                </Link>
            </div>

            {/* Filters */}
            <div className="card mb-3">
                <div className="card-body py-2">
                    <div className="row g-2">
                        <div className="col-md-4">
                            <input
                                className="form-control form-control-sm"
                                placeholder="Search by username or email…"
                                value={search}
                                onChange={e => setSearch(e.target.value)}
                            />
                        </div>
                        <div className="col-md-3">
                            <select
                                className="form-select form-select-sm"
                                value={roleFilter}
                                onChange={e => setRoleFilter(e.target.value)}
                            >
                                <option value="">All Roles</option>
                                {Object.keys(ROLE_LABELS).map(code => (
                                    <option key={code} value={code}>{ROLE_LABELS[code]}</option>
                                ))}
                            </select>
                        </div>
                        <div className="col-md-2">
                            <select
                                className="form-select form-select-sm"
                                value={activeFilter}
                                onChange={e => setActiveFilter(e.target.value)}
                            >
                                <option value="">All Status</option>
                                <option value="true">Active</option>
                                <option value="false">Inactive</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>

            {/* Table */}
            <div className="card">
                <div className="card-body p-0">
                    {loading ? (
                        <div className="p-4 text-center text-muted">Loading users…</div>
                    ) : users.length === 0 ? (
                        <div className="p-4 text-center text-muted">No users found.</div>
                    ) : (
                        <div className="table-responsive">
                            <table className="table table-hover mb-0 align-middle">
                                <thead className="table-light">
                                <tr>
                                    <th>User</th>
                                    <th>Email</th>
                                    <th>Roles</th>
                                    <th>Status</th>
                                    <th className="text-end">Actions</th>
                                </tr>
                                </thead>
                                <tbody>
                                {users.map(u => (
                                    <tr key={u.id}>
                                        <td>
                                            <div className="fw-semibold">{u.username}</div>
                                            {u.first_name || u.last_name
                                                ? <small className="text-muted">{u.first_name} {u.last_name}</small>
                                                : null}
                                            {u.is_superuser &&
                                                <span className="badge bg-danger ms-1">Super Admin</span>}
                                        </td>
                                        <td className="text-muted small">{u.email || '—'}</td>
                                        <td>
                                            {(u.roles ?? []).length === 0
                                                ? <span className="text-muted small">No roles</span>
                                                : (u.roles ?? []).map(r => (
                                                    {(() => { const bp = getRoleBadgeProps(r); return (
                                                    <span
                                                        key={r}
                                                        className={`${bp.className} me-1 mb-1`}
                                                        style={{fontSize: '0.7rem', ...bp.style}}
                                                    >
                                                            {ROLE_LABELS[r] ?? r}
                                                        </span>
                                                    ); })())
                                            }
                                        </td>
                                        <td>
                                            <span className={`badge bg-${u.is_active ? 'success' : 'secondary'}`}>
                                                {u.is_active ? 'Active' : 'Inactive'}
                                            </span>
                                        </td>
                                        <td className="text-end">
                                            <div className="btn-group btn-group-sm">
                                                <button
                                                    className="btn btn-outline-primary"
                                                    onClick={() => navigate(`/admin/users/${u.id}/edit`)}
                                                >
                                                    Edit
                                                </button>
                                                {currentUser?.is_superuser && u.id !== currentUser?.id && (
                                                    <button
                                                        className="btn btn-outline-danger"
                                                        onClick={() => setConfirmDelete(u)}
                                                    >
                                                        Delete
                                                    </button>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </div>

            {/* Delete confirmation modal */}
            {confirmDelete && (
                <div className="modal show d-block" tabIndex="-1" style={{background: 'rgba(0,0,0,0.5)'}}>
                    <div className="modal-dialog modal-sm">
                        <div className="modal-content">
                            <div className="modal-header">
                                <h5 className="modal-title">Delete User</h5>
                                <button className="btn-close" onClick={() => setConfirmDelete(null)}/>
                            </div>
                            <div className="modal-body">
                                Are you sure you want to delete <strong>{confirmDelete.username}</strong>?
                                This cannot be undone.
                            </div>
                            <div className="modal-footer">
                                <button className="btn btn-secondary btn-sm"
                                        onClick={() => setConfirmDelete(null)}>Cancel
                                </button>
                                <button className="btn btn-danger btn-sm"
                                        onClick={() => handleDelete(confirmDelete.id)}>Delete
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
