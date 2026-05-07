import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import api from '../api/axios';
import { formatIndianNumber } from '../utils/numberFormatter';
import { formatDate as formatDateUtil } from '../utils/dateFormatter';
import { generatePDF, generateExcel } from '../utils/ledgerExport';

export default function LicenseLedgerDetail() {
    const { id, companyId } = useParams();
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
    }, [id, licenseType, companyId]);

    const fetchLedgerDetail = async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams();
            if (companyId) params.append('company', companyId);
            const queryString = params.toString();
            const url = `license-ledger/${id}/ledger_detail/${queryString ? `?${queryString}` : ''}`;
            const response = await api.get(url);
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
        return formatDateUtil(dateStr) || '-';
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
    const hasPurchases = ledger.transactions.some(t => t.type === 'PURCHASE' || t.type === 'OPENING');
    const currentBalance = ledger.available_balance || 0;
    const isNegativeBalance = currentBalance < 0;
    const showPurchaseWarning = !hasPurchases || isNegativeBalance;

    const handleDownloadPDF = () => {
        const filename = `License_Ledger_${String(ledger.license_number).replace(/\//g, '-')}_${new Date().toISOString().split('T')[0]}.pdf`;
        generatePDF([ledger], filename);
    };

    const handleDownloadExcel = async () => {
        const filename = `License_Ledger_${String(ledger.license_number).replace(/\//g, '-')}_${new Date().toISOString().split('T')[0]}.xlsx`;
        await generateExcel([ledger], filename);
    };


    return (
        <div className="container-fluid" style={{ backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh', padding: '0' }}>
            {/* Tally-Style Header */}
            <div style={{
                backgroundColor: 'var(--text-dark)',
                color: 'white',
                padding: '10px 20px',
                borderBottom: '2px solid #34495e'
            }}>
                <div className="d-flex justify-content-between align-items-center">
                    <div>
                        <button
                            className="btn btn-sm btn-outline-light me-3"
                            onClick={() => navigate(-1)}
                            style={{ borderRadius: '2px' }}
                        >
                            ← Back
                        </button>
                        <span style={{ fontSize: '1.1rem', fontWeight: '500' }}>License Ledger</span>
                    </div>
                    <div>
                        <button
                            type="button"
                            className="btn btn-sm btn-danger me-2"
                            onClick={handleDownloadPDF}
                            style={{ borderRadius: '2px' }}
                        >
                            <i className="bi bi-file-pdf me-2"></i>
                            Download PDF
                        </button>
                        <button
                            type="button"
                            className="btn btn-sm btn-success me-3"
                            onClick={handleDownloadExcel}
                            style={{ borderRadius: '2px' }}
                        >
                            <i className="bi bi-file-excel me-2"></i>
                            Download Excel
                        </button>
                        <span style={{ fontSize: '0.9rem' }}>
                            {formatDate(new Date())}
                        </span>
                    </div>
                </div>
            </div>

            {/* Purchase Warning Alert */}
            {showPurchaseWarning && (
                <div style={{
                    backgroundColor: 'var(--warning-bg)',
                    border: '1px solid #ffc107',
                    borderLeft: '5px solid #ffc107',
                    padding: '15px 20px',
                    margin: '0',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '15px'
                }}>
                    <i className="bi bi-exclamation-triangle-fill" style={{ fontSize: '1.5rem', color: 'var(--warning-text)' }}></i>
                    <div>
                        <strong style={{ color: 'var(--warning-text)', display: 'block', marginBottom: '5px' }}>
                            ⚠️ Action Required
                        </strong>
                        <span style={{ color: 'var(--warning-text)' }}>
                            {!hasPurchases && isNegativeBalance &&
                                'No purchase transactions found and balance is negative. Please add purchase entries to maintain proper accounting.'}
                            {!hasPurchases && !isNegativeBalance &&
                                'No purchase transactions found. Please add purchase entries for this license.'}
                            {hasPurchases && isNegativeBalance &&
                                `Balance is negative (${formatCurrency(currentBalance, isDFIA ? 'USD' : 'INR')}). Please add purchase transactions to cover the deficit.`}
                        </span>
                    </div>
                </div>
            )}

            {/* Professional License Header */}
            <div style={{
                backgroundColor: 'white',
                border: '1px solid #dee2e6',
                borderTop: 'none',
                padding: '25px 30px',
                boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
            }}>
                <div className="row align-items-center">
                    <div className="col-md-8">
                        <h4 style={{ marginBottom: '15px', color: 'var(--text-dark)', fontWeight: '600' }}>
                            {ledger.license_number}
                            <span style={{
                                marginLeft: '15px',
                                fontSize: '0.75rem',
                                padding: '4px 12px',
                                backgroundColor: isDFIA ? 'var(--primary-color)' : 'var(--info-color)',
                                color: 'white',
                                borderRadius: '4px',
                                fontWeight: '500'
                            }}>
                                {ledger.license_type}
                            </span>
                        </h4>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '0.95rem' }}>
                            <div>
                                <span style={{ color: 'var(--bs-gray-500)', marginRight: '10px' }}>Exporter:</span>
                                <strong>{ledger.exporter || 'N/A'}</strong>
                            </div>
                            <div>
                                <span style={{ color: 'var(--bs-gray-500)', marginRight: '10px' }}>License Date:</span>
                                <strong>{formatDate(ledger.license_date)}</strong>
                            </div>
                            {isDFIA && (
                                <div>
                                    <span style={{ color: 'var(--bs-gray-500)', marginRight: '10px' }}>SION Norms:</span>
                                    <strong style={{ color: 'var(--info-color)' }}>
                                        {(() => {
                                            const allNorms = [...new Set(
                                                ledger.transactions
                                                    .filter(t => t.sion_norms)
                                                    .flatMap(t => t.sion_norms.split(', '))
                                            )];
                                            return allNorms.length > 0 ? allNorms.join(', ') : 'N/A';
                                        })()}
                                    </strong>
                                </div>
                            )}
                            <div>
                                <span style={{ color: 'var(--bs-gray-500)', marginRight: '10px' }}>Expiry Date:</span>
                                <strong>{formatDate(ledger.expiry_date)}</strong>
                            </div>
                            <div>
                                <span style={{ color: 'var(--bs-gray-500)', marginRight: '10px' }}>Total Value:</span>
                                <strong style={{ color: 'var(--primary-color)' }}>
                                    {formatCurrency(ledger.total_value, isDFIA ? 'USD' : 'INR')}
                                </strong>
                            </div>
                        </div>
                    </div>
                    <div className="col-md-4 text-end">
                        <div style={{
                            padding: '20px',
                            backgroundColor: 'var(--bs-gray-50)',
                            borderRadius: '8px',
                            border: '2px solid #e9ecef'
                        }}>
                            <div style={{ fontSize: '0.85rem', color: 'var(--bs-gray-500)', marginBottom: '8px', fontWeight: '500' }}>
                                CURRENT BALANCE
                            </div>
                            <div style={{
                                fontSize: '1.75rem',
                                fontWeight: '700',
                                color: currentBalance >= 0 ? 'var(--success-color)' : 'var(--danger-color)'
                            }}>
                                {formatCurrency(currentBalance, isDFIA ? 'USD' : 'INR')}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Company-grouped Ledger Table */}
            {(() => {
                const companiesMap = {};
                (ledger.transactions || []).forEach(txn => {
                    const key = txn.company_id != null ? txn.company_id : 'unknown';
                    if (!companiesMap[key]) {
                        companiesMap[key] = {
                            company_id: txn.company_id,
                            company_name: txn.company_name || 'N/A',
                            transactions: []
                        };
                    }
                    companiesMap[key].transactions.push(txn);
                });
                const companiesGrouped = Object.values(companiesMap);

                const TXN_SORT_ORDER = { OPENING: 0, PURCHASE: 1, SALE: 2 };

                return companiesGrouped.map((company, ci) => {
                    const rawTxns = company.transactions;

                    // Sort per-company: OPENING/PURCHASE before SALE
                    const txns = [...rawTxns].sort((a, b) =>
                        ((TXN_SORT_ORDER[a.type] ?? 1) - (TXN_SORT_ORDER[b.type] ?? 1))
                    );

                    // Compute per-company running balance (backend balance is global)
                    let companyRunning = 0;
                    const companyBalMap = new Map();
                    for (const txn of txns) {
                        if (txn.type === 'PURCHASE' || txn.type === 'OPENING') {
                            companyRunning += isDFIA ? (txn.debit_cif || 0) : (txn.debit_license_value || 0);
                        } else if (txn.type === 'SALE') {
                            companyRunning -= isDFIA ? (txn.credit_cif || 0) : (txn.credit_license_value || 0);
                        }
                        companyBalMap.set(txn, companyRunning);
                    }

                    const totalDebit = txns.reduce((s, t) => s + (t.debit_amount || 0), 0);
                    const totalCredit = txns.reduce((s, t) => s + (t.credit_amount || 0), 0);
                    const companyPL = txns.filter(t => t.type === 'SALE').reduce((s, t) => s + (t.profit_loss || 0), 0);

                    return (
                        <div key={company.company_id ?? ci} style={{
                            backgroundColor: 'white',
                            border: '1px solid #dee2e6',
                            borderRadius: '8px',
                            marginTop: ci === 0 ? '20px' : '12px',
                            marginLeft: '20px',
                            marginRight: '20px',
                            marginBottom: ci === companiesGrouped.length - 1 ? '20px' : '0',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                            overflow: 'hidden'
                        }}>
                            {/* Company Header */}
                            <div style={{
                                backgroundColor: '#1e3a5f',
                                color: 'white',
                                padding: '10px 20px',
                                fontWeight: '700',
                                fontSize: '0.95rem',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px'
                            }}>
                                <i className="bi bi-building"></i>
                                {company.company_name}
                            </div>

                            <table style={{ width: '100%', fontSize: '0.82rem', borderCollapse: 'collapse' }}>
                                <thead>
                                    <tr style={{ background: '#f0f4ff', borderBottom: '2px solid #c7d2fe' }}>
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: '#374151', textAlign: 'left' }}>Date</th>
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: '#374151', textAlign: 'left' }}>Particulars</th>
                                        {isDFIA && <th style={{ padding: '7px 10px', fontWeight: '700', color: '#374151', textAlign: 'left' }}>Items</th>}
                                        {isDFIA ? (
                                            <>
                                                <th style={{ padding: '7px 10px', fontWeight: '700', color: '#374151', textAlign: 'right' }}>CIF $ Dr</th>
                                                <th style={{ padding: '7px 10px', fontWeight: '700', color: '#374151', textAlign: 'right' }}>CIF $ Cr</th>
                                            </>
                                        ) : (
                                            <>
                                                <th style={{ padding: '7px 10px', fontWeight: '700', color: '#374151', textAlign: 'right' }}>Value Dr</th>
                                                <th style={{ padding: '7px 10px', fontWeight: '700', color: '#374151', textAlign: 'right' }}>Value Cr</th>
                                            </>
                                        )}
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: '#374151', textAlign: 'right' }}>Rate</th>
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: '#065f46', textAlign: 'right' }}>Debit (₹)</th>
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: '#991b1b', textAlign: 'right' }}>Credit (₹)</th>
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: '#374151', textAlign: 'right' }}>{isDFIA ? 'Balance ($)' : 'Balance (₹)'}</th>
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: '#374151', textAlign: 'right' }}>P/L</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {txns.map((txn, ti) => {
                                        const isPurchase = txn.type === 'PURCHASE' || txn.type === 'OPENING';
                                        const rowBg = isPurchase ? '#f0fdf4' : (txn.type === 'SALE' ? '#fef2f2' : '#ffffff');
                                        const rowBorder = isPurchase ? '1px solid #d1fae5' : (txn.type === 'SALE' ? '1px solid #fecaca' : '1px solid #f3f4f6');
                                        return (
                                            <tr key={ti} style={{ background: rowBg, borderBottom: rowBorder }}>
                                                <td style={{ padding: '5px 10px', color: '#6b7280', whiteSpace: 'nowrap' }}>{formatDate(txn.date)}</td>
                                                <td style={{ padding: '5px 10px', color: '#374151' }}>
                                                    {txn.particular}
                                                    {txn.invoice_number && <span style={{ color: '#6b7280', fontSize: '0.78rem', display: 'block' }}>({txn.invoice_number})</span>}
                                                </td>
                                                {isDFIA && <td style={{ padding: '5px 10px', color: '#374151' }}>{txn.items || '-'}</td>}
                                                {isDFIA ? (
                                                    <>
                                                        <td style={{ padding: '5px 10px', textAlign: 'right', color: '#065f46' }}>{txn.debit_cif ? formatIndianNumber(txn.debit_cif, 2) : '-'}</td>
                                                        <td style={{ padding: '5px 10px', textAlign: 'right', color: '#991b1b' }}>{txn.credit_cif ? formatIndianNumber(txn.credit_cif, 2) : '-'}</td>
                                                    </>
                                                ) : (
                                                    <>
                                                        <td style={{ padding: '5px 10px', textAlign: 'right', color: '#065f46' }}>{txn.debit_license_value ? formatIndianNumber(txn.debit_license_value, 2) : '-'}</td>
                                                        <td style={{ padding: '5px 10px', textAlign: 'right', color: '#991b1b' }}>{txn.credit_license_value ? formatIndianNumber(txn.credit_license_value, 2) : '-'}</td>
                                                    </>
                                                )}
                                                <td style={{ padding: '5px 10px', textAlign: 'right', color: '#374151' }}>{txn.rate ? formatIndianNumber(txn.rate, 2) : '-'}</td>
                                                <td style={{ padding: '5px 10px', textAlign: 'right', fontWeight: '600', color: '#065f46' }}>{txn.debit_amount ? `₹${formatIndianNumber(txn.debit_amount, 2)}` : '-'}</td>
                                                <td style={{ padding: '5px 10px', textAlign: 'right', fontWeight: '600', color: '#991b1b' }}>{txn.credit_amount ? `₹${formatIndianNumber(txn.credit_amount, 2)}` : '-'}</td>
                                                <td style={{ padding: '5px 10px', textAlign: 'right', color: (companyBalMap.get(txn) ?? 0) >= 0 ? '#065f46' : '#991b1b' }}>{formatIndianNumber(companyBalMap.get(txn) ?? 0, 2)}</td>
                                                <td style={{ padding: '5px 10px', textAlign: 'right', color: txn.profit_loss >= 0 ? '#065f46' : '#991b1b' }}>
                                                    {txn.type === 'SALE' && txn.profit_loss != null ? formatIndianNumber(Math.abs(txn.profit_loss), 2) : '-'}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                    {/* Company Total Row */}
                                    <tr style={{ background: '#1e3a5f', color: '#fff', fontWeight: '700' }}>
                                        <td colSpan={isDFIA ? 6 : 5} style={{ padding: '7px 10px', textAlign: 'right', fontSize: '0.8rem' }}>
                                            Total — {company.company_name}
                                        </td>
                                        <td style={{ padding: '7px 10px', textAlign: 'right', color: '#6ee7b7' }}>₹{formatIndianNumber(totalDebit, 2)}</td>
                                        <td style={{ padding: '7px 10px', textAlign: 'right', color: '#fca5a5' }}>₹{formatIndianNumber(totalCredit, 2)}</td>
                                        <td style={{ padding: '7px 10px', textAlign: 'right', color: '#93c5fd' }}>{formatIndianNumber(companyRunning, 2)}</td>
                                        <td style={{ padding: '7px 10px', textAlign: 'right', color: companyPL >= 0 ? '#6ee7b7' : '#fca5a5' }}>
                                            {companyPL !== 0 ? `${companyPL >= 0 ? '+' : ''}₹${formatIndianNumber(Math.abs(companyPL), 2)}` : '-'}
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    );
                });
            })()}
        </div>
    );
}
