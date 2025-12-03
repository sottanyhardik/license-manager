import {useState, useEffect} from "react";
import {useNavigate} from "react-router-dom";
import api from "../api/axios";

export default function Dashboard() {
    const navigate = useNavigate();

    // Separate loading states for lazy loading
    const [statsLoading, setStatsLoading] = useState(true);
    const [expiringLoading, setExpiringLoading] = useState(true);
    const [boeChartLoading, setBoeChartLoading] = useState(true);
    const [recentActivityLoading, setRecentActivityLoading] = useState(true);

    const [stats, setStats] = useState({
        licenses: {total: 0, active: 0, expired: 0, null_dfia: 0, expiring_soon: 0},
        allotments: {total: 0, recent: []},
        boe: {total: 0, pending_invoices: 0, recent: []},
        trade: {imports: 0, exports: 0}
    });
    const [expiringLicenses, setExpiringLicenses] = useState([]);
    const [boeMonthlyData, setBoeMonthlyData] = useState([]);

    useEffect(() => {
        // Lazy load each section independently for faster page load
        fetchLicenseStats();
        fetchExpiringLicenses();
        fetchBOEChart();
        fetchRecentActivity();
    }, []);

    // Fetch license statistics (fastest - loads first)
    const fetchLicenseStats = async () => {
        try {
            setStatsLoading(true);

            // Get today's date for comparison
            const today = new Date().toISOString().split('T')[0];
            const thirtyDaysFromNow = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

            // Get counts with correct business logic
            // Total Allotments = allotments without BOE (is_boe=False)
            // Total BOE = all BOE records (no filter)
            // Pending Invoices = BOE where invoice_number is null/blank
            const [allotmentsRes, boeRes, pendingInvoicesRes] = await Promise.all([
                api.get("/allotments/?page=1&page_size=1&is_boe=False"),
                api.get("/bill-of-entries/?page=1&page_size=1"),
                api.get("/bill-of-entries/?page=1&page_size=1&invoice_number__isnull=True")
            ]);

            // Active = expiry > today AND balance_cif > 500
            // Expired = expiry < today AND balance_cif > 500
            // Null = balance_cif < 500
            // Expiring Soon = expiry between today and 30 days from now
            const [activeRes, expiredRes, nullRes, expiringRes] = await Promise.all([
                api.get(`/licenses/?page=1&page_size=1&license_expiry_date__gte=${today}&balance_cif__gt=500`),
                api.get(`/licenses/?page=1&page_size=1&license_expiry_date__lt=${today}&balance_cif__gt=500`),
                api.get(`/licenses/?page=1&page_size=1&balance_cif__lt=500`),
                api.get(`/licenses/?page=1&page_size=1&license_expiry_date__gte=${today}&license_expiry_date__lte=${thirtyDaysFromNow}`)
            ]);

            const activeCount = activeRes.data.count || 0;
            const expiredCount = expiredRes.data.count || 0;
            const nullCount = nullRes.data.count || 0;
            const totalCount = activeCount + expiredCount + nullCount;

            setStats(prev => ({
                ...prev,
                licenses: {
                    total: totalCount,
                    active: activeCount,
                    expired: expiredCount,
                    null_dfia: nullCount,
                    expiring_soon: expiringRes.data.count || 0
                },
                allotments: {
                    ...prev.allotments,
                    total: allotmentsRes.data.count || 0
                },
                boe: {
                    ...prev.boe,
                    total: boeRes.data.count || 0,
                    pending_invoices: pendingInvoicesRes.data.count || 0
                },
                trade: {
                    imports: boeRes.data.count || 0,
                    exports: allotmentsRes.data.count || 0
                }
            }));

        } catch (error) {
            console.error("Error fetching license stats:", error);
        } finally {
            setStatsLoading(false);
        }
    };

    // Fetch expiring licenses table
    const fetchExpiringLicenses = async () => {
        try {
            setExpiringLoading(true);
            const response = await api.get("/expiring-licenses/?page_size=10&ordering=expiry_date");
            setExpiringLicenses(response.data.results || response.data || []);
        } catch (error) {
            console.error("Error fetching expiring licenses:", error);
        } finally {
            setExpiringLoading(false);
        }
    };

    // Fetch BOE data for chart
    const fetchBOEChart = async () => {
        try {
            setBoeChartLoading(true);

            // Get last 6 months of BOE data
            const sixMonthsAgo = new Date();
            sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);
            const dateFilter = sixMonthsAgo.toISOString().split('T')[0];

            const response = await api.get(`/bill-of-entries/?boe_date__gte=${dateFilter}&page_size=500`);
            const boeList = response.data.results || response.data || [];
            const monthlyData = calculateMonthlyBOE(boeList);
            setBoeMonthlyData(monthlyData);

        } catch (error) {
            console.error("Error fetching BOE chart data:", error);
        } finally {
            setBoeChartLoading(false);
        }
    };

    // Fetch recent activity
    const fetchRecentActivity = async () => {
        try {
            setRecentActivityLoading(true);

            const [allotmentsRes, boeRes] = await Promise.all([
                api.get("/allotments/?page_size=5&ordering=-created_at&is_boe=False"),
                api.get("/bill-of-entries/?page_size=5&ordering=-boe_date")
            ]);

            setStats(prev => ({
                ...prev,
                allotments: {
                    ...prev.allotments,
                    recent: allotmentsRes.data.results || []
                },
                boe: {
                    ...prev.boe,
                    recent: boeRes.data.results || []
                }
            }));

        } catch (error) {
            console.error("Error fetching recent activity:", error);
        } finally {
            setRecentActivityLoading(false);
        }
    };

    const calculateMonthlyBOE = (boeList) => {
        const months = [];
        const now = new Date();

        // Get last 6 months
        for (let i = 5; i >= 0; i--) {
            const date = new Date(now.getFullYear(), now.getMonth() - i, 1);
            months.push({
                month: date.toLocaleDateString('en-US', {month: 'short', year: 'numeric'}),
                count: 0,
                value: 0
            });
        }

        // Count BOEs per month
        boeList.forEach(boe => {
            const boeDate = new Date(boe.boe_date);
            const monthKey = boeDate.toLocaleDateString('en-US', {month: 'short', year: 'numeric'});
            const monthData = months.find(m => m.month === monthKey);
            if (monthData) {
                monthData.count++;
            }
        });

        return months;
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return '-';
        return new Date(dateStr).toLocaleDateString('en-IN');
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

    return (
        <div className="container-fluid mt-4 px-4">
            {/* Header */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h2 className="mb-1">Dashboard Overview</h2>
                    <p className="text-muted mb-0">Welcome to License Manager</p>
                </div>
                <div className="text-muted">
                    <i className="bi bi-calendar-event me-2"></i>
                    {new Date().toLocaleDateString('en-IN', {weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'})}
                </div>
            </div>

            {/* Stats Cards Row 1 - Licenses */}
            <div className="row g-3 mb-4">
                <div className="col-xl col-lg-4 col-md-6">
                    <div className="card border-0 shadow-sm h-100">
                        <div className="card-body">
                            {statsLoading ? (
                                <LoadingSkeleton />
                            ) : (
                                <div className="d-flex justify-content-between align-items-start">
                                    <div>
                                        <p className="text-muted mb-1 small">Total Licenses</p>
                                        <h3 className="mb-0 fw-bold">{stats.licenses.total}</h3>
                                        <small className="text-success">
                                            <i className="bi bi-check-circle me-1"></i>
                                            All licenses
                                        </small>
                                    </div>
                                    <div className="bg-primary bg-opacity-10 p-3 rounded">
                                        <i className="bi bi-file-earmark-text text-primary fs-4"></i>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="col-xl-3 col-md-6">
                    <div className="card border-0 shadow-sm h-100">
                        <div className="card-body">
                            {statsLoading ? (
                                <LoadingSkeleton />
                            ) : (
                                <div className="d-flex justify-content-between align-items-start">
                                    <div>
                                        <p className="text-muted mb-1 small">Active Licenses</p>
                                        <h3 className="mb-0 fw-bold text-success">{stats.licenses.active}</h3>
                                        <small className="text-muted">
                                            <i className="bi bi-activity me-1"></i>
                                            Currently valid
                                        </small>
                                    </div>
                                    <div className="bg-success bg-opacity-10 p-3 rounded">
                                        <i className="bi bi-check-circle text-success fs-4"></i>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="col-xl-3 col-md-6">
                    <div className="card border-0 shadow-sm h-100">
                        <div className="card-body">
                            {statsLoading ? (
                                <LoadingSkeleton />
                            ) : (
                                <div className="d-flex justify-content-between align-items-start">
                                    <div>
                                        <p className="text-muted mb-1 small">Expired Licenses</p>
                                        <h3 className="mb-0 fw-bold text-danger">{stats.licenses.expired}</h3>
                                        <small className="text-muted">
                                            <i className="bi bi-x-circle me-1"></i>
                                            Need renewal
                                        </small>
                                    </div>
                                    <div className="bg-danger bg-opacity-10 p-3 rounded">
                                        <i className="bi bi-exclamation-triangle text-danger fs-4"></i>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="col-xl col-lg-4 col-md-6">
                    <div className="card border-0 shadow-sm h-100">
                        <div className="card-body">
                            {statsLoading ? (
                                <LoadingSkeleton />
                            ) : (
                                <div className="d-flex justify-content-between align-items-start">
                                    <div>
                                        <p className="text-muted mb-1 small">Null DFIA</p>
                                        <h3 className="mb-0 fw-bold text-secondary">{stats.licenses.null_dfia}</h3>
                                        <small className="text-muted">
                                            <i className="bi bi-dash-circle me-1"></i>
                                            Balance &lt; $500
                                        </small>
                                    </div>
                                    <div className="bg-secondary bg-opacity-10 p-3 rounded">
                                        <i className="bi bi-file-earmark-x text-secondary fs-4"></i>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="col-xl col-lg-4 col-md-6">
                    <div className="card border-0 shadow-sm h-100 border-warning border-2">
                        <div className="card-body">
                            {statsLoading ? (
                                <LoadingSkeleton />
                            ) : (
                                <div className="d-flex justify-content-between align-items-start">
                                    <div>
                                        <p className="text-muted mb-1 small">Expiring Soon</p>
                                        <h3 className="mb-0 fw-bold text-warning">{stats.licenses.expiring_soon}</h3>
                                        <small className="text-muted">
                                            <i className="bi bi-clock-history me-1"></i>
                                            Within 30 days
                                        </small>
                                    </div>
                                    <div className="bg-warning bg-opacity-10 p-3 rounded">
                                        <i className="bi bi-hourglass-split text-warning fs-4"></i>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Stats Cards Row 2 - Operations */}
            <div className="row g-3 mb-4">
                <div className="col-xl-4 col-md-6">
                    <div className="card border-0 shadow-sm h-100">
                        <div className="card-body">
                            {statsLoading ? (
                                <LoadingSkeleton />
                            ) : (
                                <div className="d-flex justify-content-between align-items-start">
                                    <div>
                                        <p className="text-muted mb-1 small">Total Allotments</p>
                                    <h3 className="mb-0 fw-bold">{stats.allotments.total}</h3>
                                    <small className="text-info">
                                        <i className="bi bi-box-seam me-1"></i>
                                        License allocations
                                    </small>
                                </div>
                                <div className="bg-info bg-opacity-10 p-3 rounded">
                                    <i className="bi bi-diagram-3 text-info fs-4"></i>
                                </div>
                            </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="col-xl-4 col-md-6">
                    <div className="card border-0 shadow-sm h-100">
                        <div className="card-body">
                            {statsLoading ? (
                                <LoadingSkeleton />
                            ) : (
                                <div className="d-flex justify-content-between align-items-start">
                                    <div>
                                        <p className="text-muted mb-1 small">Bills of Entry</p>
                                    <h3 className="mb-0 fw-bold">{stats.boe.total}</h3>
                                    <small className="text-primary">
                                        <i className="bi bi-receipt me-1"></i>
                                        All till date
                                    </small>
                                </div>
                                <div className="bg-primary bg-opacity-10 p-3 rounded">
                                    <i className="bi bi-receipt-cutoff text-primary fs-4"></i>
                                </div>
                            </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="col-xl-4 col-md-6">
                    <div className="card border-0 shadow-sm h-100">
                        <div className="card-body">
                            {statsLoading ? (
                                <LoadingSkeleton />
                            ) : (
                                <div className="d-flex justify-content-between align-items-start">
                                    <div>
                                        <p className="text-muted mb-1 small">Pending Invoices</p>
                                        <h3 className="mb-0 fw-bold text-warning">{stats.boe.pending_invoices}</h3>
                                        <small className="text-muted">
                                            <i className="bi bi-hourglass-split me-1"></i>
                                            No invoice number
                                        </small>
                                    </div>
                                    <div className="bg-warning bg-opacity-10 p-3 rounded">
                                        <i className="bi bi-file-earmark-excel text-warning fs-4"></i>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="col-xl-4 col-md-6">
                    <div className="card border-0 shadow-sm h-100">
                        <div className="card-body">
                            {statsLoading ? (
                                <LoadingSkeleton />
                            ) : (
                                <div className="d-flex justify-content-between align-items-start">
                                    <div>
                                        <p className="text-muted mb-1 small">Trade Operations</p>
                                        <h3 className="mb-0 fw-bold">{stats.allotments.total + stats.boe.total}</h3>
                                        <small className="text-success">
                                            <i className="bi bi-arrow-left-right me-1"></i>
                                            Total transactions
                                        </small>
                                    </div>
                                    <div className="bg-success bg-opacity-10 p-3 rounded">
                                        <i className="bi bi-globe text-success fs-4"></i>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Charts and Tables Row */}
            <div className="row g-3 mb-4">
                {/* Expiring Licenses Table */}
                <div className="col-xl-6">
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
                                                <th style={{width: '35%'}}>License Number</th>
                                                <th style={{width: '30%'}}>Exporter</th>
                                                <th style={{width: '20%'}}>Expiry Date</th>
                                                <th style={{width: '15%'}} className="text-center">Days Left</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {expiringLicenses.map((license) => {
                                                const daysLeft = getDaysUntilExpiry(license.expiry_date);
                                                const urgencyClass = daysLeft <= 7 ? 'danger' : daysLeft <= 15 ? 'warning' : 'info';
                                                return (
                                                    <tr key={license.id}
                                                        style={{cursor: 'pointer'}}
                                                        onClick={() => navigate(`/licenses/${license.id}`)}>
                                                        <td className="small">{license.license_number}</td>
                                                        <td className="small text-truncate" style={{maxWidth: '150px'}}>
                                                            {license.exporter_name || '-'}
                                                        </td>
                                                        <td className="small">{formatDate(license.expiry_date)}</td>
                                                        <td className="text-center">
                                                            <span className={`badge bg-${urgencyClass}`}>
                                                                {daysLeft} days
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
                                    onClick={() => navigate('/licenses?filter=expiring_soon')}>
                                    View All Expiring Licenses
                                    <i className="bi bi-arrow-right ms-2"></i>
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {/* BOE Monthly Chart */}
                <div className="col-xl-6">
                    <div className="card border-0 shadow-sm h-100">
                        <div className="card-header bg-white border-bottom">
                            <h5 className="mb-0">
                                <i className="bi bi-bar-chart-fill text-primary me-2"></i>
                                Bill of Entry - Monthly Trend
                            </h5>
                        </div>
                        <div className="card-body">
                            <div className="chart-container" style={{height: '300px'}}>
                                {boeMonthlyData.length > 0 ? (
                                    <div className="d-flex align-items-end justify-content-between h-100 gap-2">
                                        {boeMonthlyData.map((data, idx) => {
                                            const maxCount = Math.max(...boeMonthlyData.map(d => d.count), 1);
                                            const heightPercent = (data.count / maxCount) * 100;
                                            return (
                                                <div key={idx} className="flex-fill text-center">
                                                    <div className="mb-2 fw-bold text-primary">{data.count}</div>
                                                    <div
                                                        className="bg-primary bg-gradient rounded-top"
                                                        style={{
                                                            height: `${heightPercent}%`,
                                                            minHeight: data.count > 0 ? '20px' : '5px',
                                                            transition: 'height 0.3s ease'
                                                        }}
                                                        title={`${data.month}: ${data.count} BOEs`}>
                                                    </div>
                                                    <div className="mt-2 small text-muted" style={{fontSize: '0.75rem'}}>
                                                        {data.month.split(' ')[0]}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                ) : (
                                    <div className="text-center text-muted p-5">
                                        <i className="bi bi-graph-up fs-1 d-block mb-2"></i>
                                        No BOE data available
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Recent Activity Tables */}
            <div className="row g-3 mb-4">
                {/* Recent Allotments */}
                <div className="col-xl-6">
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
                                                <th>ID</th>
                                                <th>Product</th>
                                                <th>Quantity</th>
                                                <th>Date</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {stats.allotments.recent.map((allotment) => (
                                                <tr key={allotment.id}
                                                    style={{cursor: 'pointer'}}
                                                    onClick={() => navigate(`/allotments/${allotment.id}/action`)}>
                                                    <td className="small">#{allotment.id}</td>
                                                    <td className="small text-truncate" style={{maxWidth: '200px'}}>
                                                        {allotment.product_description || '-'}
                                                    </td>
                                                    <td className="small">{allotment.required_quantity || 0}</td>
                                                    <td className="small">{formatDate(allotment.created_at)}</td>
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
                <div className="col-xl-6">
                    <div className="card border-0 shadow-sm">
                        <div className="card-header bg-white border-bottom">
                            <div className="d-flex justify-content-between align-items-center">
                                <h5 className="mb-0">
                                    <i className="bi bi-receipt text-primary me-2"></i>
                                    Recent Bills of Entry
                                </h5>
                                <button
                                    className="btn btn-sm btn-outline-primary"
                                    onClick={() => navigate('/bill-of-entry')}>
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
                                                <th>BOE Number</th>
                                                <th>Importer</th>
                                                <th>Value</th>
                                                <th>Date</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {stats.boe.recent.map((boe) => (
                                                <tr key={boe.id}
                                                    style={{cursor: 'pointer'}}
                                                    onClick={() => navigate(`/bill-of-entry/${boe.id}`)}>
                                                    <td className="small">{boe.boe_number || '-'}</td>
                                                    <td className="small text-truncate" style={{maxWidth: '200px'}}>
                                                        {boe.importer_name || '-'}
                                                    </td>
                                                    <td className="small">
                                                        {boe.total_value ? `₹${parseFloat(boe.total_value).toLocaleString('en-IN')}` : '-'}
                                                    </td>
                                                    <td className="small">{formatDate(boe.boe_date)}</td>
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

            {/* Quick Actions */}
            <div className="row g-3 mb-4">
                <div className="col-12">
                    <div className="card border-0 shadow-sm">
                        <div className="card-header bg-white border-bottom">
                            <h5 className="mb-0">
                                <i className="bi bi-lightning-fill text-warning me-2"></i>
                                Quick Actions
                            </h5>
                        </div>
                        <div className="card-body">
                            <div className="row g-3">
                                <div className="col-md-3">
                                    <button
                                        className="btn btn-outline-primary w-100"
                                        onClick={() => navigate('/licenses/new')}>
                                        <i className="bi bi-plus-circle me-2"></i>
                                        Add License
                                    </button>
                                </div>
                                <div className="col-md-3">
                                    <button
                                        className="btn btn-outline-info w-100"
                                        onClick={() => navigate('/allotments/new')}>
                                        <i className="bi bi-diagram-3 me-2"></i>
                                        Create Allotment
                                    </button>
                                </div>
                                <div className="col-md-3">
                                    <button
                                        className="btn btn-outline-success w-100"
                                        onClick={() => navigate('/bill-of-entry/new')}>
                                        <i className="bi bi-receipt me-2"></i>
                                        Add BOE
                                    </button>
                                </div>
                                <div className="col-md-3">
                                    <button
                                        className="btn btn-outline-secondary w-100"
                                        onClick={() => navigate('/reports')}>
                                        <i className="bi bi-file-earmark-bar-graph me-2"></i>
                                        View Reports
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
