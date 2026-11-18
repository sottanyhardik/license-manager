/**
 * Purchase / Sale / Bank Payment ledger tabs of the inline licence workspace (Licence Ledger).
 * Read-only: every figure (rows and summary totals) comes from the API — nothing is recomputed here.
 */
import { Fragment, useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import type { UseQueryResult } from "@tanstack/react-query";
import { EmptyState, InlineError, LoadingState, StatusBadge, type Tone } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { openDocument } from "@/utils/documentDownload";
import { formatIndianNumber } from "@/utils/numberFormatter";
import { fmtDate } from "@/pages/license-balance/licenseBalanceHelpers";
import {
    isForbidden, useBankLedger, usePaymentLedgers,
    type BankLedgerRow, type BankReconciliation, type TradeLedgerRow, type TradePaymentStatus,
} from "./paymentLedgerApi";

export const LEDGER_PAGE_SIZE = 25;

const TH = "px-2 py-1.5 font-semibold";
const TD = "px-2 py-1.5";

/** ₹ amount for a decimal string; negatives render as `-₹x`. */
function money(value: string | number | null | undefined): string {
    if (value === null || value === undefined || value === "") return "—";
    const n = Number(value);
    if (Number.isNaN(n)) return String(value);
    return `${n < 0 ? "-" : ""}₹${formatIndianNumber(Math.abs(n))}`;
}

const isNegative = (value: string) => Number(value) < 0;

interface SummaryItem { label: string; value: string }

function SummaryStrip({ label, items }: { label: string; items: SummaryItem[] }) {
    return (
        <dl aria-label={label} className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {items.map((item) => (
                <div key={item.label} className="rounded-lg border border-border/70 bg-card px-3 py-2">
                    <dt className="text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">{item.label}</dt>
                    <dd className="text-sm font-semibold tabular-nums">{item.value}</dd>
                </div>
            ))}
        </dl>
    );
}

interface LedgerFrameProps<T> {
    query: UseQueryResult<unknown>;
    forbiddenTitle: string;
    emptyTitle: string;
    searchLabel: string;
    tableLabel: string;
    summaryLabel: string;
    summary: SummaryItem[] | null;
    rows: T[];
    matches: (row: T, needle: string) => boolean;
    renderTable: (pageRows: T[]) => ReactNode;
}

/** Shared states (loading / 403 / error / empty), summary strip, search and 25-per-page pagination. */
function LedgerFrame<T>({ query, forbiddenTitle, emptyTitle, searchLabel, tableLabel, summaryLabel, summary, rows, matches, renderTable }: LedgerFrameProps<T>) {
    const [search, setSearch] = useState("");
    const [page, setPage] = useState(0);

    if (query.isLoading) return <LoadingState variant="skeleton-rows" rows={4} label={`Loading ${tableLabel.toLowerCase()}`} />;
    if (query.isError) {
        if (isForbidden(query.error)) return <EmptyState title={forbiddenTitle} />;
        return <InlineError error={query.error} onRetry={() => { void query.refetch(); }} title={`Failed to load ${tableLabel.toLowerCase()}`} />;
    }
    if (!summary) return null;

    const needle = search.trim().toLowerCase();
    const filtered = needle ? rows.filter((row) => matches(row, needle)) : rows;
    const pageCount = Math.max(1, Math.ceil(filtered.length / LEDGER_PAGE_SIZE));
    const current = Math.min(page, pageCount - 1);
    const start = current * LEDGER_PAGE_SIZE;
    const pageRows = filtered.slice(start, start + LEDGER_PAGE_SIZE);

    return (
        <div className="space-y-3">
            <SummaryStrip label={summaryLabel} items={summary} />
            {rows.length === 0 ? <EmptyState title={emptyTitle} /> : (
                <>
                    <Input
                        type="search"
                        value={search}
                        onChange={(event) => { setSearch(event.target.value); setPage(0); }}
                        placeholder="Search…"
                        aria-label={searchLabel}
                        className="h-8 max-w-xs text-xs"
                    />
                    {filtered.length === 0 ? <EmptyState title="No matching rows" /> : renderTable(pageRows)}
                    {filtered.length > 0 && (
                        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                            <span aria-live="polite">{start + 1}–{start + pageRows.length} of {filtered.length}</span>
                            <div className="flex gap-2">
                                <Button type="button" size="sm" variant="outline" disabled={current === 0} onClick={() => setPage(current - 1)}>Prev</Button>
                                <Button type="button" size="sm" variant="outline" disabled={current >= pageCount - 1} onClick={() => setPage(current + 1)}>Next</Button>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

function ExpandButton({ open, label, onClick }: { open: boolean; label: string; onClick: () => void }) {
    const Icon = open ? ChevronDown : ChevronRight;
    return (
        <button type="button" aria-expanded={open} aria-label={label} onClick={onClick}
            className="inline-flex size-6 items-center justify-center rounded text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <Icon aria-hidden="true" className="size-3.5" />
        </button>
    );
}

function TableShell({ label, minWidth, children }: { label: string; minWidth: string; children: ReactNode }) {
    return (
        <div className="overflow-x-auto rounded-lg border border-border/70 bg-card">
            <table aria-label={label} className={cn("w-full text-xs", minWidth)}>{children}</table>
        </div>
    );
}

function DetailPanel({ colSpan, children }: { colSpan: number; children: ReactNode }) {
    return (
        <tr className="border-t border-border/60 bg-muted/20">
            <td colSpan={colSpan} className="px-4 py-2">{children}</td>
        </tr>
    );
}

function MiniTable({ label, headers, children }: { label: string; headers: { text: string; right?: boolean }[]; children: ReactNode }) {
    return (
        <table aria-label={label} className="w-full max-w-2xl text-xs">
            <thead className="text-[10.5px] uppercase tracking-wide text-muted-foreground">
                <tr>{headers.map((h) => <th key={h.text} scope="col" className={cn("px-2 py-1 font-semibold", h.right ? "text-right" : "text-left")}>{h.text}</th>)}</tr>
            </thead>
            <tbody>{children}</tbody>
        </table>
    );
}

// ── Purchase / Sale ──────────────────────────────────────────────────────────

const TRADE_STATUS: Record<TradePaymentStatus, { tone: Tone; label: string }> = {
    PAID: { tone: "success", label: "Paid" },
    PARTIAL: { tone: "warning", label: "Partially paid" },
    UNPAID: { tone: "danger", label: "Unpaid" },
};

interface TradeCopy {
    key: "purchase" | "sale";
    tableLabel: string;
    searchLabel: string;
    summaryLabel: string;
    emptyTitle: string;
    forbiddenTitle: string;
    partyHeader: string;
    settledHeader: string;
    statusHeader: string;
    summaryLabels: [string, string, string, string];
    noun: string;
}

const PURCHASE_COPY: TradeCopy = {
    key: "purchase", tableLabel: "Purchase ledger", searchLabel: "Search purchase ledger", summaryLabel: "Purchase ledger summary",
    emptyTitle: "No purchase invoices for this licence", forbiddenTitle: "You don't have access to these invoices",
    partyHeader: "Supplier", settledHeader: "Paid", statusHeader: "Status",
    summaryLabels: ["Total Purchase Invoices", "Total Purchase Amount", "Total Paid", "Total Outstanding"], noun: "payments",
};
const SALE_COPY: TradeCopy = {
    key: "sale", tableLabel: "Sale ledger", searchLabel: "Search sale ledger", summaryLabel: "Sale ledger summary",
    emptyTitle: "No sale invoices for this licence", forbiddenTitle: "You don't have access to these invoices",
    partyHeader: "Customer", settledHeader: "Received", statusHeader: "Receipt status",
    summaryLabels: ["Total Sales Invoices", "Total Sales Amount", "Total Received", "Total Outstanding"], noun: "receipts",
};

function Outstanding({ value }: { value: string }) {
    return isNegative(value)
        ? <span className="font-medium text-[var(--tb-info-text)]" title="Overpaid">{money(value)} <span className="font-normal">(overpaid)</span></span>
        : <span>{money(value)}</span>;
}

function TradeTable({ copy, rows }: { copy: TradeCopy; rows: TradeLedgerRow[] }) {
    const [openId, setOpenId] = useState<number | null>(null);
    const [openError, setOpenError] = useState<string | null>(null);

    const openInvoice = async (row: TradeLedgerRow) => {
        if (!row.document) return;
        setOpenError(null);
        try {
            await openDocument(row.document.url, `${row.invoice_number}.pdf`);
        } catch {
            setOpenError(`Could not open invoice ${row.invoice_number}.`);
        }
    };

    return (
        <>
            {openError && <p role="alert" className="text-xs text-destructive">{openError}</p>}
            <TableShell label={copy.tableLabel} minWidth="min-w-[960px]">
                <thead className="bg-muted/95 text-[10.5px] uppercase tracking-wide text-muted-foreground">
                    <tr>
                        <th scope="col" className="w-8 px-2 py-1.5"><span className="sr-only">Details</span></th>
                        <th scope="col" className={cn(TH, "text-left")}>Invoice No</th>
                        <th scope="col" className={cn(TH, "text-left")}>Date</th>
                        <th scope="col" className={cn(TH, "text-left")}>{copy.partyHeader}</th>
                        <th scope="col" className={cn(TH, "text-right")}>Amount</th>
                        <th scope="col" className={cn(TH, "text-right")}>GST</th>
                        <th scope="col" className={cn(TH, "text-right")}>Total</th>
                        <th scope="col" className={cn(TH, "text-right")}>This licence</th>
                        <th scope="col" className={cn(TH, "text-right")}>{copy.settledHeader}</th>
                        <th scope="col" className={cn(TH, "text-right")}>Outstanding</th>
                        <th scope="col" className={cn(TH, "text-left")}>{copy.statusHeader}</th>
                        <th scope="col" className={cn(TH, "text-left")}>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row) => {
                        const open = openId === row.trade_id;
                        const status = TRADE_STATUS[row.status];
                        return (
                            <Fragment key={row.trade_id}>
                                <tr className="border-t border-border/60 hover:bg-muted/30">
                                    <td className="px-2 py-1.5">
                                        <ExpandButton open={open} label={`${open ? "Hide" : "Show"} ${copy.noun} for invoice ${row.invoice_number}`}
                                            onClick={() => setOpenId(open ? null : row.trade_id)} />
                                    </td>
                                    <td className={cn(TD, "font-medium")}>{row.invoice_number}</td>
                                    <td className={cn(TD, "whitespace-nowrap")}>{fmtDate(row.invoice_date)}</td>
                                    <td className={TD}>{row.company_name ?? "—"}</td>
                                    <td className={cn(TD, "text-right tabular-nums")}>{money(row.amount)}</td>
                                    <td className={cn(TD, "text-right text-muted-foreground")}>Not tracked</td>
                                    <td className={cn(TD, "text-right font-medium tabular-nums")}>{money(row.total)}</td>
                                    <td className={cn(TD, "text-right tabular-nums")}>{money(row.licence_amount)}</td>
                                    <td className={cn(TD, "text-right tabular-nums")}>{money(row.settled)}</td>
                                    <td className={cn(TD, "text-right tabular-nums")}><Outstanding value={row.outstanding} /></td>
                                    <td className={TD}><StatusBadge tone={status.tone} label={status.label} /></td>
                                    <td className={TD}>
                                        {row.document ? (
                                            <Button type="button" size="sm" variant="ghost" className="h-6 px-2 text-xs"
                                                aria-label={`Open invoice ${row.invoice_number}`} onClick={() => { void openInvoice(row); }}>
                                                <ExternalLink aria-hidden="true" className="size-3" /> Open invoice
                                            </Button>
                                        ) : <span className="text-muted-foreground">—</span>}
                                    </td>
                                </tr>
                                {open && (
                                    <DetailPanel colSpan={12}>
                                        {row.payments.length === 0 ? <p className="text-muted-foreground">No payments recorded</p> : (
                                            <MiniTable label={`Payments for invoice ${row.invoice_number}`}
                                                headers={[{ text: "Date" }, { text: "Amount", right: true }, { text: "Note" }, { text: "Bank reference" }]}>
                                                {row.payments.map((p) => (
                                                    <tr key={p.id} className="border-t border-border/50">
                                                        <td className="whitespace-nowrap px-2 py-1">{fmtDate(p.date)}</td>
                                                        <td className="px-2 py-1 text-right tabular-nums">{money(p.amount)}</td>
                                                        <td className="px-2 py-1">{p.note || "—"}</td>
                                                        <td className="px-2 py-1">{p.bank_reference || "—"}</td>
                                                    </tr>
                                                ))}
                                            </MiniTable>
                                        )}
                                    </DetailPanel>
                                )}
                            </Fragment>
                        );
                    })}
                </tbody>
            </TableShell>
        </>
    );
}

function TradeLedgerTab({ licenseId, copy }: { licenseId: number; copy: TradeCopy }) {
    const query = usePaymentLedgers(licenseId);
    const section = query.data?.[copy.key];
    const s = section?.summary;
    const [l0, l1, l2, l3] = copy.summaryLabels;
    return (
        <LedgerFrame<TradeLedgerRow>
            query={query}
            forbiddenTitle={copy.forbiddenTitle}
            emptyTitle={copy.emptyTitle}
            searchLabel={copy.searchLabel}
            tableLabel={copy.tableLabel}
            summaryLabel={copy.summaryLabel}
            summary={s ? [
                { label: l0, value: String(s.invoice_count) },
                { label: l1, value: money(s.total_amount) },
                { label: l2, value: money(s.total_settled) },
                { label: l3, value: money(s.total_outstanding) },
            ] : null}
            rows={section?.rows ?? []}
            matches={(row, needle) =>
                row.invoice_number.toLowerCase().includes(needle)
                || (row.company_name ?? "").toLowerCase().includes(needle)
                || row.payments.some((p) => (p.bank_reference ?? "").toLowerCase().includes(needle))}
            renderTable={(pageRows) => <TradeTable key={copy.key} copy={copy} rows={pageRows} />}
        />
    );
}

export function PurchaseLedgerTab({ licenseId }: { licenseId: number }) {
    return <TradeLedgerTab licenseId={licenseId} copy={PURCHASE_COPY} />;
}

export function SaleLedgerTab({ licenseId }: { licenseId: number }) {
    return <TradeLedgerTab licenseId={licenseId} copy={SALE_COPY} />;
}

// ── Bank payment ledger ──────────────────────────────────────────────────────

const RECON: Record<BankReconciliation, { tone: Tone; label: string }> = {
    RECONCILED: { tone: "success", label: "Reconciled" },
    PARTIAL: { tone: "warning", label: "Partially reconciled" },
    UNRECONCILED: { tone: "neutral", label: "Unreconciled" },
};

function BankTable({ rows }: { rows: BankLedgerRow[] }) {
    const [openId, setOpenId] = useState<number | null>(null);
    return (
        <TableShell label="Bank payment ledger" minWidth="min-w-[1100px]">
            <thead className="bg-muted/95 text-[10.5px] uppercase tracking-wide text-muted-foreground">
                <tr>
                    <th scope="col" className="w-8 px-2 py-1.5"><span className="sr-only">Details</span></th>
                    <th scope="col" className={cn(TH, "text-left")}>Date</th>
                    <th scope="col" className={cn(TH, "text-left")}>Bank account</th>
                    <th scope="col" className={cn(TH, "text-left")}>UTR / Reference</th>
                    <th scope="col" className={cn(TH, "text-left")}>Mode</th>
                    <th scope="col" className={cn(TH, "text-left")}>Type</th>
                    <th scope="col" className={cn(TH, "text-left")}>Counterparty</th>
                    <th scope="col" className={cn(TH, "text-left")}>Linked invoices</th>
                    <th scope="col" className={cn(TH, "text-right")}>Amount</th>
                    <th scope="col" className={cn(TH, "text-right")}>Allocated (this licence)</th>
                    <th scope="col" className={cn(TH, "text-right")}>Unallocated</th>
                    <th scope="col" className={cn(TH, "text-left")}>Reconciliation</th>
                </tr>
            </thead>
            <tbody>
                {rows.map((row) => {
                    const open = openId === row.payment_id;
                    const recon = RECON[row.reconciliation];
                    const name = row.reference || `payment ${row.payment_id}`;
                    return (
                        <Fragment key={row.payment_id}>
                            <tr className="border-t border-border/60 hover:bg-muted/30">
                                <td className="px-2 py-1.5">
                                    <ExpandButton open={open} label={`${open ? "Hide" : "Show"} allocations for ${name}`}
                                        onClick={() => setOpenId(open ? null : row.payment_id)} />
                                </td>
                                <td className={cn(TD, "whitespace-nowrap")}>{fmtDate(row.date)}</td>
                                <td className={TD}>{row.bank_account || "—"}</td>
                                <td className={cn(TD, "font-medium")}>{row.reference || "—"}</td>
                                <td className={TD}>{row.mode || "—"}</td>
                                <td className={TD}>
                                    <StatusBadge tone={row.direction === "PAYMENT" ? "primary" : "info"} label={row.direction === "PAYMENT" ? "Payment" : "Receipt"} />
                                </td>
                                <td className={TD}>{row.party || "—"}</td>
                                <td className={TD}>{row.invoices.length ? row.invoices.map((i) => i.number).join(", ") : "—"}</td>
                                <td className={cn(TD, "text-right tabular-nums")}>{money(row.amount)}</td>
                                <td className={cn(TD, "text-right tabular-nums")}>{money(row.allocated_to_licence)}</td>
                                <td className={cn(TD, "text-right tabular-nums")}>{money(row.unallocated)}</td>
                                <td className={TD}><StatusBadge tone={recon.tone} label={recon.label} /></td>
                            </tr>
                            {open && (
                                <DetailPanel colSpan={12}>
                                    <div className="grid gap-3 md:grid-cols-2">
                                        <div>
                                            <h4 className="mb-1 text-[11px] font-semibold text-foreground">Invoice allocations</h4>
                                            {row.invoices.length === 0 ? <p className="text-muted-foreground">No invoices linked</p> : (
                                                <MiniTable label={`Invoice allocations for ${name}`} headers={[{ text: "Invoice" }, { text: "Amount", right: true }]}>
                                                    {row.invoices.map((i) => (
                                                        <tr key={`${i.invoice_id ?? "trade"}-${i.trade_id ?? ""}-${i.number}`} className="border-t border-border/50">
                                                            <td className="px-2 py-1">{i.number}</td>
                                                            <td className="px-2 py-1 text-right tabular-nums">{money(i.amount)}</td>
                                                        </tr>
                                                    ))}
                                                </MiniTable>
                                            )}
                                        </div>
                                        <div>
                                            <h4 className="mb-1 text-[11px] font-semibold text-foreground">Matched statement lines</h4>
                                            {row.statement_lines.length === 0 ? <p className="text-muted-foreground">No statement lines matched</p> : (
                                                <MiniTable label={`Statement lines for ${name}`} headers={[{ text: "Date" }, { text: "Reference" }, { text: "Amount", right: true }]}>
                                                    {row.statement_lines.map((l) => (
                                                        <tr key={l.id} className="border-t border-border/50">
                                                            <td className="whitespace-nowrap px-2 py-1">{fmtDate(l.txn_date)}</td>
                                                            <td className="px-2 py-1">{l.reference || "—"}</td>
                                                            <td className="px-2 py-1 text-right tabular-nums">{money(l.amount)}</td>
                                                        </tr>
                                                    ))}
                                                </MiniTable>
                                            )}
                                        </div>
                                    </div>
                                </DetailPanel>
                            )}
                        </Fragment>
                    );
                })}
            </tbody>
        </TableShell>
    );
}

export function BankPaymentLedgerTab({ licenseId }: { licenseId: number }) {
    const query = useBankLedger(licenseId);
    const s = query.data?.summary;
    return (
        <LedgerFrame<BankLedgerRow>
            query={query}
            forbiddenTitle="You don't have access to bank transactions"
            emptyTitle="No bank transactions for this licence"
            searchLabel="Search bank payment ledger"
            tableLabel="Bank payment ledger"
            summaryLabel="Bank payment ledger summary"
            summary={s ? [
                { label: "Total Payments", value: money(s.total_payments) },
                { label: "Total Receipts", value: money(s.total_receipts) },
                { label: "Total Allocated", value: money(s.total_allocated) },
                { label: "Total Unallocated", value: money(s.total_unallocated) },
            ] : null}
            rows={query.data?.rows ?? []}
            matches={(row, needle) =>
                row.reference.toLowerCase().includes(needle)
                || row.party.toLowerCase().includes(needle)
                || row.invoices.some((i) => i.number.toLowerCase().includes(needle))}
            renderTable={(pageRows) => <BankTable rows={pageRows} />}
        />
    );
}
