import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { acctGet, acctKeys, acctPost, type BankAccount, type Paged, type TradeRow } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { useAccountingAccess } from "./useAccountingAccess";
import { formatMoney } from "./money";
import { useGuardedAction } from "./useGuardedAction";
import { Amount, DataGrid, inputCls, notifyError, Panel, QueryState, StatusBadge } from "./ui";

const STATUSES = ["", "NOT_ACCOUNTED", "PENDING", "ACCOUNTED", "PARTIALLY_ACCOUNTED", "EXCEPTION", "REVERSED"];

export default function TradeTracking() {
    const { entityId, entity, fyRange } = useAccounting();
    const { guard, dialog } = useGuardedAction();
    const { canApprove } = useAccountingAccess();
    const qc = useQueryClient();
    const [params, setParams] = useSearchParams();
    const status = params.get("status") ?? "";
    const pageNo = Math.max(1, Number(params.get("page")) || 1);
    const [bankId, setBankId] = useState<string>("");

    const q = useQuery({
        queryKey: acctKeys.of(entityId, "trades", status, pageNo, fyRange.start, fyRange.end),
        queryFn: () => acctGet<Paged<TradeRow> & { summary: Record<string, number> }>("trades/",
            { entity: entityId, status, page: pageNo, page_size: 50, ...fyRange }),
    });
    const banks = useQuery({
        queryKey: acctKeys.of(entityId, "banks"),
        queryFn: () => acctGet<BankAccount[]>("bank-accounts/", { entity: entityId }),
    });
    const refresh = () => qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) });

    const post = useMutation({
        mutationFn: async (row: TradeRow) => {
            const inv = row.invoice_id
                ? { id: row.invoice_id }
                : await acctPost<{ id: number }>("invoices/from-trade/", { trade_id: row.trade_id });
            return acctPost(`invoices/${inv.id}/post/`);
        },
        onSuccess: () => { toast.success("Posted to books"); void refresh(); },
        onError: notifyError,
    });
    const resync = useMutation({
        mutationFn: (row: TradeRow) => acctPost(`invoices/${row.invoice_id}/resync/`, { reason: "Trade edited after posting" }),
        onSuccess: () => { toast.success("Reversed and re-posted from the current trade"); void refresh(); },
        onError: notifyError,
    });
    const payments = useMutation({
        mutationFn: async (row: TradeRow) => {
            for (const id of row.unaccounted_payment_ids) {
                await acctPost("payments/from-trade-payment/", { trade_payment_id: id, bank_account_id: Number(bankId) });
            }
        },
        onSuccess: () => { toast.success("Trade payments accounted"); },
        onError: notifyError,
        onSettled: () => { void refresh(); },  // a partial failure still shows what was accounted
    });

    const actions = (row: TradeRow) => {
        if (!canApprove) return null;
        if (row.accounting_status === "NOT_ACCOUNTED" || row.accounting_status === "PENDING") {
            return <Button size="sm" disabled={post.isPending} onClick={() => void guard({
                title: "Post trade to books", confirmText: "Post",
                message: `Post ${row.invoice_number} (${row.party ?? ""}) for ₹ ${formatMoney(row.trade_total)} into ${entity?.name ?? ""}'s books? Posted entries can only be corrected by reversal.`,
            }, () => post.mutate(row))}>Post to books</Button>;
        }
        if (row.accounting_status === "EXCEPTION") {
            return <Button size="sm" variant="destructive" disabled={resync.isPending} onClick={() => void guard({
                title: "Reverse and re-post", severity: "danger", confirmText: "Reverse & re-post",
                message: `The trade ${row.invoice_number} changed after posting. Its voucher ${row.voucher_number ?? ""} will be reversed and the current trade posted again.`,
            }, () => resync.mutate(row))}>
                Reverse &amp; re-post</Button>;
        }
        if (row.accounting_status === "PARTIALLY_ACCOUNTED") {
            return <Button size="sm" variant="outline" disabled={!bankId || payments.isPending}
                           title={bankId ? "" : "Choose the bank account these payments went through"}
                           onClick={() => void guard({
                               title: "Account trade payments", confirmText: "Account",
                               message: `Post ${row.unaccounted_payment_ids.length} trade payment(s) of ${row.invoice_number} through the selected bank? If the money was already entered as a payment/receipt, the system refuses instead of counting it twice.`,
                           }, () => payments.mutate(row))}>Account {row.unaccounted_payment_ids.length} payment(s)</Button>;
        }
        return null;
    };

    return (
        <Panel title={`Trades of ${entity?.name ?? ""} and their accounting`} actions={<>
            <select className={inputCls} value={status} aria-label="Accounting status"
                    onChange={(e) => setParams(e.target.value ? { status: e.target.value } : {})}>
                {STATUSES.map((s) => <option key={s} value={s}>{s ? s.replace(/_/g, " ") : "All statuses"}</option>)}
            </select>
            {canApprove && <select className={inputCls} value={bankId} aria-label="Bank for trade payments" onChange={(e) => setBankId(e.target.value)}>
                <option value="">Bank for trade payments…</option>
                {(banks.data ?? []).map((b) => <option key={b.id} value={b.id}>{b.bank_name} {b.account_number}</option>)}
            </select>}
        </>}>
            <QueryState isLoading={q.isLoading} error={q.error} onRetry={() => void q.refetch()}>
                <div className="mb-3 flex flex-wrap gap-2 text-xs">
                    {Object.entries(q.data?.summary ?? {}).map(([k, v]) => (
                        <button key={k} type="button" aria-pressed={status === k} onClick={() => setParams({ status: k })}
                                className="rounded-full border border-slate-200 bg-white px-2 py-1 hover:border-blue-400">
                            <StatusBadge status={k} /> <span className="ml-1 font-semibold">{v}</span>
                        </button>
                    ))}
                </div>
                <DataGrid rows={q.data?.results ?? []} rowKey={(r) => r.trade_id} caption="Trade accounting status" columns={[
                    { key: "date", header: "Date", cell: (r) => r.invoice_date },
                    { key: "no", header: "Trade invoice", cell: (r) => <Link className="text-blue-700 hover:underline" to={`/trades/${r.trade_id}/edit`}>{r.invoice_number}</Link> },
                    { key: "dir", header: "Type", cell: (r) => r.direction.replace("_", " ") },
                    { key: "party", header: "Party", cell: (r) => r.party ?? "—" },
                    { key: "total", header: "Trade total", numeric: true, cell: (r) => <Amount value={r.trade_total} /> },
                    { key: "st", header: "Accounting", cell: (r) => <StatusBadge status={r.accounting_status} /> },
                    { key: "v", header: "Voucher", cell: (r) => r.voucher_id
                        ? <Link className="text-blue-700 hover:underline" to={`/accounting/vouchers/${r.voucher_id}`}>{r.voucher_number}</Link> : "—" },
                    { key: "pay", header: "Settlement", cell: (r) => <StatusBadge status={r.payment_status} /> },
                    { key: "out", header: "Outstanding", numeric: true, cell: (r) => r.invoice_id
                        ? <Amount value={r.outstanding} to={`/accounting/invoices/${r.invoice_id}`} /> : "—" },
                    { key: "act", header: <span className="sr-only">Actions</span>, cell: actions },
                ]} />
                <Pager page={pageNo} hasNext={!!q.data?.next} onPage={(p) => setParams({ ...(status ? { status } : {}), page: String(p) })} />
            </QueryState>
            {dialog}
        </Panel>
    );
}

export function Pager({ page, hasNext, onPage }: { page: number; hasNext: boolean; onPage: (p: number) => void }) {
    return (
        <div className="mt-3 flex items-center justify-end gap-2 text-sm">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button>
            <span className="text-slate-500">Page {page}</span>
            <Button size="sm" variant="outline" disabled={!hasNext} onClick={() => onPage(page + 1)}>Next</Button>
        </div>
    );
}
