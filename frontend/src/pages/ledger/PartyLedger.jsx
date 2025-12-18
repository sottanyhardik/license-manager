import {useEffect, useState} from "react";
import {toast} from 'react-toastify';
import api from "../../api/axios";

export default function PartyLedger() {
    const [companies, setCompanies] = useState([]);
    const [selectedCompany, setSelectedCompany] = useState('');
    const [ledgerData, setLedgerData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');

    useEffect(() => {
        fetchCompanies();
    }, []);

    const fetchCompanies = async () => {
        try {
            const response = await api.get('/companies/');
            setCompanies(response.data.results || response.data);
        } catch (error) {
            toast.error('Failed to fetch companies');
        }
    };

    const fetchLedger = async () => {
        if (!selectedCompany) {
            toast.warning('Please select a company');
            return;
        }

        setLoading(true);
        try {
            let url = `/ledger/party/${selectedCompany}/`;
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
                <h2><i className="bi bi-people me-2"></i>Party Ledger</h2>
            </div>

            <div className="card mb-4">
                <div className="card-body">
                    <div className="row">
                        <div className="col-md-4">
                            <label className="form-label">Select Company *</label>
                            <select
                                className="form-select"
                                value={selectedCompany}
                                onChange={(e) => setSelectedCompany(e.target.value)}
                            >
                                <option value="">Choose a company...</option>
                                {companies.map(company => (
                                    <option key={company.id} value={company.id}>
                                        {company.name}
                                    </option>
                                ))}
                            </select>
                        </div>
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
                                <i className="bi bi-building me-2"></i>
                                {ledgerData.company_name}
                            </h5>
                        </div>
                        <div className="card-body">
                            <div className="row">
                                <div className="col-md-3">
                                    <strong>Opening Balance:</strong>
                                    <div className={`fs-5 ${getBalanceClass(ledgerData.opening_balance)}`}>
                                        {formatCurrency(ledgerData.opening_balance)}
                                    </div>
                                </div>
                                <div className="col-md-3">
                                    <strong>Total Debit:</strong>
                                    <div className="fs-5">{formatCurrency(ledgerData.total_debit)}</div>
                                </div>
                                <div className="col-md-3">
                                    <strong>Total Credit:</strong>
                                    <div className="fs-5">{formatCurrency(ledgerData.total_credit)}</div>
                                </div>
                                <div className="col-md-3">
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
                                            <th>Type</th>
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
                                        {ledgerData.transactions?.map((transaction, index) => (
                                            <tr key={index}>
                                                <td>{new Date(transaction.date).toLocaleDateString('en-GB')}</td>
                                                <td>
                                                    <span className={`badge ${
                                                        transaction.type === 'PURCHASE' ? 'bg-info' :
                                                        transaction.type === 'SALE' ? 'bg-success' :
                                                        transaction.type === 'PAYMENT' ? 'bg-warning' :
                                                        transaction.type === 'RECEIPT' ? 'bg-primary' :
                                                        'bg-secondary'
                                                    }`}>
                                                        {transaction.type}
                                                    </span>
                                                </td>
                                                <td>{transaction.reference || '-'}</td>
                                                <td>{transaction.description || '-'}</td>
                                                <td className="text-end">
                                                    {transaction.debit ? formatCurrency(transaction.debit) : '-'}
                                                </td>
                                                <td className="text-end">
                                                    {transaction.credit ? formatCurrency(transaction.credit) : '-'}
                                                </td>
                                                <td className={`text-end fw-bold ${getBalanceClass(transaction.balance)}`}>
                                                    {formatCurrency(transaction.balance)}
                                                </td>
                                            </tr>
                                        ))}

                                        {ledgerData.transactions?.length === 0 && (
                                            <tr>
                                                <td colSpan="7" className="text-center text-muted py-3">
                                                    No transactions found for the selected period
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

                    <div className="mt-3">
                        <div className="alert alert-info">
                            <i className="bi bi-info-circle me-2"></i>
                            <strong>Note:</strong> Positive balance indicates amount receivable (you owe),
                            negative balance indicates amount payable (they owe you).
                        </div>
                    </div>
                </>
            )}

            {!ledgerData && !loading && (
                <div className="alert alert-info">
                    <i className="bi bi-info-circle me-2"></i>
                    Select a company and click "View Ledger" to see the transaction history.
                </div>
            )}
        </div>
    );
}
