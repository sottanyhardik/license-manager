import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import api from '../api/axios';
import { formatIndianNumber } from '../utils/numberFormatter';
import { generatePDF, generateExcel } from '../utils/ledgerExport';
import AsyncSelectField from '../components/AsyncSelectField';

function LicenseWiseLedger({ data, navigate }) {
    const { licenses } = data;
    const fmt = (v) => `₹${formatIndianNumber(v, 2)}`;
    const plColor = (v) => v >= 0 ? '#10b981' : '#ef4444';

    return (
        <div style={{ padding: '8px' }}>
            {licenses.map((lic) => (
                <div key={lic.license_id} style={{ marginBottom: '24px', border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden' }}>
                    {/* License Header */}
                    <div style={{ background: '#1e3a5f', color: '#fff', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: '24px' }}>
                        <span style={{ fontWeight: '700', fontSize: '0.95rem' }}>
                            <i className="bi bi-file-earmark-text me-2"></i>{lic.license_number}
                        </span>
                        <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                            <i className="bi bi-calendar3 me-1"></i>{lic.license_date}
                        </span>
                        <span style={{ background: lic.license_type === 'DFIA' ? '#3b82f6' : '#8b5cf6', color: '#fff', borderRadius: '4px', padding: '2px 8px', fontSize: '0.72rem', fontWeight: '700' }}>
                            {lic.license_type}
                        </span>
                        {navigate && (
                            <button
                                onClick={() => navigate(`/license-ledger/${lic.license_id}`)}
                                style={{ marginLeft: 'auto', background: 'rgba(255,255,255,0.15)', border: '1px solid rgba(255,255,255,0.3)', color: '#fff', borderRadius: '4px', padding: '3px 10px', fontSize: '0.75rem', fontWeight: '600', cursor: 'pointer' }}
                            >
                                <i className="bi bi-journal-text me-1"></i>View Ledger
                            </button>
                        )}
                    </div>

                    {/* Companies table */}
                    <table style={{ width: '100%', fontSize: '0.8rem', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
                                <th style={{ padding: '7px 12px', fontWeight: '700', color: '#374151', width: '30%' }}>Company</th>
                                <th style={{ padding: '7px 12px', fontWeight: '700', color: '#374151', width: '15%' }}>Type</th>
                                <th style={{ padding: '7px 12px', fontWeight: '700', color: '#374151', width: '15%' }}>Date</th>
                                <th style={{ padding: '7px 12px', fontWeight: '700', color: '#065f46', textAlign: 'right', width: '20%' }}>Purchase (₹)</th>
                                <th style={{ padding: '7px 12px', fontWeight: '700', color: '#991b1b', textAlign: 'right', width: '20%' }}>Sale (₹)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {lic.companies.map((company, ci) => {
                                return (
                                    <React.Fragment key={company.company_id}>
                                        {/* Company name row */}
                                        <tr style={{ background: ci % 2 === 0 ? '#f0f4ff' : '#f5f0ff', borderTop: ci > 0 ? '2px solid #e2e8f0' : 'none' }}>
                                            <td colSpan="5" style={{ padding: '5px 12px', fontWeight: '700', color: '#1e3a5f', fontSize: '0.82rem' }}>
                                                <i className="bi bi-building me-2"></i>{company.company_name}
                                            </td>
                                        </tr>
                                        {/* Purchase rows */}
                                        {company.purchases.map((row) => (
                                            <tr key={`p-${row.trade_id}`} style={{ background: '#f0fdf4', borderBottom: '1px solid #d1fae5' }}>
                                                <td style={{ padding: '4px 12px 4px 24px', color: '#374151' }}>
                                                    <i className="bi bi-arrow-down-circle text-success me-1"></i>Purchase
                                                </td>
                                                <td style={{ padding: '4px 12px', color: '#6b7280' }}>{lic.license_type}</td>
                                                <td style={{ padding: '4px 12px', color: '#6b7280' }}>{row.invoice_date}</td>
                                                <td style={{ padding: '4px 12px', textAlign: 'right', fontWeight: '600', color: '#065f46' }}>{fmt(row.amount)}</td>
                                                <td style={{ padding: '4px 12px' }}></td>
                                            </tr>
                                        ))}
                                        {/* Sale rows */}
                                        {company.sales.map((row) => (
                                            <tr key={`s-${row.trade_id}`} style={{ background: '#fef2f2', borderBottom: '1px solid #fecaca' }}>
                                                <td style={{ padding: '4px 12px 4px 24px', color: '#374151' }}>
                                                    <i className="bi bi-arrow-up-circle text-danger me-1"></i>Sale
                                                </td>
                                                <td style={{ padding: '4px 12px', color: '#6b7280' }}>{lic.license_type}</td>
                                                <td style={{ padding: '4px 12px', color: '#6b7280' }}>{row.invoice_date}</td>
                                                <td style={{ padding: '4px 12px' }}></td>
                                                <td style={{ padding: '4px 12px', textAlign: 'right', fontWeight: '600', color: '#991b1b' }}>{fmt(row.amount)}</td>
                                            </tr>
                                        ))}
                                        {/* Company total row */}
                                        <tr style={{ background: '#1e3a5f', color: '#fff', fontWeight: '700' }}>
                                            <td colSpan="3" style={{ padding: '5px 12px', textAlign: 'right', fontSize: '0.78rem' }}>
                                                Total — {company.company_name}
                                            </td>
                                            <td style={{ padding: '5px 12px', textAlign: 'right', color: '#6ee7b7' }}>{fmt(company.purchase_total)}</td>
                                            <td style={{ padding: '5px 12px', textAlign: 'right', color: '#fca5a5' }}>
                                                {fmt(company.sale_total)}
                                                <span style={{ marginLeft: '8px', color: plColor(company.profit_loss), fontSize: '0.72rem' }}>
                                                    P/L: {company.profit_loss >= 0 ? '+' : ''}{fmt(company.profit_loss)}
                                                </span>
                                            </td>
                                        </tr>
                                    </React.Fragment>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            ))}
            {licenses.length === 0 && (
                <div className="text-center py-5">
                    <i className="bi bi-inbox" style={{ fontSize: '2.5rem', color: '#cbd5e0' }}></i>
                    <p className="mt-3 text-muted mb-0">No trades found</p>
                </div>
            )}
        </div>
    );
}


export default function LicenseLedger() {
    const navigate = useNavigate();
    const [, setLicenses] = useState([]);
    const [summary, setSummary] = useState(null);
    const [, setLoading] = useState(true);
    const [companyWiseData, setCompanyWiseData] = useState(null);
    const [companyWiseLoading, setCompanyWiseLoading] = useState(false);

    // Get current financial year dates (April 1 to March 31)
    const getCurrentFinancialYear = () => {
        const today = new Date();
        const currentYear = today.getFullYear();
        const currentMonth = today.getMonth(); // 0-11

        // If current month is Jan-Mar (0-2), FY started last year
        // If current month is Apr-Dec (3-11), FY started this year
        const fyStartYear = currentMonth <= 2 ? currentYear - 1 : currentYear;

        const fyStart = `${fyStartYear}-04-01`;
        const fyEnd = `${fyStartYear + 1}-03-31`;

        return { fyStart, fyEnd };
    };

    const getPreviousFinancialYear = () => {
        const today = new Date();
        const currentYear = today.getFullYear();
        const currentMonth = today.getMonth();

        const fyStartYear = currentMonth <= 2 ? currentYear - 2 : currentYear - 1;

        const fyStart = `${fyStartYear}-04-01`;
        const fyEnd = `${fyStartYear + 1}-03-31`;

        return { fyStart, fyEnd };
    };

    const { fyStart: currentFYStart, fyEnd: currentFYEnd } = getCurrentFinancialYear();

    const [filters, setFilters] = useState({
        license_type: 'ALL',
        min_balance: '',
        search: '',
        company: null,
        active_only: true,
        ordering: '-license_date',
        purchase_date_from: currentFYStart,  // Default to current FY start
        purchase_date_to: currentFYEnd       // Default to current FY end
    });

    const licenseTypeOptions = [
        { value: 'ALL', label: 'All Licenses', icon: 'bi-list-ul' },
        { value: 'DFIA', label: 'DFIA Only', icon: 'bi-globe' },
        { value: 'INCENTIVE', label: 'All Incentive', icon: 'bi-trophy' },
        { value: 'RODTEP', label: 'RODTEP', icon: 'bi-award' },
        { value: 'ROSTL', label: 'ROSTL', icon: 'bi-badge-tm' },
        { value: 'MEIS', label: 'MEIS', icon: 'bi-star' },
    ];

    // Centralized function to build filter params
    const buildFilterParams = useCallback((additionalFilters = {}) => {
        const params = new URLSearchParams();

        const currentFilters = { ...filters, ...additionalFilters };

        if (currentFilters.license_type) params.append('license_type', currentFilters.license_type);
        if (currentFilters.min_balance) params.append('min_balance', currentFilters.min_balance);
        if (currentFilters.search) params.append('search', currentFilters.search);
        if (currentFilters.company) params.append('company', currentFilters.company.value || currentFilters.company);
        if (currentFilters.ordering) params.append('ordering', currentFilters.ordering);
        if (currentFilters.purchase_date_from) params.append('purchase_date_from', currentFilters.purchase_date_from);
        if (currentFilters.purchase_date_to) params.append('purchase_date_to', currentFilters.purchase_date_to);
        params.append('active_only', currentFilters.active_only);

        // Include no_purchases parameter if provided
        if (currentFilters.no_purchases) params.append('no_purchases', currentFilters.no_purchases);

        return params;
    }, [filters]);

    useEffect(() => {
        // Only fetch data if company is selected
        if (filters.company) {
            fetchLedgerData();
            fetchSummary();
        } else {
            setLicenses([]);
            setSummary(null);
            setLoading(false);
            fetchCompanyWise();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        filters.license_type,
        filters.min_balance,
        filters.search,
        filters.company,
        filters.active_only,
        filters.ordering,
        filters.purchase_date_from,
        filters.purchase_date_to
    ]);

    const fetchLedgerData = async () => {
        // Don't fetch if no company selected
        if (!filters.company) {
            setLicenses([]);
            setLoading(false);
            return;
        }

        setLoading(true);
        try {
            const params = buildFilterParams();
            const response = await api.get(`license-ledger/?${params.toString()}`);

            // Handle multiple response formats
            const data = response.data;
            if (Array.isArray(data)) {
                // Direct array
                setLicenses(data);
            } else if (data && Array.isArray(data.results)) {
                // DRF paginated response: {count, next, previous, results}
                setLicenses(data.results);
            } else if (data && Array.isArray(data.licenses)) {
                // Custom format: {licenses}
                setLicenses(data.licenses);
            } else {
                setLicenses([]);
            }
        } catch (error) {
            toast.error(error?.response?.data?.error || 'Failed to load ledger data.');
            setLicenses([]);
        } finally {
            setLoading(false);
        }
    };

    const fetchSummary = async () => {
        // Don't fetch if no company selected
        if (!filters.company) {
            setSummary(null);
            return;
        }

        try {
            const params = buildFilterParams();
            const response = await api.get(`license-ledger/summary/?${params.toString()}`);
            setSummary(response.data);
        } catch (error) {
            toast.error('Failed to load summary data.');
        }
    };

    const fetchCompanyWise = async () => {
        setCompanyWiseLoading(true);
        try {
            const params = buildFilterParams();
            params.delete('company'); // company-wise view has no company selected
            const response = await api.get(`license-ledger/license-wise/?${params.toString()}`);
            setCompanyWiseData(response.data);
        } catch (error) {
            toast.error('Failed to load company-wise ledger.');
            setCompanyWiseData(null);
        } finally {
            setCompanyWiseLoading(false);
        }
    };

    const handleFilterChange = (field, value) => {
        setFilters(prev => ({ ...prev, [field]: value }));
    };

    const setCurrentFinancialYear = () => {
        const { fyStart, fyEnd } = getCurrentFinancialYear();
        setFilters(prev => ({
            ...prev,
            purchase_date_from: fyStart,
            purchase_date_to: fyEnd
        }));
    };

    const setPreviousFinancialYear = () => {
        const { fyStart, fyEnd } = getPreviousFinancialYear();
        setFilters(prev => ({
            ...prev,
            purchase_date_from: fyStart,
            purchase_date_to: fyEnd
        }));
    };

    const clearDateFilter = () => {
        setFilters(prev => ({
            ...prev,
            purchase_date_from: '',
            purchase_date_to: ''
        }));
    };

    const [bulkExporting, setBulkExporting] = useState(false);

    const fetchFullLedgerDetails = async () => {
        const licenses = companyWiseData?.licenses || [];
        if (!licenses.length) return [];
        const results = [];
        for (const lic of licenses) {
            try {
                const { data } = await api.get(`license-ledger/${lic.license_id}/ledger_detail/`);
                results.push(data);
            } catch (e) { /* skip failed */ }
        }
        return results;
    };

    const handleBulkExportPDF = async () => {
        if (!companyWiseData?.licenses?.length) { toast.error('No data to export'); return; }
        setBulkExporting(true);
        try {
            toast.info('Fetching ledger details…', { autoClose: false, toastId: 'bulk-pdf' });
            const allLedgers = await fetchFullLedgerDetails();
            toast.dismiss('bulk-pdf');
            if (!allLedgers.length) { toast.error('No ledger data available'); return; }
            generatePDF(allLedgers, `License_Ledger_Bulk_${new Date().toISOString().split('T')[0]}.pdf`);
            toast.success(`Exported ${allLedgers.length} license(s) to PDF`);
        } catch (e) {
            toast.dismiss('bulk-pdf');
            toast.error('Failed to generate PDF');
        } finally {
            setBulkExporting(false);
        }
    };

    const handleBulkExportExcel = async () => {
        if (!companyWiseData?.licenses?.length) { toast.error('No data to export'); return; }
        setBulkExporting(true);
        try {
            toast.info('Fetching ledger details…', { autoClose: false, toastId: 'bulk-xlsx' });
            const allLedgers = await fetchFullLedgerDetails();
            toast.dismiss('bulk-xlsx');
            if (!allLedgers.length) { toast.error('No ledger data available'); return; }
            await generateExcel(allLedgers, `License_Ledger_Bulk_${new Date().toISOString().split('T')[0]}.xlsx`);
            toast.success(`Exported ${allLedgers.length} license(s) to Excel`);
        } catch (e) {
            toast.dismiss('bulk-xlsx');
            toast.error('Failed to generate Excel');
        } finally {
            setBulkExporting(false);
        }
    };

    return (
        <div className="container-fluid" style={{ backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh', padding: '20px 24px' }}>
            {/* Header */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h4 className="mb-0 fw-bold" style={{ color: 'var(--text-dark)' }}>
                        <i className="bi bi-journal-text me-2" style={{ color: '#4F46E5' }}></i>
                        License Ledger
                    </h4>
                    <small className="text-muted">Track available balance for DFIA and Incentive licenses</small>
                </div>
                <div className="d-flex gap-2">
                    {companyWiseData?.licenses?.length > 0 && (
                        <>
                            <button
                                type="button"
                                className="btn btn-sm btn-outline-secondary"
                                onClick={handleBulkExportPDF}
                                disabled={bulkExporting}
                            >
                                {bulkExporting ? <span className="spinner-border spinner-border-sm me-1" /> : <i className="bi bi-file-earmark-pdf me-1"></i>}
                                Export PDF
                            </button>
                            <button
                                type="button"
                                className="btn btn-sm btn-outline-secondary"
                                onClick={handleBulkExportExcel}
                                disabled={bulkExporting}
                            >
                                {bulkExporting ? <span className="spinner-border spinner-border-sm me-1" /> : <i className="bi bi-file-earmark-excel me-1"></i>}
                                Export Excel
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Summary Cards */}
            {summary && (
                <div className="row g-3 mb-4">
                    <div className="col-lg-6">
                        <div className="card border-0 shadow-sm" style={{ borderLeft: '3px solid #4F46E5' }}>
                            <div className="card-header bg-white border-bottom py-2 px-3 d-flex align-items-center gap-2">
                                <i className="bi bi-globe" style={{ color: '#4F46E5', fontSize: '0.95rem' }}></i>
                                <span className="fw-semibold small">DFIA Licenses</span>
                                <span className="badge ms-auto" style={{ background: '#4F46E5', fontSize: '0.7rem' }}>{summary.dfia.total_licenses} active</span>
                            </div>
                            <div className="card-body py-2 px-3">
                                <div className="row g-0 text-center">
                                    <div className="col-3 py-2 border-end">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Total Value</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#4F46E5' }}>$ {formatIndianNumber(summary.dfia.total_value_usd, 2)}</div>
                                    </div>
                                    <div className="col-3 py-2 border-end">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Balance</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#10b981' }}>$ {formatIndianNumber(summary.dfia.balance_value_usd, 2)}</div>
                                    </div>
                                    <div className="col-3 py-2 border-end">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Purchase</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#f59e0b' }}>₹{formatIndianNumber(summary.dfia.purchase_amount_inr, 0)}</div>
                                    </div>
                                    <div className="col-3 py-2">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>P / L</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: summary.dfia.profit_loss_inr >= 0 ? '#10b981' : '#ef4444' }}>
                                            {summary.dfia.profit_loss_inr >= 0 ? '+' : ''}₹{formatIndianNumber(Math.abs(summary.dfia.profit_loss_inr), 0)}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="col-lg-6">
                        <div className="card border-0 shadow-sm" style={{ borderLeft: '3px solid #06b6d4' }}>
                            <div className="card-header bg-white border-bottom py-2 px-3 d-flex align-items-center gap-2">
                                <i className="bi bi-trophy" style={{ color: '#06b6d4', fontSize: '0.95rem' }}></i>
                                <span className="fw-semibold small">Incentive Licenses</span>
                                <span className="badge ms-auto" style={{ background: '#06b6d4', fontSize: '0.7rem' }}>{summary.incentive.total_licenses} active</span>
                            </div>
                            <div className="card-body py-2 px-3">
                                <div className="row g-0 text-center">
                                    <div className="col-3 py-2 border-end">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Total Value</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#4F46E5' }}>₹{formatIndianNumber(summary.incentive.total_value_inr, 2)}</div>
                                    </div>
                                    <div className="col-3 py-2 border-end">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Balance</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#10b981' }}>₹{formatIndianNumber(summary.incentive.balance_value_inr, 2)}</div>
                                    </div>
                                    <div className="col-3 py-2 border-end">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Purchase</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#f59e0b' }}>₹{formatIndianNumber(summary.incentive.purchase_amount_inr, 0)}</div>
                                    </div>
                                    <div className="col-3 py-2">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>P / L</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: summary.incentive.profit_loss_inr >= 0 ? '#10b981' : '#ef4444' }}>
                                            {summary.incentive.profit_loss_inr >= 0 ? '+' : ''}₹{formatIndianNumber(Math.abs(summary.incentive.profit_loss_inr), 0)}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Filters Section */}
            <div className="card border-0 shadow-sm mb-4">
                <div className="card-header bg-white border-bottom py-2 px-3 d-flex align-items-center justify-content-between">
                    <div className="d-flex align-items-center gap-2">
                        <i className="bi bi-funnel" style={{ color: '#4F46E5' }}></i>
                        <h6 className="mb-0 fw-semibold">Filters & Search</h6>
                        {filters.company && (
                            <span className="badge bg-info ms-1" style={{ fontSize: '0.7rem' }}>
                                <i className="bi bi-building me-1"></i>{filters.company.label}
                            </span>
                        )}
                    </div>
                    {filters.company && (
                        <button className="btn btn-sm btn-outline-secondary" onClick={() => handleFilterChange('company', null)}>
                            <i className="bi bi-x-circle me-1"></i>Clear Company
                        </button>
                    )}
                </div>
                <div className="card-body p-3">
                    <div className="row g-3">
                        <div className="col-lg-3 col-md-5">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                <i className="bi bi-building me-1"></i>
                                Company Filter
                            </label>
                            <AsyncSelectField
                                endpoint="masters/companies/"
                                labelField="name"
                                valueField="id"
                                value={filters.company}
                                onChange={(value) => handleFilterChange('company', value)}
                                isMulti={false}
                                placeholder="Select company to view their ledger..."
                                loadOnMount={false}
                            />
                            <small className="text-muted">Filter by trades with specific company</small>
                        </div>
                        <div className="col-lg-3 col-md-6">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                License Type
                            </label>
                            <div className="d-flex flex-wrap gap-1">
                                {licenseTypeOptions.map(opt => (
                                    <button
                                        key={opt.value}
                                        type="button"
                                        onClick={() => handleFilterChange('license_type', opt.value)}
                                        style={{
                                            fontSize: '0.75rem', fontWeight: '600', padding: '4px 10px', borderRadius: '20px',
                                            background: filters.license_type === opt.value ? '#4F46E5' : 'white',
                                            color: filters.license_type === opt.value ? 'white' : 'var(--text-secondary)',
                                            border: `1px solid ${filters.license_type === opt.value ? '#4F46E5' : '#d1d5db'}`,
                                            cursor: 'pointer', transition: 'all 0.15s',
                                        }}
                                    >
                                        {opt.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div className="col-lg-2 col-md-3">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                Min Balance
                            </label>
                            <input
                                type="number"
                                className="form-control"
                                value={filters.min_balance}
                                onChange={(e) => handleFilterChange('min_balance', e.target.value)}
                                placeholder="0"
                                step="100"
                                style={{ borderColor: 'var(--bs-gray-300)', fontSize: '0.95rem' }}
                            />
                        </div>
                        <div className="col-lg-3 col-md-5">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                Search
                            </label>
                            <div className="input-group">
                                <span className="input-group-text bg-white" style={{ borderRight: 'none' }}>
                                    <i className="bi bi-search text-muted"></i>
                                </span>
                                <input
                                    type="text"
                                    className="form-control"
                                    value={filters.search}
                                    onChange={(e) => handleFilterChange('search', e.target.value)}
                                    placeholder="License # or exporter..."
                                    style={{ borderLeft: 'none', fontSize: '0.95rem' }}
                                />
                            </div>
                        </div>
                        <div className="col-lg-2 col-md-4">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                Sort By
                            </label>
                            <select
                                className="form-select"
                                value={filters.ordering}
                                onChange={(e) => handleFilterChange('ordering', e.target.value)}
                                style={{ borderColor: 'var(--bs-gray-300)', fontSize: '0.95rem' }}
                            >
                                <option value="-license_date">Latest First</option>
                                <option value="license_date">Oldest First</option>
                                <option value="-balance_value">Highest Balance</option>
                                <option value="balance_value">Lowest Balance</option>
                            </select>
                        </div>
                        <div className="col-lg-2 col-md-4 d-flex align-items-end">
                            <div className="form-check form-switch">
                                <input
                                    type="checkbox"
                                    className="form-check-input"
                                    id="activeOnly"
                                    checked={filters.active_only}
                                    onChange={(e) => handleFilterChange('active_only', e.target.checked)}
                                    style={{ cursor: 'pointer' }}
                                />
                                <label className="form-check-label" htmlFor="activeOnly" style={{ fontSize: '0.78rem', fontWeight: '600', cursor: 'pointer', color: 'var(--text-secondary)' }}>
                                    Active Only
                                </label>
                            </div>
                        </div>
                    </div>

                    {/* Purchase Date Filter Row */}
                    <div className="row g-3 mt-2">
                        <div className="col-12">
                            <div className="d-flex align-items-center justify-content-between mb-2">
                                <div className="d-flex align-items-center">
                                    <i className="bi bi-calendar-range text-primary me-2"></i>
                                    <strong style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Purchase Date Range</strong>
                                    <small className="text-muted ms-2" style={{ fontSize: '0.8rem' }}>(Defaults to current FY: Apr-Mar)</small>
                                </div>
                                <div className="btn-group" role="group">
                                    <button
                                        type="button"
                                        className="btn btn-sm btn-outline-primary"
                                        onClick={setCurrentFinancialYear}
                                        style={{ fontSize: '0.75rem' }}
                                    >
                                        <i className="bi bi-calendar-check me-1"></i>Current FY
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-sm btn-outline-secondary"
                                        onClick={setPreviousFinancialYear}
                                        style={{ fontSize: '0.75rem' }}
                                    >
                                        <i className="bi bi-calendar3 me-1"></i>Previous FY
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-sm btn-outline-danger"
                                        onClick={clearDateFilter}
                                        disabled={!filters.purchase_date_from && !filters.purchase_date_to}
                                        style={{ fontSize: '0.75rem' }}
                                    >
                                        <i className="bi bi-x-circle me-1"></i>Clear
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div className="col-lg-3 col-md-4">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                <i className="bi bi-calendar-check me-1"></i>From Date
                            </label>
                            <input
                                type="date"
                                className="form-control"
                                value={filters.purchase_date_from}
                                onChange={(e) => handleFilterChange('purchase_date_from', e.target.value)}
                                style={{ borderColor: 'var(--bs-gray-300)', fontSize: '0.95rem' }}
                            />
                        </div>
                        <div className="col-lg-3 col-md-4">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                <i className="bi bi-calendar-x me-1"></i>To Date
                            </label>
                            <input
                                type="date"
                                className="form-control"
                                value={filters.purchase_date_to}
                                onChange={(e) => handleFilterChange('purchase_date_to', e.target.value)}
                                style={{ borderColor: 'var(--bs-gray-300)', fontSize: '0.95rem' }}
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* Company-wise Ledger */}
            <div className="card border-0 shadow-sm">
                <div className="card-body p-0">
                    {companyWiseLoading ? (
                        <div className="text-center py-5">
                            <div className="spinner-border text-primary" role="status" style={{ width: '3rem', height: '3rem' }}>
                                <span className="visually-hidden">Loading...</span>
                            </div>
                            <p className="text-muted mt-3 mb-0">Loading license-wise ledger...</p>
                        </div>
                    ) : companyWiseData ? (
                        <LicenseWiseLedger
                            data={companyWiseData}
                            navigate={navigate}
                        />
                    ) : (
                        <div className="text-center py-5">
                            <i className="bi bi-building" style={{ fontSize: '2.5rem', color: 'var(--bs-gray-300)' }}></i>
                            <p className="mt-3 mb-1 fw-semibold" style={{ color: 'var(--text-dark)', fontSize: '0.95rem' }}>No Data</p>
                            <p className="text-muted mb-0 small">No trades found</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
