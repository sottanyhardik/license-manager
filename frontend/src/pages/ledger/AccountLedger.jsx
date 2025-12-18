import {useEffect, useState} from "react";
import {toast} from 'react-toastify';
import api from "../../api/axios";

export default function AccountLedger() {
    const [accounts, setAccounts] = useState([]);
    const [selectedAccount, setSelectedAccount] = useState('');
    const [ledgerData, setLedgerData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [filterType, setFilterType] = useState('');

    const accountTypes = [
        {value: '', label: 'All Types'},
        {value: 'ASSET', label: 'Asset'},
        {value: 'LIABILITY', label: 'Liability'},
        {value: 'EQUITY', label: 'Equity'},
        {value: 'REVENUE', label: 'Revenue'},
        {value: 'EXPENSE', label: 'Expense'}
    ];

    useEffect(() => {
        fetchAccounts();
    }, [filterType]);

    const fetchAccounts = async () => {
        try {
            let url = '/chart-of-accounts/';
            if (filterType) url += `?account_type=${filterType}`;
            const response = await api.get(url);
            setAccounts(response.data.results || response.data);
        } catch (error) {
            toast.error('Failed to fetch accounts');
        }
    };

    const fetchLedger = async () => {
        if (!selectedAccount) {
            toast.warning('Please select an account');
            return;
        }

        setLoading(true);
        try {
            let url = `/ledger/account/${selectedAccount}/`;
            const params = new URLSearchParams();
            if (dateFrom) params.append('date_from', dateFrom);
            if (dateTo) params.append('date_to', dateTo);
            if (params.toString()) url += `?${params.toString()}`;

            const response = await api.get(url);
            setLedgerData(response.data);
            setLoading(false);
        } catch (error) {
            toast.error('Failed to fetch ledger data');
            setLoading(false);
        }
    };

    const formatCurrency = (amount) => {
        if (!amount && amount !== 0) return '₹0.00';
        return `₹${parseFloat(amount).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    };

    const getBalanceClass = (balance) => {
        if (!balance) return '';
        return parseFloat(balance) >= 0 ? 'text-success' : 'text-danger';
    };

    return (
        <div className="container-fluid mt-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2><i className="bi bi-list-ul me-2"></i>Account Ledger</h2>
            </div>

            <div className="card mb-4">
                <div className="card-body">
                    <div className="row mb-3">
                        <div className="col-md-3">
                            <label className="form-label">Account Type</label>
                            <select
                                className="form-select"
                                value={filterType}
                                onChange={(e) => {
                                    setFilterType(e.target.value);
                                    setSelectedAccount('');
                                }}
                            >
                                {accountTypes.map(type => (
                                    <option key={type.value} value={type.value}>{type.label}</option>
                                ))}
                            </select>
                        </div>
                        <div className="col-md-5">
                            <label className="form-label">Select Account *</label>
                            <select
                                className="form-select"
                                value={selectedAccount}
                                onChange={(e) => setSelectedAccount(e.target.value)}
                            >
                                <option value="">Choose an account...</option>
                                {accounts.map(account => (
                                    <option key={account.id} value={account.id}>
                                        {account.code} - {account.name}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                    <div className="row">
                        <div className="col-md-3">
                            <label className="form-label">From Date</label>
                            <input
                                type="date"
                                className="form-control"
                                value={dateFrom}
                                onChange={(e) => setDateFrom(e.target.value)}
                            />
                        </div>
                        <div className="col-md-3">
                            <label className="form-label">To Date</label>
                            <input
                                type="date"
                                className="form-control"
                                value={dateTo}
                                onChange={(e) => setDateTo(e.target.value)}
                            />
                        </div>
                        <div className="col-md-2 d-flex align-items-end">
                            <button
                                className="btn btn-primary w-100"
                                onClick={fetchLedger}
                                disabled={loading}
                            >
                                {loading ? (
                                    <span className="spinner-border spinner-border-sm me-2"></span>
                                ) : (
                                    <i className="bi bi-search me-2"></i>
                                )}
                                View Ledger
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {ledgerData && (
                <>
                    <div className="card mb-3">
                        <div className="card-header bg-primary text-white">
                            <h5 className="mb-0">
                                <i className="bi bi-calculator me-2"></i>
                                {ledgerData.account_code} - {ledgerData.account_name}
                            </h5>
                        </div>
                        <div className="card-body">
                            <div className="row">
                                <div className="col-md-2">
                                    <strong>Account Type:</strong>
                                    <div className="badge bg-info fs-6 mt-1">{ledgerData.account_type}</div>
                                </div>
                                <div className="col-md-2">
                                    <strong>Opening Balance:</strong>
                                    <div className={`fs-5 ${getBalanceClass(ledgerData.opening_balance)}`}>
                                        {formatCurrency(ledgerData.opening_balance)}
                                    </div>
                                </div>
                                <div className="col-md-2">
                                    <strong>Total Debit:</strong>
                                    <div className="fs-5">{formatCurrency(ledgerData.total_debit)}</div>
                                </div>
                                <div className="col-md-2">
                                    <strong>Total Credit:</strong>
                                    <div className="fs-5">{formatCurrency(ledgerData.total_credit)}</div>
                                </div>
                                <div className="col-md-2">
                                    <strong>Closing Balance:</strong>
                                    <div className={`fs-5 fw-bold ${getBalanceClass(ledgerData.closing_balance)}`}>
                                        {formatCurrency(ledgerData.closing_balance)}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="card">
                        <div className="card-body p-0">
                            <div className="table-responsive">
                                <table className="table table-hover mb-0">
                                    <thead className="table-light">
                                        <tr>
                                            <th>Date</th>
                                            <th>Entry Number</th>
                                            <th>Reference</th>
                                            <th>Description</th>
                                            <th className="text-end">Debit</th>
                                            <th className="text-end">Credit</th>
                                            <th className="text-end">Balance</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {/* Opening Balance Row */}
                                        <tr className="table-secondary">
                                            <td colSpan="4"><strong>Opening Balance</strong></td>
                                            <td className="text-end">-</td>
                                            <td className="text-end">-</td>
                                            <td className={`text-end fw-bold ${getBalanceClass(ledgerData.opening_balance)}`}>
                                                {formatCurrency(ledgerData.opening_balance)}
                                            </td>
                                        </tr>

                                        {/* Transaction Rows */}
                                        {ledgerData.entries?.map((entry, index) => (
                                            <tr key={index}>
                                                <td>{new Date(entry.date).toLocaleDateString('en-GB')}</td>
                                                <td><code>{entry.entry_number}</code></td>
                                                <td>{entry.reference || '-'}</td>
                                                <td>{entry.description || '-'}</td>
                                                <td className="text-end">
                                                    {entry.debit ? formatCurrency(entry.debit) : '-'}
                                                </td>
                                                <td className="text-end">
                                                    {entry.credit ? formatCurrency(entry.credit) : '-'}
                                                </td>
                                                <td className={`text-end fw-bold ${getBalanceClass(entry.balance)}`}>
                                                    {formatCurrency(entry.balance)}
                                                </td>
                                            </tr>
                                        ))}

                                        {ledgerData.entries?.length === 0 && (
                                            <tr>
                                                <td colSpan="7" className="text-center text-muted py-3">
                                                    No entries found for the selected period
                                                </td>
                                            </tr>
                                        )}

                                        {/* Closing Balance Row */}
                                        <tr className="table-dark">
                                            <td colSpan="4"><strong>Closing Balance</strong></td>
                                            <td className="text-end"><strong>{formatCurrency(ledgerData.total_debit)}</strong></td>
                                            <td className="text-end"><strong>{formatCurrency(ledgerData.total_credit)}</strong></td>
                                            <td className={`text-end fw-bold ${getBalanceClass(ledgerData.closing_balance)}`}>
                                                {formatCurrency(ledgerData.closing_balance)}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </>
            )}

            {!ledgerData && !loading && (
                <div className="alert alert-info">
                    <i className="bi bi-info-circle me-2"></i>
                    Select an account and click "View Ledger" to see all journal entries.
                </div>
            )}
        </div>
    );
}
