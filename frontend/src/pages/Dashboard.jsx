import {useEffect, useState} from "react";
import {useNavigate} from "react-router-dom";
import { toast } from 'react-toastify';
import api from "../api/axios";

export default function Dashboard() {
    const navigate = useNavigate();

    // Single loading state for unified API call
    const [loading, setLoading] = useState(true);

    const [stats, setStats] = useState({
        licenses: {total: 0, active: 0, expired: 0, null_dfia: 0, expiring_soon: 0},
        allotments: {total: 0, recent: []},
        boe: {total: 0, pending_invoices: 0, recent: []},
        trade: {imports: 0, exports: 0}
    });
    const [expiringLicenses, setExpiringLicenses] = useState([]);
    const [boeMonthlyData, setBoeMonthlyData] = useState([]);

    useEffect(() => {
        // Fetch all dashboard data in one API call
        fetchDashboardData();
    }, []);

    // Fetch all dashboard data in one unified API call
    const fetchDashboardData = async () => {
        try {
            setLoading(true);
            const response = await api.get("/dashboard/");
            const data = response.data;

            // Set license stats with safe defaults
            setStats({
                licenses: data?.license_stats || {total: 0, active: 0, expired: 0, null_dfia: 0, expiring_soon: 0},
                allotments: data?.allotment_stats || {total: 0, recent: []},
                boe: data?.boe_stats || {total: 0, pending_invoices: 0, recent: []},
                trade: {
                    imports: data?.boe_stats?.total || 0,
                    exports: data?.allotment_stats?.total || 0
                }
            });

            // Set expiring licenses
            setExpiringLicenses(data?.expiring_licenses || []);

            // Set BOE monthly trend
            setBoeMonthlyData(data?.boe_monthly_trend || []);

        } catch (error) {
            toast.error("Failed to load dashboard data");
        } finally {
            setLoading(false);
        }
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        // Check if date is valid
        if (isNaN(date.getTime())) return '-';
        return date.toLocaleDateString('en-IN');
    };

    const getDaysUntilExpiry = (expiryDate) => {
        const today = new Date();
        const expiry = new Date(expiryDate);
        const diffTime = expiry - today;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return diffDays;
    };

    // Component for loading skeleton
    const LoadingSkeleton = ({height = "80px"}) => (
        <div className="placeholder-glow">
            <div className="placeholder col-12" style={{height}}></div>
        </div>
    );

    // Show loading for entire dashboard while fetching unified data
    if (loading) {
        return (
            <div className="container-fluid mt-4 px-4">
                <div className="d-flex justify-content-center align-items-center" style={{height: '80vh'}}>
                    <div className="text-center">
                        <div className="spinner-border text-primary" role="status"
                             style={{width: '3rem', height: '3rem'}}>
                            <span className="visually-hidden">Loading...</span>
                        </div>
                        <p className="mt-3 text-muted">Loading dashboard...</p>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="container-fluid" style={{ backgroundColor: '#f8f9fa', minHeight: '100vh', padding: '24px' }}>
            {/* Professional Header with Gradient */}
            <div style={{
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                padding: '32px',
                borderRadius: '12px',
                boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
                color: 'white',
                marginBottom: '24px'
            }}>
                <div className="d-flex justify-content-between align-items-center">
                    <div>
                        <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '8px' }}>
                            <i className="bi bi-speedometer2 me-3"></i>
                            Dashboard Overview
                        </h1>
                        <p style={{ fontSize: '1.05rem', marginBottom: '0', opacity: '0.95' }}>
                            Real-time insights into your license operations
                        </p>
                    </div>
                    <div style={{
                        backgroundColor: 'rgba(255, 255, 255, 0.2)',
                        padding: '12px 20px',
                        borderRadius: '8px',
                        backdropFilter: 'blur(10px)'
                    }}>
                        <i className="bi bi-calendar-event me-2"></i>
                        {new Date().toLocaleDateString('en-IN', {
                            weekday: 'long',
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric'
                        })}
                    </div>
                </div>
            </div>

            {/* Stats Cards Row 1 - Licenses */}
            <div className="row g-3 mb-4">
                <div className="col-xl-2-4 col-lg-4 col-md-6" style={{flex: '0 0 auto', width: '20%'}}>
                    <div className="card border-0 shadow-sm h-100"
                         style={{cursor: 'pointer', transition: 'all 0.2s ease'}}
                         onClick={() => navigate('/licenses?is_expired=all&is_null=all')}
                         onMouseEnter={(e) => {
                             e.currentTarget.style.boxShadow = '0 10px 25px rgba(0,0,0,0.15)';
                             e.currentTarget.style.transform = 'translateY(-3px)';
                         }}
                         onMouseLeave={(e) => {
                             e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
                             e.currentTarget.style.transform = 'translateY(0)';
                         }}>
                        <div className="card-body" style={{ padding: '20px' }}>
                            <div className="d-flex justify-content-between align-items-start">
                                <div style={{ flex: 1 }}>
                                    <p className="text-muted mb-2" style={{ fontSize: '0.875rem', fontWeight: '500' }}>Total Licenses</p>
                                    <h3 className="mb-2 fw-bold" style={{ fontSize: '2rem', color: '#2c3e50' }}>{stats.licenses.total}</h3>
                                    <small className="text-success d-flex align-items-center" style={{ fontSize: '0.8rem' }}>
                                        <i className="bi bi-check-circle me-1"></i>
                                        All licenses
                                    </small>
                                </div>
                                <div style={{
                                    width: '56px',
                                    height: '56px',
                                    borderRadius: '12px',
                                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    boxShadow: '0 4px 10px rgba(102, 126, 234, 0.3)'
                                }}>
                                    <i className="bi bi-file-earmark-text text-white" style={{ fontSize: '1.5rem' }}></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="col-xl-2-4 col-lg-4 col-md-6" style={{flex: '0 0 auto', width: '20%'}}>
                    <div className="card border-0 shadow-sm h-100"
                         style={{cursor: 'pointer', transition: 'all 0.2s ease'}}
                         onClick={() => navigate('/licenses?is_expired=False&is_null=False')}
                         onMouseEnter={(e) => {
                             e.currentTarget.style.boxShadow = '0 10px 25px rgba(0,0,0,0.15)';
                             e.currentTarget.style.transform = 'translateY(-3px)';
                         }}
                         onMouseLeave={(e) => {
                             e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
                             e.currentTarget.style.transform = 'translateY(0)';
                         }}>
                        <div className="card-body" style={{ padding: '20px' }}>
                            <div className="d-flex justify-content-between align-items-start">
                                <div style={{ flex: 1 }}>
                                    <p className="text-muted mb-2" style={{ fontSize: '0.875rem', fontWeight: '500' }}>Active Licenses</p>
                                    <h3 className="mb-2 fw-bold" style={{ fontSize: '2rem', color: '#10b981' }}>{stats.licenses.active}</h3>
                                    <small className="text-success d-flex align-items-center" style={{ fontSize: '0.8rem' }}>
                                        <i className="bi bi-activity me-1"></i>
                                        Currently valid
                                    </small>
                                </div>
                                <div style={{
                                    width: '56px',
                                    height: '56px',
                                    borderRadius: '12px',
                                    background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    boxShadow: '0 4px 10px rgba(16, 185, 129, 0.3)'
                                }}>
                                    <i className="bi bi-check-circle text-white" style={{ fontSize: '1.5rem' }}></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="col-xl-2-4 col-lg-4 col-md-6" style={{flex: '0 0 auto', width: '20%'}}>
                    <div className="card border-0 shadow-sm h-100"
                         style={{cursor: 'pointer', transition: 'all 0.2s ease'}}
                         onClick={() => navigate('/licenses?is_expired=True&is_null=all')}
                         onMouseEnter={(e) => {
                             e.currentTarget.style.boxShadow = '0 10px 25px rgba(0,0,0,0.15)';
                             e.currentTarget.style.transform = 'translateY(-3px)';
                         }}
                         onMouseLeave={(e) => {
                             e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
                             e.currentTarget.style.transform = 'translateY(0)';
                         }}>
                        <div className="card-body" style={{ padding: '20px' }}>
                            <div className="d-flex justify-content-between align-items-start">
                                <div style={{ flex: 1 }}>
                                    <p className="text-muted mb-2" style={{ fontSize: '0.875rem', fontWeight: '500' }}>Expired Licenses</p>
                                    <h3 className="mb-2 fw-bold" style={{ fontSize: '2rem', color: '#ef4444' }}>{stats.licenses.expired}</h3>
                                    <small className="text-danger d-flex align-items-center" style={{ fontSize: '0.8rem' }}>
                                        <i className="bi bi-x-circle me-1"></i>
                                        Need renewal
                                    </small>
                                </div>
                                <div style={{
                                    width: '56px',
                                    height: '56px',
                                    borderRadius: '12px',
                                    background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    boxShadow: '0 4px 10px rgba(239, 68, 68, 0.3)'
                                }}>
                                    <i className="bi bi-exclamation-triangle text-white" style={{ fontSize: '1.5rem' }}></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="col-xl-2-4 col-lg-4 col-md-6" style={{flex: '0 0 auto', width: '20%'}}>
                    <div className="card border-0 shadow-sm h-100"
                         style={{cursor: 'pointer', transition: 'all 0.2s ease'}}
                         onClick={() => navigate('/licenses?is_null=True&is_expired=all')}
                         onMouseEnter={(e) => {
                             e.currentTarget.style.boxShadow = '0 10px 25px rgba(0,0,0,0.15)';
                             e.currentTarget.style.transform = 'translateY(-3px)';
                         }}
                         onMouseLeave={(e) => {
                             e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
                             e.currentTarget.style.transform = 'translateY(0)';
                         }}>
                        <div className="card-body" style={{ padding: '20px' }}>
                            <div className="d-flex justify-content-between align-items-start">
                                <div style={{ flex: 1 }}>
                                    <p className="text-muted mb-2" style={{ fontSize: '0.875rem', fontWeight: '500' }}>Null DFIA</p>
                                    <h3 className="mb-2 fw-bold" style={{ fontSize: '2rem', color: '#6b7280' }}>{stats.licenses.null_dfia}</h3>
                                    <small className="text-muted d-flex align-items-center" style={{ fontSize: '0.8rem' }}>
                                        <i className="bi bi-dash-circle me-1"></i>
                                        Balance &lt; $500
                                    </small>
                                </div>
                                <div style={{
                                    width: '56px',
                                    height: '56px',
                                    borderRadius: '12px',
                                    background: 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    boxShadow: '0 4px 10px rgba(107, 114, 128, 0.3)'
                                }}>
                                    <i className="bi bi-file-earmark-x text-white" style={{ fontSize: '1.5rem' }}></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="col-xl-2-4 col-lg-4 col-md-6" style={{flex: '0 0 auto', width: '20%'}}>
                    <div className="card border-0 shadow-sm h-100"
                         style={{cursor: 'pointer', transition: 'all 0.2s ease', borderLeft: '4px solid #f59e0b'}}
                         onClick={() => {
                             const today = new Date().toISOString().split('T')[0];
                             const thirtyDaysLater = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
                             navigate(`/licenses?is_expired=False&is_null=False&license_expiry_date__gte=${today}&license_expiry_date__lte=${thirtyDaysLater}`);
                         }}
                         onMouseEnter={(e) => {
                             e.currentTarget.style.boxShadow = '0 10px 25px rgba(0,0,0,0.15)';
                             e.currentTarget.style.transform = 'translateY(-3px)';
                         }}
                         onMouseLeave={(e) => {
                             e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
                             e.currentTarget.style.transform = 'translateY(0)';
                         }}>
                        <div className="card-body" style={{ padding: '20px' }}>
                            <div className="d-flex justify-content-between align-items-start">
                                <div style={{ flex: 1 }}>
                                    <p className="text-muted mb-2" style={{ fontSize: '0.875rem', fontWeight: '500' }}>Expiring Soon</p>
                                    <h3 className="mb-2 fw-bold" style={{ fontSize: '2rem', color: '#f59e0b' }}>{stats.licenses.expiring_soon}</h3>
                                    <small className="text-warning d-flex align-items-center" style={{ fontSize: '0.8rem' }}>
                                        <i className="bi bi-clock-history me-1"></i>
                                        Within 30 days
                                    </small>
                                </div>
                                <div style={{
                                    width: '56px',
                                    height: '56px',
                                    borderRadius: '12px',
                                    background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    boxShadow: '0 4px 10px rgba(245, 158, 11, 0.3)'
                                }}>
                                    <i className="bi bi-hourglass-split text-white" style={{ fontSize: '1.5rem' }}></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Stats Cards Row 2 - Operations */}
            <div className="row g-3 mb-4">
                <div className="col-xl-4 col-md-6">
                    <div className="card border-0 shadow-sm h-100"
                         style={{cursor: 'pointer', transition: 'all 0.2s ease'}}
                         onClick={() => navigate('/allotments')}
                         onMouseEnter={(e) => {
                             e.currentTarget.style.boxShadow = '0 10px 25px rgba(0,0,0,0.15)';
                             e.currentTarget.style.transform = 'translateY(-3px)';
                         }}
                         onMouseLeave={(e) => {
                             e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
                             e.currentTarget.style.transform = 'translateY(0)';
                         }}>
                        <div className="card-body" style={{ padding: '24px' }}>
                            <div className="d-flex justify-content-between align-items-start">
                                <div style={{ flex: 1 }}>
                                    <p className="text-muted mb-2" style={{ fontSize: '0.875rem', fontWeight: '500' }}>Pending Bills of Entry</p>
                                    <h3 className="mb-2 fw-bold" style={{ fontSize: '2rem', color: '#2c3e50' }}>{stats.allotments.total}</h3>
                                    <small className="text-info d-flex align-items-center" style={{ fontSize: '0.8rem' }}>
                                        <i className="bi bi-box-seam me-1"></i>
                                        License allocations
                                    </small>
                                </div>
                                <div style={{
                                    width: '56px',
                                    height: '56px',
                                    borderRadius: '12px',
                                    background: 'linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    boxShadow: '0 4px 10px rgba(6, 182, 212, 0.3)'
                                }}>
                                    <i className="bi bi-diagram-3 text-white" style={{ fontSize: '1.5rem' }}></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="col-xl-4 col-md-6">
                    <div className="card border-0 shadow-sm h-100"
                         style={{cursor: 'pointer', transition: 'all 0.2s ease'}}
                         onClick={() => navigate('/bill-of-entries?is_invoice=all')}
                         onMouseEnter={(e) => {
                             e.currentTarget.style.boxShadow = '0 10px 25px rgba(0,0,0,0.15)';
                             e.currentTarget.style.transform = 'translateY(-3px)';
                         }}
                         onMouseLeave={(e) => {
                             e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
                             e.currentTarget.style.transform = 'translateY(0)';
                         }}>
                        <div className="card-body" style={{ padding: '24px' }}>
                            <div className="d-flex justify-content-between align-items-start">
                                <div style={{ flex: 1 }}>
                                    <p className="text-muted mb-2" style={{ fontSize: '0.875rem', fontWeight: '500' }}>Bills of Entry</p>
                                    <h3 className="mb-2 fw-bold" style={{ fontSize: '2rem', color: '#2c3e50' }}>{stats.boe.total}</h3>
                                    <small className="text-primary d-flex align-items-center" style={{ fontSize: '0.8rem' }}>
                                        <i className="bi bi-receipt me-1"></i>
                                        All till date
                                    </small>
                                </div>
                                <div style={{
                                    width: '56px',
                                    height: '56px',
                                    borderRadius: '12px',
                                    background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    boxShadow: '0 4px 10px rgba(59, 130, 246, 0.3)'
                                }}>
                                    <i className="bi bi-receipt-cutoff text-white" style={{ fontSize: '1.5rem' }}></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="col-xl-4 col-md-6">
                    <div className="card border-0 shadow-sm h-100"
                         style={{cursor: 'pointer', transition: 'all 0.2s ease'}}
                         onClick={() => navigate('/bill-of-entries')}
                         onMouseEnter={(e) => {
                             e.currentTarget.style.boxShadow = '0 10px 25px rgba(0,0,0,0.15)';
                             e.currentTarget.style.transform = 'translateY(-3px)';
                         }}
                         onMouseLeave={(e) => {
                             e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
                             e.currentTarget.style.transform = 'translateY(0)';
                         }}>
                        <div className="card-body" style={{ padding: '24px' }}>
                            <div className="d-flex justify-content-between align-items-start">
                                <div style={{ flex: 1 }}>
                                    <p className="text-muted mb-2" style={{ fontSize: '0.875rem', fontWeight: '500' }}>Pending Invoices</p>
                                    <h3 className="mb-2 fw-bold" style={{ fontSize: '2rem', color: '#f59e0b' }}>{stats.boe.pending_invoices}</h3>
                                    <small className="text-warning d-flex align-items-center" style={{ fontSize: '0.8rem' }}>
                                        <i className="bi bi-hourglass-split me-1"></i>
                                        No invoice number
                                    </small>
                                </div>
                                <div style={{
                                    width: '56px',
                                    height: '56px',
                                    borderRadius: '12px',
                                    background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    boxShadow: '0 4px 10px rgba(245, 158, 11, 0.3)'
                                }}>
                                    <i className="bi bi-file-earmark-excel text-white" style={{ fontSize: '1.5rem' }}></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

            </div>

            {/* Three Tables in One Row */}
            <div className="row g-3 mb-4">
                {/* Expiring Licenses Table */}
                <div className="col-xl-4">
                    <div className="card border-0 shadow-sm h-100">
                        <div className="card-header bg-white border-bottom">
                            <div className="d-flex justify-content-between align-items-center">
                                <h5 className="mb-0">
                                    <i className="bi bi-exclamation-triangle-fill text-warning me-2"></i>
                                    Licenses Expiring Soon
                                </h5>
                                <span className="badge bg-warning">{expiringLicenses.length}</span>
                            </div>
                        </div>
                        <div className="card-body p-0">
                            {expiringLicenses.length > 0 ? (
                                <div className="table-responsive" style={{maxHeight: '400px', overflowY: 'auto'}}>
                                    <table className="table table-hover table-sm mb-0">
                                        <thead className="table-light sticky-top">
                                        <tr>
                                            <th style={{width: '25%'}}>License Number</th>
                                            <th style={{width: '20%'}}>Expiry Date</th>
                                            <th style={{width: '20%'}} className="text-end">Balance (CIF)</th>
                                            <th style={{width: '25%'}}>SION Norms</th>
                                            <th style={{width: '10%'}} className="text-center">Days</th>
                                        </tr>
                                        </thead>
                                        <tbody>
                                        {expiringLicenses.map((license) => {
                                            const daysLeft = license.days_to_expiry || getDaysUntilExpiry(license.license_expiry_date);
                                            const urgencyClass = daysLeft <= 7 ? 'danger' : daysLeft <= 15 ? 'warning' : 'info';

                                            // SION norms from API response
                                            const uniqueNorms = license.sion_norms?.join(', ') || '-';

                                            return (
                                                <tr key={license.license_number}
                                                    style={{cursor: 'pointer'}}>
                                                    <td className="small">{license.license_number}</td>
                                                    <td className="small">{formatDate(license.license_expiry_date)}</td>
                                                    <td className="small text-end">
                                                        ${parseFloat(license.balance_cif || 0).toLocaleString('en-US', {
                                                        minimumFractionDigits: 2,
                                                        maximumFractionDigits: 2
                                                    })}
                                                    </td>
                                                    <td className="small text-truncate" style={{maxWidth: '150px'}}
                                                        title={uniqueNorms}>
                                                        {uniqueNorms}
                                                    </td>
                                                    <td className="text-center">
                                                        <span className={`badge bg-${urgencyClass}`}>
                                                            {daysLeft}
                                                        </span>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <div className="text-center p-4 text-muted">
                                    <i className="bi bi-check-circle fs-1 d-block mb-2 text-success"></i>
                                    No licenses expiring in next 30 days
                                </div>
                            )}
                        </div>
                        {expiringLicenses.length > 0 && (
                            <div className="card-footer bg-light text-center">
                                <button
                                    className="btn btn-sm btn-outline-primary"
                                    onClick={() => {
                                        const today = new Date().toISOString().split('T')[0];
                                        const thirtyDaysLater = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
                                        navigate(`/licenses?is_expired=False&is_null=False&license_expiry_date__gte=${today}&license_expiry_date__lte=${thirtyDaysLater}`);
                                    }}>
                                    View All Expiring Licenses
                                    <i className="bi bi-arrow-right ms-2"></i>
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {/* Recent Allotments */}
                <div className="col-xl-4">
                    <div className="card border-0 shadow-sm">
                        <div className="card-header bg-white border-bottom">
                            <div className="d-flex justify-content-between align-items-center">
                                <h5 className="mb-0">
                                    <i className="bi bi-clock-history text-info me-2"></i>
                                    Recent Allotments
                                </h5>
                                <button
                                    className="btn btn-sm btn-outline-info"
                                    onClick={() => navigate('/allotments')}>
                                    View All
                                </button>
                            </div>
                        </div>
                        <div className="card-body p-0">
                            {stats.allotments.recent.length > 0 ? (
                                <div className="table-responsive">
                                    <table className="table table-hover table-sm mb-0">
                                        <thead className="table-light">
                                        <tr>
                                            <th style={{width: '25%'}}>Date</th>
                                            <th style={{width: '35%'}}>Item Name</th>
                                            <th style={{width: '20%'}} className="text-end">Quantity</th>
                                            <th style={{width: '20%'}} className="text-end">CIF FC</th>
                                        </tr>
                                        </thead>
                                        <tbody>
                                        {stats.allotments.recent.map((allotment) => (
                                            <tr key={allotment.id}
                                                style={{cursor: 'pointer'}}
                                                onClick={() => navigate(`/allotments/${allotment.id}/allocate`)}>
                                                <td className="small">{formatDate(allotment.modified_on || allotment.created_at)}</td>
                                                <td className="small text-truncate" style={{maxWidth: '200px'}}
                                                    title={allotment.item_name}>
                                                    {allotment.item_name || '-'}
                                                </td>
                                                <td className="small text-end">
                                                    {parseFloat(allotment.required_quantity || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}
                                                </td>
                                                <td className="small text-end">
                                                    ${parseFloat(allotment.cif_fc || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}
                                                </td>
                                            </tr>
                                        ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <div className="text-center p-4 text-muted">
                                    <i className="bi bi-inbox fs-1 d-block mb-2"></i>
                                    No recent allotments
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Recent BOE */}
                <div className="col-xl-4">
                    <div className="card border-0 shadow-sm">
                        <div className="card-header bg-white border-bottom">
                            <div className="d-flex justify-content-between align-items-center">
                                <h5 className="mb-0">
                                    <i className="bi bi-receipt text-primary me-2"></i>
                                    Recent Bills of Entry
                                </h5>
                                <button
                                    className="btn btn-sm btn-outline-primary"
                                    onClick={() => navigate('/bill-of-entries')}>
                                    View All
                                </button>
                            </div>
                        </div>
                        <div className="card-body p-0">
                            {stats.boe.recent.length > 0 ? (
                                <div className="table-responsive">
                                    <table className="table table-hover table-sm mb-0">
                                        <thead className="table-light">
                                        <tr>
                                            <th style={{width: '30%'}}>BOE Number</th>
                                            <th style={{width: '25%'}}>BOE Date</th>
                                            <th style={{width: '45%'}}>Importer</th>
                                        </tr>
                                        </thead>
                                        <tbody>
                                        {stats.boe.recent.map((boe) => (
                                            <tr key={boe.id}
                                                style={{cursor: 'pointer'}}
                                                onClick={() => navigate(`/bill-of-entries/${boe.id}/edit`)}>
                                                <td className="small">{boe.bill_of_entry_number || '-'}</td>
                                                <td className="small">{formatDate(boe.bill_of_entry_date)}</td>
                                                <td className="small text-truncate" style={{maxWidth: '250px'}}
                                                    title={boe.company_name}>
                                                    {boe.company_name || '-'}
                                                </td>
                                            </tr>
                                        ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <div className="text-center p-4 text-muted">
                                    <i className="bi bi-inbox fs-1 d-block mb-2"></i>
                                    No recent BOE records
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
