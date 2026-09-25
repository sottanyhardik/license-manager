import React, { useCallback, useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
    AlertTriangle,
    ArrowRight,
    CheckCircle2,
    Clock,
    FileSpreadsheet,
    FileText,
    FileX,
    Hourglass,
    Inbox,
    Network,
    Plus,
    ReceiptText,
    RefreshCw,
    RotateCcw,
} from "lucide-react";
import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import PageHeader from "@/components/PageHeader";
import AlertCard from "@/components/AlertCard";
import StatCard from "@/components/StatCard";
import EmptyState from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatDashboardDate } from "@/utils/dashboardDate";

type LicenceStats = {
    total: number;
    active: number;
    expired: number;
    null_dfia: number;
    expiring_soon: number;
};
type RecentBoe = {
    id: string | number;
    bill_of_entry_number?: string | null;
    bill_of_entry_date?: string | null;
    company_name?: string | null;
};
type RecentAllotment = {
    id: string | number;
    modified_on?: string | null;
    created_at?: string | null;
    item_name?: string | null;
    required_quantity?: string | number | null;
    cif_fc?: string | number | null;
};
type ExpiringLicence = {
    license_number: string;
    license_expiry_date?: string | null;
    balance_cif?: string | number | null;
    days_to_expiry?: number | null;
};
type DashboardStats = {
    licenses: LicenceStats;
    allotments: { total: number; recent: RecentAllotment[] };
    boe: { total: number; pending_invoices: number; recent: RecentBoe[] };
};

const EMPTY_STATS: DashboardStats = {
    licenses: { total: 0, active: 0, expired: 0, null_dfia: 0, expiring_soon: 0 },
    allotments: { total: 0, recent: [] },
    boe: { total: 0, pending_invoices: 0, recent: [] },
};

const EXPIRY_WINDOW_DAYS = 30;
const EXPIRY_CRITICAL_DAYS = 7;
const EXPIRY_WARNING_DAYS = 15;

// Utility functions
const rowNav = (fn: () => void) => ({
    onClick: fn,
    role: "button",
    tabIndex: 0,
    onKeyDown: (event: React.KeyboardEvent) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            fn();
        }
    },
});

function SkeletonStat() {
    return (
        <div className="flex min-h-[76px] items-center gap-3 rounded-lg border border-border/70 bg-card px-3.5 py-3">
            <Skeleton className="size-9 rounded-lg" />
            <div className="flex-1 space-y-2">
                <Skeleton className="h-2.5 w-3/5" />
                <Skeleton className="h-6 w-2/5" />
            </div>
        </div>
    );
}

function SkeletonAlertCard() {
    return (
        <div className="space-y-3 rounded-lg border border-border/70 bg-card px-4 py-4">
            <div className="flex items-center gap-2.5">
                <Skeleton className="size-7 rounded-md" />
                <Skeleton className="h-4 w-32" />
            </div>
            <div className="space-y-2">
                <Skeleton className="h-7 w-12" />
                <Skeleton className="h-3 w-20" />
            </div>
        </div>
    );
}

function parseDashboardDate(value?: string | null) {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
}

function displayDate(value?: string | null) {
    return formatDashboardDate(value);
}

function displayMoney(value?: string | number | null) {
    if (value == null || value === "") return "—";
    const number = Number(value);
    return Number.isFinite(number)
        ? `$${number.toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
          })}`
        : "—";
}

function displayQuantity(value?: string | number | null) {
    if (value == null || value === "") return "—";
    const number = Number(value);
    return Number.isFinite(number)
        ? number.toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
          })
        : "—";
}

function getExpiryDays(licenseExpiryDate?: string | null, daysToExpiry?: number | null): number {
    if (daysToExpiry != null) return daysToExpiry;
    const date = parseDashboardDate(licenseExpiryDate);
    if (!date) return 0;
    return Math.ceil((date.getTime() - Date.now()) / 86400000);
}

function getExpiryBadgeVariant(
    days: number
): "destructive" | "default" | "secondary" {
    if (days <= 0) return "destructive";
    if (days <= EXPIRY_CRITICAL_DAYS) return "destructive";
    if (days <= EXPIRY_WARNING_DAYS) return "default";
    return "secondary";
}

export default function Dashboard() {
    const navigate = useNavigate();
    const { hasAnyRole, isSuperAdmin } = useContext(AuthContext);

    // Permission checks
    const canSeeAllotments =
        isSuperAdmin() ||
        hasAnyRole([
            "ALLOTMENT_MANAGER",
            "ALLOTMENT_VIEWER",
            "REPORT_VIEWER",
        ]);
    const canSeeBOE =
        isSuperAdmin() ||
        hasAnyRole([
            "BOE_MANAGER",
            "BOE_VIEWER",
            "ACCOUNT_ACCESS",
            "TL_GENERATE",
            "REPORT_VIEWER",
        ]);
    const canSeeLicenses =
        isSuperAdmin() ||
        hasAnyRole([
            "LICENSE_MANAGER",
            "LICENSE_VIEWER",
            "TRADE_MANAGER",
            "TRADE_VIEWER",
            "REPORT_VIEWER",
        ]);
    const canCreateAllotments =
        isSuperAdmin() || hasAnyRole(["ALLOTMENT_MANAGER"]);
    const canCreateBOE = isSuperAdmin() || hasAnyRole(["BOE_MANAGER"]);

    // State
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState(false);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const [stats, setStats] = useState<DashboardStats>(EMPTY_STATS);
    const [expiringLicenses, setExpiringLicenses] = useState<ExpiringLicence[]>(
        []
    );

    // Data fetching
    const fetchDashboardData = useCallback(async (isRefresh = false) => {
        if (isRefresh) setRefreshing(true);
        else setLoading(true);
        setError(false);
        try {
            const { data } = await api.get("dashboard/");
            setStats({
                licenses: data?.license_stats || EMPTY_STATS.licenses,
                allotments:
                    data?.allotment_stats || EMPTY_STATS.allotments,
                boe: data?.boe_stats || EMPTY_STATS.boe,
            });
            setExpiringLicenses(data?.expiring_licenses || []);
            setLastUpdated(new Date());
        } catch {
            setError(true);
            toast.error("Failed to load dashboard data");
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    React.useEffect(() => {
        void fetchDashboardData();
    }, [fetchDashboardData]);

    // Computed values
    const today = new Date();
    const dateLabel = today.toLocaleDateString("en-GB", {
        weekday: "long",
        day: "2-digit",
        month: "long",
        year: "numeric",
    });
    const lastUpdatedLabel = lastUpdated
        ? new Intl.DateTimeFormat("en-GB", {
              hour: "2-digit",
              minute: "2-digit",
          }).format(lastUpdated)
        : "Not updated";

    // Navigation helpers
    const goExpiringSoon = useCallback(() => {
        const start = new Date().toISOString().split("T")[0];
        const end = new Date(
            Date.now() + EXPIRY_WINDOW_DAYS * 864e5
        )
            .toISOString()
            .split("T")[0];
        navigate(
            `/licenses?is_expired=False&is_null=False&license_expiry_date__gte=${start}&license_expiry_date__lte=${end}`
        );
    }, [navigate]);

    const headerActions = (
        <div className="dashboard-page-actions flex flex-wrap items-center justify-end gap-2">
            <Button
                variant="outline"
                size="sm"
                onClick={() => void fetchDashboardData(true)}
                disabled={refreshing || loading}
                aria-label="Refresh dashboard data"
            >
                <RefreshCw
                    className={cn(
                        "size-4",
                        (refreshing || loading) && "animate-spin"
                    )}
                />
                {refreshing ? "Refreshing" : "Refresh"}
            </Button>
            {canCreateAllotments && (
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigate("/allotments/create")}
                >
                    <Plus className="size-4" />
                    New Allotment
                </Button>
            )}
            {canCreateBOE && (
                <Button
                    size="sm"
                    onClick={() => navigate("/bill-of-entries/create")}
                >
                    <Plus className="size-4" />
                    New BOE
                </Button>
            )}
        </div>
    );

    return (
        <section
            className="dashboard-page space-y-6"
            aria-label="Dashboard overview"
            aria-busy={loading}
        >
            {/* ── Page Header ─────────────────────────────────────────── */}
            <PageHeader
                pretitle="Home"
                title="Dashboard"
                description={
                    <span>
                        {dateLabel}{" "}
                        <span className="mx-1 text-border">•</span>{" "}
                        <span aria-live="polite">
                            {refreshing
                                ? "Refreshing…"
                                : `Updated ${lastUpdatedLabel}`}
                        </span>
                    </span>
                }
                actions={headerActions}
            />

            {/* ── Error State ─────────────────────────────────────────── */}
            {error && (
                <div
                    className="flex flex-wrap items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
                    role="alert"
                >
                    <AlertTriangle className="size-4" />
                    Some dashboard data may be unavailable.
                    {lastUpdated && " The last successful result is still shown."}
                    <Button
                        variant="outline"
                        size="sm"
                        className="ml-auto"
                        onClick={() => void fetchDashboardData(true)}
                    >
                        <RotateCcw className="size-3.5" />
                        Retry
                    </Button>
                </div>
            )}

            {/* ════════════════════════════════════════════════════════
                PHASE 2: URGENT ALERTS (Red zone)
                ════════════════════════════════════════════════════════ */}
            {canSeeLicenses && (
                <section
                    className="space-y-3"
                    aria-labelledby="urgent-alerts-title"
                >
                    <div className="space-y-1">
                        <h2
                            id="urgent-alerts-title"
                            className="text-sm font-semibold uppercase tracking-wider text-muted-foreground"
                        >
                            Urgent alerts
                        </h2>
                    </div>

                    {loading ? (
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                            {Array.from({ length: 3 }, (_, index) => (
                                <SkeletonAlertCard key={index} />
                            ))}
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                            {/* Expiring < 7 days */}
                            <AlertCard
                                icon={AlertTriangle}
                                title="Expiring soon"
                                description="Critical (< 7 days)"
                                count={expiringLicenses.filter(
                                    (lic) =>
                                        getExpiryDays(
                                            lic.license_expiry_date,
                                            lic.days_to_expiry
                                        ) <= EXPIRY_CRITICAL_DAYS &&
                                        getExpiryDays(
                                            lic.license_expiry_date,
                                            lic.days_to_expiry
                                        ) > 0
                                ).length}
                                tone="danger"
                                onViewAll={goExpiringSoon}
                            />

                            {/* Missing DGFT */}
                            <AlertCard
                                icon={FileX}
                                title="Missing DGFT"
                                description="Require data entry"
                                count={stats.licenses.null_dfia}
                                tone="danger"
                                onViewAll={() =>
                                    navigate(
                                        "/licenses?is_null=True&is_expired=all"
                                    )
                                }
                            />

                            {/* Pending invoices */}
                            {canSeeBOE && (
                                <AlertCard
                                    icon={FileSpreadsheet}
                                    title="Pending invoices"
                                    description="Awaiting follow-up"
                                    count={stats.boe.pending_invoices}
                                    tone="warning"
                                    onViewAll={() =>
                                        navigate("/bill-of-entries")
                                    }
                                />
                            )}
                        </div>
                    )}
                </section>
            )}

            {/* ════════════════════════════════════════════════════════
                PHASE 2: KPI SNAPSHOT (Yellow/Green zone)
                ════════════════════════════════════════════════════════ */}
            <section className="space-y-3" aria-labelledby="snapshot-title">
                <div className="space-y-1">
                    <h2
                        id="snapshot-title"
                        className="text-sm font-semibold uppercase tracking-wider text-muted-foreground"
                    >
                        Snapshot
                    </h2>
                </div>

                {loading ? (
                    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
                        {Array.from({ length: 4 }, (_, index) => (
                            <SkeletonStat key={index} />
                        ))}
                    </div>
                ) : (
                    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
                        {canSeeLicenses && (
                            <>
                                <StatCard
                                    compact
                                    label="Active"
                                    value={stats.licenses.active}
                                    icon={CheckCircle2}
                                    tone="success"
                                    onClick={() =>
                                        navigate(
                                            "/licenses?is_expired=False&is_null=False"
                                        )
                                    }
                                />
                                <StatCard
                                    compact
                                    label="Expired"
                                    value={stats.licenses.expired}
                                    icon={AlertTriangle}
                                    tone="danger"
                                    onClick={() =>
                                        navigate(
                                            "/licenses?is_expired=True&is_null=all"
                                        )
                                    }
                                />
                            </>
                        )}
                        {canSeeAllotments && (
                            <StatCard
                                compact
                                label="Allotments"
                                value={stats.allotments.total}
                                icon={Network}
                                tone="info"
                                onClick={() => navigate("/allotments")}
                            />
                        )}
                        {canSeeBOE && (
                            <StatCard
                                compact
                                label="BOE"
                                value={stats.boe.total}
                                icon={ReceiptText}
                                tone="primary"
                                onClick={() =>
                                    navigate("/bill-of-entries?is_invoice=all")
                                }
                            />
                        )}
                    </div>
                )}
            </section>

            {/* ════════════════════════════════════════════════════════
                PHASE 2: EXPIRING SOON TABLE (Full width, scannable)
                ════════════════════════════════════════════════════════ */}
            {canSeeLicenses && expiringLicenses.length > 0 && (
                <Card className="overflow-hidden">
                    <CardHeader className="border-b pb-3">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="text-sm font-semibold">
                                    Expiring soon
                                </h3>
                                <p className="text-xs text-muted-foreground">
                                    Next {EXPIRY_WINDOW_DAYS} days (
                                    {expiringLicenses.length} records)
                                </p>
                            </div>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={goExpiringSoon}
                            >
                                View all
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent className="max-h-[400px] overflow-auto p-0">
                        <table className="w-full text-sm">
                            <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur">
                                <tr className="border-b text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                    <th className="px-4 py-2.5">License</th>
                                    <th className="px-4 py-2.5">Expiry</th>
                                    <th className="px-4 py-2.5 text-right">
                                        Balance
                                    </th>
                                    <th className="px-4 py-2.5 text-right">
                                        Days
                                    </th>
                                    <th className="px-4 py-2.5">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {expiringLicenses.map((lic) => {
                                    const days = getExpiryDays(
                                        lic.license_expiry_date,
                                        lic.days_to_expiry
                                    );
                                    const badgeVariant =
                                        getExpiryBadgeVariant(days);
                                    return (
                                        <tr
                                            key={lic.license_number}
                                            className="border-t border-border/60 hover:bg-accent/40 focus-visible:outline-none focus-visible:bg-accent/60"
                                            {...rowNav(() =>
                                                navigate(
                                                    `/licenses?search=${lic.license_number}`
                                                )
                                            )}
                                        >
                                            <td className="px-4 py-2.5 text-sm font-medium text-primary">
                                                {lic.license_number}
                                            </td>
                                            <td className="px-4 py-2.5 text-xs text-muted-foreground">
                                                {displayDate(
                                                    lic.license_expiry_date
                                                )}
                                            </td>
                                            <td className="px-4 py-2.5 text-right text-xs tabular-nums">
                                                {displayMoney(lic.balance_cif)}
                                            </td>
                                            <td className="px-4 py-2.5 text-right text-xs tabular-nums">
                                                {days <= 0
                                                    ? "Expired"
                                                    : `${days}d`}
                                            </td>
                                            <td className="px-4 py-2.5">
                                                <Badge
                                                    variant={badgeVariant}
                                                >
                                                    {days <= 0
                                                        ? "Expired"
                                                        : `${days} days`}
                                                </Badge>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </CardContent>
                </Card>
            )}

            {/* ════════════════════════════════════════════════════════
                PHASE 2: ACTIVITY GRID (Recent BOE + Allotments)
                ════════════════════════════════════════════════════════ */}
            {(canSeeBOE || canSeeAllotments) && (
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    {/* Recent BOE Entries */}
                    {canSeeBOE && (
                        <Card className="overflow-hidden">
                            <CardHeader className="border-b pb-3">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <h3 className="text-sm font-semibold">
                                            Recent BOE entries
                                        </h3>
                                        <p className="text-xs text-muted-foreground">
                                            Latest{" "}
                                            {stats.boe.recent.length} records
                                        </p>
                                    </div>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() =>
                                            navigate("/bill-of-entries")
                                        }
                                    >
                                        View all
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent className="max-h-[300px] overflow-auto p-0">
                                {stats.boe.recent.length ? (
                                    <table className="w-full text-sm">
                                        <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur">
                                            <tr className="border-b text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                                <th className="px-4 py-2.5">
                                                    BOE #
                                                </th>
                                                <th className="px-4 py-2.5">
                                                    Date
                                                </th>
                                                <th className="px-4 py-2.5">
                                                    Importer
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {stats.boe.recent.map((boe) => (
                                                <tr
                                                    key={boe.id}
                                                    className="border-t border-border/60 hover:bg-accent/40 focus-visible:outline-none focus-visible:bg-accent/60"
                                                    {...rowNav(() =>
                                                        navigate(
                                                            `/bill-of-entries/${boe.id}/edit`
                                                        )
                                                    )}
                                                >
                                                    <td className="px-4 py-2.5 text-sm font-medium text-primary">
                                                        {boe.bill_of_entry_number ||
                                                            "—"}
                                                    </td>
                                                    <td className="px-4 py-2.5 text-xs text-muted-foreground">
                                                        {displayDate(
                                                            boe.bill_of_entry_date
                                                        )}
                                                    </td>
                                                    <td
                                                        className="max-w-[170px] truncate px-4 py-2.5 text-xs"
                                                        title={
                                                            boe.company_name ??
                                                            undefined
                                                        }
                                                    >
                                                        {boe.company_name ||
                                                            "—"}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                ) : (
                                    <EmptyState
                                        icon={Inbox}
                                        title="No recent BOE records"
                                        size="default"
                                    />
                                )}
                            </CardContent>
                        </Card>
                    )}

                    {/* Recent Allotments */}
                    {canSeeAllotments && (
                        <Card className="overflow-hidden">
                            <CardHeader className="border-b pb-3">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <h3 className="text-sm font-semibold">
                                            Recent allotments
                                        </h3>
                                        <p className="text-xs text-muted-foreground">
                                            Latest{" "}
                                            {stats.allotments.recent.length}{" "}
                                            records
                                        </p>
                                    </div>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() =>
                                            navigate("/allotments")
                                        }
                                    >
                                        View all
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent className="max-h-[300px] overflow-auto p-0">
                                {stats.allotments.recent.length ? (
                                    <table className="w-full text-sm">
                                        <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur">
                                            <tr className="border-b text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                                <th className="px-4 py-2.5">
                                                    Date
                                                </th>
                                                <th className="px-4 py-2.5">
                                                    Item
                                                </th>
                                                <th className="px-4 py-2.5 text-right">
                                                    Qty
                                                </th>
                                                <th className="px-4 py-2.5 text-right">
                                                    Value
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {stats.allotments.recent.map(
                                                (allotment) => (
                                                    <tr
                                                        key={allotment.id}
                                                        className="border-t border-border/60 hover:bg-accent/40 focus-visible:outline-none focus-visible:bg-accent/60"
                                                        {...rowNav(() =>
                                                            navigate(
                                                                `/allotments/${allotment.id}/allocate`
                                                            )
                                                        )}
                                                    >
                                                        <td className="whitespace-nowrap px-4 py-2.5 text-xs text-muted-foreground">
                                                            {displayDate(
                                                                allotment.modified_on ||
                                                                    allotment.created_at
                                                            )}
                                                        </td>
                                                        <td
                                                            className="max-w-[200px] truncate px-4 py-2.5 text-sm"
                                                            title={
                                                                allotment.item_name ??
                                                                undefined
                                                            }
                                                        >
                                                            {allotment.item_name ||
                                                                "—"}
                                                        </td>
                                                        <td className="px-4 py-2.5 text-right text-sm tabular-nums">
                                                            {displayQuantity(
                                                                allotment.required_quantity
                                                            )}
                                                        </td>
                                                        <td className="px-4 py-2.5 text-right text-sm tabular-nums">
                                                            {displayMoney(
                                                                allotment.cif_fc
                                                            )}
                                                        </td>
                                                    </tr>
                                                )
                                            )}
                                        </tbody>
                                    </table>
                                ) : (
                                    <EmptyState
                                        icon={Inbox}
                                        title="No recent allotments"
                                        size="default"
                                    />
                                )}
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}
        </section>
    );
}
