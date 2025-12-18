import {useEffect, useState} from "react";
import {toast} from 'react-toastify';
import api from "../../api/axios";

export default function JournalEntries() {
    const [journalEntries, setJournalEntries] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editingEntry, setEditingEntry] = useState(null);
    const [viewingEntry, setViewingEntry] = useState(null);
    const [showViewModal, setShowViewModal] = useState(false);
    const [formData, setFormData] = useState({
        entry_number: '',
        entry_date: new Date().toISOString().split('T')[0],
        reference_number: '',
        description: '',
        lines: []
    });
    const [accounts, setAccounts] = useState([]);
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);

    useEffect(() => {
        fetchJournalEntries();
        fetchChartOfAccounts();
    }, [currentPage]);

    const fetchJournalEntries = async () => {
        try {
            const response = await api.get(`/journal-entries/?page=${currentPage}`);
            setJournalEntries(response.data.results || response.data);
            if (response.data.count) {
                setTotalPages(Math.ceil(response.data.count / 25));
            }
            setLoading(false);
        } catch (error) {
            toast.error('Failed to fetch journal entries');
            setLoading(false);
        }
    };

    const fetchChartOfAccounts = async () => {
        try {
            const response = await api.get('/chart-of-accounts/');
            setAccounts(response.data.results || response.data);
        } catch (error) {
            console.error('Failed to fetch accounts');
        }
    };

    const addLine = () => {
        setFormData({
            ...formData,
            lines: [...formData.lines, {account: '', debit_amount: '0.00', credit_amount: '0.00', description: ''}]
        });
    };

    const removeLine = (index) => {
        const newLines = formData.lines.filter((_, i) => i !== index);
        setFormData({...formData, lines: newLines});
    };

    const updateLine = (index, field, value) => {
        const newLines = [...formData.lines];
        newLines[index][field] = value;
        setFormData({...formData, lines: newLines});
    };

    const calculateTotals = () => {
        const totalDebit = formData.lines.reduce((sum, line) => sum + (parseFloat(line.debit_amount) || 0), 0);
        const totalCredit = formData.lines.reduce((sum, line) => sum + (parseFloat(line.credit_amount) || 0), 0);
        return {totalDebit, totalCredit, difference: totalDebit - totalCredit};
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        const {totalDebit, totalCredit, difference} = calculateTotals();
        if (Math.abs(difference) > 0.01) {
            toast.error(`Entry is not balanced! Difference: ₹${difference.toFixed(2)}`);
            return;
        }

        try {
            const payload = {
                ...formData,
                lines: formData.lines.map(line => ({
                    ...line,
                    debit_amount: parseFloat(line.debit_amount) || 0,
                    credit_amount: parseFloat(line.credit_amount) || 0
                }))
            };

            if (editingEntry) {
                await api.put(`/journal-entries/${editingEntry.id}/`, payload);
                toast.success('Journal entry updated successfully');
            } else {
                await api.post('/journal-entries/', payload);
                toast.success('Journal entry created successfully');
            }
            setShowModal(false);
            resetForm();
            fetchJournalEntries();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Failed to save journal entry');
        }
    };

    const handlePost = async (id) => {
        if (window.confirm('Are you sure you want to post this entry? Posted entries cannot be modified.')) {
            try {
                await api.post(`/journal-entries/${id}/post/`);
                toast.success('Journal entry posted successfully');
                fetchJournalEntries();
            } catch (error) {
                toast.error(error.response?.data?.detail || 'Failed to post entry');
            }
        }
    };

    const handleUnpost = async (id) => {
        if (window.confirm('Are you sure you want to unpost this entry?')) {
            try {
                await api.post(`/journal-entries/${id}/unpost/`);
                toast.success('Journal entry unposted successfully');
                fetchJournalEntries();
            } catch (error) {
                toast.error(error.response?.data?.detail || 'Failed to unpost entry');
            }
        }
    };

    const handleView = async (entry) => {
        try {
            const response = await api.get(`/journal-entries/${entry.id}/`);
            setViewingEntry(response.data);
            setShowViewModal(true);
        } catch (error) {
            toast.error('Failed to fetch entry details');
        }
    };

    const handleDelete = async (id) => {
        if (window.confirm('Are you sure you want to delete this journal entry?')) {
            try {
                await api.delete(`/journal-entries/${id}/`);
                toast.success('Journal entry deleted successfully');
                fetchJournalEntries();
            } catch (error) {
                toast.error(error.response?.data?.detail || 'Failed to delete entry');
            }
        }
    };

    const resetForm = () => {
        setFormData({
            entry_number: '',
            entry_date: new Date().toISOString().split('T')[0],
            reference_number: '',
            description: '',
            lines: []
        });
        setEditingEntry(null);
    };

    const handleCloseModal = () => {
        setShowModal(false);
        resetForm();
    };

    const formatCurrency = (amount) => {
        if (!amount && amount !== 0) return '₹0.00';
        return `₹${parseFloat(amount).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    };

    const {totalDebit, totalCredit, difference} = calculateTotals();
    const isBalanced = Math.abs(difference) < 0.01;

    if (loading) {
        return <div className="container mt-4"><div className="spinner-border" role="status"></div></div>;
    }

    return (
        <div className="container-fluid mt-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2><i className="bi bi-journal-text me-2"></i>Journal Entries</h2>
                <button className="btn btn-primary" onClick={() => setShowModal(true)}>
                    <i className="bi bi-plus-circle me-2"></i>New Journal Entry
                </button>
            </div>

            <div className="card">
                <div className="card-body p-0">
                    <div className="table-responsive">
                        <table className="table table-hover mb-0">
                            <thead className="table-light">
                                <tr>
                                    <th>Entry Number</th>
                                    <th>Date</th>
                                    <th>Reference</th>
                                    <th>Description</th>
                                    <th className="text-end">Debit</th>
                                    <th className="text-end">Credit</th>
                                    <th>Status</th>
                                    <th className="text-end">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {journalEntries.map(entry => (
                                    <tr key={entry.id}>
                                        <td><code>{entry.entry_number}</code></td>
                                        <td>{new Date(entry.entry_date).toLocaleDateString('en-GB')}</td>
                                        <td>{entry.reference_number || '-'}</td>
                                        <td>{entry.description}</td>
                                        <td className="text-end">{formatCurrency(entry.total_debit)}</td>
                                        <td className="text-end">{formatCurrency(entry.total_credit)}</td>
                                        <td>
                                            <span className={`badge ${entry.is_posted ? 'bg-success' : 'bg-warning'}`}>
                                                {entry.is_posted ? 'Posted' : 'Draft'}
                                            </span>
                                        </td>
                                        <td className="text-end">
                                            <button
                                                className="btn btn-sm btn-outline-info me-2"
                                                onClick={() => handleView(entry)}
                                            >
                                                <i className="bi bi-eye"></i>
                                            </button>
                                            {!entry.is_posted ? (
                                                <>
                                                    <button
                                                        className="btn btn-sm btn-outline-success me-2"
                                                        onClick={() => handlePost(entry.id)}
                                                    >
                                                        <i className="bi bi-check-circle"></i>
                                                    </button>
                                                    <button
                                                        className="btn btn-sm btn-outline-danger"
                                                        onClick={() => handleDelete(entry.id)}
                                                    >
                                                        <i className="bi bi-trash"></i>
                                                    </button>
                                                </>
                                            ) : (
                                                <button
                                                    className="btn btn-sm btn-outline-warning"
                                                    onClick={() => handleUnpost(entry.id)}
                                                >
                                                    <i className="bi bi-x-circle"></i>
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                                {journalEntries.length === 0 && (
                                    <tr>
                                        <td colSpan="8" className="text-center text-muted py-4">
                                            No journal entries found. Click "New Journal Entry" to create one.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <nav className="mt-3">
                    <ul className="pagination justify-content-center">
                        <li className={`page-item ${currentPage === 1 ? 'disabled' : ''}`}>
                            <button className="page-link" onClick={() => setCurrentPage(currentPage - 1)}>Previous</button>
                        </li>
                        {[...Array(totalPages)].map((_, i) => (
                            <li key={i} className={`page-item ${currentPage === i + 1 ? 'active' : ''}`}>
                                <button className="page-link" onClick={() => setCurrentPage(i + 1)}>{i + 1}</button>
                            </li>
                        ))}
                        <li className={`page-item ${currentPage === totalPages ? 'disabled' : ''}`}>
                            <button className="page-link" onClick={() => setCurrentPage(currentPage + 1)}>Next</button>
                        </li>
                    </ul>
                </nav>
            )}

            {/* Create/Edit Modal */}
            {showModal && (
                <div className="modal show d-block" tabIndex="-1" style={{backgroundColor: 'rgba(0,0,0,0.5)'}}>
                    <div className="modal-dialog modal-xl">
                        <div className="modal-content">
                            <div className="modal-header">
                                <h5 className="modal-title">
                                    {editingEntry ? 'Edit Journal Entry' : 'New Journal Entry'}
                                </h5>
                                <button type="button" className="btn-close" onClick={handleCloseModal}></button>
                            </div>
                            <form onSubmit={handleSubmit}>
                                <div className="modal-body">
                                    <div className="row mb-3">
                                        <div className="col-md-4">
                                            <label className="form-label">Entry Number *</label>
                                            <input
                                                type="text"
                                                className="form-control"
                                                value={formData.entry_number}
                                                onChange={(e) => setFormData({...formData, entry_number: e.target.value})}
                                                required
                                            />
                                        </div>
                                        <div className="col-md-4">
                                            <label className="form-label">Entry Date *</label>
                                            <input
                                                type="date"
                                                className="form-control"
                                                value={formData.entry_date}
                                                onChange={(e) => setFormData({...formData, entry_date: e.target.value})}
                                                required
                                            />
                                        </div>
                                        <div className="col-md-4">
                                            <label className="form-label">Reference Number</label>
                                            <input
                                                type="text"
                                                className="form-control"
                                                value={formData.reference_number}
                                                onChange={(e) => setFormData({...formData, reference_number: e.target.value})}
                                            />
                                        </div>
                                    </div>
                                    <div className="mb-3">
                                        <label className="form-label">Description</label>
                                        <textarea
                                            className="form-control"
                                            rows="2"
                                            value={formData.description}
                                            onChange={(e) => setFormData({...formData, description: e.target.value})}
                                        ></textarea>
                                    </div>

                                    <hr />

                                    <div className="d-flex justify-content-between align-items-center mb-3">
                                        <h6>Journal Entry Lines</h6>
                                        <button type="button" className="btn btn-sm btn-success" onClick={addLine}>
                                            <i className="bi bi-plus"></i> Add Line
                                        </button>
                                    </div>

                                    {formData.lines.map((line, index) => (
                                        <div key={index} className="card mb-2">
                                            <div className="card-body p-3">
                                                <div className="row">
                                                    <div className="col-md-4">
                                                        <label className="form-label">Account *</label>
                                                        <select
                                                            className="form-select"
                                                            value={line.account}
                                                            onChange={(e) => updateLine(index, 'account', e.target.value)}
                                                            required
                                                        >
                                                            <option value="">Select Account</option>
                                                            {accounts.map(account => (
                                                                <option key={account.id} value={account.id}>
                                                                    {account.code} - {account.name}
                                                                </option>
                                                            ))}
                                                        </select>
                                                    </div>
                                                    <div className="col-md-2">
                                                        <label className="form-label">Debit</label>
                                                        <input
                                                            type="number"
                                                            step="0.01"
                                                            className="form-control"
                                                            value={line.debit_amount}
                                                            onChange={(e) => updateLine(index, 'debit_amount', e.target.value)}
                                                        />
                                                    </div>
                                                    <div className="col-md-2">
                                                        <label className="form-label">Credit</label>
                                                        <input
                                                            type="number"
                                                            step="0.01"
                                                            className="form-control"
                                                            value={line.credit_amount}
                                                            onChange={(e) => updateLine(index, 'credit_amount', e.target.value)}
                                                        />
                                                    </div>
                                                    <div className="col-md-3">
                                                        <label className="form-label">Description</label>
                                                        <input
                                                            type="text"
                                                            className="form-control"
                                                            value={line.description}
                                                            onChange={(e) => updateLine(index, 'description', e.target.value)}
                                                        />
                                                    </div>
                                                    <div className="col-md-1 d-flex align-items-end">
                                                        <button
                                                            type="button"
                                                            className="btn btn-sm btn-outline-danger w-100"
                                                            onClick={() => removeLine(index)}
                                                        >
                                                            <i className="bi bi-trash"></i>
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    ))}

                                    {formData.lines.length === 0 && (
                                        <div className="alert alert-info">
                                            Click "Add Line" to add journal entry lines. Each entry must have at least 2 lines.
                                        </div>
                                    )}

                                    <div className="card bg-light mt-3">
                                        <div className="card-body">
                                            <div className="row">
                                                <div className="col-md-4">
                                                    <strong>Total Debit:</strong> {formatCurrency(totalDebit)}
                                                </div>
                                                <div className="col-md-4">
                                                    <strong>Total Credit:</strong> {formatCurrency(totalCredit)}
                                                </div>
                                                <div className="col-md-4">
                                                    <strong className={isBalanced ? 'text-success' : 'text-danger'}>
                                                        Difference: {formatCurrency(Math.abs(difference))}
                                                    </strong>
                                                    {isBalanced && <i className="bi bi-check-circle text-success ms-2"></i>}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div className="modal-footer">
                                    <button type="button" className="btn btn-secondary" onClick={handleCloseModal}>
                                        Cancel
                                    </button>
                                    <button type="submit" className="btn btn-primary" disabled={!isBalanced || formData.lines.length < 2}>
                                        {editingEntry ? 'Update' : 'Create'}
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            )}

            {/* View Modal */}
            {showViewModal && viewingEntry && (
                <div className="modal show d-block" tabIndex="-1" style={{backgroundColor: 'rgba(0,0,0,0.5)'}}>
                    <div className="modal-dialog modal-lg">
                        <div className="modal-content">
                            <div className="modal-header">
                                <h5 className="modal-title">Journal Entry Details</h5>
                                <button type="button" className="btn-close" onClick={() => setShowViewModal(false)}></button>
                            </div>
                            <div className="modal-body">
                                <div className="row mb-3">
                                    <div className="col-md-6">
                                        <strong>Entry Number:</strong> {viewingEntry.entry_number}
                                    </div>
                                    <div className="col-md-6">
                                        <strong>Date:</strong> {new Date(viewingEntry.entry_date).toLocaleDateString('en-GB')}
                                    </div>
                                </div>
                                <div className="row mb-3">
                                    <div className="col-md-6">
                                        <strong>Reference:</strong> {viewingEntry.reference_number || '-'}
                                    </div>
                                    <div className="col-md-6">
                                        <strong>Status:</strong>{' '}
                                        <span className={`badge ${viewingEntry.is_posted ? 'bg-success' : 'bg-warning'}`}>
                                            {viewingEntry.is_posted ? 'Posted' : 'Draft'}
                                        </span>
                                    </div>
                                </div>
                                <div className="mb-3">
                                    <strong>Description:</strong> {viewingEntry.description || '-'}
                                </div>

                                <hr />

                                <h6>Entry Lines</h6>
                                <table className="table table-sm">
                                    <thead>
                                        <tr>
                                            <th>Account</th>
                                            <th className="text-end">Debit</th>
                                            <th className="text-end">Credit</th>
                                            <th>Description</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {viewingEntry.lines?.map((line, index) => (
                                            <tr key={index}>
                                                <td>{line.account_name}</td>
                                                <td className="text-end">{formatCurrency(line.debit_amount)}</td>
                                                <td className="text-end">{formatCurrency(line.credit_amount)}</td>
                                                <td>{line.description || '-'}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                    <tfoot>
                                        <tr className="table-light">
                                            <th>Total</th>
                                            <th className="text-end">{formatCurrency(viewingEntry.total_debit)}</th>
                                            <th className="text-end">{formatCurrency(viewingEntry.total_credit)}</th>
                                            <th></th>
                                        </tr>
                                    </tfoot>
                                </table>
                            </div>
                            <div className="modal-footer">
                                <button type="button" className="btn btn-secondary" onClick={() => setShowViewModal(false)}>
                                    Close
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
