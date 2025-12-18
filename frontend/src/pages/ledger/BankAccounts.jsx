import {useEffect, useState} from "react";
import {toast} from 'react-toastify';
import api from "../../api/axios";

export default function BankAccounts() {
    const [bankAccounts, setBankAccounts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editingAccount, setEditingAccount] = useState(null);
    const [formData, setFormData] = useState({
        account_name: '',
        bank_name: '',
        account_number: '',
        ifsc_code: '',
        branch: '',
        account_type: 'SAVINGS',
        opening_balance: '0.00',
        is_active: true
    });
    const [accounts, setAccounts] = useState([]);

    const accountTypes = [
        {value: 'SAVINGS', label: 'Savings'},
        {value: 'CURRENT', label: 'Current'},
        {value: 'OD', label: 'Overdraft'},
        {value: 'CC', label: 'Cash Credit'}
    ];

    useEffect(() => {
        fetchBankAccounts();
        fetchChartOfAccounts();
    }, []);

    const fetchBankAccounts = async () => {
        try {
            const response = await api.get('/bank-accounts/');
            setBankAccounts(response.data.results || response.data);
            setLoading(false);
        } catch (error) {
            toast.error('Failed to fetch bank accounts');
            setLoading(false);
        }
    };

    const fetchChartOfAccounts = async () => {
        try {
            const response = await api.get('/chart-of-accounts/');
            const allAccounts = response.data.results || response.data;
            // Filter for bank-related accounts (Assets)
            setAccounts(allAccounts.filter(a => a.account_type === 'ASSET'));
        } catch (error) {
            console.error('Failed to fetch accounts');
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const payload = {
                ...formData,
                opening_balance: parseFloat(formData.opening_balance) || 0
            };

            if (editingAccount) {
                await api.put(`/bank-accounts/${editingAccount.id}/`, payload);
                toast.success('Bank account updated successfully');
            } else {
                await api.post('/bank-accounts/', payload);
                toast.success('Bank account created successfully');
            }
            setShowModal(false);
            resetForm();
            fetchBankAccounts();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Failed to save bank account');
        }
    };

    const handleEdit = (account) => {
        setEditingAccount(account);
        setFormData({
            account_name: account.account_name,
            bank_name: account.bank_name,
            account_number: account.account_number,
            ifsc_code: account.ifsc_code || '',
            branch: account.branch || '',
            account_type: account.account_type,
            opening_balance: account.opening_balance,
            is_active: account.is_active
        });
        setShowModal(true);
    };

    const handleDelete = async (id) => {
        if (window.confirm('Are you sure you want to delete this bank account?')) {
            try {
                await api.delete(`/bank-accounts/${id}/`);
                toast.success('Bank account deleted successfully');
                fetchBankAccounts();
            } catch (error) {
                toast.error(error.response?.data?.detail || 'Failed to delete bank account');
            }
        }
    };

    const resetForm = () => {
        setFormData({
            account_name: '',
            bank_name: '',
            account_number: '',
            ifsc_code: '',
            branch: '',
            account_type: 'SAVINGS',
            opening_balance: '0.00',
            is_active: true
        });
        setEditingAccount(null);
    };

    const handleCloseModal = () => {
        setShowModal(false);
        resetForm();
    };

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
                <h2><i className="bi bi-bank me-2"></i>Bank Accounts</h2>
                <button className="btn btn-primary" onClick={() => setShowModal(true)}>
                    <i className="bi bi-plus-circle me-2"></i>New Bank Account
                </button>
            </div>

            <div className="card">
                <div className="card-body p-0">
                    <div className="table-responsive">
                        <table className="table table-hover mb-0">
                            <thead className="table-light">
                                <tr>
                                    <th>Account Name</th>
                                    <th>Bank Name</th>
                                    <th>Account Number</th>
                                    <th>IFSC Code</th>
                                    <th>Branch</th>
                                    <th>Type</th>
                                    <th className="text-end">Current Balance</th>
                                    <th>Status</th>
                                    <th className="text-end">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {bankAccounts.map(account => (
                                    <tr key={account.id}>
                                        <td><strong>{account.account_name}</strong></td>
                                        <td>{account.bank_name}</td>
                                        <td><code>{account.account_number}</code></td>
                                        <td>{account.ifsc_code || '-'}</td>
                                        <td>{account.branch || '-'}</td>
                                        <td>
                                            <span className="badge bg-info">
                                                {accountTypes.find(t => t.value === account.account_type)?.label}
                                            </span>
                                        </td>
                                        <td className="text-end">
                                            <strong>{formatCurrency(account.current_balance)}</strong>
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
                                {bankAccounts.length === 0 && (
                                    <tr>
                                        <td colSpan="9" className="text-center text-muted py-4">
                                            No bank accounts found. Click "New Bank Account" to create one.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Modal */}
            {showModal && (
                <div className="modal show d-block" tabIndex="-1" style={{backgroundColor: 'rgba(0,0,0,0.5)'}}>
                    <div className="modal-dialog modal-lg">
                        <div className="modal-content">
                            <div className="modal-header">
                                <h5 className="modal-title">
                                    {editingAccount ? 'Edit Bank Account' : 'New Bank Account'}
                                </h5>
                                <button type="button" className="btn-close" onClick={handleCloseModal}></button>
                            </div>
                            <form onSubmit={handleSubmit}>
                                <div className="modal-body">
                                    <div className="row">
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">Account Name *</label>
                                            <input
                                                type="text"
                                                className="form-control"
                                                value={formData.account_name}
                                                onChange={(e) => setFormData({...formData, account_name: e.target.value})}
                                                required
                                            />
                                        </div>
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">Bank Name *</label>
                                            <input
                                                type="text"
                                                className="form-control"
                                                value={formData.bank_name}
                                                onChange={(e) => setFormData({...formData, bank_name: e.target.value})}
                                                required
                                            />
                                        </div>
                                    </div>
                                    <div className="row">
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">Account Number *</label>
                                            <input
                                                type="text"
                                                className="form-control"
                                                value={formData.account_number}
                                                onChange={(e) => setFormData({...formData, account_number: e.target.value})}
                                                required
                                            />
                                        </div>
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">IFSC Code</label>
                                            <input
                                                type="text"
                                                className="form-control"
                                                value={formData.ifsc_code}
                                                onChange={(e) => setFormData({...formData, ifsc_code: e.target.value})}
                                            />
                                        </div>
                                    </div>
                                    <div className="row">
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">Branch</label>
                                            <input
                                                type="text"
                                                className="form-control"
                                                value={formData.branch}
                                                onChange={(e) => setFormData({...formData, branch: e.target.value})}
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
                                    <div className="row">
                                        <div className="col-md-6 mb-3">
                                            <label className="form-label">Opening Balance</label>
                                            <input
                                                type="number"
                                                step="0.01"
                                                className="form-control"
                                                value={formData.opening_balance}
                                                onChange={(e) => setFormData({...formData, opening_balance: e.target.value})}
                                            />
                                        </div>
                                        <div className="col-md-6 mb-3 d-flex align-items-end">
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
