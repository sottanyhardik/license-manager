import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import api from '../api/axios';
import { formatIndianNumber } from '../utils/numberFormatter';
import { generatePDF, generateExcel } from '../utils/ledgerExport';
import AsyncSelectField from '../components/AsyncSelectField';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import DebouncedSearchInput from '../components/DebouncedSearchInput';
import { ArrowDownCircle, ArrowUpCircle, BookOpen, Building2, Calendar, CalendarCheck, CalendarRange, CalendarX, FileSpreadsheet, FileText, Filter, Globe, Inbox, Loader2, Trophy, XCircle } from "lucide-react";

function LicenseWiseLedger({ data, navigate }) {
    const { licenses } = data;
    const fmt = (v) => `₹${formatIndianNumber(v, 2)}`;
    const plColor = (v) => v >= 0 ? 'var(--tb-success)' : 'var(--tb-danger)';

    return (
        <div style={{ padding: '8px' }}>
            {licenses.map((lic) => (
                <div key={lic.license_id} style={{ marginBottom: '24px', border: '1px solid var(--tb-border)', borderRadius: 'var(--tb-r-md)', overflow: 'hidden' }}>
                    {/* License Header */}
                    <div style={{ background: 'var(--tb-brand-active)', color: '#fff', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: '24px' }}>
                        <span style={{ fontWeight: '700', fontSize: 15 }}>
                            <FileText className="size-4" aria-hidden="true" />{lic.license_number}
                        </span>
                        <span style={{ fontSize: 12.5, color: 'var(--tb-text-tertiary)' }}>
                            <Calendar className="size-4" aria-hidden="true" />{lic.license_date}
                        </span>
                        <span style={{ background: lic.license_type === 'DFIA' ? 'var(--tb-info)' : 'var(--accent-color)', color: '#fff', borderRadius: 'var(--tb-r-sm)', padding: '2px 8px', fontSize: 11, fontWeight: '700' }}>
                            {lic.license_type}
                        </span>
                        {navigate && (
                            <button
                                onClick={() => navigate(`/license-ledger/${lic.license_id}`)}
                                style={{ marginLeft: 'auto', background: 'rgba(255,255,255,0.15)', border: '1px solid rgba(255,255,255,0.3)', color: '#fff', borderRadius: 'var(--tb-r-sm)', padding: '3px 10px', fontSize: 12, fontWeight: '600', cursor: 'pointer' }}
                            >
                                <BookOpen className="size-4" aria-hidden="true" />View Ledger
                            </button>
                        )}
                    </div>

                    {/* Companies table */}
                    <table style={{ width: '100%', fontSize: 12.5, borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ background: 'var(--tb-sunken)', borderBottom: '2px solid var(--tb-border)' }}>
                                <th style={{ padding: '7px 12px', fontWeight: '700', color: 'var(--tb-text)', width: '30%' }}>Company</th>
                                <th style={{ padding: '7px 12px', fontWeight: '700', color: 'var(--tb-text)', width: '15%' }}>Type</th>
                                <th style={{ padding: '7px 12px', fontWeight: '700', color: 'var(--tb-text)', width: '15%' }}>Date</th>
                                <th style={{ padding: '7px 12px', fontWeight: '700', color: 'var(--tb-success-text)', textAlign: 'right', width: '20%' }}>Purchase (₹)</th>
                                <th style={{ padding: '7px 12px', fontWeight: '700', color: 'var(--tb-danger-text)', textAlign: 'right', width: '20%' }}>Sale (₹)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {lic.companies.map((company, ci) => {
                                return (
                                    <React.Fragment key={company.company_id}>
                                        {/* Company name row */}
                                        <tr style={{ background: ci % 2 === 0 ? 'var(--tb-brand-50)' : 'var(--tb-sunken)', borderTop: ci > 0 ? '2px solid var(--tb-border)' : 'none' }}>
                                            <td colSpan="5" style={{ padding: '5px 12px', fontWeight: '700', color: 'var(--tb-text)', fontSize: '0.82rem' }}>
                                                <Building2 className="size-4" aria-hidden="true" />{company.company_name}
                                            </td>
                                        </tr>
                                        {/* Purchase rows */}
                                        {company.purchases.map((row) => (
                                            <tr key={`p-${row.trade_id}`} style={{ background: 'var(--tb-success-soft)', borderBottom: '1px solid var(--tb-success-border)' }}>
                                                <td style={{ padding: '4px 12px 4px 24px', color: 'var(--tb-text)' }}>
                                                    <ArrowDownCircle className="size-4" aria-hidden="true" />Purchase
                                                </td>
                                                <td style={{ padding: '4px 12px', color: 'var(--tb-text-secondary)' }}>{lic.license_type}</td>
                                                <td style={{ padding: '4px 12px', color: 'var(--tb-text-secondary)' }}>{row.invoice_date}</td>
                                                <td style={{ padding: '4px 12px', textAlign: 'right', fontWeight: '600', color: 'var(--tb-success-text)' }}>{fmt(row.amount)}</td>
                                                <td style={{ padding: '4px 12px' }}></td>
                                            </tr>
                                        ))}
                                        {/* Sale rows */}
                                        {company.sales.map((row) => (
                                            <tr key={`s-${row.trade_id}`} style={{ background: 'var(--tb-danger-soft)', borderBottom: '1px solid var(--tb-danger-border)' }}>
                                                <td style={{ padding: '4px 12px 4px 24px', color: 'var(--tb-text)' }}>
                                                    <ArrowUpCircle className="size-4" aria-hidden="true" />Sale
                                                </td>
                                                <td style={{ padding: '4px 12px', color: 'var(--tb-text-secondary)' }}>{lic.license_type}</td>
                                                <td style={{ padding: '4px 12px', color: 'var(--tb-text-secondary)' }}>{row.invoice_date}</td>
                                                <td style={{ padding: '4px 12px' }}></td>
                                                <td style={{ padding: '4px 12px', textAlign: 'right', fontWeight: '600', color: 'var(--tb-danger-text)' }}>{fmt(row.amount)}</td>
                                            </tr>
                                        ))}
                                        {/* Company total row */}
                                        <tr style={{ background: 'var(--tb-brand-active)', color: '#fff', fontWeight: '700' }}>
                                            <td colSpan="3" style={{ padding: '5px 12px', textAlign: 'right', fontSize: 12 }}>
                                                Total — {company.company_name}
                                            </td>
                                            <td style={{ padding: '5px 12px', textAlign: 'right', color: 'var(--tb-success-soft)' }}>{fmt(company.purchase_total)}</td>
                                            <td style={{ padding: '5px 12px', textAlign: 'right', color: 'var(--tb-danger-border)' }}>
                                                {fmt(company.sale_total)}
                                                <span style={{ marginLeft: '8px', color: plColor(company.profit_loss), fontSize: 11 }}>
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
                    <Inbox className="size-4" aria-hidden="true" />
                    <p className="mt-3 text-muted-foreground mb-0">No trades found</p>
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
        <div className="container-fluid" style={{ minHeight: '100vh', background: 'var(--tb-body-bg)' }}>
            {/* Header */}
            <div className="flex justify-between items-center mb-4">
                <div>
                    <h4 className="mb-0 font-bold" style={{ color: 'var(--tb-text)' }}>
                        <BookOpen className="size-4" aria-hidden="true" />
                        License Ledger
                    </h4>
                    <small className="text-muted">Track available balance for DFIA and Incentive licenses</small>
                </div>
                <div className="flex gap-2">
                    {companyWiseData?.licenses?.length > 0 && (
                        <>
                            <Button variant="outline" size="sm" onClick={handleBulkExportPDF} disabled={bulkExporting}>
                                {bulkExporting ? <Loader2 className="size-3.5 animate-spin" /> : <FileText className="size-3.5" />}
                                Export PDF
                            </Button>
                            <Button variant="outline" size="sm" onClick={handleBulkExportExcel} disabled={bulkExporting}>
                                {bulkExporting ? <Loader2 className="size-3.5 animate-spin" /> : <FileSpreadsheet className="size-3.5" />}
                                Export Excel
                            </Button>
                        </>
                    )}
                </div>
            </div>

            {/* Summary Cards */}
            {summary && (
                <div className="mb-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
                    <div className="card" style={{ borderLeft: '3px solid var(--tb-brand)' }}>
                            <div className="card-header border-bottom py-2 px-3 flex items-center gap-2">
                                <Globe className="size-4" aria-hidden="true" />
                                <span className="fw-semibold small">DFIA Licenses</span>
                                <span className="badge ms-auto" style={{ background: 'var(--tb-brand)', fontSize: 11 }}>{summary.dfia.total_licenses} active</span>
                            </div>
                            <div className="card-body py-2 px-3">
                                <div className="grid grid-cols-4 divide-x divide-border text-center">
                                    <div className="py-2">
                                        <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Total Value</div>
                                        <div className="text-sm font-bold text-primary">$ {formatIndianNumber(summary.dfia.total_value_usd, 2)}</div>
                                    </div>
                                    <div className="py-2">
                                        <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Balance</div>
                                        <div className="text-sm font-bold text-success">$ {formatIndianNumber(summary.dfia.balance_value_usd, 2)}</div>
                                    </div>
                                    <div className="py-2">
                                        <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Purchase</div>
                                        <div className="text-sm font-bold text-warning">₹{formatIndianNumber(summary.dfia.purchase_amount_inr, 0)}</div>
                                    </div>
                                    <div className="py-2">
                                        <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">P / L</div>
                                        <div className="text-sm font-bold" style={{ color: summary.dfia.profit_loss_inr >= 0 ? 'var(--tb-success)' : 'var(--tb-danger)' }}>
                                            {summary.dfia.profit_loss_inr >= 0 ? '+' : ''}₹{formatIndianNumber(Math.abs(summary.dfia.profit_loss_inr), 0)}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    <div className="card" style={{ borderLeft: '3px solid var(--tb-info)' }}>
                            <div className="card-header border-bottom py-2 px-3 flex items-center gap-2">
                                <Trophy className="size-4" aria-hidden="true" />
                                <span className="fw-semibold small">Incentive Licenses</span>
                                <span className="badge ms-auto" style={{ background: 'var(--tb-info)', fontSize: 11 }}>{summary.incentive.total_licenses} active</span>
                            </div>
                            <div className="card-body py-2 px-3">
                                <div className="grid grid-cols-4 divide-x divide-border text-center">
                                    <div className="py-2">
                                        <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Total Value</div>
                                        <div className="text-sm font-bold text-primary">₹{formatIndianNumber(summary.incentive.total_value_inr, 2)}</div>
                                    </div>
                                    <div className="py-2">
                                        <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Balance</div>
                                        <div className="text-sm font-bold text-success">₹{formatIndianNumber(summary.incentive.balance_value_inr, 2)}</div>
                                    </div>
                                    <div className="py-2">
                                        <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Purchase</div>
                                        <div className="text-sm font-bold text-warning">₹{formatIndianNumber(summary.incentive.purchase_amount_inr, 0)}</div>
                                    </div>
                                    <div className="py-2">
                                        <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">P / L</div>
                                        <div className="text-sm font-bold" style={{ color: summary.incentive.profit_loss_inr >= 0 ? 'var(--tb-success)' : 'var(--tb-danger)' }}>
                                            {summary.incentive.profit_loss_inr >= 0 ? '+' : ''}₹{formatIndianNumber(Math.abs(summary.incentive.profit_loss_inr), 0)}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                </div>
            )}

            {/* Filters Section */}
            <div className="card mb-3">
                <div className="card-header border-bottom py-2 px-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Filter className="size-4" aria-hidden="true" />
                        <h6 className="mb-0 font-semibold">Filters & Search</h6>
                        {filters.company && (
                            <span className="badge bg-info ml-1" style={{ fontSize: 11 }}>
                                <Building2 className="size-4" aria-hidden="true" />{filters.company.label}
                            </span>
                        )}
                    </div>
                    {filters.company && (
                        <Button size="sm" variant="outline" onClick={() => handleFilterChange('company', null)}>
                            <XCircle className="size-4" aria-hidden="true" />Clear Company
                        </Button>
                    )}
                </div>
                <div className="card-body p-3">
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-6">
                        <div className="lg:col-span-2">
                            <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground"><Building2 className="size-4" aria-hidden="true" />Company Filter</label>
                            <AsyncSelectField endpoint="masters/companies/" labelField="name" valueField="id" value={filters.company} onChange={(value) => handleFilterChange('company', value)} isMulti={false} placeholder="Select company to view their ledger..." loadOnMount={false} />
                            <p className="mt-0.5 text-[11px] text-muted-foreground">Filter by trades with specific company</p>
                        </div>
                        <div className="lg:col-span-2">
                            <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">License Type</label>
                            <div className="flex flex-wrap gap-1">
                                {licenseTypeOptions.map(opt => {
                                    const active = filters.license_type === opt.value;
                                    return (
                                        <button key={opt.value} type="button" onClick={() => handleFilterChange('license_type', opt.value)} className={`cursor-pointer rounded-full border px-2.5 py-1 text-xs font-semibold transition-colors ${active ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card text-muted-foreground hover:bg-muted'}`}>
                                            {opt.label}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                        <div>
                            <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">Min Balance</label>
                            <Input type="number" value={filters.min_balance} onChange={(e) => handleFilterChange('min_balance', e.target.value)} placeholder="0" step="100" />
                        </div>
                        <div>
                            <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">Search</label>
                            <DebouncedSearchInput value={filters.search} onChange={(v) => handleFilterChange('search', v)} placeholder="License # or exporter..." />
                        </div>
                    </div>
                    <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <div>
                            <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">Sort By</label>
                            <select className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm" value={filters.ordering} onChange={(e) => handleFilterChange('ordering', e.target.value)}>
                                <option value="-license_date">Latest First</option>
                                <option value="license_date">Oldest First</option>
                                <option value="-balance_value">Highest Balance</option>
                                <option value="balance_value">Lowest Balance</option>
                            </select>
                        </div>
                        <div className="flex items-end">
                            <label className="flex cursor-pointer items-center gap-2.5 text-sm" htmlFor="activeOnly">
                                <Switch id="activeOnly" checked={filters.active_only} onCheckedChange={(v) => handleFilterChange('active_only', v)} />
                                <span className="text-xs font-semibold text-muted-foreground">Active Only</span>
                            </label>
                        </div>
                    </div>

                    {/* Purchase Date Filter */}
                    <div className="mt-3 border-t border-border/60 pt-3">
                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2 text-[12px] font-semibold text-muted-foreground">
                                <CalendarRange className="size-4" aria-hidden="true" />
                                Purchase Date Range
                                <span className="text-[11.5px] font-normal text-muted-foreground">(Defaults to current FY: Apr-Mar)</span>
                            </div>
                            <div className="flex gap-1">
                                <Button size="sm" variant="outline" onClick={setCurrentFinancialYear}><CalendarCheck className="size-4" aria-hidden="true" />Current FY</Button>
                                <Button size="sm" variant="outline" onClick={setPreviousFinancialYear}><Calendar className="size-4" aria-hidden="true" />Previous FY</Button>
                                <Button size="sm" variant="outline" className="text-destructive hover:bg-destructive/10" onClick={clearDateFilter} disabled={!filters.purchase_date_from && !filters.purchase_date_to}><XCircle className="size-4" aria-hidden="true" />Clear</Button>
                            </div>
                        </div>
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            <div>
                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground"><CalendarCheck className="size-4" aria-hidden="true" />From Date</label>
                                <Input type="date" value={filters.purchase_date_from} onChange={(e) => handleFilterChange('purchase_date_from', e.target.value)} />
                            </div>
                            <div>
                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground"><CalendarX className="size-4" aria-hidden="true" />To Date</label>
                                <Input type="date" value={filters.purchase_date_to} onChange={(e) => handleFilterChange('purchase_date_to', e.target.value)} />
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Company-wise Ledger */}
            <div className="card">
                <div className="card-body p-0">
                    {companyWiseLoading ? (
                        <div className="flex flex-col items-center gap-2 py-10 text-center">
                            <span className="inline-block size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" aria-hidden="true" />
                            <p className="text-sm text-muted-foreground">Loading license-wise ledger…</p>
                        </div>
                    ) : companyWiseData ? (
                        <LicenseWiseLedger
                            data={companyWiseData}
                            navigate={navigate}
                        />
                    ) : (
                        <div className="text-center py-5">
                            <Building2 className="size-4" aria-hidden="true" />
                            <p className="mt-3 mb-1 font-semibold" style={{ color: 'var(--tb-text)', fontSize: 15 }}>No Data</p>
                            <p className="text-muted mb-0 small">No trades found</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
