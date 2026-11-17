import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { acctGet, acctKeys, acctPost, type BankAccount, type Invoice, type Paged, type Payment } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { useAccountingAccess } from "./useAccountingAccess";
import { useGuardedAction } from "./useGuardedAction";
import { formatMoney, isMoneyInput, isZero, sumMoney } from "./money";
import PartyPicker, { type Party } from "./PartyPicker";
import { Pager } from "./TradeTracking";
import { Amount, DataGrid, Field, inputCls, notifyError, Panel, QueryState, ReadOnlyNote, StatusBadge } from "./ui";

const PAYABLE = "PURCHASE,EXPENSE,COMMISSION_PAYABLE";
const RECEIVABLE = "SALES,COMMISSION_RECEIVABLE";

function RecordPayment({ onDone }: { onDone: () => void }) {
    const { entityId } = useAccounting();
    const { guard, dialog } = useGuardedAction();
    const [direction, setDirection] = useState<"PAYMENT" | "RECEIPT">("PAYMENT");
    const [party, setParty] = useState<Party | null>(null);
    const [form, setForm] = useState({ bank_account_id: "", date: new Date().toISOString().slice(0, 10), amount: "", tds_amount: "",
        mode: "NEFT", reference: "", narration: "" });
    const [alloc, setAlloc] = useState<Record<number, string>>({});
    const banks = useQuery({ queryKey: acctKeys.of(entityId, "banks"), queryFn: () => acctGet<BankAccount[]>("bank-accounts/", { entity: entityId }) });
    const bills = useQuery({
        queryKey: acctKeys.of(entityId, "open-bills", party?.id, direction),
        queryFn: () => acctGet<Paged<Invoice>>("invoices/", { entity: entityId, party_id: party?.id, status: "POSTED",
            kind: direction === "PAYMENT" ? PAYABLE : RECEIVABLE, page_size: 200 }),
        enabled: !!party,
    });
    const open = useMemo(() => (bills.data?.results ?? []).filter((b) => b.outstanding !== "0.00"), [bills.data]);
    const allocated = sumMoney(Object.values(alloc).filter(isMoneyInput));
    const partyAmount = sumMoney([form.amount || "0", direction === "RECEIPT" ? form.tds_amount || "0" : "0"]);
    const unallocated = sumMoney([partyAmount, `-${allocated}`]);
    const valid = party && form.bank_account_id && isMoneyInput(form.amount) && !unallocated.startsWith("-");
    const save = useMutation({
        mutationFn: () => acctPost<Payment>("payments/", { entity: entityId, direction, party_id: party?.id, ...form,
            tds_amount: direction === "RECEIPT" ? form.tds_amount || "0" : "0",
            allocations: Object.entries(alloc).filter(([, a]) => isMoneyInput(a) && !isZero(a)).map(([id, amount]) => ({ invoice_id: Number(id), amount })) }),
        onSuccess: (p) => { toast.success(`${p.voucher_number} posted`); setAlloc({}); setForm({ ...form, amount: "", tds_amount: "", reference: "" }); onDone(); },
        onError: notifyError,
    });
    const autoAllocate = () => {
        let remaining = partyAmount;
        const next: Record<number, string> = {};
        for (const b of [...open].sort((x, y) => x.date.localeCompare(y.date))) {
            if (remaining === "0.00" || remaining.startsWith("-")) break;
            const take = sumMoney([remaining, `-${b.outstanding}`]).startsWith("-") ? remaining : b.outstanding;
            next[b.id] = take;
            remaining = sumMoney([remaining, `-${take}`]);
        }
        setAlloc(next);
    };
    return (
        <Panel title="Record payment / receipt" actions={
            <div role="radiogroup" aria-label="Direction" className="flex rounded-lg border border-slate-300 p-0.5 text-sm">
                {(["PAYMENT", "RECEIPT"] as const).map((d) => (
                    <button key={d} type="button" role="radio" aria-checked={direction === d} onClick={() => { setDirection(d); setAlloc({}); }}
                            className={`rounded-md px-3 py-1 ${direction === d ? "bg-slate-900 text-white" : "text-slate-600"}`}>
                        {d === "PAYMENT" ? "Pay supplier" : "Receive from customer"}</button>))}
            </div>}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
                <div className="sm:col-span-2"><Field label="Party"><PartyPicker value={party} onChange={(p) => { setParty(p); setAlloc({}); }} /></Field></div>
                <Field label="Bank / cash"><select className={inputCls} value={form.bank_account_id} onChange={(e) => setForm({ ...form, bank_account_id: e.target.value })}>
                    <option value="">Select…</option>{(banks.data ?? []).map((b) => <option key={b.id} value={b.id}>{b.bank_name} {b.account_number}</option>)}</select></Field>
                <Field label="Date"><input type="date" className={inputCls} value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} /></Field>
                <Field label="Amount through bank"><input inputMode="decimal" className={`${inputCls} text-right`} value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} /></Field>
                {direction === "RECEIPT" && <Field label="TDS deducted by customer"><input inputMode="decimal" className={`${inputCls} text-right`} value={form.tds_amount} onChange={(e) => setForm({ ...form, tds_amount: e.target.value })} /></Field>}
                <Field label="Mode"><select className={inputCls} value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}>
                    {["NEFT", "RTGS", "IMPS", "UPI", "CHEQUE", "CASH", "OTHER"].map((m) => <option key={m}>{m}</option>)}</select></Field>
                <Field label="UTR / cheque no." hint="Used first when matching the bank statement"><input className={inputCls} value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} /></Field>
            </div>
            {party && (
                <div className="mt-4">
                    <div className="mb-2 flex items-center justify-between">
                        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Open bills of {party.name}</h3>
                        <Button size="sm" variant="outline" onClick={autoAllocate} disabled={!isMoneyInput(form.amount)}>Allocate oldest first</Button>
                    </div>
                    {(bills.data?.count ?? 0) > (bills.data?.results.length ?? 0) && (
                        <p className="mb-2 text-xs text-amber-700" role="status">Showing the first {bills.data?.results.length} of {bills.data?.count} posted bills; allocate the rest after posting.</p>
                    )}
                    <DataGrid rows={open} rowKey={(b) => b.id} empty="No open bills — the amount stays on account as an advance." caption="Open bills" columns={[
                        { key: "no", header: "Bill", cell: (b) => b.number },
                        { key: "date", header: "Date", cell: (b) => b.date },
                        { key: "due", header: "Due", cell: (b) => b.due_date ?? "—" },
                        { key: "st", header: "Status", cell: (b) => <StatusBadge status={b.payment_status} /> },
                        { key: "out", header: "Outstanding", numeric: true, cell: (b) => <Amount value={b.outstanding} /> },
                        { key: "alloc", header: "Allocate", numeric: true, cell: (b) => (
                            <input inputMode="decimal" className={`${inputCls} w-32 text-right`} aria-label={`Allocate to ${b.number}`} value={alloc[b.id] ?? ""}
                                   onChange={(e) => setAlloc({ ...alloc, [b.id]: e.target.value })} />) },
                    ]} />
                </div>
            )}
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
                <span>Allocated <b>{formatMoney(allocated)}</b> · On account (advance) <b className={unallocated.startsWith("-") ? "text-red-700" : ""}>{formatMoney(unallocated)}</b></span>
                <Button disabled={!valid || save.isPending} onClick={() => void guard({
                    title: direction === "PAYMENT" ? "Post payment" : "Post receipt", confirmText: "Post",
                    message: `${direction === "PAYMENT" ? "Pay" : "Receive"} ₹ ${formatMoney(form.amount)} ${direction === "PAYMENT" ? "to" : "from"} ${party?.name ?? ""}; allocate ₹ ${formatMoney(allocated)} to bills and keep ₹ ${formatMoney(unallocated)} on account?`,
                }, () => save.mutate())}>Post {direction === "PAYMENT" ? "payment" : "receipt"}</Button>
            </div>
            {dialog}
        </Panel>
    );
}

export default function Payments() {
    const { entityId, fyRange } = useAccounting();
    const { canApprove } = useAccountingAccess();
    const qc = useQueryClient();
    const [params, setParams] = useSearchParams();
    const pageNo = Math.max(1, Number(params.get("page")) || 1);
    const direction = params.get("direction") ?? "";
    const q = useQuery({ queryKey: acctKeys.of(entityId, "payments", direction, pageNo, fyRange.start),
        queryFn: () => acctGet<Paged<Payment>>("payments/", { entity: entityId, direction, page: pageNo, page_size: 50, ...fyRange }) });
    const refresh = () => qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) });
    return (
        <div className="space-y-4">
            {canApprove ? <RecordPayment onDone={() => void refresh()} />
                : <ReadOnlyNote need="the accounts approver role (recording a payment posts it)" />}
            <Panel title="Payments and receipts" actions={
                <select className={inputCls} value={direction} aria-label="Direction filter" onChange={(e) => setParams(e.target.value ? { direction: e.target.value } : {})}>
                    <option value="">All</option><option value="PAYMENT">Payments</option><option value="RECEIPT">Receipts</option></select>}>
                <QueryState isLoading={q.isLoading} error={q.error} onRetry={() => void q.refetch()}>
                    <DataGrid rows={q.data?.results ?? []} rowKey={(p) => p.id} caption="Payments" columns={[
                        { key: "date", header: "Date", cell: (p) => p.date },
                        { key: "v", header: "Voucher", cell: (p) => p.voucher_id ? <Link className="text-blue-700 hover:underline" to={`/accounting/vouchers/${p.voucher_id}`}>{p.voucher_number}</Link> : "—" },
                        { key: "d", header: "Type", cell: (p) => p.direction },
                        { key: "party", header: "Party", cell: (p) => p.party },
                        { key: "ref", header: "UTR / ref", cell: (p) => p.reference || (p.trade_payment_id ? `trade payment #${p.trade_payment_id}` : "—") },
                        { key: "amt", header: "Amount", numeric: true, cell: (p) => <Amount value={p.amount} /> },
                        { key: "tds", header: "TDS", numeric: true, cell: (p) => <Amount value={p.tds_amount} blankZero /> },
                        { key: "un", header: "On account", numeric: true, cell: (p) => <Amount value={p.unallocated} blankZero /> },
                        { key: "st", header: "Status", cell: (p) => <StatusBadge status={p.status} /> },
                    ]} />
                    <Pager page={pageNo} hasNext={!!q.data?.next} onPage={(p) => setParams({ ...(direction ? { direction } : {}), page: String(p) })} />
                </QueryState>
            </Panel>
        </div>
    );
}
