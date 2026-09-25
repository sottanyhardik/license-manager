import { Building2, Calendar, CalendarX, Fingerprint, Inbox, MapPin, Plus, Pencil, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { saveFilterState } from "../../../utils/filterPersistence";
import { formatTruthyInr, parseMasterDisplayDate } from "../masterDisplayFormatters";

interface IncentiveLicensesTableProps {
    loading: boolean;
    data: any[];
    canWrite: boolean;
    entityName: string;
    filterParams: Record<string, any>;
    currentPage: number;
    pageSize: number;
    navigate: (path: string) => void;
    onDelete: (item: any) => void;
}

/**
 * Incentive Licenses — modernized card layout using Tailwind v4 + shadcn/ui.
 * Consistent with Licenses page; professional status indicators; proper empty state.
 */
export default function IncentiveLicensesTable({
    loading,
    data,
    canWrite,
    entityName,
    filterParams,
    currentPage,
    pageSize,
    navigate,
    onDelete,
}: IncentiveLicensesTableProps) {
    if (loading) {
        return (
            <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="overflow-hidden rounded-2xl border border-border/60 bg-card p-4">
                        <div className="flex items-center gap-4">
                            <Skeleton className="h-5 w-32 rounded" />
                            <Skeleton className="h-3.5 w-24 rounded" />
                            <Skeleton className="h-3.5 w-28 rounded" />
                            <Skeleton className="ml-auto h-5 w-16 rounded-full" />
                        </div>
                    </div>
                ))}
            </div>
        );
    }

    if (data.length === 0) {
        return (
            <div className="flex flex-col items-center py-16 text-center">
                <div className="mb-4 flex size-14 items-center justify-center rounded-full bg-muted">
                    <Inbox className="size-7 text-muted-foreground/50" aria-hidden="true" />
                </div>
                <h3 className="text-base font-semibold text-foreground">No incentive licenses found</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                    Try adjusting your search or filters.
                </p>
                {canWrite && (
                    <Button
                        size="sm"
                        onClick={() => {
                            saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' });
                            navigate('/incentive-licenses/create');
                        }}
                        className="mt-4"
                    >
                        <Plus className="size-3.5" />
                        Create Incentive License
                    </Button>
                )}
            </div>
        );
    }

    return (
        <div className="incentive-licenses-list flex flex-col gap-2.5" role="list" aria-label="Incentive Licenses">
            {data.map((item) => {
                const fmtInr = (val: any) => formatTruthyInr(val, "—");
                const expiryDate = parseMasterDisplayDate(item.license_expiry_date);
                const isExpired = Boolean(expiryDate && expiryDate < new Date());

                // Status → Tailwind class sets
                const statusConfig = item.sold_status === "YES"
                    ? {
                        card: "border-l-destructive",
                        badge: "bg-destructive/10 text-destructive ring-1 ring-destructive/20",
                        label: "Sold",
                    }
                    : item.sold_status === "PARTIAL"
                        ? {
                            card: "border-l-amber-500",
                            badge: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
                            label: "Partial",
                        }
                        : {
                            card: "border-l-emerald-500",
                            badge: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
                            label: "Available",
                        };

                return (
                    <article
                        key={item.id}
                        className={cn(
                            "incentive-license-row overflow-hidden rounded-2xl border border-l-[3px] bg-card shadow-sm transition-shadow hover:shadow-md",
                            statusConfig.card
                        )}
                    >
                        {/* Header */}
                        <div className="border-b border-border/50 bg-muted/20 px-5 py-4">
                            <div className="mb-3 flex flex-wrap items-center gap-2 gap-y-2">
                                {/* License Number */}
                                <span className="font-mono text-[17px] font-bold tracking-tight text-foreground">
                                    {item.license_number || "—"}
                                </span>

                                {/* Type Badge */}
                                {item.license_type && (
                                    <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                                        {item.license_type}
                                    </span>
                                )}

                                {/* Status Badge */}
                                <span className={cn("rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold", statusConfig.badge)}>
                                    {statusConfig.label}
                                </span>

                                {!item.is_active && (
                                    <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                                        Inactive
                                    </span>
                                )}
                            </div>

                            {/* Metadata chips */}
                            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                                {item.license_date && (
                                    <span className="flex items-center gap-1.5 rounded-md bg-muted/50 px-2.5 py-1">
                                        <Calendar className="size-3" aria-hidden="true" />
                                        {item.license_date}
                                    </span>
                                )}
                                {item.license_expiry_date && (
                                    <span className={cn(
                                        "flex items-center gap-1.5 rounded-md px-2.5 py-1",
                                        isExpired
                                            ? "bg-destructive/10 text-destructive"
                                            : "bg-muted/50"
                                    )}>
                                        <CalendarX className="size-3" aria-hidden="true" />
                                        Exp: {item.license_expiry_date}
                                    </span>
                                )}
                                {item.port_name && (
                                    <span className="flex items-center gap-1.5 rounded-md bg-blue-50 px-2.5 py-1 text-blue-700">
                                        <MapPin className="size-3" aria-hidden="true" />
                                        {item.port_name}
                                    </span>
                                )}
                                {item.exporter_name && (
                                    <span className="flex items-center gap-1.5 rounded-md bg-muted/50 px-2.5 py-1">
                                        <Building2 className="size-3" aria-hidden="true" />
                                        {item.exporter_name}
                                    </span>
                                )}
                                {item.exporter_iec && (
                                    <span className="flex items-center gap-1.5 rounded-md bg-amber-50 px-2.5 py-1 text-amber-700">
                                        <Fingerprint className="size-3" aria-hidden="true" />
                                        IEC: {item.exporter_iec}
                                    </span>
                                )}
                            </div>
                        </div>

                        {/* Stats + Actions */}
                        <div className="flex flex-col items-start justify-between gap-4 px-5 py-4 sm:flex-row sm:items-center">
                            {/* Stats grid */}
                            <div className="grid grid-cols-3 gap-4 sm:gap-6">
                                <div className="min-w-0">
                                    <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                        License Value
                                    </div>
                                    <div className="mt-1 text-sm font-bold text-foreground tabular-nums">
                                        {fmtInr(item.license_value)}
                                    </div>
                                </div>
                                <div className="min-w-0">
                                    <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                        Sold Value
                                    </div>
                                    <div className="mt-1 text-sm font-semibold text-destructive tabular-nums">
                                        {fmtInr(item.sold_value)}
                                    </div>
                                </div>
                                <div className="min-w-0">
                                    <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                        Balance
                                    </div>
                                    <div className={cn(
                                        "mt-1 text-sm font-semibold tabular-nums",
                                        Number(item.balance_value ?? 0) > 0
                                            ? "text-emerald-700"
                                            : "text-muted-foreground"
                                    )}>
                                        {fmtInr(item.balance_value)}
                                    </div>
                                </div>
                            </div>

                            {/* Actions */}
                            {canWrite && (
                                <div className="flex shrink-0 gap-2 sm:ml-auto">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => {
                                            saveFilterState(entityName, {
                                                filters: filterParams,
                                                pagination: { currentPage, pageSize },
                                                search: "",
                                            });
                                            navigate(`/incentive-licenses/${item.id}/edit`);
                                        }}
                                    >
                                        <Pencil className="size-3.5" />
                                        <span className="hidden sm:inline">Edit</span>
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => onDelete(item)}
                                    >
                                        <Trash2 className="size-3.5" />
                                        <span className="hidden sm:inline">Delete</span>
                                    </Button>
                                </div>
                            )}
                        </div>
                    </article>
                );
            })}
        </div>
    );
}
