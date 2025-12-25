import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import api from '../api/axios';
import { formatIndianNumber } from '../utils/numberFormatter';

export default function LicenseLedgerDetail() {
    const { id } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const [ledger, setLedger] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Get license_type from query params or location state
    const queryParams = new URLSearchParams(location.search);
    const licenseType = queryParams.get('license_type') || location.state?.license_type || 'DFIA';

    useEffect(() => {
        fetchLedgerDetail();
    }, [id, licenseType]);

    const fetchLedgerDetail = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.get(`/license-ledger/${id}/ledger_detail/?license_type=${licenseType}`);
            setLedger(response.data);
        } catch (err) {
            console.error('Error fetching ledger detail:', err);
            setError(err.response?.data?.error || 'Failed to load ledger details');
        } finally {
            setLoading(false);
        }
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return '-';
        return new Date(dateStr).toLocaleDateString('en-GB');
    };

    const formatCurrency = (value, currency = 'INR') => {
        if (!value && value !== 0) return '-';
        const symbol = currency === 'USD' ? '$' : '₹';
        return `${symbol}${formatIndianNumber(value, 2)}`;
    };

    if (loading) {
        return (
            <div className="container-fluid py-4">
                <div className="text-center py-5">
                    <div className="spinner-border text-primary" role="status">
                        <span className="visually-hidden">Loading...</span>
                    </div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="container-fluid py-4">
                <div className="alert alert-danger" role="alert">
                    <i className="bi bi-exclamation-triangle me-2"></i>
                    {error}
                </div>
                <button className="btn btn-primary" onClick={() => navigate(-1)}>
                    <i className="bi bi-arrow-left me-2"></i>
                    Go Back
                </button>
            </div>
        );
    }

    if (!ledger) return null;

    const isDFIA = ledger.license_type === 'DFIA';

    return (
        <div className="container-fluid py-4">
            {/* Header */}
            <div className="row mb-4">
                <div className="col">
                    <button className="btn btn-outline-secondary mb-3" onClick={() => navigate(-1)}>
                        <i className="bi bi-arrow-left me-2"></i>
                        Back to Ledger
                    </button>
                    <h2>License Ledger - Detailed View</h2>
                </div>
            </div>

            {/* License Info Card */}
            <div className="card mb-4">
                <div className="card-header bg-primary text-white">
                    <h5 className="mb-0">
                        <i className="bi bi-file-earmark-text me-2"></i>
                        License Information
                    </h5>
                </div>
                <div className="card-body">
                    <div className="row">
                        <div className="col-md-3">
                            <p className="text-muted small mb-1">License Type</p>
                            <p className="fw-bold">
                                <span className={`badge ${isDFIA ? 'bg-primary' : 'bg-info'}`}>
                                    {ledger.license_type}
                                </span>
                            </p>
                        </div>
                        <div className="col-md-3">
                            <p className="text-muted small mb-1">License Number</p>
                            <p className="fw-bold">{ledger.license_number}</p>
                        </div>
                        <div className="col-md-3">
                            <p className="text-muted small mb-1">License Date</p>
                            <p className="fw-bold">{formatDate(ledger.license_date)}</p>
                        </div>
                        <div className="col-md-3">
                            <p className="text-muted small mb-1">Expiry Date</p>
                            <p className="fw-bold">{formatDate(ledger.expiry_date)}</p>
                        </div>
                    </div>
                    <hr />
                    <div className="row">
                        <div className="col-md-4">
                            <p className="text-muted small mb-1">Exporter</p>
                            <p className="fw-bold">{ledger.exporter || 'N/A'}</p>
                        </div>
                        <div className="col-md-4">
                            <p className="text-muted small mb-1">Total Value</p>
                            <p className="fw-bold text-primary">
                                {formatCurrency(ledger.total_value, isDFIA ? 'USD' : 'INR')}
                            </p>
                        </div>
                        <div className="col-md-4">
                            <p className="text-muted small mb-1">Available Balance</p>
                            <p className="fw-bold text-success">
                                {formatCurrency(ledger.available_balance, isDFIA ? 'USD' : 'INR')}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Transactions Table */}
            <div className="card">
                <div className="card-header bg-light">
                    <h5 className="mb-0">
                        <i className="bi bi-list-ul me-2"></i>
                        Transaction Ledger
                    </h5>
                </div>
                <div className="card-body p-0">
                    <div className="table-responsive">
                        <table className="table table-hover table-striped mb-0">
                            <thead className="table-dark sticky-top">
                                <tr>
                                    <th rowSpan="2">Date</th>
                                    <th rowSpan="2">Particular</th>
                                    {isDFIA && <th rowSpan="2">Item Name</th>}
                                    {isDFIA && <th colSpan="2" className="text-center border-end">CIF $</th>}
                                    {!isDFIA && <th colSpan="2" className="text-center border-end">License Value</th>}
                                    <th rowSpan="2" className="text-end">Rate</th>
                                    <th colSpan="2" className="text-center border-end">Amount (₹)</th>
                                    <th rowSpan="2" className="text-end">Balance</th>
                                    <th rowSpan="2" className="text-end">Profit/Loss</th>
                                </tr>
                                <tr>
                                    <th className="text-end">Debit</th>
                                    <th className="text-end border-end">Credit</th>
                                    <th className="text-end">Debit</th>
                                    <th className="text-end border-end">Credit</th>
                                </tr>
                            </thead>
                            <tbody>
                                {ledger.transactions.map((txn, index) => {
                                    const profitLoss = txn.profit_loss || 0;
                                    const isProfitable = profitLoss > 0;
                                    const isLoss = profitLoss < 0;

                                    return (
                                        <tr key={index} className={
                                            txn.type === 'OPENING' ? 'table-info fw-bold' :
                                            txn.type === 'PURCHASE' ? 'table-warning' :
                                            'table-success'
                                        }>
                                            <td>{formatDate(txn.date)}</td>
                                            <td>
                                                <div>{txn.particular}</div>
                                                {txn.invoice_number && (
                                                    <small className="text-muted">
                                                        Invoice: {txn.invoice_number}
                                                    </small>
                                                )}
                                            </td>
                                            {isDFIA && <td><small>{txn.items || '-'}</small></td>}
                                            {isDFIA && (
                                                <>
                                                    <td className="text-end">
                                                        {txn.debit_cif ? formatIndianNumber(txn.debit_cif, 2) : '-'}
                                                    </td>
                                                    <td className="text-end border-end">
                                                        {txn.credit_cif ? formatIndianNumber(txn.credit_cif, 2) : '-'}
                                                    </td>
                                                </>
                                            )}
                                            {!isDFIA && (
                                                <>
                                                    <td className="text-end">
                                                        {txn.debit_license_value ? formatIndianNumber(txn.debit_license_value, 2) : '-'}
                                                    </td>
                                                    <td className="text-end border-end">
                                                        {txn.credit_license_value ? formatIndianNumber(txn.credit_license_value, 2) : '-'}
                                                    </td>
                                                </>
                                            )}
                                            <td className="text-end">
                                                {txn.rate ? formatIndianNumber(txn.rate, 2) : '-'}
                                            </td>
                                            <td className="text-end">
                                                {txn.debit_amount ? formatCurrency(txn.debit_amount, 'INR') : '-'}
                                            </td>
                                            <td className="text-end border-end">
                                                {txn.credit_amount ? formatCurrency(txn.credit_amount, 'INR') : '-'}
                                            </td>
                                            <td className="text-end fw-bold">
                                                {formatIndianNumber(txn.balance, 2)}
                                            </td>
                                            <td className={`text-end fw-bold ${
                                                isProfitable ? 'text-success' :
                                                isLoss ? 'text-danger' : ''
                                            }`}>
                                                {txn.type === 'SALE' && profitLoss !== 0 ? (
                                                    <>
                                                        {isProfitable && <i className="bi bi-arrow-up-circle me-1"></i>}
                                                        {isLoss && <i className="bi bi-arrow-down-circle me-1"></i>}
                                                        {formatCurrency(Math.abs(profitLoss), 'INR')}
                                                    </>
                                                ) : '-'}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Summary */}
            {ledger.transactions.length > 0 && (
                <div className="card mt-4">
                    <div className="card-body">
                        <div className="row text-center">
                            <div className="col-md-3">
                                <p className="text-muted small mb-1">Total Transactions</p>
                                <h4>{ledger.transactions.length - 1}</h4>
                                <small className="text-muted">(Excluding Opening)</small>
                            </div>
                            <div className="col-md-3">
                                <p className="text-muted small mb-1">Purchases</p>
                                <h4 className="text-warning">
                                    {ledger.transactions.filter(t => t.type === 'PURCHASE').length}
                                </h4>
                            </div>
                            <div className="col-md-3">
                                <p className="text-muted small mb-1">Sales</p>
                                <h4 className="text-success">
                                    {ledger.transactions.filter(t => t.type === 'SALE').length}
                                </h4>
                            </div>
                            <div className="col-md-3">
                                <p className="text-muted small mb-1">Total Profit/Loss</p>
                                <h4 className={
                                    ledger.transactions.reduce((sum, t) => sum + (t.profit_loss || 0), 0) >= 0
                                        ? 'text-success' : 'text-danger'
                                }>
                                    {formatCurrency(
                                        ledger.transactions.reduce((sum, t) => sum + (t.profit_loss || 0), 0),
                                        'INR'
                                    )}
                                </h4>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
