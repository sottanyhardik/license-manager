import React, { useMemo } from "react";
import { ChevronDown, Inbox, Link as LinkIcon } from "lucide-react";
import { toast } from "sonner";
import api from "../../api/axios";
import EntityCard from "../../components/primitives/EntityCard";
import DetailTable from "../../components/primitives/DetailTable";
import { saveFilterState } from "../../utils/filterPersistence";
import { cn } from "@/lib/utils";
import "./TradesListView.css";

/**
 * Presentation-only view for the /trades list.  Data fetching, permissions,
 * grouping and mutation ownership intentionally remain in MasterList so this
 * component cannot alter the list API contract or filter behaviour.
 */
export type TradeListItem = {
    id: number;
    direction?: string | null;
    direction_label?: string | null;
    invoice_number?: string | null;
    invoice_date?: string | null;
    license_type_label?: string | null;
    total_amount?: string | number | null;
    paid_or_received?: string | number | null;
    due_amount?: string | number | null;
    from_company_label?: string | null;
    to_company_label?: string | null;
    counterpart_id?: number | null;
    counterpart_info?: { id: number; type?: string | null } | null;
    linked_trade_info?: { id: number; type?: string | null } | null;
    lines?: Array<Record<string, unknown>> | null;
    boes?: Array<{ bill_of_entry_number?: string | null }> | null;
    incentive_license?: string | null;
    [key: string]: any;
};

export type TradeGroup =
    | { type: "single"; trade: TradeListItem; pairKey: string }
    | { type: "pair"; sale: TradeListItem; purchase: TradeListItem; pairKey: string };

type Props = {
    loading: boolean;
    data: TradeListItem[];
    tradeGroups: TradeGroup[];
    canWrite: boolean;
    entityName: string;
    filterParams: Record<string, unknown>;
    currentPage: number;
    pageSize: number;
    navigate: (path: string) => void;
    onDelete: (item: TradeListItem) => void;
    onOpenLink: (item: TradeListItem) => void;
    onCopyToCounterpart: (item: TradeListItem) => void | Promise<void>;
    onTransferLetter: (item: TradeListItem) => void;
    expandedTrades: Set<number>;
    onToggleTrade: (id: number) => void;
    expandedPairs: Set<string>;
    onTogglePair: (id: string) => void;
};

const dash = "—";

function hasValue(value: unknown) {
    return value !== null && value !== undefined && value !== "";
}

/** Keeps explicit zero values visible while preserving API decimal values. */
function formatInr(value: unknown) {
    if (!hasValue(value)) return dash;
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return String(value);
    return `₹${parsed.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatDecimal(value: unknown, digits = 3) {
    if (!hasValue(value)) return dash;
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return String(value);
    return parsed.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

function formatForeignCurrency(value: unknown) {
    if (!hasValue(value)) return dash;
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return String(value);
    return `$${parsed.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

async function downloadSaleInvoice(item: TradeListItem, includeSignature: boolean) {
    try {
        const response = await api.get(`trades/${item.id}/generate-bill-of-supply/`, {
            params: { include_signature: includeSignature },
            responseType: "blob",
        });
        const url = window.URL.createObjectURL(new Blob([response.data], { type: "application/pdf" }));
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `Bill_of_Supply_${item.invoice_number}_${includeSignature ? "with" : "without"}_sign.pdf`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        window.URL.revokeObjectURL(url);
    } catch {
        toast.error("Failed to generate invoice");
    }
}

function directionTone(direction?: string | null) {
    if (direction === "SALE") return "success";
    if (direction === "PURCHASE") return "info";
    if (direction === "COMMISSION_SALE") return "warning";
    return "primary";
}

export default function TradesListView({
    loading,
    data,
    tradeGroups,
    canWrite,
    entityName,
    filterParams,
    currentPage,
    pageSize,
    navigate,
    onDelete,
    onOpenLink,
    onCopyToCounterpart,
    onTransferLetter,
    expandedTrades,
    onToggleTrade,
    expandedPairs,
    onTogglePair,
}: Props) {
    const groupCountLabel = useMemo(() => `${tradeGroups.length} trade ${tradeGroups.length === 1 ? "record" : "records"}`, [tradeGroups.length]);

    if (loading) {
        return (
            <section aria-busy="true" aria-live="polite" className="space-y-2" aria-label="Loading trades">
                <div className="sr-only">Loading trades</div>
                {[0, 1, 2].map((row) => <div key={row} className="h-28 animate-pulse rounded-[--tb-r-md] border border-border bg-muted/35" />)}
            </section>
        );
    }

    if (data.length === 0) {
        return (
            <section className="surface-panel flex min-h-36 flex-col items-center justify-center gap-2 px-4 py-6 text-center" aria-live="polite">
                <Inbox className="size-5 text-muted-foreground" aria-hidden="true" />
                <h2 className="text-sm font-semibold text-foreground">No trades found</h2>
                <p className="max-w-md text-sm text-muted-foreground">Adjust the current filters or search to find a trade.</p>
            </section>
        );
    }

    const renderTradeCard = (item: TradeListItem) => {
        const counterpart = item.counterpart_info || item.linked_trade_info;
        const isLinked = Boolean(item.counterpart_id || counterpart);
        const detailRows = item.lines || [];
        const direction = item.direction || dash;
        const counterpartyLabel = item.direction === "SALE" ? "Buyer" : item.direction === "PURCHASE" ? "Supplier" : "Counterparty";
        const counterparty = item.direction === "SALE" ? item.to_company_label : item.from_company_label;

        return (
            <EntityCard
                key={item.id}
                accent={directionTone(item.direction)}
                className="trade-entity-card"
                title={<span aria-label={`Invoice ${item.invoice_number || "not available"}`}>{item.invoice_number || <span className="italic font-normal text-muted-foreground">No Invoice</span>}</span>}
                headerChips={[
                    { tone: directionTone(item.direction), label: item.direction_label || direction },
                    item.license_type_label && { label: item.license_type_label },
                    item.invoice_date && { icon: "calendar3", label: item.invoice_date },
                ].filter(Boolean)}
                summary={[
                    { label: "Total INR", value: formatInr(item.total_amount) },
                    { label: item.direction === "SALE" ? "Received INR" : "Paid INR", value: formatInr(item.paid_or_received), tone: "success" },
                    { label: "Due INR", value: formatInr(item.due_amount), tone: Number(item.due_amount) > 0 ? "danger" : undefined },
                ]}
                actions={[
                    { icon: "file-earmark-text", title: "Transfer Letter", tone: "warning", onClick: () => onTransferLetter(item), children: "TL" },
                    ...(item.direction === "SALE" ? [
                        { icon: "file-pdf", title: "Invoice (With Sign)", tone: "success", onClick: () => downloadSaleInvoice(item, true) },
                        { icon: "file-pdf", title: "Invoice (Without Sign)", tone: "warning", onClick: () => downloadSaleInvoice(item, false) },
                    ] : []),
                    canWrite && !isLinked && (item.direction === "PURCHASE" || item.direction === "SALE") && {
                        icon: "copy",
                        label: item.direction === "SALE" ? "Copy to Purchase" : "Copy to Sale",
                        title: item.direction === "SALE" ? "Copy this Sale to a linked Purchase" : "Copy this Purchase to a linked Sale",
                        tone: "info",
                        onClick: () => onCopyToCounterpart(item),
                    },
                    isLinked && {
                        icon: "link-45deg",
                        title: `View Linked ${counterpart?.type === "purchase" ? "Purchase" : "Sale"}`,
                        tone: "success",
                        label: `Linked ${counterpart?.type === "purchase" ? "Purchase" : "Sale"}`,
                        onClick: () => counterpart?.id && navigate(`/trades/${counterpart.id}/edit`),
                    },
                    canWrite && !isLinked && { icon: "link-45deg", title: "Link to existing trade", tone: "primary", onClick: () => onOpenLink(item) },
                    canWrite && {
                        icon: "pencil-fill",
                        title: "Edit",
                        tone: "primary",
                        onClick: () => {
                            saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: "" });
                            navigate(`/trades/${item.id}/edit`);
                        },
                    },
                    canWrite && { icon: "trash", title: "Delete", tone: "danger", onClick: () => onDelete(item) },
                ].filter(Boolean)}
                viewOpen={expandedTrades.has(item.id)}
                onView={() => onToggleTrade(item.id)}
                detailLabel={detailRows.length ? `${detailRows.length} Line${detailRows.length === 1 ? "" : "s"}` : "Details"}
                detail={() => (
                    <DetailTable
                        columns={[
                            { key: "sr_number_label", label: "Sr#", nowrap: true, render: (value: unknown, row: any) => value || (row.sr_number != null ? String(row.sr_number) : dash) },
                            { key: "description", label: "Description", muted: true, render: (value: unknown) => hasValue(value) ? value : dash },
                            { key: "hsn_code", label: "HSN", nowrap: true, render: (value: unknown) => hasValue(value) ? <code>{String(value)}</code> : dash },
                            { key: "qty_kg", label: "Qty (KG)", align: "right", nowrap: true, render: (value: unknown) => formatDecimal(value) },
                            { key: "cif_fc", label: "CIF FC $", align: "right", nowrap: true, render: (value: unknown) => formatForeignCurrency(value) },
                            { key: "cif_inr", label: "CIF INR", align: "right", nowrap: true, render: (value: unknown) => formatInr(value) },
                            { key: "amount_inr", label: "Amount INR", align: "right", nowrap: true, bold: true, render: (value: unknown) => formatInr(value) },
                        ]}
                        rows={detailRows}
                        emptyMessage="No trade lines."
                    />
                )}
            >
                <dl className="grid gap-x-5 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
                    <div className="min-w-0">
                        <dt className="entity-card-stat-label trade-stat-label">From</dt>
                        <dd className="truncate text-[13.5px] font-medium text-foreground" title={item.from_company_label || dash}>{item.from_company_label || dash}</dd>
                    </div>
                    <div className="min-w-0">
                        <dt className="entity-card-stat-label trade-stat-label">To</dt>
                        <dd className="truncate text-[13.5px] font-medium text-foreground" title={item.to_company_label || dash}>{item.to_company_label || dash}</dd>
                    </div>
                    <div className="min-w-0">
                        <dt className="entity-card-stat-label trade-stat-label">{counterpartyLabel}</dt>
                        <dd className="truncate text-[13.5px] font-medium text-primary" title={counterparty || dash}>{counterparty || dash}</dd>
                    </div>
                    {item.boes && item.boes.length > 0 && (
                        <div className="min-w-0">
                            <dt className="entity-card-stat-label trade-stat-label">BOE</dt>
                            <dd className="truncate text-[13.5px] font-medium text-primary" title={item.boes.map((boe) => boe.bill_of_entry_number).filter(Boolean).join(", ")}>{item.boes.map((boe) => boe.bill_of_entry_number).filter(Boolean).join(", ") || dash}</dd>
                        </div>
                    )}
                    {item.incentive_license && (
                        <div className="min-w-0">
                            <dt className="entity-card-stat-label trade-stat-label">Incentive Licence</dt>
                            <dd className="truncate text-[13.5px] font-medium text-success" title={item.incentive_license}>{item.incentive_license}</dd>
                        </div>
                    )}
                </dl>
            </EntityCard>
        );
    };

    return (
        <section aria-label="Trades" className="trades-list-view space-y-2.5">
            <p className="sr-only" aria-live="polite">{groupCountLabel}</p>
            {tradeGroups.map((group) => {
                if (group.type === "single") return renderTradeCard(group.trade);
                const { sale, purchase, pairKey } = group;
                const isExpanded = expandedPairs.has(pairKey);
                const companies = `${sale.from_company_label || "-"} ↔ ${sale.to_company_label || "-"}`;
                return (
                    <section key={pairKey} className="overflow-hidden rounded-[--tb-r-md] border border-primary/25 border-l-4 border-l-primary/70 bg-card shadow-sm">
                        <button
                            type="button"
                            className="flex w-full flex-wrap items-center gap-2 bg-primary/5 px-3.5 py-2.5 text-left hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                            aria-expanded={isExpanded}
                            aria-controls={`${pairKey}-contents`}
                            onClick={() => onTogglePair(pairKey)}
                        >
                            <span className="rounded-[--tb-r-sm] bg-success/10 px-2 py-0.5 text-xs font-bold text-success">Sale</span>
                            <LinkIcon className="size-4" aria-hidden="true" />
                            <span className="trade-pair-purchase rounded-[--tb-r-sm] bg-primary/10 px-2 py-0.5 text-xs font-bold">Purchase</span>
                            <span className="trade-pair-companies min-w-0 flex-1 truncate text-[0.82rem] font-semibold">{companies}</span>
                            <span className="text-[12.5px] text-muted-foreground">{sale.invoice_date || dash}</span>
                            <span className="text-[12.5px] tabular-nums text-muted-foreground">Sale: {formatInr(sale.total_amount)} · Purchase: {formatInr(purchase.total_amount)}</span>
                            <ChevronDown className={cn("trade-pair-toggle size-4 shrink-0 transition-transform", isExpanded && "rotate-180")} aria-hidden="true" />
                        </button>
                        {isExpanded && <div id={`${pairKey}-contents`} className="flex flex-col gap-2 bg-[--tb-sunken] p-2">{renderTradeCard(sale)}{renderTradeCard(purchase)}</div>}
                    </section>
                );
            })}
        </section>
    );
}
