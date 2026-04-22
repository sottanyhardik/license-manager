import {useEffect, useState} from "react";
import {useNavigate} from "react-router-dom";
import {toast} from 'react-toastify';
import api from "../api/axios";

function StatCard({icon, iconBg, label, value, valueColor, subLabel, subIcon, subColor = 'muted', onClick}) {
    return (
        <div
            className="card border-0 shadow-sm h-100 stat-card"
            style={{cursor: 'pointer', transition: 'transform 0.15s ease, box-shadow 0.15s ease'}}
            onClick={onClick}
            onMouseEnter={e => {
                e.currentTarget.style.transform = 'translateY(-3px)';
                e.currentTarget.style.boxShadow = '0 8px 24px rgba(0,0,0,0.13)';
            }}
            onMouseLeave={e => {
                e.currentTarget.style.transform = '';
                e.currentTarget.style.boxShadow = '';
            }}
        >
            <div className="card-body p-3">
                <div className="d-flex justify-content-between align-items-start">
                    <div style={{flex: 1, minWidth: 0}}>
                        <p className="text-muted mb-1" style={{
                            fontSize: '0.72rem', fontWeight: '600',
                            textTransform: 'uppercase', letterSpacing: '0.05em'
                        }}>
                            {label}
                        </p>
                        <h3 className="mb-1 fw-bold" style={{
                            fontSize: '1.75rem', lineHeight: 1,
                            color: valueColor || 'var(--text-dark)'
                        }}>
                            {value}
                        </h3>
                        {subLabel && (
                            <small className={`text-${subColor} d-flex align-items-center`}
                                   style={{fontSize: '0.73rem'}}>
                                {subIcon && <i className={`bi bi-${subIcon} me-1`}></i>}
                                {subLabel}
                            </small>
                        )}
                    </div>
                    <div style={{
                        width: '46px', height: '46px', borderRadius: '10px',
                        background: iconBg, flexShrink: 0,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <i className={`bi bi-${icon} text-white`} style={{fontSize: '1.25rem'}}></i>
                    </div>
                </div>
            </div>
        </div>
    );
}

function SectionHeader({icon, iconColor, title, badge, action}) {
    return (
        <div className="card-header bg-white border-bottom d-flex justify-content-between align-items-center py-3">
            <h6 className="mb-0 fw-semibold">
                <i className={`bi bi-${icon} me-2`} style={{color: iconColor}}></i>
                {title}
                {badge != null && (
                    <span className="badge ms-2" style={{
                        backgroundColor: iconColor + '22',
                        color: iconColor,
                        fontSize: '0.7rem'
                    }}>
                        {badge}
                    </span>
                )}
            </h6>
            {action}
        </div>
    );
}

function SkeletonRow() {
    return (
        <tr>
            {[1, 2, 3].map(i => (
                <td key={i}>
                    <div className="placeholder-glow">
                        <span className="placeholder col-10 rounded"></span>
                    </div>
                </td>
            ))}
        </tr>
    );
}

export default function Dashboard() {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState({
        licenses: {total: 0, active: 0, expired: 0, null_dfia: 0, expiring_soon: 0},
        allotments: {total: 0, recent: []},
        boe: {total: 0, pending_invoices: 0, recent: []},
    });
    const [expiringLicenses, setExpiringLicenses] = useState([]);
    const [boeMonthlyData, setBoeMonthlyData] = useState([]);

    useEffect(() => {
        fetchDashboardData();
    }, []);

    const fetchDashboardData = async () => {
        try {
            setLoading(true);
            const {data} = await api.get("dashboard/");
            setStats({
                licenses: data?.license_stats || {total: 0, active: 0, expired: 0, null_dfia: 0, expiring_soon: 0},
                allotments: data?.allotment_stats || {total: 0, recent: []},
                boe: data?.boe_stats || {total: 0, pending_invoices: 0, recent: []},
            });
            setExpiringLicenses(data?.expiring_licenses || []);
            setBoeMonthlyData(data?.boe_monthly_trend || []);
        } catch {
            toast.error("Failed to load dashboard data");
        } finally {
            setLoading(false);
        }
    };

    const fmtDate = (dateStr) => {
        if (!dateStr) return '-';
        const p = dateStr.split('-');
        return p.length === 3 && p[0].length === 4 ? `${p[2]}-${p[1]}-${p[0]}` : dateStr;
    };

    const daysUntil = (d) => Math.ceil((new Date(d) - new Date()) / 86400000);

    const today = new Date();
    const dateLabel = today.toLocaleDateString('en-GB', {
        weekday: 'long', day: '2-digit', month: 'long', year: 'numeric'
    });

    // BOE trend: max bar = 100% width
    const maxBoe = boeMonthlyData.length ? Math.max(...boeMonthlyData.map(d => d.count || 0), 1) : 1;

    if (loading) {
        return (
            <div className="container-fluid" style={{padding: '20px 24px', backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh'}}>
                {/* Header skeleton */}
                <div className="d-flex justify-content-between align-items-center mb-4">
                    <div>
                        <div className="placeholder-glow mb-1"><span className="placeholder col-3 rounded" style={{height: 24}}></span></div>
                        <div className="placeholder-glow"><span className="placeholder col-5 rounded" style={{height: 14}}></span></div>
                    </div>
                </div>
                {/* Stat card skeletons */}
                <div className="row g-3 mb-3">
                    {[...Array(5)].map((_, i) => (
                        <div className="col" key={i}>
                            <div className="card border-0 shadow-sm" style={{height: 100}}>
                                <div className="card-body p-3 placeholder-glow">
                                    <span className="placeholder col-8 rounded mb-2 d-block" style={{height: 12}}></span>
                                    <span className="placeholder col-5 rounded d-block" style={{height: 28}}></span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
                <div className="row g-3 mb-3">
                    {[...Array(3)].map((_, i) => (
                        <div className="col-xl-4" key={i}>
                            <div className="card border-0 shadow-sm" style={{height: 100}}>
                                <div className="card-body p-3 placeholder-glow">
                                    <span className="placeholder col-8 rounded mb-2 d-block" style={{height: 12}}></span>
                                    <span className="placeholder col-5 rounded d-block" style={{height: 28}}></span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div className="container-fluid" style={{padding: '20px 24px', backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh'}}>

            {/* Compact Header */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h4 className="mb-0 fw-bold" style={{color: 'var(--text-dark)'}}>
                        <i className="bi bi-speedometer2 me-2" style={{color: 'var(--primary-color)'}}></i>
                        Dashboard
                    </h4>
                    <small className="text-muted">{dateLabel}</small>
                </div>
                <div className="d-flex gap-2">
                    <button className="btn btn-sm btn-outline-secondary" onClick={fetchDashboardData}>
                        <i className="bi bi-arrow-clockwise me-1"></i>Refresh
                    </button>
                    <button className="btn btn-sm btn-outline-primary" onClick={() => navigate('/allotments/new')}>
                        <i className="bi bi-plus-lg me-1"></i>New Allotment
                    </button>
                    <button className="btn btn-sm btn-primary" onClick={() => navigate('/bill-of-entries/new')}>
                        <i className="bi bi-plus-lg me-1"></i>New BOE
                    </button>
                </div>
            </div>

            {/* License Stats — 5 equal columns */}
            <div className="row g-3 mb-3">
                <div className="col">
                    <StatCard
                        icon="file-earmark-text"
                        iconBg="linear-gradient(135deg,#4F46E5,#4338CA)"
                        label="Total Licenses"
                        value={stats.licenses.total}
                        subLabel="All licenses" subIcon="layers" subColor="muted"
                        onClick={() => navigate('/licenses?is_expired=all&is_null=all')}
                    />
                </div>
                <div className="col">
                    <StatCard
                        icon="check-circle"
                        iconBg="linear-gradient(135deg,#10b981,#059669)"
                        label="Active"
                        value={stats.licenses.active}
                        valueColor="var(--success-color)"
                        subLabel="Currently valid" subIcon="activity" subColor="success"
                        onClick={() => navigate('/licenses?is_expired=False&is_null=False')}
                    />
                </div>
                <div className="col">
                    <StatCard
                        icon="exclamation-triangle"
                        iconBg="linear-gradient(135deg,#ef4444,#dc2626)"
                        label="Expired"
                        value={stats.licenses.expired}
                        valueColor="var(--danger-color)"
                        subLabel="Need renewal" subIcon="x-circle" subColor="danger"
                        onClick={() => navigate('/licenses?is_expired=True&is_null=all')}
                    />
                </div>
                <div className="col">
                    <StatCard
                        icon="file-earmark-x"
                        iconBg="linear-gradient(135deg,#6b7280,#4b5563)"
                        label="Null DFIA"
                        value={stats.licenses.null_dfia}
                        valueColor="var(--text-secondary)"
                        subLabel="Balance < $500" subIcon="dash-circle" subColor="secondary"
                        onClick={() => navigate('/licenses?is_null=True&is_expired=all')}
                    />
                </div>
                <div className="col">
                    <StatCard
                        icon="hourglass-split"
                        iconBg="linear-gradient(135deg,#f59e0b,#d97706)"
                        label="Expiring Soon"
                        value={stats.licenses.expiring_soon}
                        valueColor="var(--warning-color)"
                        subLabel="Within 30 days" subIcon="clock-history" subColor="warning"
                        onClick={() => {
                            const t = new Date().toISOString().split('T')[0];
                            const t30 = new Date(Date.now() + 30 * 864e5).toISOString().split('T')[0];
                            navigate(`/licenses?is_expired=False&is_null=False&license_expiry_date__gte=${t}&license_expiry_date__lte=${t30}`);
                        }}
                    />
                </div>
            </div>

            {/* Operations Stats — 3 cards */}
            <div className="row g-3 mb-3">
                <div className="col-xl-4 col-md-6">
                    <StatCard
                        icon="diagram-3"
                        iconBg="linear-gradient(135deg,#06b6d4,#0891b2)"
                        label="Allotments"
                        value={stats.allotments.total}
                        subLabel="License allocations" subIcon="box-seam" subColor="info"
                        onClick={() => navigate('/allotments')}
                    />
                </div>
                <div className="col-xl-4 col-md-6">
                    <StatCard
                        icon="receipt-cutoff"
                        iconBg="linear-gradient(135deg,#6366F1,#4F46E5)"
                        label="Bills of Entry"
                        value={stats.boe.total}
                        subLabel="Total till date" subIcon="receipt" subColor="primary"
                        onClick={() => navigate('/bill-of-entries?is_invoice=all')}
                    />
                </div>
                <div className="col-xl-4 col-md-6">
                    <StatCard
                        icon="file-earmark-excel"
                        iconBg="linear-gradient(135deg,#f59e0b,#d97706)"
                        label="Pending Invoices"
                        value={stats.boe.pending_invoices}
                        valueColor="var(--warning-color)"
                        subLabel="No invoice number" subIcon="hourglass-split" subColor="warning"
                        onClick={() => navigate('/bill-of-entries')}
                    />
                </div>
            </div>

            {/* Tables Row */}
            <div className="row g-3 mb-3">
                {/* Expiring Licenses */}
                <div className="col-xl-5">
                    <div className="card border-0 shadow-sm h-100">
                        <SectionHeader
                            icon="exclamation-triangle-fill" iconColor="#f59e0b"
                            title="Expiring Soon"
                            badge={expiringLicenses.length}
                            action={
                                <button className="btn btn-sm btn-outline-warning" onClick={() => {
                                    const t = new Date().toISOString().split('T')[0];
                                    const t30 = new Date(Date.now() + 30 * 864e5).toISOString().split('T')[0];
                                    navigate(`/licenses?is_expired=False&is_null=False&license_expiry_date__gte=${t}&license_expiry_date__lte=${t30}`);
                                }}>
                                    View All <i className="bi bi-arrow-right ms-1"></i>
                                </button>
                            }
                        />
                        <div className="card-body p-0" style={{overflowY: 'auto', maxHeight: 340}}>
                            {expiringLicenses.length > 0 ? (
                                <table className="table table-hover table-sm mb-0">
                                    <thead className="table-light sticky-top">
                                    <tr>
                                        <th>License No.</th>
                                        <th>Expiry</th>
                                        <th className="text-end">Balance (CIF)</th>
                                        <th className="text-center">Days</th>
                                    </tr>
                                    </thead>
                                    <tbody>
                                    {expiringLicenses.map(lic => {
                                        const d = lic.days_to_expiry ?? daysUntil(lic.license_expiry_date);
                                        const color = d <= 7 ? 'danger' : d <= 15 ? 'warning' : 'info';
                                        return (
                                            <tr key={lic.license_number} style={{cursor: 'pointer'}}
                                                onClick={() => navigate(`/licenses?search=${lic.license_number}`)}>
                                                <td className="small fw-medium">{lic.license_number}</td>
                                                <td className="small">{fmtDate(lic.license_expiry_date)}</td>
                                                <td className="small text-end">
                                                    ${parseFloat(lic.balance_cif || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                                                </td>
                                                <td className="text-center">
                                                    <span className={`badge bg-${color}`}>{d}</span>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                    </tbody>
                                </table>
                            ) : (
                                <div className="text-center py-5 text-muted">
                                    <i className="bi bi-check-circle fs-2 d-block mb-2 text-success"></i>
                                    <small>No licenses expiring in next 30 days</small>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* BOE Monthly Trend */}
                <div className="col-xl-3">
                    <div className="card border-0 shadow-sm h-100">
                        <SectionHeader
                            icon="bar-chart-fill" iconColor="#4F46E5"
                            title="BOE Monthly Trend"
                        />
                        <div className="card-body" style={{overflowY: 'auto', maxHeight: 340}}>
                            {boeMonthlyData.length > 0 ? (
                                <div className="d-flex flex-column gap-2">
                                    {boeMonthlyData.map((row, i) => (
                                        <div key={i}>
                                            <div className="d-flex justify-content-between mb-1">
                                                <small className="text-muted fw-medium">{row.month || row.label || `Month ${i + 1}`}</small>
                                                <small className="fw-semibold">{row.count ?? row.value ?? 0}</small>
                                            </div>
                                            <div className="progress" style={{height: '6px', borderRadius: '3px'}}>
                                                <div
                                                    className="progress-bar"
                                                    style={{
                                                        width: `${((row.count ?? row.value ?? 0) / maxBoe) * 100}%`,
                                                        background: 'linear-gradient(90deg,#4F46E5,#6366F1)',
                                                        borderRadius: '3px'
                                                    }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-center py-5 text-muted">
                                    <i className="bi bi-bar-chart fs-2 d-block mb-2"></i>
                                    <small>No monthly trend data</small>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Recent BOE */}
                <div className="col-xl-4">
                    <div className="card border-0 shadow-sm h-100">
                        <SectionHeader
                            icon="receipt" iconColor="#6366F1"
                            title="Recent Bills of Entry"
                            action={
                                <button className="btn btn-sm btn-outline-primary"
                                        onClick={() => navigate('/bill-of-entries')}>
                                    View All
                                </button>
                            }
                        />
                        <div className="card-body p-0">
                            {stats.boe.recent.length > 0 ? (
                                <table className="table table-hover table-sm mb-0">
                                    <thead className="table-light">
                                    <tr>
                                        <th>BOE No.</th>
                                        <th>Date</th>
                                        <th>Importer</th>
                                    </tr>
                                    </thead>
                                    <tbody>
                                    {stats.boe.recent.map(boe => (
                                        <tr key={boe.id} style={{cursor: 'pointer'}}
                                            onClick={() => navigate(`/bill-of-entries/${boe.id}/edit`)}>
                                            <td className="small fw-medium">{boe.bill_of_entry_number || '-'}</td>
                                            <td className="small">{fmtDate(boe.bill_of_entry_date)}</td>
                                            <td className="small text-truncate" style={{maxWidth: 160}}
                                                title={boe.company_name}>
                                                {boe.company_name || '-'}
                                            </td>
                                        </tr>
                                    ))}
                                    </tbody>
                                </table>
                            ) : (
                                <div className="text-center py-5 text-muted">
                                    <i className="bi bi-inbox fs-2 d-block mb-2"></i>
                                    <small>No recent BOE records</small>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Recent Allotments */}
            <div className="row g-3">
                <div className="col-12">
                    <div className="card border-0 shadow-sm">
                        <SectionHeader
                            icon="clock-history" iconColor="#06b6d4"
                            title="Recent Allotments"
                            action={
                                <button className="btn btn-sm btn-outline-info"
                                        onClick={() => navigate('/allotments')}>
                                    View All
                                </button>
                            }
                        />
                        <div className="card-body p-0">
                            {stats.allotments.recent.length > 0 ? (
                                <table className="table table-hover table-sm mb-0">
                                    <thead className="table-light">
                                    <tr>
                                        <th>Date</th>
                                        <th>Item Name</th>
                                        <th className="text-end">Quantity</th>
                                        <th className="text-end">CIF FC</th>
                                    </tr>
                                    </thead>
                                    <tbody>
                                    {stats.allotments.recent.map(a => (
                                        <tr key={a.id} style={{cursor: 'pointer'}}
                                            onClick={() => navigate(`/allotments/${a.id}/allocate`)}>
                                            <td className="small">{fmtDate(a.modified_on || a.created_at)}</td>
                                            <td className="small text-truncate" style={{maxWidth: 300}}
                                                title={a.item_name}>
                                                {a.item_name || '-'}
                                            </td>
                                            <td className="small text-end">
                                                {parseFloat(a.required_quantity || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}
                                            </td>
                                            <td className="small text-end">
                                                ${parseFloat(a.cif_fc || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}
                                            </td>
                                        </tr>
                                    ))}
                                    </tbody>
                                </table>
                            ) : (
                                <div className="text-center py-4 text-muted">
                                    <i className="bi bi-inbox fs-2 d-block mb-2"></i>
                                    <small>No recent allotments</small>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

        </div>
    );
}
