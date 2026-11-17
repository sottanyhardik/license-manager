import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { acctGet, acctKeys, acctPost, type BankAccount, type Invoice, type Money, type Paged, type Payment } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { useAccountingAccess } from "./useAccountingAccess";
import { useGuardedAction } from "./useGuardedAction";
import { formatMoney, isMoneyInput, isZero, sumMoney } from "./money";
import PartyPicker, { type Party } from "./PartyPicker";
import { Pager } from "./TradeTracking";
import { Amount, DataGrid, Field, inputCls, notifyError, Panel, QueryState, ReadOnlyNote, StatusBadge } from "./ui";

const PAYABLE = "PURCHASE,EXPENSE,COMMISSION_PAYABLE";
const RECEIVABLE = "SALES,COMMISSION_RECEIVABLE";

/** An unmatched bank statement line offered for this party (GET parties/<id>/bank-lines/). */
interface BankLine {
    id: number; bank_account_id: number; bank: string; txn_date: string; narration: string; reference: string;
    amount: Money; remaining: Money; status: string; mode: string; score: number; source: "alias" | "name" | "";
}

type Basis = "BILLS" | "ACCOUNT";

function BankLinePicker({ party, direction, selected, onPick, onClear }: {
    party: Party; direction: "PAYMENT" | "RECEIPT"; selected: BankLine | null;
    onPick: (line: BankLine) => void; onClear: () => void;
}) {
    const { entityId } = useAccounting();
    const [search, setSearch] = useState("");
    const [open, setOpen] = useState(false);
    const lines = useQuery({
        queryKey: acctKeys.of(entityId, "party-bank-lines", party.id, direction, search),
        queryFn: () => acctGet<{ lines: BankLine[] }>(`parties/${party.id}/bank-lines/`, { entity: entityId, direction, search }),
        enabled: open,
    });
    if (selected) {
        return (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm" role="status">
                <span>Bank transaction <b>{selected.txn_date}</b> · {selected.bank} · <span className="break-all">{selected.narration}</span>
                    {" "}· <b><Amount value={selected.remaining} /></b> unmatched</span>
                <Button size="sm" variant="outline" onClick={onClear}>Clear</Button>
            </div>
        );
    }
    return (
        <div className="rounded-lg border border-slate-200 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm text-slate-600">Came through a bank transaction? Pick it to fill bank, date, amount and UTR; posting also matches it.</span>
                <Button size="sm" variant="outline" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Hide bank transactions" : "Pick bank transaction"}</Button>
            </div>
            {open && (
                <div className="mt-3 space-y-2">
                    <input className={inputCls} placeholder="Search narration or UTR (shows all unmatched lines)" aria-label="Search bank transactions"
                           value={search} onChange={(e) => setSearch(e.target.value)} />
                    <QueryState isLoading={lines.isLoading} error={lines.error} onRetry={() => void lines.refetch()}>
                        <DataGrid rows={lines.data?.lines ?? []} rowKey={(l) => l.id} caption="Unmatched bank transactions"
                                  empty={search ? "No unmatched bank transaction matches the search." : `No unmatched ${direction === "RECEIPT" ? "deposits" : "withdrawals"} look like ${party.name}; search to see all.`}
                                  columns={[
                            { key: "d", header: "Date", cell: (l) => l.txn_date },
                            { key: "b", header: "Bank", cell: (l) => l.bank },
                            { key: "n", header: "Narration", cell: (l) => <span className="break-all">{l.narration}{l.source === "alias" && <span className="ml-1 text-xs text-emerald-700">(learned)</span>}</span> },
                            { key: "r", header: "UTR / ref", cell: (l) => l.reference || "—" },
                            { key: "a", header: "Unmatched", numeric: true, cell: (l) => <Amount value={l.remaining} /> },
                            { key: "p", header: "", cell: (l) => <Button size="sm" onClick={() => { onPick(l); setOpen(false); }} aria-label={`Use bank transaction of ${l.txn_date} for ${l.remaining}`}>Use</Button> },
                        ]} />
                    </QueryState>
                </div>
            )}
        </div>
    );
}

function RecordPayment({ onDone }: { onDone: () => void }) {
    const { entityId } = useAccounting();
    const { guard, dialog } = useGuardedAction();
    const [direction, setDirection] = useState<"PAYMENT" | "RECEIPT">("PAYMENT");
    const [party, setParty] = useState<Party | null>(null);
    const [basis, setBasis] = useState<Basis>("BILLS");
    const [bankLine, setBankLine] = useState<BankLine | null>(null);
    const [amountTouched, setAmountTouched] = useState(false);
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
    const effectiveAlloc = basis === "BILLS" ? alloc : {};
    const allocated = sumMoney(Object.values(effectiveAlloc).filter(isMoneyInput));
    const partyAmount = sumMoney([form.amount || "0", direction === "RECEIPT" ? form.tds_amount || "0" : "0"]);
    const unallocated = sumMoney([partyAmount, `-${allocated}`]);
    const overLine = !!bankLine && isMoneyInput(form.amount) && sumMoney([bankLine.remaining, `-${form.amount}`]).startsWith("-");
    const valid = party && form.bank_account_id && isMoneyInput(form.amount) && !unallocated.startsWith("-") && !overLine;
    const resetSelection = () => { setAlloc({}); setBankLine(null); setAmountTouched(false); };
    const save = useMutation({
        mutationFn: () => acctPost<Payment>("payments/", { entity: entityId, direction, party_id: party?.id, ...form,
            tds_amount: direction === "RECEIPT" ? form.tds_amount || "0" : "0",
            ...(bankLine ? { statement_line_id: bankLine.id } : {}),
            allocations: Object.entries(effectiveAlloc).filter(([, a]) => isMoneyInput(a) && !isZero(a)).map(([id, amount]) => ({ invoice_id: Number(id), amount })) }),
        onSuccess: (p) => {
            toast.success(`${p.voucher_number} posted${bankLine ? " and matched to the bank transaction" : ""}`);
            resetSelection(); setForm({ ...form, amount: "", tds_amount: "", reference: "" }); onDone();
        },
        onError: notifyError,
    });
    /** Ticking bills fills the amount with their total until the user types an amount or picks a bank line. */
    const applyAlloc = (next: Record<number, string>) => {
        setAlloc(next);
        if (!amountTouched) setForm((f) => ({ ...f, amount: Object.keys(next).length ? sumMoney(Object.values(next).filter(isMoneyInput)) : "" }));
    };
    const toggleBill = (b: Invoice, checked: boolean) => {
        const next = { ...alloc };
        if (checked) next[b.id] = b.outstanding; else delete next[b.id];
        applyAlloc(next);
    };
    const allTicked = open.length > 0 && open.every((b) => alloc[b.id] !== undefined);
    const toggleAll = (checked: boolean) => applyAlloc(checked ? Object.fromEntries(open.map((b) => [b.id, b.outstanding])) : {});
    const autoAllocate = () => {
        let remaining = partyAmount;
        const next: Record<number, string> = {};
        for (const b of [...open].sort((x, y) => (x.due_date ?? x.date).localeCompare(y.due_date ?? y.date) || x.date.localeCompare(y.date))) {
            if (remaining === "0.00" || remaining.startsWith("-")) break;
            const take = sumMoney([remaining, `-${b.outstanding}`]).startsWith("-") ? remaining : b.outstanding;
            next[b.id] = take;
            remaining = sumMoney([remaining, `-${take}`]);
        }
        setAlloc(next);
    };
    const pickLine = (l: BankLine) => {
        setBankLine(l); setAmountTouched(true);
        setForm((f) => ({ ...f, bank_account_id: String(l.bank_account_id), date: l.txn_date, amount: l.remaining,
            mode: l.mode || f.mode, reference: l.reference || f.reference }));
    };
    const verb = direction === "PAYMENT" ? "Pay" : "Receive";
    const message = `${verb} ₹ ${formatMoney(form.amount)} ${direction === "PAYMENT" ? "to" : "from"} ${party?.name ?? ""}; `
        + (basis === "BILLS" ? `allocate ₹ ${formatMoney(allocated)} to bills and keep ₹ ${formatMoney(unallocated)} on account` : `keep the whole ₹ ${formatMoney(unallocated)} on account (advance)`)
        + (bankLine ? `, and match the bank transaction of ${bankLine.txn_date}?` : "?");
    return (
        <Panel title="Record payment / receipt" actions={
            <div role="radiogroup" aria-label="Direction" className="flex rounded-lg border border-slate-300 p-0.5 text-sm">
                {(["PAYMENT", "RECEIPT"] as const).map((d) => (
                    <button key={d} type="button" role="radio" aria-checked={direction === d} onClick={() => { setDirection(d); resetSelection(); }}
                            className={`rounded-md px-3 py-1 ${direction === d ? "bg-slate-900 text-white" : "text-slate-600"}`}>
                        {d === "PAYMENT" ? "Pay supplier" : "Receive from customer"}</button>))}
            </div>}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
                <div className="sm:col-span-2"><Field label="Party"><PartyPicker value={party} onChange={(p) => { setParty(p); resetSelection(); }} /></Field></div>
                <Field label="Bank / cash"><select className={inputCls} value={form.bank_account_id} disabled={!!bankLine}
                                                   onChange={(e) => setForm({ ...form, bank_account_id: e.target.value })}>
                    <option value="">Select…</option>{(banks.data ?? []).map((b) => <option key={b.id} value={b.id}>{b.bank_name} {b.account_number}</option>)}</select></Field>
                <Field label="Date"><input type="date" className={inputCls} value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} /></Field>
                <Field label="Amount through bank" hint={bankLine ? `max ${formatMoney(bankLine.remaining)}` : undefined}>
                    <input inputMode="decimal" className={`${inputCls} text-right`} value={form.amount} aria-invalid={overLine || undefined}
                           onChange={(e) => { setAmountTouched(true); setForm({ ...form, amount: e.target.value }); }} /></Field>
                {direction === "RECEIPT" && <Field label="TDS deducted by customer"><input inputMode="decimal" className={`${inputCls} text-right`} value={form.tds_amount} onChange={(e) => setForm({ ...form, tds_amount: e.target.value })} /></Field>}
                <Field label="Mode"><select className={inputCls} value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}>
                    {["NEFT", "RTGS", "IMPS", "UPI", "CHEQUE", "CASH", "OTHER"].map((m) => <option key={m}>{m}</option>)}</select></Field>
                <Field label="UTR / cheque no." hint="Used first when matching the bank statement"><input className={inputCls} value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} /></Field>
            </div>
            {overLine && <p className="mt-2 text-sm text-red-700" role="alert">The amount is more than the bank transaction's unmatched {formatMoney(bankLine?.remaining ?? "0")}.</p>}
            {party && (
                <div className="mt-4 space-y-4">
                    <BankLinePicker party={party} direction={direction} selected={bankLine} onPick={pickLine}
                                    onClear={() => { setBankLine(null); setAmountTouched(false); }} />
                    <div>
                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                            <div role="radiogroup" aria-label="Settle against" className="flex rounded-lg border border-slate-300 p-0.5 text-sm">
                                {([["BILLS", "Against invoices"], ["ACCOUNT", "On account (advance)"]] as const).map(([b, label]) => (
                                    <button key={b} type="button" role="radio" aria-checked={basis === b} onClick={() => setBasis(b)}
                                            className={`rounded-md px-3 py-1 ${basis === b ? "bg-slate-900 text-white" : "text-slate-600"}`}>{label}</button>))}
                            </div>
                            {basis === "BILLS" && <Button size="sm" variant="outline" onClick={autoAllocate} disabled={!isMoneyInput(form.amount)}>Allocate oldest first</Button>}
                        </div>
                        {basis === "ACCOUNT" ? (
                            <p className="rounded-lg border border-dashed border-slate-300 px-3 py-4 text-sm text-slate-600">
                                No bills are settled now. The whole amount stays on {party.name}'s account as an advance; allocate it to bills later from this list.</p>
                        ) : (<>
                            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Open bills of {party.name} — tick to settle in full, or type an amount</h3>
                            {(bills.data?.count ?? 0) > (bills.data?.results.length ?? 0) && (
                                <p className="mb-2 text-xs text-amber-700" role="status">Showing the first {bills.data?.results.length} of {bills.data?.count} posted bills; allocate the rest after posting.</p>
                            )}
                            <DataGrid rows={open} rowKey={(b) => b.id} empty="No open bills — the amount stays on account as an advance." caption="Open bills" columns={[
                                { key: "sel", header: <input type="checkbox" aria-label="Select all open bills" checked={allTicked} disabled={!open.length}
                                                           onChange={(e) => toggleAll(e.target.checked)} />,
                                  cell: (b) => <input type="checkbox" aria-label={`Settle ${b.number}`} checked={alloc[b.id] !== undefined}
                                                      onChange={(e) => toggleBill(b, e.target.checked)} /> },
                                { key: "no", header: "Bill", cell: (b) => b.number },
                                { key: "date", header: "Date", cell: (b) => b.date },
                                { key: "due", header: "Due", cell: (b) => b.due_date ?? "—" },
                                { key: "st", header: "Status", cell: (b) => <StatusBadge status={b.payment_status} /> },
                                { key: "out", header: "Outstanding", numeric: true, cell: (b) => <Amount value={b.outstanding} /> },
                                { key: "alloc", header: "Allocate", numeric: true, cell: (b) => (
                                    <input inputMode="decimal" className={`${inputCls} w-32 text-right`} aria-label={`Allocate to ${b.number}`} value={alloc[b.id] ?? ""}
                                           onChange={(e) => { const next = { ...alloc }; if (e.target.value === "") delete next[b.id]; else next[b.id] = e.target.value; setAlloc(next); }} />) },
                            ]} />
                        </>)}
                    </div>
                </div>
            )}
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
                <span>Allocated <b>{formatMoney(allocated)}</b> · On account (advance) <b className={unallocated.startsWith("-") ? "text-red-700" : ""}>{formatMoney(unallocated)}</b></span>
                <Button disabled={!valid || save.isPending} onClick={() => void guard({
                    title: direction === "PAYMENT" ? "Post payment" : "Post receipt", confirmText: "Post", message,
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
    const q = useQuery({ queryKey: acctKeys.of(entityId, "payments", direction, pageNo, fyRange.start, fyRange.end),
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
