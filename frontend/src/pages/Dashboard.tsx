import React, { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
    RefreshCw, Plus, FileText, CheckCircle2, AlertTriangle, FileX,
    Hourglass, Network, ReceiptText, FileSpreadsheet, BarChart3,
    Receipt, Clock, Inbox, ArrowRight,
} from "lucide-react";

import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import PageHeader from "@/components/PageHeader";
import StatCard from "@/components/StatCard";
import EmptyState from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function SkeletonStat() {
    return (
        <div className="flex items-start gap-3.5 rounded-xl border border-border bg-card p-4 shadow-sm">
            <Skeleton className="size-10 rounded-lg" />
            <div className="flex-1 space-y-2">
                <Skeleton className="h-3 w-3/5" />
                <Skeleton className="h-6 w-2/5" />
            </div>
        </div>
    );
}

function SectionTitle({ icon: Icon, tone = "primary", title, subtitle, action }: { icon: React.ElementType; tone?: string; title: React.ReactNode; subtitle?: React.ReactNode; action?: React.ReactNode }) {
    const toneCls = {
        primary: "bg-primary/10 text-primary",
        warning: "bg-warning/10 text-warning",
        info: "bg-info/10 text-info",
    }[tone];
    return (
        <div className="flex items-center gap-3">
            <span className={`flex size-8 items-center justify-center rounded-lg ${toneCls}`}>
                <Icon className="size-4" />
            </span>
            <div className="flex-1">
                <div className="text-sm font-semibold tracking-tight text-foreground">{title}</div>
                {subtitle && <div className="text-xs text-muted-foreground">{subtitle}</div>}
            </div>
            {action}
        </div>
    );
}

function BarRow({ label, value, pct }) {
    return (
        <div>
            <div className="mb-1 flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">{label}</span>
                <span className="text-xs font-semibold tabular-nums text-foreground">{value}</span>
            </div>
            <div className="h-[7px] overflow-hidden rounded-full border border-border/60 bg-muted">
                <div
                    className="h-full rounded-full transition-[width] duration-700"
                    style={{ width: `${pct}%`, background: "linear-gradient(90deg, var(--tb-brand), var(--tb-brand-hover))" }}
                />
            </div>
        </div>
    );
}

// Makes a clickable table row keyboard-operable (WCAG AA): focusable + Enter/Space.
const rowNav = (fn: () => void) => ({
    onClick: fn,
    role: "button",
    tabIndex: 0,
    onKeyDown: (e: React.KeyboardEvent) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fn(); }
    },
});

export default function Dashboard() {
    const navigate = useNavigate();
    const { hasAnyRole, isSuperAdmin } = useContext(AuthContext);

    const canSeeAllotments = isSuperAdmin() || hasAnyRole(["ALLOTMENT_MANAGER", "ALLOTMENT_VIEWER", "REPORT_VIEWER"]);
    const canSeeBOE = isSuperAdmin() || hasAnyRole(["BOE_MANAGER", "BOE_VIEWER", "ACCOUNT_ACCESS", "TL_GENERATE", "REPORT_VIEWER"]);
    const canSeeLicenses = isSuperAdmin() || hasAnyRole(["LICENSE_MANAGER", "LICENSE_VIEWER", "TRADE_MANAGER", "TRADE_VIEWER", "REPORT_VIEWER"]);

    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState({
        licenses: { total: 0, active: 0, expired: 0, null_dfia: 0, expiring_soon: 0 },
        allotments: { total: 0, recent: [] },
        boe: { total: 0, pending_invoices: 0, recent: [] },
    });
    const [expiringLicenses, setExpiringLicenses] = useState([]);
    const [boeMonthlyData, setBoeMonthlyData] = useState([]);

    const fetchDashboardData = async () => {
        try {
            setLoading(true);
            const { data } = await api.get("dashboard/");
            setStats({
                licenses: data?.license_stats || { total: 0, active: 0, expired: 0, null_dfia: 0, expiring_soon: 0 },
                allotments: data?.allotment_stats || { total: 0, recent: [] },
                boe: data?.boe_stats || { total: 0, pending_invoices: 0, recent: [] },
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
    const daysUntil = (d: string) => Math.ceil((new Date(d).getTime() - new Date().getTime()) / 86400000);
    const today = new Date();
    const dateLabel = today.toLocaleDateString("en-GB", { weekday: "long", day: "2-digit", month: "long", year: "numeric" });
    const maxBoe = boeMonthlyData.length ? Math.max(...boeMonthlyData.map((d) => d.count ?? d.value ?? 0), 1) : 1;

    const goExpiringSoon = () => {
        const t = new Date().toISOString().split("T")[0];
        const t30 = new Date(Date.now() + 30 * 864e5).toISOString().split("T")[0];
        navigate(`/licenses?is_expired=False&is_null=False&license_expiry_date__gte=${t}&license_expiry_date__lte=${t30}`);
    };

    const headerActions = (
        <>
            <Button variant="outline" size="sm" onClick={fetchDashboardData} disabled={loading}>
                <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
                Refresh
            </Button>
            <Button variant="outline" size="sm" onClick={() => navigate("/allotments/create")}>
                <Plus className="size-4" />New Allotment
            </Button>
            <Button size="sm" onClick={() => navigate("/bill-of-entries/create")}>
                <Plus className="size-4" />New BOE
            </Button>
        </>
    );

    if (loading) {
        return (
            <>
                <PageHeader pretitle="Overview" title="Dashboard" description={dateLabel} actions={headerActions} />
                <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
                    {[...Array(5)].map((_, i) => <SkeletonStat key={i} />)}
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    {[...Array(3)].map((_, i) => <SkeletonStat key={i} />)}
                </div>
            </>
        );
    }

    return (
        <>
            <PageHeader pretitle="Overview" title="Dashboard" description={dateLabel} actions={headerActions} />

            {/* License KPIs */}
            {canSeeLicenses && (
                <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
                    <StatCard label="Total Licenses" value={stats.licenses.total} icon={FileText} tone="primary" onClick={() => navigate("/licenses?is_expired=all&is_null=all")} />
                    <StatCard label="Active" value={stats.licenses.active} icon={CheckCircle2} tone="success" onClick={() => navigate("/licenses?is_expired=False&is_null=False")} />
                    <StatCard label="Expired" value={stats.licenses.expired} icon={AlertTriangle} tone="danger" onClick={() => navigate("/licenses?is_expired=True&is_null=all")} />
                    <StatCard label="Null DFIA" value={stats.licenses.null_dfia} icon={FileX} tone="neutral" onClick={() => navigate("/licenses?is_null=True&is_expired=all")} />
                    <StatCard label="Expiring Soon" value={stats.licenses.expiring_soon} icon={Hourglass} tone="warning" onClick={goExpiringSoon} />
                </div>
            )}

            {/* Operations KPIs */}
            {(canSeeAllotments || canSeeBOE) && (
                <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-3">
                    {canSeeAllotments && <StatCard label="Allotments" value={stats.allotments.total} icon={Network} tone="info" onClick={() => navigate("/allotments")} />}
                    {canSeeBOE && <StatCard label="Bills of Entry" value={stats.boe.total} icon={ReceiptText} tone="primary" onClick={() => navigate("/bill-of-entries?is_invoice=all")} />}
                    {canSeeBOE && <StatCard label="Pending Invoices" value={stats.boe.pending_invoices} icon={FileSpreadsheet} tone="warning" onClick={() => navigate("/bill-of-entries")} />}
                </div>
            )}

            {/* Detail panels */}
            <div className="mb-3 grid grid-cols-1 gap-3 xl:grid-cols-12">
                {canSeeLicenses && (
                    <Card className="xl:col-span-5">
                        <CardHeader className="border-b">
                            <SectionTitle
                                icon={AlertTriangle} tone="warning" title="Expiring Soon"
                                subtitle={`${expiringLicenses.length} licence${expiringLicenses.length === 1 ? "" : "s"} in next 30 days`}
                                action={<Button variant="outline" size="sm" onClick={goExpiringSoon}>View All <ArrowRight className="size-3.5" /></Button>}
                            />
                        </CardHeader>
                        <CardContent className="max-h-80 overflow-y-auto p-0">
                            {expiringLicenses.length > 0 ? (
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b border-border bg-muted/50 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                            <th className="px-4 py-2">License No.</th>
                                            <th className="px-4 py-2">Expiry</th>
                                            <th className="px-4 py-2 text-right">Balance (CIF)</th>
                                            <th className="px-4 py-2 text-center">Days</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {expiringLicenses.map((lic) => {
                                            const d = lic.days_to_expiry ?? daysUntil(lic.license_expiry_date);
                                            const variant = d <= 7 ? "destructive" : d <= 15 ? "warning" : "info";
                                            return (
                                                <tr key={lic.license_number} className="cursor-pointer border-b border-border/60 hover:bg-accent/40 focus-visible:outline-none focus-visible:bg-accent/60" {...rowNav(() => navigate(`/licenses?search=${lic.license_number}`))}>
                                                    <td className="px-4 py-2 text-[13px] font-medium text-primary">{lic.license_number}</td>
                                                    <td className="px-4 py-2 text-xs text-muted-foreground">{fmtDate(lic.license_expiry_date)}</td>
                                                    <td className="px-4 py-2 text-right text-xs tabular-nums">${parseFloat(lic.balance_cif || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                                                    <td className="px-4 py-2 text-center"><Badge variant={variant}>{d}d</Badge></td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            ) : (
                                <EmptyState icon={CheckCircle2} title="All clear" description="No licenses expiring in the next 30 days" />
                            )}
                        </CardContent>
                    </Card>
                )}

                {canSeeBOE && (
                    <Card className="xl:col-span-3">
                        <CardHeader className="border-b"><SectionTitle icon={BarChart3} title="BOE Monthly Trend" /></CardHeader>
                        <CardContent className="max-h-80 overflow-y-auto pt-4">
                            {boeMonthlyData.length > 0 ? (
                                <div className="flex flex-col gap-2.5">
                                    {boeMonthlyData.map((row, i) => {
                                        const v = row.count ?? row.value ?? 0;
                                        return <BarRow key={i} label={row.month || row.label || `Month ${i + 1}`} value={v} pct={maxBoe > 0 ? (v / maxBoe) * 100 : 0} />;
                                    })}
                                </div>
                            ) : (
                                <EmptyState icon={BarChart3} title="No data yet" />
                            )}
                        </CardContent>
                    </Card>
                )}

                {canSeeBOE && (
                    <Card className="xl:col-span-4">
                        <CardHeader className="border-b">
                            <SectionTitle icon={Receipt} title="Recent Bills of Entry" action={<Button variant="outline" size="sm" onClick={() => navigate("/bill-of-entries")}>View All</Button>} />
                        </CardHeader>
                        <CardContent className="p-0">
                            {stats.boe.recent.length > 0 ? (
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b border-border bg-muted/50 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                            <th className="px-4 py-2">BOE No.</th>
                                            <th className="px-4 py-2">Date</th>
                                            <th className="px-4 py-2">Importer</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {stats.boe.recent.map((boe) => (
                                            <tr key={boe.id} className="cursor-pointer border-b border-border/60 hover:bg-accent/40 focus-visible:outline-none focus-visible:bg-accent/60" {...rowNav(() => navigate(`/bill-of-entries/${boe.id}/edit`))}>
                                                <td className="px-4 py-2 text-[13px] font-medium text-primary">{boe.bill_of_entry_number || "—"}</td>
                                                <td className="px-4 py-2 text-xs text-muted-foreground">{fmtDate(boe.bill_of_entry_date)}</td>
                                                <td className="max-w-[160px] truncate px-4 py-2 text-xs" title={boe.company_name}>{boe.company_name || "—"}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            ) : (
                                <EmptyState icon={Inbox} title="No recent BOE records" />
                            )}
                        </CardContent>
                    </Card>
                )}
            </div>

            {/* Recent allotments */}
            {canSeeAllotments && (
                <Card>
                    <CardHeader className="border-b">
                        <SectionTitle icon={Clock} tone="info" title="Recent Allotments" action={<Button variant="outline" size="sm" onClick={() => navigate("/allotments")}>View All</Button>} />
                    </CardHeader>
                    <CardContent className="p-0">
                        {stats.allotments.recent.length > 0 ? (
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-border bg-muted/50 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                        <th className="px-4 py-2">Date</th>
                                        <th className="px-4 py-2">Item Name</th>
                                        <th className="px-4 py-2 text-right">Quantity</th>
                                        <th className="px-4 py-2 text-right">CIF FC</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {stats.allotments.recent.map((a) => (
                                        <tr key={a.id} className="cursor-pointer border-b border-border/60 hover:bg-accent/40 focus-visible:outline-none focus-visible:bg-accent/60" {...rowNav(() => navigate(`/allotments/${a.id}/allocate`))}>
                                            <td className="whitespace-nowrap px-4 py-2 text-xs text-muted-foreground">{fmtDate(a.modified_on || a.created_at)}</td>
                                            <td className="max-w-[340px] truncate px-4 py-2 text-[13px]" title={a.item_name}>{a.item_name || "—"}</td>
                                            <td className="px-4 py-2 text-right text-[13px] tabular-nums">{parseFloat(a.required_quantity || 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
                                            <td className="px-4 py-2 text-right text-[13px] tabular-nums">${parseFloat(a.cif_fc || 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        ) : (
                            <EmptyState icon={Inbox} title="No recent allotments" />
                        )}
                    </CardContent>
                </Card>
            )}
        </>
    );
}
