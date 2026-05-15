import {useContext, useEffect, useState} from 'react';
import {useNavigate, useParams} from 'react-router-dom';
import {toast} from 'react-toastify';
import {createUser, getAvailableRoles, getUser, resetPassword, updateUser} from '../../api/users';
import {AuthContext} from '../../context/AuthContext';
import {getErrorMessage} from '../../utils/errorUtils';
import {ROLE_LABELS} from '../../utils/roleConstants';

const emptyForm = {
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    is_active: true,
    is_staff: false,
    is_superuser: false,
    roles: [],
};

export default function UserForm() {
    const {id} = useParams();
    const navigate = useNavigate();
    const {user: currentUser} = useContext(AuthContext);
    const isEdit = Boolean(id);

    const [form, setForm] = useState(emptyForm);
    const [availableRoles, setAvailableRoles] = useState([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [resettingPw, setResettingPw] = useState(false);
    const [newPassword, setNewPassword] = useState('');
    const [showPwReset, setShowPwReset] = useState(false);
    const [fieldErrors, setFieldErrors] = useState({});

    useEffect(() => {
        const init = async () => {
            setLoading(true);
            try {
                const [{data: roles}] = await Promise.all([getAvailableRoles()]);
                setAvailableRoles(roles);

                if (isEdit) {
                    const {data: user} = await getUser(id);
                    setForm({
                        username: user.username ?? '',
                        email: user.email ?? '',
                        first_name: user.first_name ?? '',
                        last_name: user.last_name ?? '',
                        password: '',
                        is_active: user.is_active,
                        is_staff: user.is_staff ?? false,
                        is_superuser: user.is_superuser ?? false,
                        roles: user.roles ?? [],
                    });
                }
            } catch (err) {
                toast.error(getErrorMessage(err));
            } finally {
                setLoading(false);
            }
        };
        init();
    }, [id, isEdit]);

    const handleChange = (e) => {
        const {name, value, type, checked} = e.target;
        setForm(prev => ({...prev, [name]: type === 'checkbox' ? checked : value}));
        setFieldErrors(prev => ({...prev, [name]: undefined}));
    };

    const toggleRole = (code) => {
        setForm(prev => ({
            ...prev,
            roles: prev.roles.includes(code)
                ? prev.roles.filter(r => r !== code)
                : [...prev.roles, code],
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        setFieldErrors({});
        try {
            const payload = {...form};
            if (isEdit && !payload.password) delete payload.password;

            if (isEdit) {
                await updateUser(id, payload);
                toast.success('User updated');
            } else {
                await createUser(payload);
                toast.success('User created');
            }
            navigate('/admin/users');
        } catch (err) {
            if (err?.response?.data && typeof err.response.data === 'object') {
                setFieldErrors(err.response.data);
            }
            toast.error(getErrorMessage(err));
        } finally {
            setSaving(false);
        }
    };

    const handleResetPassword = async () => {
        if (!newPassword) return;
        setResettingPw(true);
        try {
            await resetPassword(id, newPassword);
            toast.success('Password reset successfully');
            setShowPwReset(false);
            setNewPassword('');
        } catch (err) {
            toast.error(getErrorMessage(err));
        } finally {
            setResettingPw(false);
        }
    };

    if (loading) return <div className="p-4 text-muted">Loading…</div>;

    return (
        <div className="container py-4" style={{maxWidth: 700}}>
            <div className="d-flex align-items-center gap-2 mb-4">
                <button className="btn btn-sm btn-outline-secondary" onClick={() => navigate('/admin/users')}>
                    ← Back
                </button>
                <h4 className="fw-bold mb-0">{isEdit ? 'Edit User' : 'Create User'}</h4>
            </div>

            <form onSubmit={handleSubmit}>
                <div className="card mb-3">
                    <div className="card-header fw-semibold">Account Details</div>
                    <div className="card-body">
                        <div className="row g-3">
                            <div className="col-md-6">
                                <label className="form-label">Username *</label>
                                <input
                                    className={`form-control ${fieldErrors.username ? 'is-invalid' : ''}`}
                                    name="username"
                                    value={form.username}
                                    onChange={handleChange}
                                    required
                                    autoComplete="off"
                                />
                                {fieldErrors.username && (
                                    <div className="invalid-feedback">{fieldErrors.username}</div>
                                )}
                            </div>
                            <div className="col-md-6">
                                <label className="form-label">Email</label>
                                <input
                                    type="email"
                                    className={`form-control ${fieldErrors.email ? 'is-invalid' : ''}`}
                                    name="email"
                                    value={form.email}
                                    onChange={handleChange}
                                    autoComplete="off"
                                />
                                {fieldErrors.email && (
                                    <div className="invalid-feedback">{fieldErrors.email}</div>
                                )}
                            </div>
                            <div className="col-md-6">
                                <label className="form-label">First Name</label>
                                <input
                                    className="form-control"
                                    name="first_name"
                                    value={form.first_name}
                                    onChange={handleChange}
                                />
                            </div>
                            <div className="col-md-6">
                                <label className="form-label">Last Name</label>
                                <input
                                    className="form-control"
                                    name="last_name"
                                    value={form.last_name}
                                    onChange={handleChange}
                                />
                            </div>

                            {!isEdit && (
                                <div className="col-md-6">
                                    <label className="form-label">Password</label>
                                    <input
                                        type="password"
                                        className={`form-control ${fieldErrors.password ? 'is-invalid' : ''}`}
                                        name="password"
                                        value={form.password}
                                        onChange={handleChange}
                                        autoComplete="new-password"
                                    />
                                    {fieldErrors.password && (
                                        <div className="invalid-feedback">{fieldErrors.password}</div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Status flags */}
                <div className="card mb-3">
                    <div className="card-header fw-semibold">Access Flags</div>
                    <div className="card-body">
                        <div className="d-flex gap-4 flex-wrap">
                            <div className="form-check form-switch">
                                <input
                                    className="form-check-input"
                                    type="checkbox"
                                    id="is_active"
                                    name="is_active"
                                    checked={form.is_active}
                                    onChange={handleChange}
                                />
                                <label className="form-check-label" htmlFor="is_active">Active</label>
                            </div>
                            <div className="form-check form-switch">
                                <input
                                    className="form-check-input"
                                    type="checkbox"
                                    id="is_staff"
                                    name="is_staff"
                                    checked={form.is_staff}
                                    onChange={handleChange}
                                />
                                <label className="form-check-label" htmlFor="is_staff">Staff (Django admin)</label>
                            </div>
                            {currentUser?.is_superuser && (
                                <div className="form-check form-switch">
                                    <input
                                        className="form-check-input"
                                        type="checkbox"
                                        id="is_superuser"
                                        name="is_superuser"
                                        checked={form.is_superuser}
                                        onChange={handleChange}
                                    />
                                    <label className="form-check-label" htmlFor="is_superuser">
                                        Super Admin (bypasses all role checks)
                                    </label>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Roles */}
                <div className="card mb-3">
                    <div className="card-header fw-semibold">Roles</div>
                    <div className="card-body">
                        <div className="row g-2">
                            {availableRoles.map(code => (
                                <div className="col-md-6 col-lg-4" key={code}>
                                    <div
                                        className={`form-check border rounded p-2 ${form.roles.includes(code) ? 'border-primary bg-primary bg-opacity-10' : ''}`}
                                    >
                                        <input
                                            className="form-check-input"
                                            type="checkbox"
                                            id={`role-${code}`}
                                            checked={form.roles.includes(code)}
                                            onChange={() => toggleRole(code)}
                                        />
                                        <label className="form-check-label small" htmlFor={`role-${code}`}>
                                            {ROLE_LABELS[code] ?? code}
                                        </label>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="d-flex gap-2">
                    <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={saving}
                        style={{ background: 'linear-gradient(135deg, #4F46E5, #4338CA)', border: 'none' }}
                    >
                        <i className="bi bi-check-circle me-2"></i>
                        {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Create User'}
                    </button>
                    <button type="button" className="btn btn-outline-secondary"
                            onClick={() => navigate('/admin/users')}>
                        <i className="bi bi-x-lg me-2"></i>Cancel
                    </button>
                    {isEdit && (
                        <button
                            type="button"
                            className="btn btn-outline-secondary ms-auto"
                            onClick={() => setShowPwReset(v => !v)}
                        >
                            <i className="bi bi-key me-2"></i>Reset Password
                        </button>
                    )}
                </div>
            </form>

            {/* Inline password reset */}
            {showPwReset && (
                <div className="card mt-3">
                    <div className="card-header fw-semibold text-warning">Reset Password</div>
                    <div className="card-body d-flex gap-2">
                        <input
                            type="password"
                            className="form-control"
                            placeholder="New password"
                            value={newPassword}
                            onChange={e => setNewPassword(e.target.value)}
                            autoComplete="new-password"
                        />
                        <button
                            className="btn btn-primary"
                            onClick={handleResetPassword}
                            disabled={resettingPw || !newPassword}
                            style={{ background: 'linear-gradient(135deg, #4F46E5, #4338CA)', border: 'none' }}
                        >
                            <i className="bi bi-check-circle me-2"></i>
                            {resettingPw ? 'Saving…' : 'Set Password'}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
