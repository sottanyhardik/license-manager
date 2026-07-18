import {
    Building2, Calendar, CalendarX, Fingerprint, Inbox, MapPin, Pencil, Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
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
 * Incentive-licenses list rendering, extracted verbatim from MasterList as the
 * first step of the config-driven <EntityTable> decomposition. Behaviour
 * unchanged; the parent passes state + handlers as props.
 */
export default function IncentiveLicensesTable({
    loading, data, canWrite, entityName, filterParams, currentPage, pageSize, navigate, onDelete,
}: IncentiveLicensesTableProps) {
    return (
        loading ? (
            <div className="py-5 text-center">
                <span className="inline-block size-5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                <div className="mt-2 text-muted-foreground">Loading Incentive Licenses...</div>
            </div>
        ) : data.length === 0 ? (
            <div className="py-5 text-center text-muted-foreground">
                <Inbox className="size-4" aria-hidden="true" />
                <div className="mt-2">No incentive licenses found</div>
            </div>
        ) : (
            <div>
                {data.map(item => {
                    const fmtInr = (val) => formatTruthyInr(val, "-");
                    const expiryDate = parseMasterDisplayDate(item.license_expiry_date);
                    const isExpired = Boolean(expiryDate && expiryDate < new Date());

                    // Sold-status → Tailwind class sets (replaces CSS-var soldStyle object)
                    const soldCls = item.sold_status === 'YES'
                        ? { card: 'border-destructive/40 border-l-destructive', badge: 'bg-destructive/10 text-destructive', label: 'Sold' }
                        : item.sold_status === 'PARTIAL'
                        ? { card: 'border-warning/40 border-l-warning', badge: 'bg-warning/10 text-warning', label: 'Partial' }
                        : { card: 'border-emerald-500/40 border-l-emerald-500', badge: 'bg-emerald-50 text-emerald-700', label: 'Available' };

                    return (
                        <div key={item.id} className={cn('mb-2.5 overflow-hidden rounded-[var(--tb-r-md)] border border-l-4 bg-card shadow-sm', soldCls.card)}>
                            {/* Row 1: Identity */}
                            <div className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/40 px-3.5 py-2.5">
                                <span className="mr-1 text-[16px] font-bold text-primary">{item.license_number || '-'}</span>
                                {item.license_type && (
                                    <span className="rounded-[var(--tb-r-sm)] bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">{item.license_type}</span>
                                )}
                                {item.license_date && (
                                    <span className="chip chip-neutral">
                                        <Calendar className="size-3" aria-hidden="true" />{item.license_date}
                                    </span>
                                )}
                                {item.license_expiry_date && (
                                    <span className={cn('chip', isExpired ? 'chip-danger' : 'chip-neutral')}>
                                        <CalendarX className="size-3" aria-hidden="true" />Exp: {item.license_expiry_date}
                                    </span>
                                )}
                                {item.port_name && (
                                    <span className="chip chip-info">
                                        <MapPin className="size-3" aria-hidden="true" />{item.port_name}
                                    </span>
                                )}
                                {item.exporter_name && (
                                    <span className="chip chip-neutral">
                                        <Building2 className="size-3" aria-hidden="true" />{item.exporter_name}
                                    </span>
                                )}
                                {item.exporter_iec && (
                                    <span className="chip chip-warning">
                                        <Fingerprint className="size-3" aria-hidden="true" />IEC: {item.exporter_iec}
                                    </span>
                                )}
                                <span className={cn('rounded-[var(--tb-r-sm)] px-2 py-0.5 text-xs font-semibold', soldCls.badge)}>
                                    {soldCls.label}
                                </span>
                                {!item.is_active && (
                                    <span className="rounded-[var(--tb-r-sm)] bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">Inactive</span>
                                )}
                            </div>

                            {/* Row 2: Stats + Actions */}
                            <div className="flex flex-wrap items-center gap-2 bg-muted/40 px-3.5 py-2">
                                <div className="flex flex-1 flex-wrap gap-5">
                                    <div>
                                        <div className="text-[0.67rem] font-semibold uppercase text-muted-foreground/70">License Value</div>
                                        <div className="text-sm font-bold text-foreground">{fmtInr(item.license_value)}</div>
                                    </div>
                                    <div>
                                        <div className="text-[0.67rem] font-semibold uppercase text-muted-foreground/70">Sold Value</div>
                                        <div className="text-sm font-semibold text-destructive">{fmtInr(item.sold_value)}</div>
                                    </div>
                                    <div>
                                        <div className="text-[0.67rem] font-semibold uppercase text-muted-foreground/70">Balance</div>
                                        <div className={cn('text-sm font-semibold', item.balance_value > 0 ? 'text-emerald-600' : 'text-muted-foreground/70')}>{fmtInr(item.balance_value)}</div>
                                    </div>
                                </div>
                                <div className="flex shrink-0 gap-1.5">
                                    {canWrite && (
                                        <button
                                            type="button"
                                            onClick={() => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/incentive-licenses/${item.id}/edit`); }}
                                            title="Edit"
                                            className="flex cursor-pointer items-center gap-1 rounded-md border border-primary/30 bg-primary/5 px-2.5 py-1 text-xs text-primary hover:bg-primary/10"
                                        >
                                            <Pencil className="size-4" aria-hidden="true" />
                                        </button>
                                    )}
                                    {canWrite && (
                                        <button
                                            type="button"
                                            onClick={() => onDelete(item)}
                                            title="Delete"
                                            className="flex cursor-pointer items-center gap-1 rounded-md border border-destructive/30 bg-destructive/10 px-2.5 py-1 text-xs text-destructive hover:bg-destructive/20"
                                        >
                                            <Trash2 className="size-4" aria-hidden="true" />
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        )
    );
}
