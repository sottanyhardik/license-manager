import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

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
        { value: 'ALL', label: 'All Licenses' },
        { value: 'DFIA', label: 'DFIA Only' },
        { value: 'INCENTIVE', label: 'All Incentive' },
        { value: 'RODTEP', label: 'RODTEP' },
        { value: 'ROSTL', label: 'ROSTL' },
        { value: 'MEIS', label: 'MEIS' },
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
        return new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: currency === 'USD' ? 'USD' : 'INR',
            minimumFractionDigits: 2
        }).format(value);
    };

    const getSoldStatusBadge = (status) => {
        const badges = {
            'NO': 'bg-success',
            'PARTIAL': 'bg-warning',
            'YES': 'bg-danger'
        };
        const labels = {
            'NO': 'Available',
            'PARTIAL': 'Partial',
            'YES': 'Sold Out'
        };
        return (
            <span className={`badge ${badges[status] || 'bg-secondary'}`}>
                {labels[status] || status}
            </span>
        );
    };

    const handleViewDetails = (license) => {
        if (license.license_type === 'DFIA') {
            navigate(`/licenses/${license.id}`);
        } else {
            navigate(`/incentive-licenses/${license.id}`);
        }
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
        <div className="container-fluid py-4">
            <div className="row mb-4">
                <div className="col">
                    <h2>License Ledger - Available Balance</h2>
                    <p className="text-muted">
                        View available balance for DFIA and Incentive licenses for trading
                    </p>
                </div>
            </div>

            {/* Summary Cards */}
            {summary && (
                <div className="row mb-4">
                    <div className="col-md-6">
                        <div className="card border-primary">
                            <div className="card-header bg-primary text-white">
                                <h5 className="mb-0">DFIA Licenses</h5>
                            </div>
                            <div className="card-body">
                                <div className="row">
                                    <div className="col-6">
                                        <p className="mb-1 text-muted small">Total Licenses</p>
                                        <h4>{summary.dfia.total_licenses}</h4>
                                    </div>
                                    <div className="col-6">
                                        <p className="mb-1 text-muted small">Total Value (USD)</p>
                                        <h4>${summary.dfia.total_value_usd.toLocaleString()}</h4>
                                    </div>
                                </div>
                                <hr />
                                <div className="row">
                                    <div className="col-6">
                                        <p className="mb-1 text-muted small">Sold (USD)</p>
                                        <p className="h5 text-danger">${summary.dfia.sold_value_usd.toLocaleString()}</p>
                                    </div>
                                    <div className="col-6">
                                        <p className="mb-1 text-muted small">Available Balance (USD)</p>
                                        <p className="h5 text-success">${summary.dfia.balance_value_usd.toLocaleString()}</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="col-md-6">
                        <div className="card border-info">
                            <div className="card-header bg-info text-white">
                                <h5 className="mb-0">Incentive Licenses</h5>
                            </div>
                            <div className="card-body">
                                <div className="row">
                                    <div className="col-6">
                                        <p className="mb-1 text-muted small">Total Licenses</p>
                                        <h4>{summary.incentive.total_licenses}</h4>
                                    </div>
                                    <div className="col-6">
                                        <p className="mb-1 text-muted small">Total Value (INR)</p>
                                        <h4>₹{summary.incentive.total_value_inr.toLocaleString()}</h4>
                                    </div>
                                </div>
                                <hr />
                                <div className="row">
                                    <div className="col-6">
                                        <p className="mb-1 text-muted small">Sold (INR)</p>
                                        <p className="h5 text-danger">₹{summary.incentive.sold_value_inr.toLocaleString()}</p>
                                    </div>
                                    <div className="col-6">
                                        <p className="mb-1 text-muted small">Available Balance (INR)</p>
                                        <p className="h5 text-success">₹{summary.incentive.balance_value_inr.toLocaleString()}</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Filters */}
            <div className="card mb-4">
                <div className="card-body">
                    <div className="row g-3">
                        <div className="col-md-3">
                            <label className="form-label fw-bold">License Type</label>
                            <select
                                className="form-select"
                                value={filters.license_type}
                                onChange={(e) => handleFilterChange('license_type', e.target.value)}
                            >
                                {licenseTypeOptions.map(opt => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                            </select>
                        </div>
                        <div className="col-md-2">
                            <label className="form-label fw-bold">Min Balance</label>
                            <input
                                type="number"
                                className="form-control"
                                value={filters.min_balance}
                                onChange={(e) => handleFilterChange('min_balance', e.target.value)}
                                placeholder="0"
                                step="100"
                            />
                        </div>
                        <div className="col-md-3">
                            <label className="form-label fw-bold">Search</label>
                            <input
                                type="text"
                                className="form-control"
                                value={filters.search}
                                onChange={(e) => handleFilterChange('search', e.target.value)}
                                placeholder="License number or exporter..."
                            />
                        </div>
                        <div className="col-md-2">
                            <label className="form-label fw-bold">Sort By</label>
                            <select
                                className="form-select"
                                value={filters.ordering}
                                onChange={(e) => handleFilterChange('ordering', e.target.value)}
                            >
                                <option value="-license_date">Latest First</option>
                                <option value="license_date">Oldest First</option>
                                <option value="-balance_value">Highest Balance</option>
                                <option value="balance_value">Lowest Balance</option>
                            </select>
                        </div>
                        <div className="col-md-2 d-flex align-items-end">
                            <div className="form-check">
                                <input
                                    type="checkbox"
                                    className="form-check-input"
                                    id="activeOnly"
                                    checked={filters.active_only}
                                    onChange={(e) => handleFilterChange('active_only', e.target.checked)}
                                />
                                <label className="form-check-label" htmlFor="activeOnly">
                                    Active Only
                                </label>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* License Table */}
            <div className="card">
                <div className="card-body">
                    <div className="table-responsive">
                        <table className="table table-hover">
                            <thead className="table-light">
                                <tr>
                                    <th>Type</th>
                                    <th>License Number</th>
                                    <th>License Date</th>
                                    <th>Expiry Date</th>
                                    <th>Exporter</th>
                                    <th className="text-end">Total Value</th>
                                    <th className="text-end">Sold Value</th>
                                    <th className="text-end">Available Balance</th>
                                    <th className="text-center">Status</th>
                                    <th className="text-center">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? (
                                    <tr>
                                        <td colSpan="10" className="text-center py-4">
                                            <div className="spinner-border text-primary" role="status">
                                                <span className="visually-hidden">Loading...</span>
                                            </div>
                                        </td>
                                    </tr>
                                ) : licenses.length === 0 ? (
                                    <tr>
                                        <td colSpan="10" className="text-center py-4 text-muted">
                                            No licenses found matching your criteria
                                        </td>
                                    </tr>
                                ) : (
                                    licenses.map((license) => (
                                        <tr key={`${license.license_type}-${license.id}`}>
                                            <td>
                                                <span className={`badge ${license.license_type === 'DFIA' ? 'bg-primary' : 'bg-info'}`}>
                                                    {license.license_type}
                                                </span>
                                            </td>
                                            <td className="fw-bold">{license.license_number}</td>
                                            <td>{new Date(license.license_date).toLocaleDateString('en-GB')}</td>
                                            <td>
                                                {new Date(license.license_expiry_date).toLocaleDateString('en-GB')}
                                                {license.is_expired && (
                                                    <span className="badge bg-danger ms-2">Expired</span>
                                                )}
                                            </td>
                                            <td>{license.exporter_name}</td>
                                            <td className="text-end">
                                                {formatCurrency(license.total_value, license.currency)}
                                            </td>
                                            <td className="text-end text-danger">
                                                {formatCurrency(license.sold_value, license.currency)}
                                            </td>
                                            <td className="text-end text-success fw-bold">
                                                {formatCurrency(license.balance_value, license.currency)}
                                            </td>
                                            <td className="text-center">
                                                {getSoldStatusBadge(license.sold_status)}
                                            </td>
                                            <td className="text-center">
                                                <button
                                                    className="btn btn-sm btn-outline-primary me-1"
                                                    onClick={() => handleViewDetails(license)}
                                                    title="View Details"
                                                >
                                                    <i className="bi bi-eye"></i>
                                                </button>
                                                {license.balance_value > 0 && (
                                                    <button
                                                        className="btn btn-sm btn-outline-success"
                                                        onClick={() => handleCreateTrade(license)}
                                                        title="Create Sale"
                                                    >
                                                        <i className="bi bi-cart-plus"></i>
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
