import {useEffect, useState} from "react";
import {toast} from 'react-toastify';
import api from "../../api/axios";

export default function TrialBalance() {
    const [trialBalance, setTrialBalance] = useState(null);
    const [loading, setLoading] = useState(false);
    const [asOfDate, setAsOfDate] = useState(new Date().toISOString().split('T')[0]);
    const [filterType, setFilterType] = useState('');

    const accountTypes = [
        {value: '', label: 'All Accounts'},
        {value: 'ASSET', label: 'Assets'},
        {value: 'LIABILITY', label: 'Liabilities'},
        {value: 'EQUITY', label: 'Equity'},
        {value: 'REVENUE', label: 'Revenue'},
        {value: 'EXPENSE', label: 'Expenses'}
    ];

    const fetchTrialBalance = async () => {
        setLoading(true);
        try {
            let url = `/chart-of-accounts/trial_balance/?as_of_date=${asOfDate}`;
            if (filterType) url += `&account_type=${filterType}`;
            const response = await api.get(url);
            setTrialBalance(response.data);
            setLoading(false);
        } catch (error) {
            toast.error('Failed to fetch trial balance');
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTrialBalance();
    }, []);

    const formatCurrency = (amount) => {
        if (!amount && amount !== 0) return '₹0.00';
        return `₹${parseFloat(amount).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    };

    const printReport = () => {
        window.print();
    };

    if (loading) {
        return <div className="container mt-4"><div className="spinner-border" role="status"></div></div>;
    }

    return (
        <div className="container-fluid mt-4">
            <div className="d-flex justify-content-between align-items-center mb-4 no-print">
                <h2><i className="bi bi-calculator me-2"></i>Trial Balance</h2>
                <div className="d-flex gap-2">
                    <select
                        className="form-select"
                        value={filterType}
                        onChange={(e) => setFilterType(e.target.value)}
                        style={{width: '200px'}}
                    >
                        {accountTypes.map(type => (
                            <option key={type.value} value={type.value}>{type.label}</option>
                        ))}
                    </select>
                    <input
                        type="date"
                        className="form-control"
                        value={asOfDate}
                        onChange={(e) => setAsOfDate(e.target.value)}
                        style={{width: '200px'}}
                    />
                    <button className="btn btn-primary" onClick={fetchTrialBalance}>
                        <i className="bi bi-arrow-clockwise me-2"></i>Refresh
                    </button>
                    <button className="btn btn-secondary" onClick={printReport}>
                        <i className="bi bi-printer me-2"></i>Print
                    </button>
                </div>
            </div>

            {trialBalance && (
                <div className="card">
                    <div className="card-body">
                        <div className="text-center mb-4 print-header">
                            <h3>Trial Balance</h3>
                            <p className="text-muted">As of {new Date(asOfDate).toLocaleDateString('en-GB')}</p>
                        </div>

                        <div className="table-responsive">
                            <table className="table table-bordered table-hover">
                                <thead className="table-dark">
                                    <tr>
                                        <th style={{width: '10%'}}>Code</th>
                                        <th style={{width: '40%'}}>Account Name</th>
                                        <th style={{width: '15%'}}>Type</th>
                                        <th className="text-end" style={{width: '17.5%'}}>Debit (₹)</th>
                                        <th className="text-end" style={{width: '17.5%'}}>Credit (₹)</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {trialBalance.accounts?.map((account, index) => (
                                        <tr key={index} className={account.balance === 0 ? 'text-muted' : ''}>
                                            <td><code>{account.code}</code></td>
                                            <td>{account.name}</td>
                                            <td>
                                                <span className={`badge ${
                                                    account.account_type === 'ASSET' ? 'bg-primary' :
                                                    account.account_type === 'LIABILITY' ? 'bg-danger' :
                                                    account.account_type === 'EQUITY' ? 'bg-success' :
                                                    account.account_type === 'REVENUE' ? 'bg-info' :
                                                    account.account_type === 'EXPENSE' ? 'bg-warning' :
                                                    'bg-secondary'
                                                }`}>
                                                    {account.account_type}
                                                </span>
                                            </td>
                                            <td className="text-end">
                                                {account.debit_balance > 0 ? formatCurrency(account.debit_balance) : '-'}
                                            </td>
                                            <td className="text-end">
                                                {account.credit_balance > 0 ? formatCurrency(account.credit_balance) : '-'}
                                            </td>
                                        </tr>
                                    ))}
                                    {trialBalance.accounts?.length === 0 && (
                                        <tr>
                                            <td colSpan="5" className="text-center text-muted py-4">
                                                No accounts found
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                                <tfoot className="table-dark">
                                    <tr>
                                        <th colSpan="3" className="text-end">Total:</th>
                                        <th className="text-end">{formatCurrency(trialBalance.total_debit)}</th>
                                        <th className="text-end">{formatCurrency(trialBalance.total_credit)}</th>
                                    </tr>
                                    <tr>
                                        <th colSpan="3" className="text-end">Difference:</th>
                                        <th colSpan="2" className={`text-center ${
                                            Math.abs(trialBalance.difference) < 0.01 ? 'text-success' : 'text-danger'
                                        }`}>
                                            {formatCurrency(Math.abs(trialBalance.difference))}
                                        </th>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>

                        {/* Balance Check */}
                        <div className={`alert ${
                            Math.abs(trialBalance.difference) < 0.01 ? 'alert-success' : 'alert-danger'
                        } mt-3`}>
                            {Math.abs(trialBalance.difference) < 0.01 ? (
                                <>
                                    <i className="bi bi-check-circle me-2"></i>
                                    <strong>Trial Balance is balanced!</strong>
                                    <div className="mt-2">
                                        Total Debit = Total Credit = {formatCurrency(trialBalance.total_debit)}
                                    </div>
                                </>
                            ) : (
                                <>
                                    <i className="bi bi-exclamation-triangle me-2"></i>
                                    <strong>Trial Balance is not balanced!</strong>
                                    <div className="mt-2">
                                        Difference: {formatCurrency(Math.abs(trialBalance.difference))}
                                    </div>
                                    <div className="mt-2">
                                        Total Debit: {formatCurrency(trialBalance.total_debit)} |
                                        Total Credit: {formatCurrency(trialBalance.total_credit)}
                                    </div>
                                </>
                            )}
                        </div>

                        {/* Summary by Account Type */}
                        <div className="row mt-4">
                            <div className="col-md-12">
                                <h5>Summary by Account Type</h5>
                                <table className="table table-sm">
                                    <thead className="table-light">
                                        <tr>
                                            <th>Account Type</th>
                                            <th className="text-end">Total Debit</th>
                                            <th className="text-end">Total Credit</th>
                                            <th className="text-end">Net Balance</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {trialBalance.summary_by_type?.map((summary, index) => (
                                            <tr key={index}>
                                                <td>
                                                    <span className={`badge ${
                                                        summary.account_type === 'ASSET' ? 'bg-primary' :
                                                        summary.account_type === 'LIABILITY' ? 'bg-danger' :
                                                        summary.account_type === 'EQUITY' ? 'bg-success' :
                                                        summary.account_type === 'REVENUE' ? 'bg-info' :
                                                        summary.account_type === 'EXPENSE' ? 'bg-warning' :
                                                        'bg-secondary'
                                                    }`}>
                                                        {summary.account_type}
                                                    </span>
                                                </td>
                                                <td className="text-end">{formatCurrency(summary.total_debit)}</td>
                                                <td className="text-end">{formatCurrency(summary.total_credit)}</td>
                                                <td className="text-end">
                                                    <strong>{formatCurrency(summary.net_balance)}</strong>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <style>{`
                @media print {
                    .no-print {
                        display: none !important;
                    }
                    .card {
                        border: none !important;
                        box-shadow: none !important;
                    }
                    .print-header {
                        margin-bottom: 30px;
                    }
                    table {
                        font-size: 10pt;
                    }
                }
            `}</style>
        </div>
    );
}
