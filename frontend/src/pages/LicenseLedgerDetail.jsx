import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import api from '../api/axios';
import { formatIndianNumber } from '../utils/numberFormatter';
import { formatDate as formatDateUtil } from '../utils/dateFormatter';
import { generatePDF, generateExcel } from '../utils/ledgerExport';
import { Button } from "@/components/ui/button";
import { ArrowLeft, FileText, FileSpreadsheet, Loader2, TriangleAlert } from "lucide-react";

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

        fetchLedgerDetail();
    }, [id, licenseType, companyId]);

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
                <div className="flex flex-col items-center gap-2 py-12 text-center">
                    <Loader2 className="size-8 animate-spin text-primary" />
                    <span className="text-sm text-muted-foreground">Loading…</span>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="container-fluid py-4">
                <div className="mb-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive" role="alert">
                    <TriangleAlert className="size-4 shrink-0" />
                    {error}
                </div>
                <Button onClick={() => navigate(-1)}>
                    <ArrowLeft className="size-4" />Go Back
                </Button>
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
        <div className="container-fluid" style={{ backgroundColor: 'var(--tb-sunken)', minHeight: '100vh', padding: '0' }}>
            {/* Tally-Style Header */}
            <div style={{
                backgroundColor: 'var(--tb-text)',
                color: '#fff',
                padding: '10px 20px',
                borderBottom: '2px solid var(--tb-border-strong)'
            }}>
                <div className="d-flex justify-content-between align-items-center">
                    <div className="flex items-center gap-3">
                        <Button variant="secondary" size="sm" onClick={() => navigate(-1)}>
                            <ArrowLeft className="size-4" />Back
                        </Button>
                        <span style={{ fontSize: '1.1rem', fontWeight: '500' }}>License Ledger</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button variant="destructive" size="sm" onClick={handleDownloadPDF}>
                            <FileText className="size-4" />Download PDF
                        </Button>
                        <Button size="sm" onClick={handleDownloadExcel} style={{ background: 'var(--tb-success)', color: '#fff' }}>
                            <FileSpreadsheet className="size-4" />Download Excel
                        </Button>
                        <span className="ml-1" style={{ fontSize: 14.5 }}>
                            {formatDate(new Date())}
                        </span>
                    </div>
                </div>
            </div>

            {/* Purchase Warning Alert */}
            {showPurchaseWarning && (
                <div style={{
                    backgroundColor: 'var(--warning-bg)',
                    border: '1px solid var(--tb-warning)',
                    borderLeft: '5px solid var(--tb-warning)',
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
                backgroundColor: 'var(--tb-card-bg)',
                border: '1px solid var(--tb-border)',
                borderTop: 'none',
                padding: '25px 30px',
                boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
            }}>
                <div className="row align-items-center">
                    <div className="col-md-8">
                        <h4 style={{ marginBottom: '15px', color: 'var(--tb-text)', fontWeight: '600' }}>
                            {ledger.license_number}
                            <span style={{
                                marginLeft: '15px',
                                fontSize: 12,
                                padding: '4px 12px',
                                backgroundColor: isDFIA ? 'var(--primary-color)' : 'var(--info-color)',
                                color: '#fff',
                                borderRadius: 'var(--tb-r-sm)',
                                fontWeight: '500'
                            }}>
                                {ledger.license_type}
                            </span>
                        </h4>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: 15 }}>
                            <div>
                                <span style={{ color: 'var(--tb-text-secondary)', marginRight: '10px' }}>Exporter:</span>
                                <strong>{ledger.exporter || 'N/A'}</strong>
                            </div>
                            <div>
                                <span style={{ color: 'var(--tb-text-secondary)', marginRight: '10px' }}>License Date:</span>
                                <strong>{formatDate(ledger.license_date)}</strong>
                            </div>
                            {isDFIA && (
                                <div>
                                    <span style={{ color: 'var(--tb-text-secondary)', marginRight: '10px' }}>SION Norms:</span>
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
                                <span style={{ color: 'var(--tb-text-secondary)', marginRight: '10px' }}>Expiry Date:</span>
                                <strong>{formatDate(ledger.expiry_date)}</strong>
                            </div>
                            <div>
                                <span style={{ color: 'var(--tb-text-secondary)', marginRight: '10px' }}>Total Value:</span>
                                <strong style={{ color: 'var(--primary-color)' }}>
                                    {formatCurrency(ledger.total_value, isDFIA ? 'USD' : 'INR')}
                                </strong>
                            </div>
                        </div>
                    </div>
                    <div className="col-md-4 text-end">
                        <div style={{
                            padding: '20px',
                            backgroundColor: 'var(--tb-sunken)',
                            borderRadius: 'var(--tb-r-md)',
                            border: '2px solid var(--tb-border)'
                        }}>
                            <div style={{ fontSize: 13.5, color: 'var(--tb-text-secondary)', marginBottom: '8px', fontWeight: '500' }}>
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
                            backgroundColor: 'var(--tb-card-bg)',
                            border: '1px solid var(--tb-border)',
                            borderRadius: 'var(--tb-r-md)',
                            marginTop: ci === 0 ? '20px' : '12px',
                            marginLeft: '20px',
                            marginRight: '20px',
                            marginBottom: ci === companiesGrouped.length - 1 ? '20px' : '0',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                            overflow: 'hidden'
                        }}>
                            {/* Company Header */}
                            <div style={{
                                backgroundColor: 'var(--tb-brand-active)',
                                color: '#fff',
                                padding: '10px 20px',
                                fontWeight: '700',
                                fontSize: 15,
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px'
                            }}>
                                <i className="bi bi-building"></i>
                                {company.company_name}
                            </div>

                            <table style={{ width: '100%', fontSize: '0.82rem', borderCollapse: 'collapse' }}>
                                <thead>
                                    <tr style={{ background: 'var(--tb-brand-50)', borderBottom: '2px solid var(--tb-brand-100)' }}>
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: 'var(--tb-text)', textAlign: 'left' }}>Date</th>
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: 'var(--tb-text)', textAlign: 'left' }}>Particulars</th>
                                        {isDFIA && <th style={{ padding: '7px 10px', fontWeight: '700', color: 'var(--tb-text)', textAlign: 'left' }}>Items</th>}
                                        {isDFIA ? (
                                            <>
                                                <th style={{ padding: '7px 10px', fontWeight: '700', color: 'var(--tb-text)', textAlign: 'right' }}>CIF $ Dr</th>
                                                <th style={{ padding: '7px 10px', fontWeight: '700', color: 'var(--tb-text)', textAlign: 'right' }}>CIF $ Cr</th>
                                            </>
                                        ) : (
                                            <>
                                                <th style={{ padding: '7px 10px', fontWeight: '700', color: 'var(--tb-text)', textAlign: 'right' }}>Value Dr</th>
                                                <th style={{ padding: '7px 10px', fontWeight: '700', color: 'var(--tb-text)', textAlign: 'right' }}>Value Cr</th>
                                            </>
                                        )}
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: 'var(--tb-text)', textAlign: 'right' }}>Rate</th>
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: 'var(--tb-success-text)', textAlign: 'right' }}>Debit (₹)</th>
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: 'var(--tb-danger-text)', textAlign: 'right' }}>Credit (₹)</th>
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: 'var(--tb-text)', textAlign: 'right' }}>{isDFIA ? 'Balance ($)' : 'Balance (₹)'}</th>
                                        <th style={{ padding: '7px 10px', fontWeight: '700', color: 'var(--tb-text)', textAlign: 'right' }}>P/L</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {txns.map((txn, ti) => {
                                        const isPurchase = txn.type === 'PURCHASE' || txn.type === 'OPENING';
                                        const rowBg = isPurchase ? 'var(--tb-success-soft)' : (txn.type === 'SALE' ? 'var(--tb-danger-soft)' : 'var(--tb-card-bg)');
                                        const rowBorder = isPurchase ? '1px solid var(--tb-success-border)' : (txn.type === 'SALE' ? '1px solid var(--tb-danger-border)' : '1px solid var(--tb-border-soft)');
                                        return (
                                            <tr key={ti} style={{ background: rowBg, borderBottom: rowBorder }}>
                                                <td style={{ padding: '5px 10px', color: 'var(--tb-text-secondary)', whiteSpace: 'nowrap' }}>{formatDate(txn.date)}</td>
                                                <td style={{ padding: '5px 10px', color: 'var(--tb-text)' }}>
                                                    {txn.particular}
                                                    {txn.invoice_number && <span style={{ color: 'var(--tb-text-secondary)', fontSize: 12, display: 'block' }}>({txn.invoice_number})</span>}
                                                </td>
                                                {isDFIA && <td style={{ padding: '5px 10px', color: 'var(--tb-text)' }}>{txn.items || '-'}</td>}
                                                {isDFIA ? (
                                                    <>
                                                        <td style={{ padding: '5px 10px', textAlign: 'right', color: 'var(--tb-success-text)' }}>{txn.debit_cif ? formatIndianNumber(txn.debit_cif, 2) : '-'}</td>
                                                        <td style={{ padding: '5px 10px', textAlign: 'right', color: 'var(--tb-danger-text)' }}>{txn.credit_cif ? formatIndianNumber(txn.credit_cif, 2) : '-'}</td>
                                                    </>
                                                ) : (
                                                    <>
                                                        <td style={{ padding: '5px 10px', textAlign: 'right', color: 'var(--tb-success-text)' }}>{txn.debit_license_value ? formatIndianNumber(txn.debit_license_value, 2) : '-'}</td>
                                                        <td style={{ padding: '5px 10px', textAlign: 'right', color: 'var(--tb-danger-text)' }}>{txn.credit_license_value ? formatIndianNumber(txn.credit_license_value, 2) : '-'}</td>
                                                    </>
                                                )}
                                                <td style={{ padding: '5px 10px', textAlign: 'right', color: 'var(--tb-text)' }}>{txn.rate ? formatIndianNumber(txn.rate, 2) : '-'}</td>
                                                <td style={{ padding: '5px 10px', textAlign: 'right', fontWeight: '600', color: 'var(--tb-success-text)' }}>{txn.debit_amount ? `₹${formatIndianNumber(txn.debit_amount, 2)}` : '-'}</td>
                                                <td style={{ padding: '5px 10px', textAlign: 'right', fontWeight: '600', color: 'var(--tb-danger-text)' }}>{txn.credit_amount ? `₹${formatIndianNumber(txn.credit_amount, 2)}` : '-'}</td>
                                                <td style={{ padding: '5px 10px', textAlign: 'right', color: (companyBalMap.get(txn) ?? 0) >= 0 ? 'var(--tb-success-text)' : 'var(--tb-danger-text)' }}>{formatIndianNumber(companyBalMap.get(txn) ?? 0, 2)}</td>
                                                <td style={{ padding: '5px 10px', textAlign: 'right', color: txn.profit_loss >= 0 ? 'var(--tb-success-text)' : 'var(--tb-danger-text)' }}>
                                                    {txn.type === 'SALE' && txn.profit_loss != null ? formatIndianNumber(Math.abs(txn.profit_loss), 2) : '-'}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                    {/* Company Total Row */}
                                    <tr style={{ background: 'var(--tb-brand-active)', color: '#fff', fontWeight: '700' }}>
                                        <td colSpan={isDFIA ? 6 : 5} style={{ padding: '7px 10px', textAlign: 'right', fontSize: 12.5 }}>
                                            Total — {company.company_name}
                                        </td>
                                        <td style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--tb-success-soft)' }}>₹{formatIndianNumber(totalDebit, 2)}</td>
                                        <td style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--tb-danger-border)' }}>₹{formatIndianNumber(totalCredit, 2)}</td>
                                        <td style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--tb-brand-200)' }}>{formatIndianNumber(companyRunning, 2)}</td>
                                        <td style={{ padding: '7px 10px', textAlign: 'right', color: companyPL >= 0 ? 'var(--tb-success-soft)' : 'var(--tb-danger-border)' }}>
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
