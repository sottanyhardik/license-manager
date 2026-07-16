import {
    Building2, Calendar, CalendarX, Fingerprint, Inbox, MapPin, Pencil, Trash2,
} from "lucide-react";
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
                            <div className="text-center py-5"><span className="inline-block size-5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" /><div className="mt-2 text-muted-foreground">Loading Incentive Licenses...</div></div>
                        ) : data.length === 0 ? (
                            <div className="text-center py-5 text-muted-foreground"><Inbox className="size-4" aria-hidden="true" /><div className="mt-2">No incentive licenses found</div></div>
                        ) : (
                            <div>
                                {data.map(item => {
                                    const fmtInr = (val) => formatTruthyInr(val, "-");
                                    const expiryDate = parseMasterDisplayDate(item.license_expiry_date);
                                    const isExpired = Boolean(expiryDate && expiryDate < new Date());
                                    const soldStyle = item.sold_status === 'YES' ? { border: 'var(--tb-danger-border)', left: 'var(--tb-danger)', badge: 'var(--tb-danger-soft)', badgeText: 'var(--tb-danger-text)', label: 'Sold' }
                                        : item.sold_status === 'PARTIAL' ? { border: 'var(--tb-warning-border)', left: 'var(--tb-warning)', badge: 'var(--tb-warning-soft)', badgeText: 'var(--tb-warning-text)', label: 'Partial' }
                                        : { border: 'var(--tb-success-border)', left: 'var(--tb-success)', badge: 'var(--tb-success-soft)', badgeText: 'var(--tb-success-text)', label: 'Available' };
                                    return (
                                        <div key={item.id} style={{ display: 'block', background: 'var(--tb-card-bg)', border: `1px solid ${soldStyle.border}`, borderLeft: `4px solid ${soldStyle.left}`, borderRadius: 'var(--tb-r-md)', marginBottom: '10px', overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
                                            {/* Row 1: Identity */}
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: 'var(--tb-sunken)', borderBottom: '1px solid var(--tb-border)', flexWrap: 'wrap' }}>
                                                <span style={{ fontWeight: '700', fontSize: 16, color: 'var(--tb-brand-active)', marginRight: '4px' }}>{item.license_number || '-'}</span>
                                                {item.license_type && (
                                                    <span style={{ fontSize: 12, color: 'var(--tb-text-secondary)', background: 'var(--tb-gray-100)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)', fontWeight: '500' }}>{item.license_type}</span>
                                                )}
                                                {item.license_date && (
                                                    <span className="chip chip-neutral" style={{}}>
                                                        <Calendar className="size-3" aria-hidden="true" />{item.license_date}
                                                    </span>
                                                )}
                                                {item.license_expiry_date && (
                                                    <span className={`chip ${isExpired ? 'chip-danger' : 'chip-neutral'}`} style={{}}>
                                                        <CalendarX className="size-3" aria-hidden="true" />Exp: {item.license_expiry_date}
                                                    </span>
                                                )}
                                                {item.port_name && (
                                                    <span className="chip chip-info" style={{}}>
                                                        <MapPin className="size-3" aria-hidden="true" />{item.port_name}
                                                    </span>
                                                )}
                                                {item.exporter_name && (
                                                    <span className="chip chip-neutral" style={{}}>
                                                        <Building2 className="size-3" aria-hidden="true" />{item.exporter_name}
                                                    </span>
                                                )}
                                                {item.exporter_iec && (
                                                    <span className="chip chip-warning" style={{}}>
                                                        <Fingerprint className="size-3" aria-hidden="true" />IEC: {item.exporter_iec}
                                                    </span>
                                                )}
                                                <span style={{ fontSize: 12, color: soldStyle.badgeText, background: soldStyle.badge, padding: '2px 8px', borderRadius: 'var(--tb-r-sm)', fontWeight: '600' }}>
                                                    {soldStyle.label}
                                                </span>
                                                {!item.is_active && (
                                                    <span style={{ fontSize: 11, color: 'var(--tb-text-secondary)', background: 'var(--tb-gray-100)', padding: '2px 6px', borderRadius: 'var(--tb-r-sm)' }}>Inactive</span>
                                                )}
                                            </div>

                                            {/* Row 3: Stats + Actions */}
                                            <div style={{ display: 'flex', alignItems: 'center', padding: '8px 14px', background: 'var(--tb-sunken)', gap: '8px', flexWrap: 'wrap' }}>
                                                <div style={{ display: 'flex', gap: '20px', flex: 1, flexWrap: 'wrap' }}>
                                                    <div><div style={{ fontSize: '0.67rem', color: 'var(--tb-text-tertiary)', fontWeight: '600', textTransform: 'uppercase' }}>License Value</div><div style={{ fontSize: 14, color: 'var(--tb-text)', fontWeight: '700' }}>{fmtInr(item.license_value)}</div></div>
                                                    <div><div style={{ fontSize: '0.67rem', color: 'var(--tb-text-tertiary)', fontWeight: '600', textTransform: 'uppercase' }}>Sold Value</div><div style={{ fontSize: 14, color: 'var(--tb-danger-text)', fontWeight: '600' }}>{fmtInr(item.sold_value)}</div></div>
                                                    <div><div style={{ fontSize: '0.67rem', color: 'var(--tb-text-tertiary)', fontWeight: '600', textTransform: 'uppercase' }}>Balance</div><div style={{ fontSize: 14, color: item.balance_value > 0 ? 'var(--tb-success)' : 'var(--tb-text-tertiary)', fontWeight: '600' }}>{fmtInr(item.balance_value)}</div></div>
                                                </div>
                                                <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                                                    {canWrite && <button onClick={() => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/incentive-licenses/${item.id}/edit`); }} title="Edit" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 12, color: 'var(--tb-brand-hover)', background: 'var(--tb-brand-50)', border: '1px solid #93c5fd', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <Pencil className="size-4" aria-hidden="true" />
                                                    </button>}
                                                    {canWrite && <button onClick={() => onDelete(item)} title="Delete" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 12, color: 'var(--tb-danger-text)', background: 'var(--tb-danger-soft)', border: '1px solid #fca5a5', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <Trash2 className="size-4" aria-hidden="true" />
                                                    </button>}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )
    );
}
