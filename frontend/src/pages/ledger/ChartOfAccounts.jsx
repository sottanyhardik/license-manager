import {useEffect, useState} from "react";
import {toast} from 'react-toastify';
import api from "../../api/axios";

export default function ChartOfAccounts() {
    const [accounts, setAccounts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editingAccount, setEditingAccount] = useState(null);
    const [formData, setFormData] = useState({
        code: '',
        name: '',
        account_type: 'ASSET',
        parent: '',
        linked_company: '',
        description: '',
        is_active: true
    });
    const [companies, setCompanies] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [filterType, setFilterType] = useState('');

    const accountTypes = [
        {value: 'ASSET', label: 'Asset'},
        {value: 'LIABILITY', label: 'Liability'},
        {value: 'EQUITY', label: 'Equity'},
        {value: 'REVENUE', label: 'Revenue'},
        {value: 'EXPENSE', label: 'Expense'}
    ];

    useEffect(() => {
        fetchAccounts();
        fetchCompanies();
    }, []);

    const fetchAccounts = async () => {
        try {
            const response = await api.get('/chart-of-accounts/');
            setAccounts(response.data.results || response.data);
            setLoading(false);
        } catch (error) {
            toast.error('Failed to fetch chart of accounts');
            setLoading(false);
        }
    };

    const fetchCompanies = async () => {
        try {
            const response = await api.get('/companies/');
            setCompanies(response.data.results || response.data);
        } catch (error) {
            console.error('Failed to fetch companies');
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const payload = {
                ...formData,
                parent: formData.parent || null,
                linked_company: formData.linked_company || null
            };

            if (editingAccount) {
                await api.put(`/chart-of-accounts/${editingAccount.id}/`, payload);
                toast.success('Account updated successfully');
            } else {
                await api.post('/chart-of-accounts/', payload);
                toast.success('Account created successfully');
            }
            setShowModal(false);
            resetForm();
            fetchAccounts();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Failed to save account');
        }
    };

    const handleEdit = (account) => {
        setEditingAccount(account);
        setFormData({
            code: account.code,
            name: account.name,
            account_type: account.account_type,
            parent: account.parent || '',
            linked_company: account.linked_company || '',
            description: account.description || '',
            is_active: account.is_active
        });
        setShowModal(true);
    };

    const handleDelete = async (id) => {
        if (window.confirm('Are you sure you want to delete this account?')) {
            try {
                await api.delete(`/chart-of-accounts/${id}/`);
                toast.success('Account deleted successfully');
                fetchAccounts();
            } catch (error) {
                toast.error(error.response?.data?.detail || 'Failed to delete account');
            }
        }
    };

    const resetForm = () => {
        setFormData({
            code: '',
            name: '',
            account_type: 'ASSET',
            parent: '',
            linked_company: '',
            description: '',
            is_active: true
        });
        setEditingAccount(null);
    };

    const handleCloseModal = () => {
        setShowModal(false);
        resetForm();
    };

    const filteredAccounts = accounts.filter(account => {
        const matchesSearch = account.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            account.code.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesType = filterType === '' || account.account_type === filterType;
        return matchesSearch && matchesType;
    });

    // Group accounts by type
    const groupedAccounts = accountTypes.reduce((acc, type) => {
        acc[type.value] = filteredAccounts.filter(a => a.account_type === type.value);
        return acc;
    }, {});

    const formatCurrency = (amount) => {
        if (!amount && amount !== 0) return '₹0.00';
        return `₹${parseFloat(amount).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    };

    if (loading) {
        return <div className="container mt-4"><div className="spinner-border" role="status"></div></div>;
    }

    return (
        <div className="container-fluid mt-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2><i className="bi bi-list-columns me-2"></i>Chart of Accounts</h2>
                <button className="btn btn-primary" onClick={() => setShowModal(true)}>
                    <i className="bi bi-plus-circle me-2"></i>New Account
                </button>
            </div>

            {/* Filters */}
            <div className="card mb-4">
                <div className="card-body">
                    <div className="row">
                        <div className="col-md-6">
                            <input
                                type="text"
                                className="form-control"
                                placeholder="Search by name or code..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>
                        <div className="col-md-4">
                            <select
                                className="form-select"
                                value={filterType}
                                onChange={(e) => setFilterType(e.target.value)}
                            >
                                <option value="">All Types</option>
                                {accountTypes.map(type => (
                                    <option key={type.value} value={type.value}>{type.label}</option>
                                ))}
                            </select>
                        </div>
                        <div className="col-md-2">
                            <button className="btn btn-secondary w-100" onClick={() => {
                                setSearchTerm('');
                                setFilterType('');
                            }}>
                                Clear
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Accounts by Type */}
            {accountTypes.map(type => {
                const typeAccounts = groupedAccounts[type.value];
                if (typeAccounts.length === 0) return null;

                return (
                    <div key={type.value} className="card mb-3">
                        <div className="card-header bg-primary text-white">
                            <h5 className="mb-0">{type.label} Accounts ({typeAccounts.length})</h5>
                        </div>
                        <div className="card-body p-0">
                            <div className="table-responsive">
                                <table className="table table-hover mb-0">
                                    <thead className="table-light">
                                        <tr>
                                            <th>Code</th>
                                            <th>Name</th>
                                            <th>Parent</th>
                                            <th>Linked Company</th>
                                            <th className="text-end">Balance</th>
                                            <th>Status</th>
                                            <th className="text-end">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {typeAccounts.map(account => (
                                            <tr key={account.id}>
                                                <td><code>{account.code}</code></td>
                                                <td>{account.name}</td>
                                                <td>{account.parent_name || '-'}</td>
                                                <td>{account.company_name || '-'}</td>
                                                <td className="text-end">
                                                    <strong>{formatCurrency(account.balance)}</strong>
                                                </td>
                                                <td>
                                                    <span className={`badge ${account.is_active ? 'bg-success' : 'bg-secondary'}`}>
                                                        {account.is_active ? 'Active' : 'Inactive'}
                                                    </span>
                                                </td>
                                                <td className="text-end">
                                                    <button
                                                        className="btn btn-sm btn-outline-primary me-2"
                                                        onClick={() => handleEdit(account)}
                                                    >
                                                        <i className="bi bi-pencil"></i>
                                                    </button>
                                                    <button
                                                        className="btn btn-sm btn-outline-danger"
                                                        onClick={() => handleDelete(account.id)}
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
                );
            })}

            {/* Modal */}
            {showModal && (
                <div className="modal show d-block" tabIndex="-1" style={{backgroundColor: 'rgba(0,0,0,0.5)'}}>
                    <div className="modal-dialog modal-lg">
                        <div className="modal-content">
                            <div className="modal-header">
                                <h5 className="modal-title">
                                    {editingAccount ? 'Edit Account' : 'New Account'}
                                </h5>
                                <button type="button" className="btn-close" onClick={handleCloseModal}></button>
                            </div>
                            <form onSubmit={handleSubmit}>
                                <div className="modal-body">
                                    <div className="row">
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">Code *</label>
                                            <input
                                                type="text"
                                                className="form-control"
                                                value={formData.code}
                                                onChange={(e) => setFormData({...formData, code: e.target.value})}
                                                required
                                            />
                                        </div>
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">Account Type *</label>
                                            <select
                                                className="form-select"
                                                value={formData.account_type}
                                                onChange={(e) => setFormData({...formData, account_type: e.target.value})}
                                                required
                                            >
                                                {accountTypes.map(type => (
                                                    <option key={type.value} value={type.value}>{type.label}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>
                                    <div className="mb-3">
                                        <label className="form-label">Name *</label>
                                        <input
                                            type="text"
                                            className="form-control"
                                            value={formData.name}
                                            onChange={(e) => setFormData({...formData, name: e.target.value})}
                                            required
                                        />
                                    </div>
                                    <div className="row">
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">Parent Account</label>
                                            <select
                                                className="form-select"
                                                value={formData.parent}
                                                onChange={(e) => setFormData({...formData, parent: e.target.value})}
                                            >
                                                <option value="">None</option>
                                                {accounts.filter(a => a.id !== editingAccount?.id).map(account => (
                                                    <option key={account.id} value={account.id}>
                                                        {account.code} - {account.name}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">Linked Company</label>
                                            <select
                                                className="form-select"
                                                value={formData.linked_company}
                                                onChange={(e) => setFormData({...formData, linked_company: e.target.value})}
                                            >
                                                <option value="">None</option>
                                                {companies.map(company => (
                                                    <option key={company.id} value={company.id}>
                                                        {company.name}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>
                                    <div className="mb-3">
                                        <label className="form-label">Description</label>
                                        <textarea
                                            className="form-control"
                                            rows="3"
                                            value={formData.description}
                                            onChange={(e) => setFormData({...formData, description: e.target.value})}
                                        ></textarea>
                                    </div>
                                    <div className="form-check">
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
                                        {editingAccount ? 'Update' : 'Create'}
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
