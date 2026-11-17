import { createContext, useContext, useMemo } from "react";
import { Link } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { Pencil, PlusCircle, Receipt, TriangleAlert, X } from "lucide-react";

import { ExpandableDataTable } from "@/components/data-table";
import { ActionMenu, StatusBadge } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { saveFilterState } from "@/utils/filterPersistence";

import BoeRecordWorkspace from "./BoeRecordWorkspace";
import { fmtFc2, fmtInr, fmtQty } from "./format";
import { useBoeRowActions, type BoeRowActionContext } from "./useBoeRowActions";
import type { BoeDetailRow, BoeListItem } from "./types";

export interface BoeTableProps {
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

interface BoeTableContextValue extends BoeTableProps {
    actionCtx: BoeRowActionContext;
}

/**
 * Row cells are stable module-level components (columns are memoised), so the
 * mutable register state (inline invoice draft, filters) reaches them through
 * this context instead of closures. That keeps the invoice input mounted while typing.
 */
const BoeTableContext = createContext<BoeTableContextValue | null>(null);

function useBoeTable(): BoeTableContextValue {
    const ctx = useContext(BoeTableContext);
    if (!ctx) throw new Error("BoeTable cells must render inside <BoeTable>");
    return ctx;
}

const disputeCount = (item: BoeListItem): number =>
    ((item.item_details || []) as BoeDetailRow[]).filter((r) => r.is_dispute).length;

const boeLabel = (item: BoeListItem): string => `BOE ${item.bill_of_entry_number || item.id}`;

function BoeNumberCell({ item }: { item: BoeListItem }) {
    const { entityName, filterParams, currentPage, pageSize } = useBoeTable();
    const disputes = disputeCount(item);
    const secondary = [item.bill_of_entry_date, item.port_name].filter(Boolean).join(" · ");
    const qty = fmtQty(item.total_quantity);
    const figures = `CIF ${fmtInr(item.total_inr)}${qty === "—" ? "" : ` · ${qty} MT`}`;
    const tertiary = [item.product_name, item.licenses].filter(Boolean).join(" · ");
    return (
        <div className="flex min-w-0 max-w-[140px] flex-col gap-0.5 md:max-w-none">
            <div className="flex flex-wrap items-center gap-1.5">
                {item.bill_of_entry_number ? (
                    <Link
                        to={`/bill-of-entries/${item.id}`}
                        onClick={() => {
                            saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: "" });
                        }}
                        className="rounded font-mono text-[13px] font-semibold tracking-tight text-primary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                        {item.bill_of_entry_number}
                    </Link>
                ) : <span className="text-muted-foreground">—</span>}
                {disputes > 0 && (
                    <StatusBadge
                        tone="danger"
                        icon={TriangleAlert}
                        label={`${disputes} Dispute${disputes > 1 ? "s" : ""}`}
                        title="Not found in latest ledger upload"
                    />
                )}
            </div>
            {secondary && <span className="text-[11px] text-muted-foreground md:hidden">{secondary}</span>}
            <span className="text-[11px] tabular-nums text-muted-foreground md:hidden">{figures}</span>
            {tertiary && <span className="break-words text-[11px] text-muted-foreground lg:hidden">{tertiary}</span>}
        </div>
    );
}

function LicencesCell({ item }: { item: BoeListItem }) {
    const rows = (item.item_details || []) as BoeDetailRow[];
    const seen = new Map<string, { id: number | null; dispute: boolean }>();
    for (const r of rows) {
        if (!r.license_number) continue;
        const prev = seen.get(r.license_number);
        seen.set(r.license_number, {
            id: prev?.id ?? r.license_id ?? null,
            dispute: Boolean(prev?.dispute || r.is_dispute),
        });
    }
    if (seen.size === 0) {
        return item.licenses ? <span className="text-xs">{item.licenses}</span> : <span className="text-muted-foreground">—</span>;
    }
    return (
        <span className="flex flex-wrap gap-x-2 gap-y-0.5">
            {[...seen.entries()].map(([number, info]) =>
                info.id ? (
                    <Link
                        key={number}
                        to={`/licenses/${info.id}/overview`}
                        className={cn("rounded font-mono text-xs underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", info.dispute ? "text-destructive" : "text-primary")}
                    >
                        {number}
                    </Link>
                ) : (
                    <span key={number} className="font-mono text-xs">{number}</span>
                ),
            )}
        </span>
    );
}

function InvoiceCell({ item }: { item: BoeListItem }) {
    const {
        editingInvoiceId, invoiceDraft, setInvoiceDraft, invoiceSaving,
        startInvoiceEdit, cancelInvoiceEdit, saveInvoiceEdit,
    } = useBoeTable();
    if (editingInvoiceId === item.id) {
        return (
            <span className="inline-flex items-center gap-1">
                <Input
                    autoFocus
                    aria-label="Invoice number"
                    value={invoiceDraft}
                    onChange={(e) => setInvoiceDraft(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") saveInvoiceEdit(item.id); if (e.key === "Escape") cancelInvoiceEdit(); }}
                    placeholder="Invoice number"
                    className="h-7 w-36 rounded-md border-success px-2 py-0.5 text-xs"
                />
                <Button
                    type="button"
                    size="sm"
                    onClick={() => saveInvoiceEdit(item.id)}
                    disabled={invoiceSaving}
                    className="h-7 rounded-md bg-success px-2 text-xs text-white hover:bg-success/90 focus-visible:ring-success/40"
                >
                    {invoiceSaving ? "…" : "Save"}
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
        );
    }
    return (
        <button
            type="button"
            onClick={() => startInvoiceEdit(item)}
            title="Click to edit invoice number"
            className="inline-flex cursor-pointer items-center gap-1 whitespace-nowrap rounded-md border border-success/50 bg-success/10 px-1.5 py-0.5 text-xs font-medium text-success outline-none focus-visible:ring-[3px] focus-visible:ring-success/40"
        >
            {item.invoice_no
                ? (<><Receipt className="size-3.5" aria-hidden="true" /> {item.invoice_no}</>)
                : (<><PlusCircle className="size-3.5" aria-hidden="true" /> <span className="sr-only sm:not-sr-only">Add Invoice No</span></>)}
            <Pencil className="size-3 opacity-70" aria-hidden="true" />
        </button>
    );
}

function InvoiceStatusCell({ item }: { item: BoeListItem }) {
    return item.invoice_no
        ? <StatusBadge tone="success" label="Invoiced" />
        : <StatusBadge tone="neutral" label="Pending" />;
}

function QtyCell({ item }: { item: BoeListItem }) {
    const q = fmtQty(item.total_quantity);
    return q === "—" ? <>—</> : <>{q} <span className="text-muted-foreground">MT</span></>;
}

const col = (
    id: string,
    header: string,
    Cell: (p: { item: BoeListItem }) => React.ReactNode,
    meta?: ColumnDef<BoeListItem, unknown>["meta"],
): ColumnDef<BoeListItem, unknown> => ({
    id,
    header,
    meta,
    cell: ({ row }) => <Cell item={row.original} />,
});

function buildColumns(canEditInvoice: boolean): ColumnDef<BoeListItem, unknown>[] {
    return [
        col("bill_of_entry_number", "BOE Number", BoeNumberCell),
        col("bill_of_entry_date", "BOE Date", ({ item }) => <span className="whitespace-nowrap">{item.bill_of_entry_date || "—"}</span>, { hideBelow: "md" }),
        col("port_name", "Port", ({ item }) => <>{item.port_name || "—"}</>, { hideBelow: "md" }),
        col("product_name", "Product", ({ item }) => (
            item.product_name
                ? <span className="block max-w-[200px] truncate" title={item.product_name}>{item.product_name}</span>
                : <span className="italic text-muted-foreground">No product name</span>
        ), { hideBelow: "lg" }),
        ...(canEditInvoice ? [col("invoice_no", "Invoice No", InvoiceCell)] : []),
        col("total_inr", "CIF (INR)", ({ item }) => <span className="font-medium">{fmtInr(item.total_inr)}</span>, { numeric: true, hideBelow: "md" }),
        col("total_fc", "CIF (FC)", ({ item }) => <>{fmtFc2(item.total_fc)}</>, { numeric: true, hideBelow: "md" }),
        col("total_quantity", "Qty", QtyCell, { numeric: true, hideBelow: "md" }),
        col("unit_price", "Unit Price", ({ item }) => <>{fmtFc2(item.unit_price)}</>, { numeric: true, hideBelow: "lg" }),
        col("licenses", "Licence(s)", LicencesCell, { hideBelow: "lg" }),
        col("invoice_status", "Invoice", InvoiceStatusCell, { hideBelow: "md" }),
    ];
}

/** Trailing actions cell: one shared ActionMenu per row (same gating as before). */
function RowActionsMenu({ item }: { item: BoeListItem }) {
    const { actionCtx } = useBoeTable();
    const { actions } = useBoeRowActions(item, actionCtx);
    return <ActionMenu items={actions} label={`Actions for ${boeLabel(item)}`} />;
}

/** Expanded body: the existing `boe:<id>` record workspace (actions live in the row menu). */
function ExpandedBoe({ item }: { item: BoeListItem }) {
    const { canTransferLetter, onTransferLetter } = useBoeTable();
    return (
        // w-0 + min-w-full: the workspace fills the row but never widens the table (tab strip scrolls itself).
        <div className="w-0 min-w-full">
            <BoeRecordWorkspace
                item={item}
                onTransferLetter={canTransferLetter ? () => onTransferLetter(item.id) : undefined}
            />
        </div>
    );
}

/**
 * BOE register as a compact data table on the shared ExpandableDataTable
 * (Licence-style density). Several rows may be open together; each opens its
 * `boe:<id>` record workspace. List lifecycle and mutations stay in MasterList.
 */
export default function BoeTable(props: BoeTableProps) {
    const {
        loading, data, canWrite, canTransferLetter, entityName, filterParams, currentPage, pageSize, navigate,
        onDelete, invalidateList, confirmDangerousAction, onTransferLetter, onMerge, canEditInvoice,
    } = props;
    const columns = useMemo(() => buildColumns(canEditInvoice), [canEditInvoice]);
    const actionCtx: BoeRowActionContext = {
        canWrite, canTransferLetter, entityName, filterParams, currentPage, pageSize, navigate,
        onDelete, invalidateList, confirmDangerousAction, onTransferLetter, onMerge,
    };

    return (
        <BoeTableContext.Provider value={{ ...props, actionCtx }}>
            <ExpandableDataTable<BoeListItem>
                caption="Bills of entry"
                columns={columns}
                data={data}
                getRowId={(row) => String(row.id)}
                state={{ status: loading ? "loading" : "success" }}
                empty={{ title: "No bill of entries found", description: "Try adjusting filters or create a new BOE." }}
                density="compact"
                stickyHeader={false}
                singleExpand={false}
                getRowLabel={boeLabel}
                rowActions={(item) => <RowActionsMenu item={item} />}
                renderExpanded={(item) => <ExpandedBoe item={item} />}
            />
        </BoeTableContext.Provider>
    );
}
