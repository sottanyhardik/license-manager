import { useState } from "react";
import { Link } from "react-router-dom";
import { Pencil, PlusCircle, Receipt, X } from "lucide-react";

import EntityCard from "@/components/primitives/EntityCard";
import { EmptyState, LoadingState } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { saveFilterState } from "@/utils/filterPersistence";

import BoeRecordWorkspace from "./BoeRecordWorkspace";
import { fmtFc2, fmtInr, fmtQty } from "./format";
import { useBoeRowActions, type BoeRowActionContext } from "./useBoeRowActions";
import type { BoeListItem } from "./types";

export interface BoeCardListProps {
    loading: boolean;
    data: BoeListItem[];
    canWrite: boolean;
    /** canWrite || ACCOUNT_ACCESS: may edit invoice_no only. */
    canEditInvoice: boolean;
    /** Mirrors backend TransferLetterPermission (no BOE_VIEWER). */
    canTransferLetter: boolean;
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
    canTransferLetter,
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
    const actionCtx: BoeRowActionContext = {
        canWrite, canTransferLetter, entityName, filterParams, currentPage, pageSize, navigate,
        onDelete: handleDelete, invalidateList, confirmDangerousAction, onTransferLetter, onMerge: openMergeModal,
    };

    const itemProps = { canEditInvoice, editingInvoiceId, invoiceDraft, setInvoiceDraft, invoiceSaving, startInvoiceEdit, cancelInvoiceEdit, saveInvoiceEdit, onTransferLetter };

    return (
        loading ? (
            <LoadingState variant="skeleton-rows" label="Loading Bill of Entries..." />
        ) : data.length === 0 ? (
            <EmptyState size="page" title="No bill of entries found" description="Try adjusting filters or create a new BOE." />
        ) : (
            <div>
                {data.map(item => (
                    <BoeCardItem
                        key={item.id}
                        item={item}
                        expanded={expandedBoeRows.has(item.id)}
                        onToggle={() => toggleBoeRow(item.id)}
                        actionCtx={actionCtx}
                        {...itemProps}
                    />
                ))}
            </div>
        )
    );
}

type BoeCardItemProps = Pick<BoeCardListProps,
    "canEditInvoice" | "editingInvoiceId" | "invoiceDraft" | "setInvoiceDraft" | "invoiceSaving"
    | "startInvoiceEdit" | "cancelInvoiceEdit" | "saveInvoiceEdit" | "onTransferLetter"
> & {
    item: BoeListItem;
    expanded: boolean;
    onToggle: () => void;
    actionCtx: BoeRowActionContext;
};

/** One BOE card; owns the per-row `useBoeRowActions` mutations. */
function BoeCardItem({
    item, expanded, onToggle, actionCtx,
    canEditInvoice, editingInvoiceId, invoiceDraft, setInvoiceDraft, invoiceSaving,
    startInvoiceEdit, cancelInvoiceEdit, saveInvoiceEdit, onTransferLetter,
}: BoeCardItemProps) {
    const { entityName, filterParams, currentPage, pageSize } = actionCtx;
    const { actions } = useBoeRowActions(item, actionCtx);
            const detailRows = item.item_details || [];
            const disputeRows = detailRows.filter(r => r.is_dispute);
            const hasDispute = disputeRows.length > 0;
            const invoiceChip = canEditInvoice
                ? (editingInvoiceId === item.id
                    ? (
                        <span className="inline-flex items-center gap-1">
                            <Input
                                autoFocus
                                aria-label="Invoice number"
                                value={invoiceDraft}
                                onChange={e => setInvoiceDraft(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter') saveInvoiceEdit(item.id); if (e.key === 'Escape') cancelInvoiceEdit(); }}
                                placeholder="Invoice number"
                                className="h-7 w-40 rounded-md border-success px-2 py-0.5 text-[0.82rem]"
                            />
                            <Button
                                type="button"
                                size="sm"
                                onClick={() => saveInvoiceEdit(item.id)}
                                disabled={invoiceSaving}
                                className="h-7 rounded-md bg-success px-2 text-xs text-white hover:bg-success/90 focus-visible:ring-success/40"
                            >
                                {invoiceSaving ? '…' : 'Save'}
                            </Button>
                            <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                onClick={cancelInvoiceEdit}
                                aria-label="Cancel invoice edit"
                                title="Cancel invoice edit"
                                className="size-7 rounded-md border border-border bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
                            >
                                <X className="size-3.5" aria-hidden="true" />
                            </Button>
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
                        { label: 'CIF (FC)',  value: fmtFc2(item.total_fc) },
                        { label: 'Qty (MT)',  value: fmtQty(item.total_quantity) },
                        { label: 'Unit Price', value: fmtFc2(item.unit_price) },
                    ]}
                    viewOpen={expanded}
                    ariaExpanded={expanded}
                    ariaControls={`boe-detail-${item.id}`}
                    onView={onToggle}
                    detailLabel={detailRows.length ? `${detailRows.length} Item${detailRows.length !== 1 ? 's' : ''}` : 'Details'}
                    detail={() => (
                        <BoeRecordWorkspace
                            item={item}
                            actionItems={actions}
                            onTransferLetter={actionCtx.canTransferLetter ? () => onTransferLetter(item.id) : undefined}
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
}
