import { useState } from "react";
import { Link, Route, Routes, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { acctDelete, acctGet, acctKeys, acctPost, type Account, type Paged, type Voucher } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { useAccountingAccess } from "./useAccountingAccess";
import { useGuardedAction } from "./useGuardedAction";
import { isMoneyInput, sumMoney } from "./money";
import { Pager } from "./TradeTracking";
import { Amount, DataGrid, Field, inputCls, notifyError, Panel, QueryState, ReadOnlyNote, StatusBadge } from "./ui";

const TYPES = ["", "PURCHASE", "SALES", "PAYMENT", "RECEIPT", "CONTRA", "JOURNAL", "DEBIT_NOTE", "CREDIT_NOTE", "EXPENSE",
    "COMMISSION", "LOAN_DISBURSEMENT", "LOAN_REPAYMENT", "INTEREST_ACCRUAL", "OPENING", "ADJUSTMENT", "REVERSAL"];

function VoucherList() {
    const { entityId, fyRange } = useAccounting();
    const { canWrite } = useAccountingAccess();
    const [params, setParams] = useSearchParams();
    const filters = { type: params.get("type") ?? "", status: params.get("status") ?? "", search: params.get("search") ?? "",
        page: Math.max(1, Number(params.get("page")) || 1) };
    const set = (patch: Record<string, string>) => setParams({ ...Object.fromEntries(params), page: "1", ...patch });
    const q = useQuery({
        queryKey: acctKeys.of(entityId, "vouchers", filters, fyRange.start),
        queryFn: () => acctGet<Paged<Voucher>>("vouchers/", { entity: entityId, ...filters, ...fyRange, page_size: 50 }),
    });
    return (
        <div className="space-y-4">
            <Panel title="Vouchers" actions={<>
                <input className={inputCls} placeholder="Number / narration" defaultValue={filters.search} aria-label="Search vouchers"
                       onKeyDown={(e) => { if (e.key === "Enter") set({ search: (e.target as HTMLInputElement).value }); }} />
                <select className={inputCls} value={filters.type} aria-label="Voucher type" onChange={(e) => set({ type: e.target.value })}>
                    {TYPES.map((t) => <option key={t} value={t}>{t ? t.replace(/_/g, " ") : "All types"}</option>)}
                </select>
                <select className={inputCls} value={filters.status} aria-label="Status" onChange={(e) => set({ status: e.target.value })}>
                    {["", "DRAFT", "POSTED", "REVERSED"].map((s) => <option key={s} value={s}>{s || "All statuses"}</option>)}
                </select>
                {canWrite && <Link to="/accounting/vouchers/new"><Button size="sm">New journal</Button></Link>}
            </>}>
                <QueryState isLoading={q.isLoading} error={q.error} onRetry={() => void q.refetch()}>
                    <DataGrid rows={q.data?.results ?? []} rowKey={(v) => v.id} caption="Vouchers" columns={[
                        { key: "date", header: "Date", cell: (v) => v.date },
                        { key: "no", header: "Number", cell: (v) => <Link className="font-medium text-blue-700 hover:underline" to={`/accounting/vouchers/${v.id}`}>{v.number ?? "Draft"}</Link> },
                        { key: "type", header: "Type", cell: (v) => v.voucher_type.replace(/_/g, " ") },
                        { key: "narr", header: "Narration", cell: (v) => <span className="line-clamp-1">{v.narration}</span> },
                        { key: "src", header: "Source", cell: (v) => v.source_type ? `${v.source_type} #${v.source_id ?? ""}` : "—" },
                        { key: "total", header: "Amount", numeric: true, cell: (v) => <Amount value={v.total} /> },
                        { key: "st", header: "Status", cell: (v) => <StatusBadge status={v.status} /> },
                    ]} />
                    <Pager page={filters.page} hasNext={!!q.data?.next} onPage={(p) => set({ page: String(p) })} />
                </QueryState>
            </Panel>
        </div>
    );
}

function VoucherDetail() {
    const { canWrite, canApprove } = useAccountingAccess();
    const { id } = useParams();
    const { entityId } = useAccounting();
    const qc = useQueryClient();
    const navigate = useNavigate();
    const [reason, setReason] = useState("");
    const [alloc, setAlloc] = useState({ invoice_id: "", amount: "" });
    const { guard, dialog } = useGuardedAction();
    const q = useQuery({ queryKey: acctKeys.of(entityId, "voucher", id), queryFn: () => acctGet<Voucher>(`vouchers/${id}/`) });
    const done = (msg: string) => { toast.success(msg); void qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) }); };
    const post = useMutation({ mutationFn: () => acctPost(`vouchers/${id}/post/`), onSuccess: () => done("Posted"), onError: notifyError });
    const reverse = useMutation({
        mutationFn: () => acctPost<Voucher>(`vouchers/${id}/reverse/`, { reason }),
        onSuccess: (rev) => { done("Reversal posted"); navigate(`/accounting/vouchers/${rev.id}`); }, onError: notifyError,
    });
    const allocate = useMutation({
        mutationFn: () => acctPost(`vouchers/${id}/allocate/`, { allocations: [{ invoice_id: Number(alloc.invoice_id), amount: alloc.amount }] }),
        onSuccess: () => { done("Allocated to the bill"); setAlloc({ invoice_id: "", amount: "" }); }, onError: notifyError,
    });
    const remove = useMutation({ mutationFn: () => acctDelete(`vouchers/${id}/`), onSuccess: () => { done("Draft deleted"); navigate("/accounting/vouchers"); }, onError: notifyError });
    const v = q.data;
    return (
        <QueryState isLoading={q.isLoading} error={q.error} onRetry={() => void q.refetch()}>
            {v && (
                <Panel title={<span>{v.number ?? "Draft voucher"} <span className="ml-2"><StatusBadge status={v.status} /></span></span>}
                       actions={<>
                           {canApprove && v.status === "DRAFT" && <Button size="sm" disabled={post.isPending} onClick={() => void guard({
                               title: "Post voucher", confirmText: "Post", message: `Post this ${v.voucher_type.toLowerCase()} voucher for ₹ ${v.total}? It becomes immutable.`,
                           }, () => post.mutate())}>Post</Button>}
                           {canWrite && v.status === "DRAFT" && <Button size="sm" variant="outline" disabled={remove.isPending} onClick={() => void guard({
                               title: "Delete draft", severity: "danger", confirmText: "Delete", message: "Delete this draft voucher? Drafts have no ledger effect.",
                           }, () => remove.mutate())}>Delete draft</Button>}
                           {canApprove && v.status === "POSTED" && v.voucher_type !== "REVERSAL" && (
                               <>
                                   <input className={inputCls} placeholder="Reason for reversal" value={reason}
                                          onChange={(e) => setReason(e.target.value)} aria-label="Reversal reason" />
                                   <Button size="sm" variant="destructive" disabled={!reason.trim() || reverse.isPending}
                                           onClick={() => void guard({
                                               title: "Reverse voucher", severity: "danger", confirmText: "Reverse",
                                               message: `Post an exact reversal of ${v.number} (₹ ${v.total})? Document vouchers must be reversed from their bill/payment.`,
                                           }, () => reverse.mutate())}>Reverse</Button>
                               </>
                           )}
                       </>}>
                    <dl className="mb-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                        <div><dt className="text-xs text-slate-500">Date</dt><dd>{v.date}</dd></div>
                        <div><dt className="text-xs text-slate-500">Type</dt><dd>{v.voucher_type.replace(/_/g, " ")}</dd></div>
                        <div><dt className="text-xs text-slate-500">Source</dt><dd>{v.source_type} {v.source_id ?? ""} {v.source_event}</dd></div>
                        <div><dt className="text-xs text-slate-500">Posted by</dt><dd>{v.posted_by ?? "—"}</dd></div>
                        {v.reversal_of_id && <div><dt className="text-xs text-slate-500">Reverses</dt><dd><Link className="text-blue-700" to={`/accounting/vouchers/${v.reversal_of_id}`}>#{v.reversal_of_id}</Link></dd></div>}
                        {v.reversed_by_id && <div><dt className="text-xs text-slate-500">Reversed by</dt><dd><Link className="text-blue-700" to={`/accounting/vouchers/${v.reversed_by_id}`}>#{v.reversed_by_id}</Link></dd></div>}
                    </dl>
                    <p className="mb-3 text-sm text-slate-700">{v.narration}</p>
                    <DataGrid rows={v.lines ?? []} rowKey={(l) => l.line_no} caption="Voucher lines" columns={[
                        { key: "acct", header: "Account", cell: (l) => <Link className="text-blue-700 hover:underline" to={`/accounting/reports/general-ledger?account=${l.account_id}`}>{l.account_code} {l.account}</Link> },
                        { key: "narr", header: "Narration", cell: (l) => l.narration },
                        { key: "trade", header: "Trade", cell: (l) => l.trade_id ? <Link className="text-blue-700" to={`/trades/${l.trade_id}/edit`}>#{l.trade_id}</Link> : "" },
                        { key: "dr", header: "Debit", numeric: true, cell: (l) => <Amount value={l.debit} blankZero /> },
                        { key: "cr", header: "Credit", numeric: true, cell: (l) => <Amount value={l.credit} blankZero /> },
                    ]} footer={<tr><td className="px-3 py-1.5" colSpan={3}>Total</td>
                        <td className="px-3 py-1.5 text-right"><Amount value={sumMoney((v.lines ?? []).map((l) => l.debit))} /></td>
                        <td className="px-3 py-1.5 text-right"><Amount value={sumMoney((v.lines ?? []).map((l) => l.credit))} /></td></tr>} />
                    {canApprove && v.status === "POSTED" && v.voucher_type === "JOURNAL" && (
                        <form className="mt-4 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); allocate.mutate(); }}>
                            <Field label="Allocate on-account amount to bill id"><input inputMode="numeric" className={`${inputCls} w-28`} value={alloc.invoice_id} onChange={(e) => setAlloc({ ...alloc, invoice_id: e.target.value.replace(/\D/g, "") })} /></Field>
                            <Field label="Amount"><input inputMode="decimal" className={`${inputCls} w-32`} value={alloc.amount} onChange={(e) => setAlloc({ ...alloc, amount: e.target.value })} /></Field>
                            <Button size="sm" type="submit" disabled={!alloc.invoice_id || !isMoneyInput(alloc.amount) || allocate.isPending}>Allocate</Button>
                        </form>
                    )}
                    {!!v.audit?.length && (
                        <ol className="mt-4 space-y-1 border-l-2 border-slate-200 pl-3 text-xs text-slate-600">
                            {v.audit.map((a, i) => <li key={i}><span className="font-semibold">{a.action}</span> · {a.actor ?? "system"} · {a.at}</li>)}
                        </ol>
                    )}
                </Panel>
            )}
            {dialog}
        </QueryState>
    );
}

interface DraftLine { account_id: string; debit: string; credit: string; narration: string }

function NewJournal() {
    const { canWrite } = useAccountingAccess();
    const { entityId } = useAccounting();
    const qc = useQueryClient();
    const navigate = useNavigate();
    const [form, setForm] = useState({ voucher_type: "JOURNAL", date: new Date().toISOString().slice(0, 10), narration: "" });
    const [lines, setLines] = useState<DraftLine[]>([
        { account_id: "", debit: "", credit: "", narration: "" }, { account_id: "", debit: "", credit: "", narration: "" }]);
    const accounts = useQuery({
        queryKey: acctKeys.of(entityId, "accounts"),
        queryFn: () => acctGet<{ accounts: Account[] }>("accounts/", { entity: entityId }),
    });
    const dr = sumMoney(lines.map((l) => l.debit || "0"));
    const cr = sumMoney(lines.map((l) => l.credit || "0"));
    const valid = dr === cr && dr !== "0.00" && lines.every((l) => l.account_id && (isMoneyInput(l.debit || "0") && isMoneyInput(l.credit || "0")));
    const save = useMutation({
        mutationFn: () => acctPost<Voucher>("vouchers/", { entity: entityId, ...form,
            lines: lines.filter((l) => l.account_id).map((l) => ({ account_id: Number(l.account_id), debit: l.debit || "0",
                credit: l.credit || "0", narration: l.narration })) }),
        onSuccess: (v) => { toast.success("Draft saved — an approver can now post it"); void qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) }); navigate(`/accounting/vouchers/${v.id}`); },
        onError: notifyError,
    });
    const setLine = (i: number, patch: Partial<DraftLine>) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)));
    if (!canWrite) return <ReadOnlyNote need="an accounts manager or approver role" />;
    return (
        <Panel title="New manual voucher (draft)">
            <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-4">
                <Field label="Type"><select className={inputCls} value={form.voucher_type} onChange={(e) => setForm({ ...form, voucher_type: e.target.value })}>
                    {["JOURNAL", "CONTRA", "OPENING", "ADJUSTMENT"].map((t) => <option key={t}>{t}</option>)}</select></Field>
                <Field label="Date"><input type="date" className={inputCls} value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} /></Field>
                <div className="sm:col-span-2"><Field label="Narration"><input className={inputCls} value={form.narration} onChange={(e) => setForm({ ...form, narration: e.target.value })} /></Field></div>
            </div>
            <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-sm">
                <caption className="sr-only">Voucher lines</caption>
                <thead className="text-left text-xs text-slate-500"><tr><th className="py-1">Account</th><th>Narration</th><th className="text-right">Debit</th><th className="text-right">Credit</th></tr></thead>
                <tbody>
                    {lines.map((l, i) => (
                        <tr key={i}>
                            <td className="py-1 pr-2"><select className={`${inputCls} w-full`} value={l.account_id} aria-label={`Account line ${i + 1}`} onChange={(e) => setLine(i, { account_id: e.target.value })}>
                                <option value="">Select account…</option>
                                {(accounts.data?.accounts ?? []).filter((a) => a.is_active).map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}
                            </select></td>
                            <td className="pr-2"><input className={`${inputCls} w-full`} value={l.narration} aria-label={`Narration line ${i + 1}`} onChange={(e) => setLine(i, { narration: e.target.value })} /></td>
                            <td className="pr-2"><input inputMode="decimal" className={`${inputCls} w-32 text-right`} value={l.debit} aria-label={`Debit line ${i + 1}`} onChange={(e) => setLine(i, { debit: e.target.value, credit: e.target.value ? "" : l.credit })} /></td>
                            <td><input inputMode="decimal" className={`${inputCls} w-32 text-right`} value={l.credit} aria-label={`Credit line ${i + 1}`} onChange={(e) => setLine(i, { credit: e.target.value, debit: e.target.value ? "" : l.debit })} /></td>
                        </tr>
                    ))}
                </tbody>
                <tfoot><tr className="font-semibold"><td colSpan={2} className="py-2">
                    <Button size="sm" variant="ghost" onClick={() => setLines([...lines, { account_id: "", debit: "", credit: "", narration: "" }])}>+ Line</Button></td>
                    <td className="text-right"><Amount value={dr} /></td><td className="text-right"><Amount value={cr} /></td></tr></tfoot>
            </table></div>
            <div className="mt-3 flex items-center justify-between">
                <p className={`text-sm ${dr === cr ? "text-emerald-700" : "text-red-700"}`} role="status">
                    {dr === cr ? "Balanced" : `Difference ${sumMoney([dr, `-${cr}`])}`}
                </p>
                <Button disabled={!valid || save.isPending} onClick={() => save.mutate()}>Save draft</Button>
            </div>
        </Panel>
    );
}

export default function Vouchers() {
    return (
        <Routes>
            <Route index element={<VoucherList />} />
            <Route path="new" element={<NewJournal />} />
            <Route path=":id" element={<VoucherDetail />} />
        </Routes>
    );
}
