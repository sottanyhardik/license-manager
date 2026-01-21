import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import { formatIndianNumber } from '../utils/numberFormatter';

export default function LicenseLedger() {
    const navigate = useNavigate();
    const [licenses, setLicenses] = useState([]);
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [filters, setFilters] = useState({
        license_type: 'ALL',
        min_balance: '',
        search: '',
        active_only: true,
        ordering: '-license_date'
    });

    const licenseTypeOptions = [
        { value: 'ALL', label: 'All Licenses', icon: 'bi-list-ul' },
        { value: 'DFIA', label: 'DFIA Only', icon: 'bi-globe' },
        { value: 'INCENTIVE', label: 'All Incentive', icon: 'bi-trophy' },
        { value: 'RODTEP', label: 'RODTEP', icon: 'bi-award' },
        { value: 'ROSTL', label: 'ROSTL', icon: 'bi-badge-tm' },
        { value: 'MEIS', label: 'MEIS', icon: 'bi-star' },
    ];

    useEffect(() => {
        fetchLedgerData();
        fetchSummary();
    }, [filters]);

    const fetchLedgerData = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (filters.license_type) params.append('license_type', filters.license_type);
            if (filters.min_balance) params.append('min_balance', filters.min_balance);
            if (filters.search) params.append('search', filters.search);
            if (filters.ordering) params.append('ordering', filters.ordering);
            params.append('active_only', filters.active_only);

            const response = await api.get(`/license-ledger/?${params.toString()}`);
            setLicenses(response.data || []);
        } catch (error) {
            console.error('Error fetching ledger data:', error);
        } finally {
            setLoading(false);
        }
    };

    const fetchSummary = async () => {
        try {
            const response = await api.get('/license-ledger/summary/');
            setSummary(response.data);
        } catch (error) {
            console.error('Error fetching summary:', error);
        }
    };

    const handleFilterChange = (field, value) => {
        setFilters(prev => ({ ...prev, [field]: value }));
    };

    const formatCurrency = (value, currency) => {
        const formatted = formatIndianNumber(value, 2);
        return currency === 'USD' ? `$ ${formatted}` : `₹ ${formatted}`;
    };

    const getSoldStatusBadge = (status) => {
        const badges = {
            'NO': { bg: 'success', text: 'Available', icon: 'bi-check-circle' },
            'PARTIAL': { bg: 'warning', text: 'Partial', icon: 'bi-hourglass-split' },
            'YES': { bg: 'danger', text: 'Sold Out', icon: 'bi-x-circle' }
        };
        const badge = badges[status] || { bg: 'secondary', text: status, icon: 'bi-question-circle' };
        return (
            <span className={`badge bg-${badge.bg}`} style={{ fontSize: '0.8rem', fontWeight: '500' }}>
                <i className={`bi ${badge.icon} me-1`}></i>
                {badge.text}
            </span>
        );
    };

    const handleViewDetails = (license) => {
        navigate(`/license-ledger/${license.id}`, {
            state: { license_type: license.license_type }
        });
    };

    const handleCreateTrade = (license) => {
        navigate('/trades/new', {
            state: {
                license_type: license.license_type === 'DFIA' ? 'DFIA' : 'INCENTIVE',
                license_id: license.id,
                license_number: license.license_number
            }
        });
    };

    return (
        <div className="container-fluid" style={{ backgroundColor: '#f8f9fa', minHeight: '100vh', padding: '24px' }}>
            {/* Professional Header */}
            <div className="row mb-4">
                <div className="col-12">
                    <div style={{
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        padding: '32px',
                        borderRadius: '12px',
                        boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
                        color: 'white'
                    }}>
                        <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '8px' }}>
                            <i className="bi bi-journal-text me-3"></i>
                            License Ledger
                        </h1>
                        <p style={{ fontSize: '1.05rem', marginBottom: '0', opacity: '0.95' }}>
                            Track and manage available balance for DFIA and Incentive licenses
                        </p>
                    </div>
                </div>
            </div>

            {/* Summary Cards - Business Grade */}
            {summary && (
                <div className="row mb-4">
                    <div className="col-lg-6 mb-3 mb-lg-0">
                        <div className="card border-0 shadow-sm h-100" style={{ borderLeft: '4px solid #4285f4' }}>
                            <div className="card-body p-4">
                                <div className="d-flex align-items-center mb-3">
                                    <div style={{
                                        width: '48px',
                                        height: '48px',
                                        borderRadius: '12px',
                                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        marginRight: '16px'
                                    }}>
                                        <i className="bi bi-globe text-white" style={{ fontSize: '24px' }}></i>
                                    </div>
                                    <div>
                                        <h5 className="mb-0" style={{ fontSize: '1.25rem', fontWeight: '700', color: '#2c3e50' }}>
                                            DFIA Licenses
                                        </h5>
                                        <p className="text-muted mb-0" style={{ fontSize: '0.9rem' }}>
                                            {summary.dfia.total_licenses} Active Licenses
                                        </p>
                                    </div>
                                </div>

                                <div className="row g-3 mb-3">
                                    <div className="col-6">
                                        <div style={{ padding: '16px', background: '#f8f9fa', borderRadius: '8px' }}>
                                            <p className="text-muted mb-1" style={{ fontSize: '0.85rem', fontWeight: '500' }}>
                                                Total Value
                                            </p>
                                            <h4 className="mb-0" style={{ fontSize: '1.5rem', fontWeight: '700', color: '#4285f4' }}>
                                                $ {formatIndianNumber(summary.dfia.total_value_usd, 2)}
                                            </h4>
                                        </div>
                                    </div>
                                    <div className="col-6">
                                        <div style={{ padding: '16px', background: '#e8f5e9', borderRadius: '8px' }}>
                                            <p className="text-muted mb-1" style={{ fontSize: '0.85rem', fontWeight: '500' }}>
                                                Available Balance
                                            </p>
                                            <h4 className="mb-0" style={{ fontSize: '1.5rem', fontWeight: '700', color: '#2e7d32' }}>
                                                $ {formatIndianNumber(summary.dfia.balance_value_usd, 2)}
                                            </h4>
                                        </div>
                                    </div>
                                </div>

                                <hr style={{ margin: '20px 0', borderColor: '#dee2e6' }} />

                                <div className="row g-3">
                                    <div className="col-4">
                                        <p className="text-muted mb-1" style={{ fontSize: '0.8rem' }}>Sold Value</p>
                                        <p className="mb-0" style={{ fontSize: '1.1rem', fontWeight: '600', color: '#d32f2f' }}>
                                            $ {formatIndianNumber(summary.dfia.sold_value_usd, 2)}
                                        </p>
                                    </div>
                                    <div className="col-4">
                                        <p className="text-muted mb-1" style={{ fontSize: '0.8rem' }}>Purchase (₹)</p>
                                        <p className="mb-0" style={{ fontSize: '1.1rem', fontWeight: '600', color: '#f57c00' }}>
                                            ₹ {formatIndianNumber(summary.dfia.purchase_amount_inr, 0)}
                                        </p>
                                    </div>
                                    <div className="col-4">
                                        <p className="text-muted mb-1" style={{ fontSize: '0.8rem' }}>Profit/Loss</p>
                                        <p className="mb-0" style={{
                                            fontSize: '1.1rem',
                                            fontWeight: '700',
                                            color: summary.dfia.profit_loss_inr >= 0 ? '#2e7d32' : '#d32f2f'
                                        }}>
                                            {summary.dfia.profit_loss_inr >= 0 ? '+' : ''}₹ {formatIndianNumber(Math.abs(summary.dfia.profit_loss_inr), 2)}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="col-lg-6">
                        <div className="card border-0 shadow-sm h-100" style={{ borderLeft: '4px solid #00acc1' }}>
                            <div className="card-body p-4">
                                <div className="d-flex align-items-center mb-3">
                                    <div style={{
                                        width: '48px',
                                        height: '48px',
                                        borderRadius: '12px',
                                        background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        marginRight: '16px'
                                    }}>
                                        <i className="bi bi-trophy text-white" style={{ fontSize: '24px' }}></i>
                                    </div>
                                    <div>
                                        <h5 className="mb-0" style={{ fontSize: '1.25rem', fontWeight: '700', color: '#2c3e50' }}>
                                            Incentive Licenses
                                        </h5>
                                        <p className="text-muted mb-0" style={{ fontSize: '0.9rem' }}>
                                            {summary.incentive.total_licenses} Active Licenses
                                        </p>
                                    </div>
                                </div>

                                <div className="row g-3 mb-3">
                                    <div className="col-6">
                                        <div style={{ padding: '16px', background: '#f8f9fa', borderRadius: '8px' }}>
                                            <p className="text-muted mb-1" style={{ fontSize: '0.85rem', fontWeight: '500' }}>
                                                Total Value
                                            </p>
                                            <h4 className="mb-0" style={{ fontSize: '1.5rem', fontWeight: '700', color: '#00acc1' }}>
                                                ₹ {formatIndianNumber(summary.incentive.total_value_inr, 2)}
                                            </h4>
                                        </div>
                                    </div>
                                    <div className="col-6">
                                        <div style={{ padding: '16px', background: '#e8f5e9', borderRadius: '8px' }}>
                                            <p className="text-muted mb-1" style={{ fontSize: '0.85rem', fontWeight: '500' }}>
                                                Available Balance
                                            </p>
                                            <h4 className="mb-0" style={{ fontSize: '1.5rem', fontWeight: '700', color: '#2e7d32' }}>
                                                ₹ {formatIndianNumber(summary.incentive.balance_value_inr, 2)}
                                            </h4>
                                        </div>
                                    </div>
                                </div>

                                <hr style={{ margin: '20px 0', borderColor: '#dee2e6' }} />

                                <div className="row g-3">
                                    <div className="col-4">
                                        <p className="text-muted mb-1" style={{ fontSize: '0.8rem' }}>Sold Value</p>
                                        <p className="mb-0" style={{ fontSize: '1.1rem', fontWeight: '600', color: '#d32f2f' }}>
                                            ₹ {formatIndianNumber(summary.incentive.sold_value_inr, 2)}
                                        </p>
                                    </div>
                                    <div className="col-4">
                                        <p className="text-muted mb-1" style={{ fontSize: '0.8rem' }}>Purchase (₹)</p>
                                        <p className="mb-0" style={{ fontSize: '1.1rem', fontWeight: '600', color: '#f57c00' }}>
                                            ₹ {formatIndianNumber(summary.incentive.purchase_amount_inr, 0)}
                                        </p>
                                    </div>
                                    <div className="col-4">
                                        <p className="text-muted mb-1" style={{ fontSize: '0.8rem' }}>Profit/Loss</p>
                                        <p className="mb-0" style={{
                                            fontSize: '1.1rem',
                                            fontWeight: '700',
                                            color: summary.incentive.profit_loss_inr >= 0 ? '#2e7d32' : '#d32f2f'
                                        }}>
                                            {summary.incentive.profit_loss_inr >= 0 ? '+' : ''}₹ {formatIndianNumber(Math.abs(summary.incentive.profit_loss_inr), 2)}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Enhanced Filters Section */}
            <div className="card border-0 shadow-sm mb-4">
                <div className="card-body p-4">
                    <div className="d-flex align-items-center mb-3">
                        <i className="bi bi-funnel text-primary me-2" style={{ fontSize: '1.25rem' }}></i>
                        <h5 className="mb-0" style={{ fontWeight: '600', color: '#2c3e50' }}>Filters & Search</h5>
                    </div>
                    <div className="row g-3">
                        <div className="col-lg-3 col-md-4">
                            <label className="form-label" style={{ fontSize: '0.9rem', fontWeight: '600', color: '#5a6c7d' }}>
                                License Type
                            </label>
                            <select
                                className="form-select"
                                value={filters.license_type}
                                onChange={(e) => handleFilterChange('license_type', e.target.value)}
                                style={{ borderColor: '#ced4da', fontSize: '0.95rem' }}
                            >
                                {licenseTypeOptions.map(opt => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                            </select>
                        </div>
                        <div className="col-lg-2 col-md-3">
                            <label className="form-label" style={{ fontSize: '0.9rem', fontWeight: '600', color: '#5a6c7d' }}>
                                Min Balance
                            </label>
                            <input
                                type="number"
                                className="form-control"
                                value={filters.min_balance}
                                onChange={(e) => handleFilterChange('min_balance', e.target.value)}
                                placeholder="0"
                                step="100"
                                style={{ borderColor: '#ced4da', fontSize: '0.95rem' }}
                            />
                        </div>
                        <div className="col-lg-3 col-md-5">
                            <label className="form-label" style={{ fontSize: '0.9rem', fontWeight: '600', color: '#5a6c7d' }}>
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
                            <label className="form-label" style={{ fontSize: '0.9rem', fontWeight: '600', color: '#5a6c7d' }}>
                                Sort By
                            </label>
                            <select
                                className="form-select"
                                value={filters.ordering}
                                onChange={(e) => handleFilterChange('ordering', e.target.value)}
                                style={{ borderColor: '#ced4da', fontSize: '0.95rem' }}
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
                                <label className="form-check-label" htmlFor="activeOnly" style={{ fontSize: '0.9rem', fontWeight: '500', cursor: 'pointer' }}>
                                    Active Only
                                </label>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Enhanced License Table */}
            <div className="card border-0 shadow-sm">
                <div className="card-header bg-white border-0 pt-4 px-4 pb-0">
                    <div className="d-flex justify-content-between align-items-center mb-3">
                        <h5 className="mb-0" style={{ fontWeight: '600', color: '#2c3e50' }}>
                            <i className="bi bi-table text-primary me-2"></i>
                            License Listings
                        </h5>
                        <span className="badge bg-light text-dark" style={{ fontSize: '0.9rem', fontWeight: '500' }}>
                            {licenses.length} {licenses.length === 1 ? 'License' : 'Licenses'}
                        </span>
                    </div>
                </div>
                <div className="card-body p-0">
                    <div style={{ overflowX: 'auto' }}>
                        <table className="table table-hover mb-0" style={{ minWidth: '1200px' }}>
                            <thead style={{ backgroundColor: '#f8f9fa', borderBottom: '2px solid #dee2e6' }}>
                                <tr>
                                    <th style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Type
                                    </th>
                                    <th style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        License #
                                    </th>
                                    <th style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Issue Date
                                    </th>
                                    <th style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Expiry
                                    </th>
                                    <th style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Exporter
                                    </th>
                                    <th className="text-end" style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Total Value
                                    </th>
                                    <th className="text-end" style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Balance
                                    </th>
                                    <th className="text-end" style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Purchase (₹)
                                    </th>
                                    <th className="text-end" style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        P/L (₹)
                                    </th>
                                    <th className="text-center" style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Status
                                    </th>
                                    <th className="text-center" style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Actions
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? (
                                    <tr>
                                        <td colSpan="11" className="text-center py-5">
                                            <div className="spinner-border text-primary" role="status" style={{ width: '3rem', height: '3rem' }}>
                                                <span className="visually-hidden">Loading...</span>
                                            </div>
                                            <p className="text-muted mt-3 mb-0">Loading license data...</p>
                                        </td>
                                    </tr>
                                ) : licenses.length === 0 ? (
                                    <tr>
                                        <td colSpan="11" className="text-center py-5">
                                            <i className="bi bi-inbox text-muted" style={{ fontSize: '3rem' }}></i>
                                            <p className="text-muted mt-3 mb-0" style={{ fontSize: '1.05rem' }}>
                                                No licenses found matching your criteria
                                            </p>
                                        </td>
                                    </tr>
                                ) : (
                                    licenses.map((license) => (
                                        <tr key={`${license.license_type}-${license.id}`}
                                            style={{
                                                borderBottom: '1px solid #f0f0f0',
                                                transition: 'all 0.2s ease'
                                            }}
                                            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f8f9fa'}
                                            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                                        >
                                            <td style={{ padding: '16px', verticalAlign: 'middle' }}>
                                                <span className={`badge ${license.license_type === 'DFIA' ? 'bg-primary' : 'bg-info'}`}
                                                    style={{ fontSize: '0.8rem', fontWeight: '600', padding: '6px 12px', borderRadius: '6px' }}>
                                                    {license.license_type}
                                                </span>
                                            </td>
                                            <td style={{ padding: '16px', verticalAlign: 'middle' }}>
                                                <span style={{ fontSize: '0.95rem', fontWeight: '600', color: '#2c3e50' }}>
                                                    {license.license_number}
                                                </span>
                                            </td>
                                            <td style={{ padding: '16px', verticalAlign: 'middle', fontSize: '0.9rem', color: '#5a6c7d' }}>
                                                {new Date(license.license_date).toLocaleDateString('en-GB')}
                                            </td>
                                            <td style={{ padding: '16px', verticalAlign: 'middle', fontSize: '0.9rem' }}>
                                                <span style={{ color: license.is_expired ? '#d32f2f' : '#5a6c7d' }}>
                                                    {new Date(license.license_expiry_date).toLocaleDateString('en-GB')}
                                                </span>
                                                {license.is_expired && (
                                                    <span className="badge bg-danger ms-2" style={{ fontSize: '0.7rem', padding: '3px 6px' }}>
                                                        EXPIRED
                                                    </span>
                                                )}
                                            </td>
                                            <td style={{ padding: '16px', verticalAlign: 'middle', fontSize: '0.9rem', color: '#5a6c7d', maxWidth: '200px' }}>
                                                <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                                    title={license.exporter_name}>
                                                    {license.exporter_name}
                                                </div>
                                            </td>
                                            <td className="text-end" style={{ padding: '16px', verticalAlign: 'middle', fontSize: '0.95rem', fontWeight: '600', color: '#2c3e50' }}>
                                                {formatCurrency(license.total_value, license.currency)}
                                            </td>
                                            <td className="text-end" style={{ padding: '16px', verticalAlign: 'middle' }}>
                                                <span style={{
                                                    fontSize: '1rem',
                                                    fontWeight: '700',
                                                    color: license.balance_value > 0 ? '#2e7d32' : '#9e9e9e'
                                                }}>
                                                    {formatCurrency(license.balance_value, license.currency)}
                                                </span>
                                            </td>
                                            <td className="text-end" style={{ padding: '16px', verticalAlign: 'middle', fontSize: '0.9rem', color: '#f57c00', fontWeight: '600' }}>
                                                ₹ {formatIndianNumber(license.purchase_amount || 0, 0)}
                                            </td>
                                            <td className="text-end" style={{ padding: '16px', verticalAlign: 'middle' }}>
                                                <span style={{
                                                    fontSize: '0.95rem',
                                                    fontWeight: '700',
                                                    color: (license.profit_loss || 0) >= 0 ? '#2e7d32' : '#d32f2f'
                                                }}>
                                                    {(license.profit_loss || 0) >= 0 ? '+' : ''}₹ {formatIndianNumber(Math.abs(license.profit_loss || 0), 0)}
                                                </span>
                                            </td>
                                            <td className="text-center" style={{ padding: '16px', verticalAlign: 'middle' }}>
                                                {getSoldStatusBadge(license.sold_status)}
                                            </td>
                                            <td className="text-center" style={{ padding: '16px', verticalAlign: 'middle' }}>
                                                <button
                                                    className="btn btn-sm me-2"
                                                    onClick={() => handleViewDetails(license)}
                                                    title="View Ledger Details"
                                                    style={{
                                                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                                                        border: '1px solid rgba(102, 126, 234, 0.3)',
                                                        color: '#667eea',
                                                        padding: '6px 12px',
                                                        borderRadius: '6px',
                                                        fontSize: '0.85rem',
                                                        fontWeight: '500'
                                                    }}
                                                >
                                                    <i className="bi bi-journal-text me-1"></i>
                                                    View
                                                </button>
                                                {license.balance_value > 0 && (
                                                    <button
                                                        className="btn btn-sm btn-success"
                                                        onClick={() => handleCreateTrade(license)}
                                                        title="Create Sale"
                                                        style={{
                                                            padding: '6px 12px',
                                                            borderRadius: '6px',
                                                            fontSize: '0.85rem',
                                                            fontWeight: '500'
                                                        }}
                                                    >
                                                        <i className="bi bi-cart-plus me-1"></i>
                                                        Trade
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
