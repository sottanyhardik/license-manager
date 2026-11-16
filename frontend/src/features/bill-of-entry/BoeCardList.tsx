import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Inbox, Pencil, PlusCircle, Receipt } from "lucide-react";

import api from "@/api/axios";
import EntityCard from "@/components/primitives/EntityCard";
import { saveFilterState } from "@/utils/filterPersistence";

import BoeRecordWorkspace from "./BoeRecordWorkspace";
import { fmtInr, fmtQty } from "./format";
import type { BoeListItem } from "./types";

export interface BoeCardListProps {
    loading: boolean;
    data: BoeListItem[];
    canWrite: boolean;
    /** canWrite || ACCOUNT_ACCESS: may edit invoice_no only. */
    canEditInvoice: boolean;
    entityName: string;
    filterParams: Record<string, unknown>;
    currentPage: number;
    pageSize: number;
    navigate: (path: string) => void;
    onDelete: (item: BoeListItem) => void;
    invalidateList: () => void;
    confirmDangerousAction: (title: string, message: string) => Promise<unknown>;
    onTransferLetter: (id: number) => void;
    onMerge: (item: BoeListItem) => void;
    editingInvoiceId: number | null;
    invoiceDraft: string;
    setInvoiceDraft: (value: string) => void;
    invoiceSaving: boolean;
    startInvoiceEdit: (item: BoeListItem) => void;
    cancelInvoiceEdit: () => void;
    saveInvoiceEdit: (id: number) => void;
}

/**
 * BOE card register (moved verbatim out of MasterList). Card header, body,
 * actions, links and role gating are unchanged; list lifecycle and mutations
 * stay in MasterList and arrive as props. The expanded body is the
 * `boe:<id>` record workspace (several cards may be open together).
 */
export default function BoeCardList({
    loading,
    data,
    canWrite,
    canEditInvoice,
    entityName,
    filterParams,
    currentPage,
    pageSize,
    navigate,
    onDelete: handleDelete,
    invalidateList,
    confirmDangerousAction,
    onTransferLetter,
    onMerge: openMergeModal,
    editingInvoiceId,
    invoiceDraft,
    setInvoiceDraft,
    invoiceSaving,
    startInvoiceEdit,
    cancelInvoiceEdit,
    saveInvoiceEdit,
}: BoeCardListProps) {
    // Several cards may be open together; each keeps its own `boe:<id>` workspace.
    const [expandedBoeRows, setExpandedBoeRows] = useState<Set<number>>(new Set());
    const toggleBoeRow = (id: number) => {
        setExpandedBoeRows(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    return (
        loading ? (
            <div className="text-center py-5">
                <span className="inline-block size-5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                <div className="mt-2 text-muted-foreground">Loading Bill of Entries...</div>
            </div>
        ) : data.length === 0 ? (
            <div className="empty-state">
                <div className="empty-icon"><Inbox className="size-4" aria-hidden="true" /></div>
                <div className="empty-title">No bill of entries found</div>
                <div className="empty-sub">Try adjusting filters or create a new BOE.</div>
            </div>
        ) : (
            <div>
                {data.map(item => {
                    const detailRows = item.item_details || [];
                    const disputeRows = detailRows.filter(r => r.is_dispute);
                    const hasDispute = disputeRows.length > 0;
                    const invoiceChip = canEditInvoice
                        ? (editingInvoiceId === item.id
                            ? (
                                <span className="inline-flex items-center gap-1">
                                    <input
                                        autoFocus
                                        value={invoiceDraft}
                                        onChange={e => setInvoiceDraft(e.target.value)}
                                        onKeyDown={e => { if (e.key === 'Enter') saveInvoiceEdit(item.id); if (e.key === 'Escape') cancelInvoiceEdit(); }}
                                        placeholder="Invoice number"
                                        className="w-40 rounded-md border border-success px-2 py-0.5 text-[0.82rem] outline-none"
                                    />
                                    <button type="button" onClick={() => saveInvoiceEdit(item.id)} disabled={invoiceSaving} className="cursor-pointer rounded-md bg-success px-2 py-0.5 text-xs text-white disabled:opacity-50">
                                        {invoiceSaving ? '…' : 'Save'}
                                    </button>
                                    <button type="button" onClick={cancelInvoiceEdit} className="cursor-pointer rounded-md border border-border bg-muted px-2 py-0.5 text-xs text-muted-foreground">✕</button>
                                </span>
                            )
                            : (
                                <button
                                    type="button"
                                    onClick={() => startInvoiceEdit(item)}
                                    title="Click to edit invoice number"
                                    className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-success bg-success/10 px-2 py-0.5 text-[0.82rem] font-medium text-success"
                                >
                                    {item.invoice_no
                                        ? (<><Receipt className="size-4" aria-hidden="true" /> {item.invoice_no}</>)
                                        : (<><PlusCircle className="size-4" aria-hidden="true" /> Add Invoice No</>)
                                    }
                                    <Pencil className="size-4" aria-hidden="true" />
                                </button>
                            ))
                        : null;

                    const boeTitleEl = item.bill_of_entry_number ? (
                        <Link
                            to={`/bill-of-entries/${item.id}/edit`}
                            onClick={() => {
                                saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' });
                            }}
                            className="font-mono text-[16px] font-bold tracking-tight text-inherit underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:rounded"
                        >
                            {item.bill_of_entry_number}
                        </Link>
                    ) : '—';

                    return (
                        <EntityCard
                            key={item.id}
                            className={hasDispute ? 'is-dispute' : ''}
                            accent={hasDispute ? 'danger' : 'primary'}
                            title={boeTitleEl}
                            headerChips={[
                                item.bill_of_entry_date && { icon: 'calendar3', label: item.bill_of_entry_date },
                                item.port_name           && { icon: 'geo-alt', label: item.port_name, tone: 'info' },
                                item.company_name        && { icon: 'building', label: item.company_name, tone: 'primary' },
                                hasDispute && {
                                    icon: 'exclamation-triangle-fill',
                                    label: `${disputeRows.length} Dispute${disputeRows.length > 1 ? 's' : ''}`,
                                    tone: 'danger',
                                },
                            ].filter(Boolean)}
                            statusBadges={[]}
                            summary={[
                                { label: 'CIF (INR)', value: fmtInr(item.total_inr) },
                                { label: 'CIF (FC)',  value: item.total_fc ? Number(item.total_fc).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—' },
                                { label: 'Qty (MT)',  value: fmtQty(item.total_quantity) },
                                { label: 'Unit Price', value: item.unit_price ? Number(item.unit_price).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—' },
                            ]}
                            actions={[
                                hasDispute && {
                                    icon: 'check2-circle', title: 'Resolve Dispute', tone: 'danger',
                                    onClick: async () => {
                                        const confirmed = await confirmDangerousAction('Resolve Dispute', `Resolve ${disputeRows.length} dispute row(s) on BOE ${item.bill_of_entry_number}? This clears the dispute flag on all flagged rows.`);
                                        if (!confirmed) return;
                                        try {
                                            const response = await api.post(`bill-of-entries/${item.id}/resolve-dispute/`);
                                            toast.success(response.data.message || 'Dispute resolved');
                                            invalidateList();
                                        } catch (err) {
                                            toast.error(err.response?.data?.detail || err.response?.data?.message || 'Failed to resolve dispute');
                                        }
                                    }
                                },
                                { icon: 'file-earmark-text', title: 'Transfer Letter', tone: 'warning',
                                    onClick: () => onTransferLetter(item.id) },
                                { icon: 'intersect', title: 'Merge BOE', tone: 'info',
                                    onClick: () => openMergeModal(item) },
                                (!item.product_name || item.product_name.trim() === '') && {
                                    icon: 'arrow-repeat', title: 'Update Product Name', tone: 'info',
                                    onClick: async () => {
                                        const confirmed = await confirmDangerousAction('Update Product Name', `Update product name for BOE ${item.bill_of_entry_number}?`);
                                        if (!confirmed) return;
                                        try {
                                            const response = await api.post(`bill-of-entries/${item.id}/update-product-name/`);
                                            toast.success(response.data.message || 'Product name updated');
                                            invalidateList();
                                        } catch (err) {
                                            toast.error(err.response?.data?.message || 'Failed to update product name');
                                        }
                                    }
                                },
                                canWrite && { icon: 'pencil', title: 'Edit', tone: 'primary',
                                    onClick: () => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/bill-of-entries/${item.id}/edit`); } },
                                canWrite && { icon: 'trash', title: 'Delete', tone: 'danger', onClick: () => handleDelete(item) },
                            ].filter(Boolean)}
                            viewOpen={expandedBoeRows.has(item.id)}
                            ariaExpanded={expandedBoeRows.has(item.id)}
                            ariaControls={`boe-detail-${item.id}`}
                            onView={() => toggleBoeRow(item.id)}
                            detailLabel={detailRows.length ? `${detailRows.length} Item${detailRows.length !== 1 ? 's' : ''}` : 'Details'}
                            detail={() => (
                                <BoeRecordWorkspace
                                    item={item}
                                    canWrite={canWrite}
                                    onEdit={() => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/bill-of-entries/${item.id}/edit`); }}
                                    onTransferLetter={() => onTransferLetter(item.id)}
                                    onMerge={() => openMergeModal(item)}
                                />
                            )}
                        >
                            <div className="flex flex-wrap items-start gap-6">
                                <div className="min-w-[200px] flex-1">
                                    <div className="mb-0.5 text-[0.66rem] font-semibold uppercase tracking-[0.06em] text-muted-foreground">Product</div>
                                    <div className="text-[14.5px] font-medium text-foreground">
                                        {item.product_name || <span className="italic text-muted-foreground">No product name</span>}
                                    </div>
                                </div>
                                {item.licenses && (
                                    <div className="min-w-[140px] flex-1">
                                        <div className="mb-0.5 text-[0.66rem] font-semibold uppercase tracking-[0.06em] text-muted-foreground">Licenses</div>
                                        <div className="text-[13.5px] font-medium text-primary">{item.licenses}</div>
                                    </div>
                                )}
                                {invoiceChip && (
                                    <div className="self-center">
                                        {invoiceChip}
                                    </div>
                                )}
                            </div>
                        </EntityCard>
                    );
                })}
            </div>
        )
    );
}
