import { toast } from "sonner";
import { Inbox } from "lucide-react";
import { EntityCard, DetailTable } from "../../../components/ui";
import api from "../../../api/axios";
import { saveFilterState } from "../../../utils/filterPersistence";
import { openPdfPreview } from "../../../utils/pdfPreview";

interface AllotmentsTableProps {
    loading: boolean;
    data: any[];
    canWrite: boolean;
    entityName: string;
    filterParams: Record<string, any>;
    currentPage: number;
    pageSize: number;
    navigate: (path: string) => void;
    onDelete: (item: any) => void;
    expandedAllotments: Set<any>;
    toggleAllotment: (id: any) => void;
}

/**
 * Allotments list rendering, extracted verbatim from MasterList as part of the
 * config-driven <EntityTable> decomposition. Behaviour unchanged.
 */
export default function AllotmentsTable({
    loading, data, canWrite, entityName, filterParams, currentPage, pageSize,
    navigate, onDelete, expandedAllotments, toggleAllotment,
}: AllotmentsTableProps) {
    return (
                        loading ? (
                            <div className="text-center py-5">
                                <span className="inline-block size-5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                                <div className="mt-2 text-muted-foreground">Loading Allotments...</div>
                            </div>
                        ) : data.length === 0 ? (
                            <div className="empty-state">
                                <div className="empty-icon"><Inbox className="size-4" aria-hidden="true" /></div>
                                <div className="empty-title">No allotments found</div>
                                <div className="empty-sub">Try adjusting filters or create a new allotment.</div>
                            </div>
                        ) : (
                            <div>
                                {data.map(item => {
                                    const fmtInr = (val) => val ? `₹${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—';
                                    const fmtQty = (val) => val ? Number(val).toLocaleString('en-IN', { maximumFractionDigits: 3 }) : '—';
                                    const detailRows = item.allotment_details || [];
                                    return (
                                        <EntityCard
                                            key={item.id}
                                            accent={item.is_boe ? 'success' : 'primary'}
                                            title={item.invoice || <span style={{ fontStyle: 'italic', color: 'var(--text-tertiary)', fontWeight: 400 }}>No Invoice</span>}
                                            headerChips={[
                                                item.estimated_arrival_date && { icon: 'calendar3', label: item.estimated_arrival_date },
                                                item.port_name           && { icon: 'geo-alt', label: item.port_name, tone: 'info' },
                                                item.company_name        && { icon: 'building', label: item.company_name, tone: 'primary' },
                                            ].filter(Boolean)}
                                            statusBadges={[
                                                item.is_boe      && { tone: 'success', label: 'BOE ✓' },
                                                item.is_approved && { tone: 'info',    label: 'Approved' },
                                            ].filter(Boolean)}
                                            summary={[
                                                { label: 'Req Qty',      value: fmtQty(item.required_quantity) },
                                                { label: 'Req Value',    value: fmtInr(item.required_value) },
                                                { label: 'Balanced Qty', value: fmtQty(item.balanced_quantity), tone: (item.balanced_quantity > 0 ? 'success' : undefined) },
                                            ]}
                                            actions={[
                                                canWrite && { icon: 'pencil', title: 'Edit', tone: 'primary',
                                                    onClick: () => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/allotments/${item.id}/edit`); } },
                                                canWrite && { icon: 'copy', title: 'Copy', tone: 'info',
                                                    onClick: async () => {
                                                        if (!window.confirm(`Create a copy of allotment ${item.invoice || 'this allotment'}?`)) return;
                                                        try {
                                                            const r = await api.post(`allotments/${item.id}/copy/`);
                                                            toast.success('Allotment copied. Opening in edit mode...');
                                                            saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' });
                                                            navigate(`/allotments/${r.data.id}/edit`);
                                                        } catch (err) { toast.error(err.response?.data?.error || 'Failed to copy'); }
                                                    } },
                                                canWrite && { icon: 'box-arrow-in-down', title: 'Allocate', tone: 'success',
                                                    onClick: () => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/allotments/${item.id}/allocate`); } },
                                                { icon: 'file-pdf', title: 'Preview PDF', tone: 'warning',
                                                    onClick: async () => {
                                                        try {
                                                            const r = await api.get(`allotment-actions/${item.id}/generate-pdf/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                                                            openPdfPreview(r.data, `${item.invoice_number || item.id}.pdf`);
                                                        } catch (err) { toast.error(err.response?.data?.error || 'Failed to generate PDF'); }
                                                    } },
                                                { icon: 'download', title: 'Download',
                                                    onClick: async () => {
                                                        try {
                                                            const r = await api.get(`allotment-actions/${item.id}/generate-pdf/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                                                            const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
                                                            const a = document.createElement('a');
                                                            a.href = url;
                                                            a.download = `Allotment-${item.invoice || item.id}.pdf`;
                                                            document.body.appendChild(a); a.click(); a.remove();
                                                            setTimeout(() => window.URL.revokeObjectURL(url), 10000);
                                                        } catch (err) { toast.error(err.response?.data?.error || 'Failed to download PDF'); }
                                                    } },
                                                canWrite && { icon: 'trash', title: 'Delete', tone: 'danger', onClick: () => onDelete(item) },
                                            ].filter(Boolean)}
                                            viewOpen={expandedAllotments.has(item.id)}
                                            onView={() => toggleAllotment(item.id)}
                                            detailLabel={detailRows.length ? `${detailRows.length} Item${detailRows.length !== 1 ? 's' : ''}` : 'Details'}
                                            detail={() => (
                                                <DetailTable
                                                    columns={[
                                                        { key: 'license_number',     label: 'License',     bold: true, nowrap: true,
                                                            render: v => v ? <span style={{ color: 'var(--primary-color)' }}>{v}</span> : '—' },
                                                        { key: 'serial_number',      label: 'Sl#',         align: 'right', nowrap: true },
                                                        { key: 'product_description', label: 'Item',       muted: true },
                                                        { key: 'qty',                 label: 'Qty',        align: 'right', nowrap: true,
                                                            render: v => fmtQty(v) },
                                                        { key: 'cif_fc',              label: 'CIF (FC)',   align: 'right', nowrap: true,
                                                            render: v => v ? Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—' },
                                                        { key: 'cif_inr',             label: 'CIF (INR)',  align: 'right', nowrap: true, bold: true,
                                                            render: v => fmtInr(v) },
                                                    ]}
                                                    rows={detailRows}
                                                    emptyMessage="No items have been allotted yet."
                                                />
                                            )}
                                        >
                                            {(item.item_name || item.dfia_list) && (
                                                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 24, flexWrap: 'wrap' }}>
                                                    <div style={{ flex: 1, minWidth: 200 }}>
                                                        <div style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>Item</div>
                                                        <div style={{ fontSize: 14.5, color: 'var(--text-primary)', fontWeight: 500 }}>
                                                            {item.item_name || <span style={{ color: 'var(--text-tertiary)', fontStyle: 'italic' }}>No item name</span>}
                                                        </div>
                                                    </div>
                                                    {item.dfia_list && (
                                                        <div style={{ flex: 1, minWidth: 140 }}>
                                                            <div style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>Licenses</div>
                                                            <div style={{ fontSize: 13.5, color: 'var(--primary-color)', fontWeight: 500 }}>{item.dfia_list}</div>
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                        </EntityCard>
                                    );
                                })}
                            </div>
                        )
    );
}
