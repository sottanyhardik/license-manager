import { useState } from "react";
import { Link, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
    acctGet, acctKeys, acctPost, uploadStatement, type Account, type BankAccount, type Candidate, type Money, type Paged,
    type StatementLine, type SuspenseRow,
} from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { useAccountingAccess } from "./useAccountingAccess";
import BankProposals from "./BankProposals";
import { Pager } from "./TradeTracking";
import { useGuardedAction } from "./useGuardedAction";
import { formatMoney, isMoneyInput, sumMoney } from "./money";
import { Amount, DataGrid, Field, inputCls, notifyError, Panel, QueryState, StatusBadge } from "./ui";

function useBanks() {
    const { entityId } = useAccounting();
    return useQuery({ queryKey: acctKeys.of(entityId, "banks"), queryFn: () => acctGet<BankAccount[]>("bank-accounts/", { entity: entityId }) });
}

function useRefresh() {
    const { entityId } = useAccounting();
    const qc = useQueryClient();
    return () => qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) });
}

function BankAccounts() {
    const { canApprove } = useAccountingAccess();
    const { entityId } = useAccounting();
    const banks = useBanks();
    const refresh = useRefresh();
    const [f, setF] = useState({ bank_name: "", account_number: "", ifsc: "", opening_balance: "", is_cash: false });
    const add = useMutation({
        mutationFn: () => acctPost("bank-accounts/", { entity: entityId, ...f, opening_balance: f.opening_balance || null }),
        onSuccess: () => { toast.success("Bank account added"); setF({ bank_name: "", account_number: "", ifsc: "", opening_balance: "", is_cash: false }); void refresh(); },
        onError: notifyError,
    });
    return (
        <Panel title="Bank and cash accounts (this entity only)">
            <DataGrid rows={banks.data ?? []} rowKey={(b) => b.id} empty="No bank accounts yet." caption="Bank accounts" columns={[
                { key: "n", header: "Bank", cell: (b) => `${b.bank_name}${b.is_cash ? " (cash)" : ""}` },
                { key: "a", header: "Account no.", cell: (b) => b.account_number },
                { key: "i", header: "IFSC", cell: (b) => b.ifsc || "—" },
                { key: "bal", header: "Book balance", numeric: true, cell: (b) => <Amount value={b.book_balance} to={`/accounting/reports/general-ledger?account=${b.account_id}`} /> },
                { key: "go", header: <span className="sr-only">Open</span>, cell: (b) => <Link className="text-sm text-blue-700 hover:underline" to={`/accounting/banking/workbench/${b.id}`}>Reconcile →</Link> },
            ]} />
            {canApprove && <form className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-6" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
                <Field label="Bank name"><input className={inputCls} required value={f.bank_name} onChange={(e) => setF({ ...f, bank_name: e.target.value })} /></Field>
                <Field label="Account number"><input className={inputCls} required value={f.account_number} onChange={(e) => setF({ ...f, account_number: e.target.value })} /></Field>
                <Field label="IFSC"><input className={inputCls} value={f.ifsc} onChange={(e) => setF({ ...f, ifsc: e.target.value })} /></Field>
                <Field label="Opening balance" hint="At books start date"><input inputMode="decimal" className={inputCls} value={f.opening_balance} onChange={(e) => setF({ ...f, opening_balance: e.target.value })} /></Field>
                <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={f.is_cash} onChange={(e) => setF({ ...f, is_cash: e.target.checked })} /> Cash account</label>
                <Button className="self-end" type="submit" disabled={add.isPending || (!!f.opening_balance && !isMoneyInput(f.opening_balance.replace("-", "")))}>Add account</Button>
            </form>}
        </Panel>
    );
}

function Upload({ bank }: { bank: BankAccount }) {
    const { canWrite } = useAccountingAccess();
    const refresh = useRefresh();
    const [file, setFile] = useState<File | null>(null);
    const [mapping, setMapping] = useState("");
    const [result, setResult] = useState<Awaited<ReturnType<typeof uploadStatement>> | null>(null);
    const up = useMutation({
        mutationFn: () => {
            let cm: Record<string, string> | undefined;
            if (mapping.trim()) cm = JSON.parse(mapping) as Record<string, string>;
            return uploadStatement(bank.id, file as File, cm);
        },
        onSuccess: (r) => { setResult(r); toast.success(`${r.rows_new} new line(s); ${r.rows_duplicate} duplicate(s) skipped`); void refresh(); },
        onError: notifyError,
    });
    if (!canWrite) return null;
    return (
        <Panel title="Upload statement (CSV or Excel)">
            <div className="flex flex-wrap items-end gap-3">
                <Field label="Statement file"><input type="file" accept=".csv,.txt,.xlsx,.xlsm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
                <div className="min-w-72 flex-1"><Field label="Column mapping (optional)" hint='Only if auto-detect fails, e.g. {"txn_date":"Tran Date","debit":"Dr Amt","credit":"Cr Amt"}'>
                    <input className={inputCls} value={mapping} onChange={(e) => setMapping(e.target.value)} /></Field></div>
                <Button disabled={!file || up.isPending} onClick={() => up.mutate()}>Import</Button>
            </div>
            {result && (
                <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm" role="status">
                    {result.rows_total} rows · <b>{result.rows_new} new</b> · {result.rows_duplicate} duplicates skipped · {result.rows_rejected} rejected
                    {result.errors.length > 0 && <ul className="mt-2 list-disc pl-5 text-red-700">{result.errors.slice(0, 10).map((e) => <li key={e.row}>Row {e.row}: {e.error}</li>)}</ul>}
                </div>
            )}
        </Panel>
    );
}

function LineMatcher({ line, onDone }: { line: StatementLine; onDone: () => void }) {
    const { canWrite, canApprove } = useAccountingAccess();
    const { entityId } = useAccounting();
    const cands = useQuery({ queryKey: acctKeys.of(entityId, "candidates", line.id, line.matched_amount),
        queryFn: () => acctGet<{ candidates: Candidate[] }>(`statement-lines/${line.id}/candidates/`) });
    const [split, setSplit] = useState<Record<number, string>>({});
    const [reason, setReason] = useState("");
    const { guard, dialog } = useGuardedAction();
    const total = sumMoney(Object.values(split).filter(isMoneyInput));
    const match = useMutation({
        mutationFn: () => acctPost(`statement-lines/${line.id}/match/`, { allocations: Object.entries(split)
            .filter(([, a]) => isMoneyInput(a)).map(([voucher_id, amount]) => ({ voucher_id: Number(voucher_id), amount })) }),
        onSuccess: () => { toast.success("Matched"); setSplit({}); onDone(); }, onError: notifyError,
    });
    const suspense = useMutation({
        mutationFn: () => acctPost("suspense/", { line_id: line.id, reason }),
        onSuccess: () => { toast.success("Moved to suspense — resolve it from the Suspense tab"); onDone(); }, onError: notifyError,
    });
    const unmatch = useMutation({
        mutationFn: (matchId: number) => acctPost(`bank-matches/${matchId}/unmatch/`, { reason: reason.trim() }),
        onSuccess: () => { toast.success("Match removed (history kept)"); onDone(); }, onError: notifyError,
    });
    return (
        <div className="rounded-lg border border-blue-200 bg-blue-50/40 p-3">
            <p className="mb-2 text-sm"><b>{line.txn_date}</b> · {line.narration} · {line.reference && <code className="text-xs">{line.reference}</code>} · unmatched <b>{formatMoney(line.unmatched)}</b></p>
            {line.matches.length > 0 && (
                <ul className="mb-2 space-y-1 text-xs">{line.matches.map((m) => (
                    <li key={m.id} className={m.is_active ? "" : "text-slate-400 line-through"}>
                        {m.method} → <Link className="text-blue-700" to={`/accounting/vouchers/${m.voucher_id}`}>{m.voucher_number}</Link> {formatMoney(m.amount)}
                        {canWrite && m.is_active && m.method !== "SUSPENSE" && <button type="button" className="ml-2 text-red-700 hover:underline disabled:opacity-50" disabled={!reason.trim() || unmatch.isPending}
                            title={reason.trim() ? "" : "Enter a reason first"} aria-label={`Unmatch ${m.voucher_number}`}
                            onClick={() => void guard({ title: "Remove match", severity: "danger", confirmText: "Unmatch",
                                message: `Remove the match to ${m.voucher_number} (₹ ${formatMoney(m.amount)})? The history is kept.` }, () => unmatch.mutate(m.id))}>unmatch</button>}
                    </li>))}</ul>
            )}
            <QueryState isLoading={cands.isLoading} error={cands.error}>
                <DataGrid rows={cands.data?.candidates ?? []} rowKey={(c) => c.voucher.id} empty="No book entry on this side of the bank ledger. Record the payment/receipt, or move the line to suspense." caption="Candidates" columns={[
                    { key: "v", header: "Voucher", cell: (c) => <Link className="text-blue-700" to={`/accounting/vouchers/${c.voucher.id}`}>{c.voucher.number}</Link> },
                    { key: "d", header: "Date", cell: (c) => c.voucher.date },
                    { key: "p", header: "Party", cell: (c) => c.party || c.voucher.narration },
                    { key: "s", header: "Signals", cell: (c) => <span className="text-xs text-slate-600">{c.signals.join(" · ")}</span> },
                    { key: "u", header: "Unmatched", numeric: true, cell: (c) => <Amount value={c.unmatched} /> },
                    { key: "a", header: "Match amount", numeric: true, cell: (c) => (
                        <input inputMode="decimal" className={`${inputCls} w-28 text-right`} aria-label={`Match amount for ${c.voucher.number}`}
                               value={split[c.voucher.id] ?? ""} placeholder={c.unmatched} onChange={(e) => setSplit({ ...split, [c.voucher.id]: e.target.value })}
                               onFocus={() => { if (!split[c.voucher.id]) setSplit({ ...split, [c.voucher.id]: minMoney(c.unmatched, line.unmatched) }); }} />) },
                ]} />
            </QueryState>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <input className={inputCls} placeholder="Reason (suspense / unmatch)" value={reason} aria-label="Reason for suspense or unmatch" onChange={(e) => setReason(e.target.value)} />
                    {canApprove && <Button size="sm" variant="outline" disabled={!reason.trim() || suspense.isPending} onClick={() => void guard({
                        title: "Move to suspense", confirmText: "Post to suspense",
                        message: `Post ₹ ${formatMoney(line.unmatched)} of this bank line to Bank Suspense (not to income or expense) until it is identified?`,
                    }, () => suspense.mutate())}>Move to suspense</Button>}
                </div>
                {canWrite && <Button size="sm" disabled={total === "0.00" || match.isPending} onClick={() => match.mutate()}>Match {formatMoney(total)}{Object.keys(split).length > 1 ? " (split)" : ""}</Button>}
            </div>
            {dialog}
        </div>
    );
}

function minMoney(a: Money, b: Money): Money {
    return sumMoney([a, `-${b}`]).startsWith("-") ? a : b;
}

function Workbench({ bank, initialStatus = "UNMATCHED,PARTIAL", title = "Statement lines", dated = false }: {
    bank: BankAccount; initialStatus?: string; title?: string; /** Limit to the selected FY / date range (history view only; queues show every open line). */ dated?: boolean;
}) {
    const { canWrite } = useAccountingAccess();
    const { entityId, fyRange } = useAccounting();
    const refresh = useRefresh();
    const [status, setStatus] = useState(initialStatus);
    const [search, setSearch] = useState("");
    const [pageNo, setPageNo] = useState(1);
    const [open, setOpen] = useState<number | null>(null);
    const lines = useQuery({ queryKey: acctKeys.of(entityId, "lines", bank.id, status, search, pageNo, fyRange.start, fyRange.end),
        queryFn: () => acctGet<Paged<StatementLine>>(`bank-accounts/${bank.id}/lines/`,
            { status, search, page: pageNo, page_size: 100, ...(dated ? fyRange : {}) }) });
    const auto = useMutation({
        mutationFn: () => acctPost<Record<string, number>>(`bank-accounts/${bank.id}/auto-match/`),
        onSuccess: (r) => { toast.success(`Auto-matched: ${r.utr ?? 0} by UTR, ${r.amount ?? 0} by amount; ${(r.ambiguous ?? 0) + (r.unmatched ?? 0)} left for review`); void refresh(); },
        onError: notifyError,
    });
    return (
        <Panel title={`${title} — ${bank.bank_name} ${bank.account_number}`} actions={<>
            <input className={inputCls} placeholder="UTR / reference / narration" aria-label="Search statement lines" defaultValue={search}
                   onKeyDown={(e) => { if (e.key === "Enter") { setSearch((e.target as HTMLInputElement).value.trim()); setPageNo(1); } }} />
            <select className={inputCls} value={status} aria-label="Line status" onChange={(e) => { setStatus(e.target.value); setPageNo(1); }}>
                <option value="UNMATCHED,PARTIAL">Needs attention</option><option value="">All lines</option>
                {["UNMATCHED", "PARTIAL", "MATCHED", "SUSPENSE", "RESOLVED"].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            {canWrite && <Button size="sm" onClick={() => auto.mutate()} disabled={auto.isPending}>Auto-match (UTR → amount)</Button>}
        </>}>
            <QueryState isLoading={lines.isLoading} error={lines.error}>
                <div className="space-y-2">
                    <DataGrid rows={lines.data?.results ?? []} rowKey={(l) => l.id} empty="No lines in this view." caption="Statement lines" columns={[
                        { key: "d", header: "Date", cell: (l) => l.txn_date },
                        { key: "n", header: "Narration", cell: (l) => <span className="line-clamp-1">{l.narration}</span> },
                        { key: "r", header: "UTR / ref", cell: (l) => <code className="text-xs">{l.reference}</code> },
                        { key: "w", header: "Withdrawal", numeric: true, cell: (l) => <Amount value={l.debit} blankZero /> },
                        { key: "dp", header: "Deposit", numeric: true, cell: (l) => <Amount value={l.credit} blankZero /> },
                        { key: "u", header: "Unmatched", numeric: true, cell: (l) => <Amount value={l.unmatched} blankZero /> },
                        { key: "s", header: "Status", cell: (l) => <StatusBadge status={l.status} /> },
                        { key: "a", header: <span className="sr-only">Match</span>, cell: (l) => (
                            <Button size="sm" variant="ghost" aria-expanded={open === l.id} onClick={() => setOpen(open === l.id ? null : l.id)}>
                                {open === l.id ? "Close" : (canWrite ? "Match…" : "Details")}</Button>) },
                    ]} />
                    {open !== null && lines.data?.results.find((l) => l.id === open) && (
                        <LineMatcher key={open} line={lines.data.results.find((l) => l.id === open)!} onDone={() => void refresh()} />
                    )}
                    <Pager page={pageNo} hasNext={!!lines.data?.next} onPage={setPageNo} />
                </div>
            </QueryState>
        </Panel>
    );
}

interface Brs {
    book_balance: Money; statement_balance: Money | null; uncleared_deposits: Money; unpresented_payments: Money;
    unrecorded_credits: Money; unrecorded_debits: Money; expected_statement_balance: Money; difference: Money | null;
    unpresented: { voucher_id: number; number: string; date: string; deposit: boolean; amount: Money }[];
    unrecorded: { line_id: number; date: string; narration: string; deposit: boolean; amount: Money; status: string }[];
    open_suspense: number;
}

function Reconciliation({ bank }: { bank: BankAccount }) {
    const { entityId } = useAccounting();
    const [asOf, setAsOf] = useState(new Date().toISOString().slice(0, 10));
    const q = useQuery({ queryKey: acctKeys.of(entityId, "brs", bank.id, asOf),
        queryFn: () => acctGet<Brs>(`bank-accounts/${bank.id}/reconciliation/`, { as_of: asOf }) });
    const b = q.data;
    const row = (label: string, value: Money | null | undefined, strong = false) => (
        <div className={`flex justify-between py-1 ${strong ? "border-t border-slate-300 font-semibold" : ""}`}><span>{label}</span><Amount value={value ?? null} /></div>);
    return (
        <Panel title="Bank reconciliation statement" actions={<input type="date" className={inputCls} aria-label="As of" value={asOf} onChange={(e) => setAsOf(e.target.value)} />}>
            <QueryState isLoading={q.isLoading} error={q.error}>
                {b && (
                    <div className="grid gap-6 lg:grid-cols-2">
                        <div className="text-sm">
                            {row("Balance as per books", b.book_balance)}
                            {row("Less: deposits in books not yet on statement", b.uncleared_deposits)}
                            {row("Add: payments in books not yet on statement", b.unpresented_payments)}
                            {row("Add: statement credits not yet in books", b.unrecorded_credits)}
                            {row("Less: statement debits not yet in books", b.unrecorded_debits)}
                            {row("Expected statement balance", b.expected_statement_balance, true)}
                            {row("Balance as per statement", b.statement_balance)}
                            <div className={`mt-2 rounded-md p-2 text-center font-semibold ${b.difference === "0.00" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`} role="status">
                                {b.difference === null ? "No statement balance imported yet" : b.difference === "0.00" ? "Reconciled — difference 0.00" : `Difference ${formatMoney(b.difference)}`}
                            </div>
                            {b.open_suspense > 0 && <p className="mt-2 text-xs text-amber-700">{b.open_suspense} open suspense item(s) in this entity.</p>}
                        </div>
                        <div className="space-y-3">
                            <DataGrid rows={b.unpresented} rowKey={(u) => u.voucher_id} empty="None." caption="In books, not on statement" columns={[
                                { key: "d", header: "In books, not on statement", cell: (u) => <Link className="text-blue-700" to={`/accounting/vouchers/${u.voucher_id}`}>{u.number} · {u.date}</Link> },
                                { key: "a", header: "Amount", numeric: true, cell: (u) => <Amount value={u.deposit ? u.amount : `-${u.amount}`} /> },
                            ]} />
                            <DataGrid rows={b.unrecorded} rowKey={(u) => u.line_id} empty="None." caption="On statement, not in books" columns={[
                                { key: "d", header: "On statement, not in books", cell: (u) => `${u.date} · ${u.narration}` },
                                { key: "a", header: "Amount", numeric: true, cell: (u) => <Amount value={u.deposit ? u.amount : `-${u.amount}`} /> },
                            ]} />
                        </div>
                    </div>
                )}
            </QueryState>
        </Panel>
    );
}

/** Renders `children(bank)` for the bank in the URL tail (`.../<bankId>`), defaulting to the first. */
function WithBank({ base, children }: { base: string; children: (bank: BankAccount) => React.ReactNode }) {
    const banks = useBanks();
    const navigate = useNavigate();
    const fromUrl = Number(useParams()["*"]) || null;
    const bank = (banks.data ?? []).find((b) => b.id === fromUrl) ?? banks.data?.[0];
    if (banks.isLoading) return null;
    if (banks.error) return <QueryState isLoading={false} error={banks.error} onRetry={() => void banks.refetch()}>{null}</QueryState>;
    if (!bank) return <p className="text-sm text-slate-600">Add a bank account under <Link className="text-blue-700 hover:underline" to="/accounting/banking">Bank Accounts</Link> first.</p>;
    return (
        <div className="space-y-4">
            <select className={inputCls} aria-label="Bank account" value={bank.id} onChange={(e) => navigate(`/accounting/banking/${base}/${e.target.value}`)}>
                {(banks.data ?? []).map((b) => <option key={b.id} value={b.id}>{b.bank_name} {b.account_number}</option>)}
            </select>
            <div key={bank.id} className="space-y-4">{children(bank)}</div>
        </div>
    );
}

function BankWorkbenchPage() {
    const banks = useBanks();
    const fromUrl = Number(useParams()["*"]) || null;
    const [bankId, setBankId] = useState<number | null>(fromUrl);
    const bank = (banks.data ?? []).find((b) => b.id === bankId) ?? banks.data?.[0];
    if (banks.isLoading) return null;
    if (!bank) return <p className="text-sm text-slate-600">Add a bank account first.</p>;
    return (
        <div className="space-y-4">
            <select className={inputCls} aria-label="Bank account" value={bank.id} onChange={(e) => setBankId(Number(e.target.value))}>
                {(banks.data ?? []).map((b) => <option key={b.id} value={b.id}>{b.bank_name} {b.account_number}</option>)}
            </select>
            <Upload bank={bank} />
            <Workbench bank={bank} />
            <Reconciliation bank={bank} />
        </div>
    );
}

function Suspense() {
    const { canApprove } = useAccountingAccess();
    const { entityId } = useAccounting();
    const refresh = useRefresh();
    const q = useQuery({ queryKey: acctKeys.of(entityId, "suspense"), queryFn: () => acctGet<SuspenseRow[]>("suspense/", { entity: entityId }) });
    const accounts = useQuery({ queryKey: acctKeys.of(entityId, "accounts"), queryFn: () => acctGet<{ accounts: Account[] }>("accounts/", { entity: entityId }) });
    const [target, setTarget] = useState<Record<number, { account_id: string; note: string; voucher_id: string }>>({});
    const { guard, dialog } = useGuardedAction();
    const resolve = useMutation({
        mutationFn: ({ id, mode }: { id: number; mode: "reclassify" | "match" }) => {
            const t = target[id];
            return acctPost(`suspense/${id}/resolve/`, mode === "match"
                ? { mode, voucher_id: Number(t.voucher_id), note: t.note }
                : { mode, account_id: Number(t.account_id), note: t.note });
        },
        onSuccess: () => { toast.success("Suspense resolved"); void refresh(); }, onError: notifyError,
    });
    const set = (id: number, p: Partial<{ account_id: string; note: string; voucher_id: string }>) =>
        setTarget({ ...target, [id]: { account_id: "", note: "", voucher_id: "", ...target[id], ...p } });
    const choices = (accounts.data?.accounts ?? []).filter((a) => a.is_active && a.kind !== "SUSPENSE");
    return (
        <Panel title="Suspense register — unidentified bank transactions">
            <QueryState isLoading={q.isLoading} error={q.error}>
                <DataGrid rows={q.data ?? []} rowKey={(s) => s.id} empty="No suspense items." caption="Suspense" columns={[
                    { key: "d", header: "Date", cell: (s) => s.date },
                    { key: "age", header: "Age", numeric: true, cell: (s) => `${s.age_days}d` },
                    { key: "dir", header: "In/out", cell: (s) => (s.is_receipt ? "Receipt" : "Payment") },
                    { key: "a", header: "Amount", numeric: true, cell: (s) => <Amount value={s.amount} /> },
                    { key: "r", header: "Reason", cell: (s) => s.reason },
                    { key: "o", header: "Owner", cell: (s) => s.owner ?? "—" },
                    { key: "s", header: "Status", cell: (s) => <StatusBadge status={s.status} /> },
                    { key: "x", header: "Resolve", cell: (s) => s.status === "RESOLVED" ? <span className="text-xs text-slate-500">{s.resolution_note}</span> : !canApprove ? <span className="text-xs text-slate-500">Approver resolves</span> : (
                        <div className="flex flex-wrap items-center gap-1">
                            <select className={`${inputCls} w-48`} aria-label="Reclassify to" value={target[s.id]?.account_id ?? ""} onChange={(e) => set(s.id, { account_id: e.target.value })}>
                                <option value="">Reclassify to…</option>{choices.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select>
                            <input inputMode="numeric" className={`${inputCls} w-24`} placeholder="or voucher id" aria-label="Existing voucher id" value={target[s.id]?.voucher_id ?? ""} onChange={(e) => set(s.id, { voucher_id: e.target.value.replace(/\D/g, "") })} />
                            <input className={`${inputCls} w-40`} placeholder="Resolution note" aria-label="Resolution note" value={target[s.id]?.note ?? ""} onChange={(e) => set(s.id, { note: e.target.value })} />
                            <Button size="sm" disabled={resolve.isPending || !target[s.id]?.note || (!target[s.id]?.account_id && !target[s.id]?.voucher_id)}
                                    onClick={() => void guard({
                                        title: "Resolve suspense", confirmText: "Resolve",
                                        message: target[s.id]?.voucher_id
                                            ? `Reverse the suspense entry and match the bank line to voucher #${target[s.id]?.voucher_id}?`
                                            : `Post a journal moving ₹ ${formatMoney(s.amount)} out of Suspense to the chosen account?`,
                                    }, () => resolve.mutate({ id: s.id, mode: target[s.id]?.voucher_id ? "match" : "reclassify" }))}>Resolve</Button>
                        </div>) },
                ]} />
            </QueryState>
            {dialog}
        </Panel>
    );
}

export default function Banking() {
    // Section navigation lives in the workspace header (sections.ts); these are the banking pages.
    return (
        <div className="space-y-4">
            <Routes>
                <Route index element={<BankAccounts />} />
                <Route path="transactions/*" element={<WithBank base="transactions">{(bank) => (<>
                    <Upload bank={bank} />
                    <Workbench bank={bank} initialStatus="" title="Bank transactions" dated />
                </>)}</WithBank>} />
                <Route path="unmatched/*" element={<WithBank base="unmatched">{(bank) => (
                    <Workbench bank={bank} initialStatus="UNMATCHED,PARTIAL" title="Unmatched transactions" />)}</WithBank>} />
                <Route path="proposals/*" element={<WithBank base="proposals">{(bank) => <BankProposals bank={bank} />}</WithBank>} />
                <Route path="reconciliation/*" element={<WithBank base="reconciliation">{(bank) => <Reconciliation bank={bank} />}</WithBank>} />
                <Route path="workbench/*" element={<BankWorkbenchPage />} />
                <Route path="suspense" element={<Suspense />} />
            </Routes>
        </div>
    );
}
