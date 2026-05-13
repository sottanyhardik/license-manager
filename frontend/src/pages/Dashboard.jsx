import { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import {
    PageHeader,
    SectionHeader,
    StatCard,
    StatusBadge,
    Button,
    EmptyState,
    Skeleton,
} from "../components/ui";

function SkeletonStatCard() {
    return (
        <div className="tb-stat">
            <Skeleton variant="block" width={40} height={40} style={{ borderRadius: 6 }} />
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
                <Skeleton variant="text" width="60%" />
                <Skeleton variant="title" width="40%" height={22} />
                <Skeleton variant="text" width="50%" />
            </div>
        </div>
    );
}

export default function Dashboard() {
    const navigate = useNavigate();
    const { hasAnyRole, isSuperAdmin } = useContext(AuthContext);

    const canSeeAllotments = isSuperAdmin() || hasAnyRole(["ALLOTMENT_MANAGER", "ALLOTMENT_VIEWER", "REPORT_VIEWER"]);
    const canSeeBOE        = isSuperAdmin() || hasAnyRole(["BOE_MANAGER", "BOE_VIEWER", "ACCOUNT_ACCESS", "TL_GENERATE", "REPORT_VIEWER"]);
    const canSeeLicenses   = isSuperAdmin() || hasAnyRole(["LICENSE_MANAGER", "LICENSE_VIEWER", "TRADE_MANAGER", "TRADE_VIEWER", "REPORT_VIEWER"]);

    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState({
        licenses:   { total: 0, active: 0, expired: 0, null_dfia: 0, expiring_soon: 0 },
        allotments: { total: 0, recent: [] },
        boe:        { total: 0, pending_invoices: 0, recent: [] },
    });
    const [expiringLicenses, setExpiringLicenses] = useState([]);
    const [boeMonthlyData, setBoeMonthlyData] = useState([]);

    const fetchDashboardData = async () => {
        try {
            setLoading(true);
            const { data } = await api.get("dashboard/");
            setStats({
                licenses:   data?.license_stats   || { total: 0, active: 0, expired: 0, null_dfia: 0, expiring_soon: 0 },
                allotments: data?.allotment_stats || { total: 0, recent: [] },
                boe:        data?.boe_stats       || { total: 0, pending_invoices: 0, recent: [] },
            });
            setExpiringLicenses(data?.expiring_licenses || []);
            setBoeMonthlyData(data?.boe_monthly_trend || []);
        } catch {
            toast.error("Failed to load dashboard data");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchDashboardData(); }, []);

    const fmtDate = (s) => {
        if (!s) return "—";
        const p = s.split("-");
        return p.length === 3 && p[0].length === 4 ? `${p[2]}-${p[1]}-${p[0]}` : s;
    };
    const daysUntil = (d) => Math.ceil((new Date(d) - new Date()) / 86400000);
    const today = new Date();
    const dateLabel = today.toLocaleDateString("en-GB", { weekday: "long", day: "2-digit", month: "long", year: "numeric" });
    const maxBoe = boeMonthlyData.length ? Math.max(...boeMonthlyData.map(d => d.count || 0), 1) : 1;

    const goExpiringSoon = () => {
        const t = new Date().toISOString().split("T")[0];
        const t30 = new Date(Date.now() + 30 * 864e5).toISOString().split("T")[0];
        navigate(`/licenses?is_expired=False&is_null=False&license_expiry_date__gte=${t}&license_expiry_date__lte=${t30}`);
    };

    if (loading) {
        return (
            <>
                <PageHeader
                    pretitle="Overview"
                    title="Dashboard"
                    description={dateLabel}
                    actions={
                        <>
                            <Button variant="outline-secondary" size="sm" icon="arrow-clockwise" disabled>Refresh</Button>
                            <Button variant="primary" size="sm" icon="plus-lg" disabled>New BOE</Button>
                        </>
                    }
                />
                <div className="row g-3 mb-3">
                    {[...Array(5)].map((_, i) => (
                        <div className="col-md-6 col-lg-4 col-xl" key={i}><SkeletonStatCard /></div>
                    ))}
                </div>
                <div className="row g-3 mb-3">
                    {[...Array(3)].map((_, i) => (
                        <div className="col-xl-4 col-md-6" key={i}><SkeletonStatCard /></div>
                    ))}
                </div>
            </>
        );
    }

    return (
        <>
            <PageHeader
                pretitle="Overview"
                title="Dashboard"
                description={dateLabel}
                actions={
                    <>
                        <Button variant="outline-secondary" size="sm" icon="arrow-clockwise" onClick={fetchDashboardData}>
                            Refresh
                        </Button>
                        <Button variant="outline-primary" size="sm" icon="plus-lg" onClick={() => navigate("/allotments/create")}>
                            New Allotment
                        </Button>
                        <Button variant="primary" size="sm" icon="plus-lg" onClick={() => navigate("/bill-of-entries/create")}>
                            New BOE
                        </Button>
                    </>
                }
            />

            {/* License KPIs */}
            {canSeeLicenses && (
                <div className="row g-3 mb-3">
                    <div className="col-md-6 col-lg-4 col-xl">
                        <StatCard
                            label="Total Licenses"
                            value={stats.licenses.total}
                            icon="file-earmark-text"
                            tone="primary"
                            onClick={() => navigate("/licenses?is_expired=all&is_null=all")}
                        />
                    </div>
                    <div className="col-md-6 col-lg-4 col-xl">
                        <StatCard
                            label="Active"
                            value={stats.licenses.active}
                            icon="check-circle"
                            tone="success"
                            onClick={() => navigate("/licenses?is_expired=False&is_null=False")}
                        />
                    </div>
                    <div className="col-md-6 col-lg-4 col-xl">
                        <StatCard
                            label="Expired"
                            value={stats.licenses.expired}
                            icon="exclamation-triangle"
                            tone="danger"
                            onClick={() => navigate("/licenses?is_expired=True&is_null=all")}
                        />
                    </div>
                    <div className="col-md-6 col-lg-4 col-xl">
                        <StatCard
                            label="Null DFIA"
                            value={stats.licenses.null_dfia}
                            icon="file-earmark-x"
                            tone="neutral"
                            onClick={() => navigate("/licenses?is_null=True&is_expired=all")}
                        />
                    </div>
                    <div className="col-md-6 col-lg-4 col-xl">
                        <StatCard
                            label="Expiring Soon"
                            value={stats.licenses.expiring_soon}
                            icon="hourglass-split"
                            tone="warning"
                            onClick={goExpiringSoon}
                        />
                    </div>
                </div>
            )}

            {/* Operations KPIs */}
            {(canSeeAllotments || canSeeBOE) && (
                <div className="row g-3 mb-3">
                    {canSeeAllotments && (
                        <div className="col-xl-4 col-md-6">
                            <StatCard
                                label="Allotments"
                                value={stats.allotments.total}
                                icon="diagram-3"
                                tone="info"
                                onClick={() => navigate("/allotments")}
                            />
                        </div>
                    )}
                    {canSeeBOE && (
                        <div className="col-xl-4 col-md-6">
                            <StatCard
                                label="Bills of Entry"
                                value={stats.boe.total}
                                icon="receipt-cutoff"
                                tone="primary"
                                onClick={() => navigate("/bill-of-entries?is_invoice=all")}
                            />
                        </div>
                    )}
                    {canSeeBOE && (
                        <div className="col-xl-4 col-md-6">
                            <StatCard
                                label="Pending Invoices"
                                value={stats.boe.pending_invoices}
                                icon="file-earmark-excel"
                                tone="warning"
                                onClick={() => navigate("/bill-of-entries")}
                            />
                        </div>
                    )}
                </div>
            )}

            {/* Detail panels */}
            <div className="row g-3 mb-3">
                {canSeeLicenses && (
                    <div className="col-xl-5">
                        <div className="card h-100">
                            <div className="card-header">
                                <SectionHeader
                                    icon="exclamation-triangle-fill"
                                    iconTone="warning"
                                    title="Expiring Soon"
                                    subtitle={`${expiringLicenses.length} licence${expiringLicenses.length === 1 ? "" : "s"} in next 30 days`}
                                    actions={
                                        <Button variant="outline-warning" size="sm" iconRight="arrow-right" onClick={goExpiringSoon}>
                                            View All
                                        </Button>
                                    }
                                />
                            </div>
                            <div className="card-body p-0" style={{ overflowY: "auto", maxHeight: 340 }}>
                                {expiringLicenses.length > 0 ? (
                                    <table className="table table-hover mb-0">
                                        <thead>
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
                                                const tone = d <= 7 ? "danger" : d <= 15 ? "warning" : "info";
                                                return (
                                                    <tr key={lic.license_number} style={{ cursor: "pointer" }}
                                                        onClick={() => navigate(`/licenses?search=${lic.license_number}`)}>
                                                        <td className="fw-medium">{lic.license_number}</td>
                                                        <td>{fmtDate(lic.license_expiry_date)}</td>
                                                        <td className="text-end">
                                                            ${parseFloat(lic.balance_cif || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                                        </td>
                                                        <td className="text-center">
                                                            <StatusBadge tone={tone}>{d}</StatusBadge>
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                ) : (
                                    <EmptyState
                                        icon="check-circle"
                                        title="All clear"
                                        description="No licenses expiring in the next 30 days"
                                    />
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {canSeeBOE && (
                    <div className="col-xl-3">
                        <div className="card h-100">
                            <div className="card-header">
                                <SectionHeader icon="bar-chart-fill" iconTone="primary" title="BOE Monthly Trend" />
                            </div>
                            <div className="card-body" style={{ overflowY: "auto", maxHeight: 340 }}>
                                {boeMonthlyData.length > 0 ? (
                                    <div className="d-flex flex-column" style={{ gap: 10 }}>
                                        {boeMonthlyData.map((row, i) => {
                                            const v = row.count ?? row.value ?? 0;
                                            return (
                                                <div key={i}>
                                                    <div className="d-flex justify-content-between" style={{ marginBottom: 4 }}>
                                                        <small style={{ color: "var(--tb-text-secondary)", fontWeight: 500 }}>
                                                            {row.month || row.label || `Month ${i + 1}`}
                                                        </small>
                                                        <small style={{ fontWeight: 600 }}>{v}</small>
                                                    </div>
                                                    <div style={{ height: 6, borderRadius: 3, background: "var(--tb-sunken)", overflow: "hidden" }}>
                                                        <div style={{
                                                            width: `${(v / maxBoe) * 100}%`,
                                                            height: "100%",
                                                            background: "var(--tb-brand)",
                                                        }}/>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                ) : (
                                    <EmptyState icon="bar-chart" title="No data yet" />
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {canSeeBOE && (
                    <div className="col-xl-4">
                        <div className="card h-100">
                            <div className="card-header">
                                <SectionHeader
                                    icon="receipt"
                                    iconTone="primary"
                                    title="Recent Bills of Entry"
                                    actions={
                                        <Button variant="outline-primary" size="sm" onClick={() => navigate("/bill-of-entries")}>
                                            View All
                                        </Button>
                                    }
                                />
                            </div>
                            <div className="card-body p-0">
                                {stats.boe.recent.length > 0 ? (
                                    <table className="table table-hover mb-0">
                                        <thead>
                                            <tr>
                                                <th>BOE No.</th>
                                                <th>Date</th>
                                                <th>Importer</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {stats.boe.recent.map(boe => (
                                                <tr key={boe.id} style={{ cursor: "pointer" }}
                                                    onClick={() => navigate(`/bill-of-entries/${boe.id}/edit`)}>
                                                    <td className="fw-medium">{boe.bill_of_entry_number || "—"}</td>
                                                    <td>{fmtDate(boe.bill_of_entry_date)}</td>
                                                    <td className="truncate" style={{ maxWidth: 180 }} title={boe.company_name}>
                                                        {boe.company_name || "—"}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                ) : (
                                    <EmptyState icon="inbox" title="No recent BOE records" />
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {canSeeAllotments && (
                <div className="row g-3">
                    <div className="col-12">
                        <div className="card">
                            <div className="card-header">
                                <SectionHeader
                                    icon="clock-history"
                                    iconTone="info"
                                    title="Recent Allotments"
                                    actions={
                                        <Button variant="outline-info" size="sm" onClick={() => navigate("/allotments")}>
                                            View All
                                        </Button>
                                    }
                                />
                            </div>
                            <div className="card-body p-0">
                                {stats.allotments.recent.length > 0 ? (
                                    <table className="table table-hover mb-0">
                                        <thead>
                                            <tr>
                                                <th>Date</th>
                                                <th>Item Name</th>
                                                <th className="text-end">Quantity</th>
                                                <th className="text-end">CIF FC</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {stats.allotments.recent.map(a => (
                                                <tr key={a.id} style={{ cursor: "pointer" }}
                                                    onClick={() => navigate(`/allotments/${a.id}/allocate`)}>
                                                    <td>{fmtDate(a.modified_on || a.created_at)}</td>
                                                    <td className="truncate" style={{ maxWidth: 360 }} title={a.item_name}>
                                                        {a.item_name || "—"}
                                                    </td>
                                                    <td className="text-end">
                                                        {parseFloat(a.required_quantity || 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                                                    </td>
                                                    <td className="text-end">
                                                        ${parseFloat(a.cif_fc || 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                ) : (
                                    <EmptyState icon="inbox" title="No recent allotments" />
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
