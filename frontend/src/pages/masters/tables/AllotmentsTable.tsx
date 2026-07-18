import { toast } from "sonner";
import { Inbox } from "lucide-react";
import EntityCard from "../../../components/primitives/EntityCard";
import DetailTable from "../../../components/primitives/DetailTable";
import api from "../../../api/axios";
import { saveFilterState } from "../../../utils/filterPersistence";
import { openPdfPreview } from "../../../utils/pdfPreview";
import { formatTruthyIndianNumber, formatTruthyInr } from "../masterDisplayFormatters";

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
                                    const fmtInr = (val) => formatTruthyInr(val);
                                    const fmtQty = (val) => formatTruthyIndianNumber(val, { maximumFractionDigits: 3 });
                                    const detailRows = item.allotment_details || [];
                                    return (
                                        <EntityCard
                                            key={item.id}
                                            accent={item.is_boe ? 'success' : 'primary'}
                                            title={item.invoice || <span className="italic font-normal text-muted-foreground/70">No Invoice</span>}
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
                                                            render: v => v ? <span className="text-primary">{v}</span> : '—' },
                                                        { key: 'serial_number',      label: 'Sl#',         align: 'right', nowrap: true },
                                                        { key: 'product_description', label: 'Item',       muted: true },
                                                        { key: 'qty',                 label: 'Qty',        align: 'right', nowrap: true,
                                                            render: v => fmtQty(v) },
                                                        { key: 'cif_fc',              label: 'CIF (FC)',   align: 'right', nowrap: true,
                                                            render: v => formatTruthyIndianNumber(v, { maximumFractionDigits: 2 }) },
                                                        { key: 'cif_inr',             label: 'CIF (INR)',  align: 'right', nowrap: true, bold: true,
                                                            render: v => fmtInr(v) },
                                                    ]}
                                                    rows={detailRows}
                                                    emptyMessage="No items have been allotted yet."
                                                />
                                            )}
                                        >
                                            {(item.item_name || item.dfia_list) && (
                                                <div className="flex flex-wrap items-start gap-6">
                                                    <div className="min-w-[200px] flex-1">
                                                        <div className="mb-0.5 text-[0.66rem] font-semibold uppercase tracking-[0.06em] text-muted-foreground/70">Item</div>
                                                        <div className="text-[14.5px] font-medium text-foreground">
                                                            {item.item_name || <span className="italic text-muted-foreground/70">No item name</span>}
                                                        </div>
                                                    </div>
                                                    {item.dfia_list && (
                                                        <div className="min-w-[140px] flex-1">
                                                            <div className="mb-0.5 text-[0.66rem] font-semibold uppercase tracking-[0.06em] text-muted-foreground/70">Licenses</div>
                                                            <div className="text-[13.5px] font-medium text-primary">{item.dfia_list}</div>
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
