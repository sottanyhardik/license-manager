/**
 * Accounting masters: chart of accounts, account groups, parties (from the existing company master)
 * and the customer / supplier ledgers. All figures come from the API (trial-balance, parties/summary,
 * party-ledger); this file only formats them.
 */
import { useMemo, useState } from "react";
import { Link, Route, Routes, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
    acctGet, acctKeys, acctPatch, acctPost, type Account, type ChartData, type PartySummary, type PartySummaryRow,
    type TrialBalanceRow,
} from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { useAccountingAccess } from "./useAccountingAccess";
import { useGuardedAction } from "./useGuardedAction";
import { drCr, formatMoney, isZero, type Money } from "./money";
import { PartyLedgerView } from "./PartyLedger";
import { Amount, DataGrid, Field, inputCls, notifyError, Panel, QueryState, ReadOnlyNote } from "./ui";

/** Dr/Cr label for a trial-balance debit/credit pair (formatting only; the server computed both). */
function sideOf(debit: Money | undefined, credit: Money | undefined): string {
    if (!isZero(debit)) return `${formatMoney(debit)} Dr`;
    if (!isZero(credit)) return `${formatMoney(credit)} Cr`;
    return "";
}

export function useChart() {
    const { entityId } = useAccounting();
    return useQuery({ queryKey: acctKeys.of(entityId, "accounts"), queryFn: () => acctGet<ChartData>("accounts/", { entity: entityId }) });
}

function useTrialBalance() {
    const { entityId, scope } = useAccounting();
    return useQuery({
        queryKey: acctKeys.of(entityId, "report", "trial-balance", scope.start, scope.end),
        queryFn: () => acctGet<{ rows: TrialBalanceRow[] }>("reports/trial-balance/", scope),
    });
}

const KIND_LABEL: Record<string, string> = {
    GENERAL: "General", PARTY: "Party", BANK: "Bank", CASH: "Cash", TAX: "Tax", SUSPENSE: "Suspense", LOAN: "Loan",
};

function AccountRow({ account, onSaved }: { account: Account; onSaved: () => void }) {
    const { canApprove } = useAccountingAccess();
    const [editing, setEditing] = useState(false);
    const [name, setName] = useState(account.name);
    const { guard, dialog } = useGuardedAction();
    const save = useMutation({
        mutationFn: (body: { name?: string; is_active?: boolean }) => acctPatch(`accounts/${account.id}/`, body),
        onSuccess: () => { toast.success("Ledger updated"); setEditing(false); onSaved(); }, onError: notifyError,
    });
    if (!canApprove) return null;
    if (editing) {
        return (
            <form className="flex items-center gap-1" onSubmit={(e) => { e.preventDefault(); if (name.trim()) save.mutate({ name }); }}>
                <input className={`${inputCls} h-8 w-48`} value={name} aria-label={`New name for ${account.code}`} onChange={(e) => setName(e.target.value)} />
                <Button size="sm" type="submit" disabled={!name.trim() || save.isPending}>Save</Button>
                <Button size="sm" type="button" variant="ghost" onClick={() => { setEditing(false); setName(account.name); }}>Cancel</Button>
            </form>
        );
    }
    return (
        <div className="flex items-center gap-1">
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>Rename</Button>
            {!account.system_role && (
                <Button size="sm" variant="ghost" disabled={save.isPending} onClick={() => void guard({
                    title: account.is_active ? "Deactivate ledger" : "Activate ledger",
                    severity: account.is_active ? "danger" : undefined,
                    confirmText: account.is_active ? "Deactivate" : "Activate",
                    message: account.is_active
                        ? `Deactivate ${account.code} ${account.name}? It can no longer be chosen on new vouchers; its history is kept.`
                        : `Activate ${account.code} ${account.name} for new vouchers?`,
                }, () => save.mutate({ is_active: !account.is_active }))}>{account.is_active ? "Deactivate" : "Activate"}</Button>
            )}
            {dialog}
        </div>
    );
}

function NewLedgerForm({ groups, onSaved }: { groups: ChartData["groups"]; onSaved: () => void }) {
    const { entityId } = useAccounting();
    const blank = { group_id: "", code: "", name: "", kind: "GENERAL" };
    const [f, setF] = useState(blank);
    const add = useMutation({
        mutationFn: () => acctPost<Account>("accounts/", { entity: entityId, ...f }),
        onSuccess: (a) => { toast.success(`Ledger ${a.code} added`); setF(blank); onSaved(); }, onError: notifyError,
    });
    return (
        <form className="mb-3 flex flex-wrap items-end gap-2 rounded-lg border border-slate-200 bg-slate-50/60 p-3"
              onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
            <Field label="Group"><select className={inputCls} required value={f.group_id} onChange={(e) => setF({ ...f, group_id: e.target.value })}>
                <option value="">Select…</option>{groups.map((g) => <option key={g.id} value={g.id}>{g.name} ({g.nature})</option>)}</select></Field>
            <Field label="Code"><input className={`${inputCls} w-24`} required value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} /></Field>
            <Field label="Name"><input className={`${inputCls} w-64`} required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
            <Field label="Kind" hint="Party, bank and loan ledgers are created by their own workflows">
                <select className={inputCls} value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>
                    <option value="GENERAL">General</option><option value="TAX">Tax</option></select></Field>
            <Button type="submit" disabled={add.isPending || !f.group_id || !f.code.trim() || !f.name.trim()}>Add ledger</Button>
        </form>
    );
}

function ChartOfAccounts() {
    const { entityId } = useAccounting();
    const { canApprove, canWrite } = useAccountingAccess();
    const qc = useQueryClient();
    const [params, setParams] = useSearchParams();
    const chart = useChart();
    const tb = useTrialBalance();
    const f = { search: params.get("search") ?? "", group: params.get("group") ?? "", kind: params.get("kind") ?? "",
        status: params.get("status") ?? "active" };
    const set = (patch: Record<string, string>) => setParams({ ...Object.fromEntries(params), ...patch });
    const byAccount = useMemo(() => new Map((tb.data?.rows ?? []).filter((r) => r.account_id).map((r) => [r.account_id!, r])), [tb.data]);
    const rows = (chart.data?.accounts ?? []).filter((a) =>
        (!f.search || `${a.code} ${a.name}`.toLowerCase().includes(f.search.toLowerCase()))
        && (!f.group || String(a.group_id) === f.group) && (!f.kind || a.kind === f.kind)
        && (f.status === "all" || (f.status === "active" ? a.is_active : !a.is_active)));
    const refresh = () => void qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) });
    return (
        <Panel title="Chart of accounts" actions={<>
            <input className={inputCls} placeholder="Code or name" aria-label="Search ledgers" value={f.search} onChange={(e) => set({ search: e.target.value })} />
            <select className={inputCls} aria-label="Group" value={f.group} onChange={(e) => set({ group: e.target.value })}>
                <option value="">All groups</option>{(chart.data?.groups ?? []).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select>
            <select className={inputCls} aria-label="Kind" value={f.kind} onChange={(e) => set({ kind: e.target.value })}>
                <option value="">All kinds</option>{Object.entries(KIND_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            <select className={inputCls} aria-label="Status" value={f.status} onChange={(e) => set({ status: e.target.value })}>
                <option value="active">Active</option><option value="inactive">Inactive</option><option value="all">All</option></select>
            {canWrite && <Link to="/accounting/vouchers/new?type=OPENING"><Button size="sm" variant="outline">Enter opening balances</Button></Link>}
        </>}>
            {canApprove ? chart.data && <NewLedgerForm groups={chart.data.groups} onSaved={refresh} />
                : <div className="mb-3"><ReadOnlyNote need="the accounts approver role to add, rename or deactivate ledgers" /></div>}
            <QueryState isLoading={chart.isLoading} error={chart.error} onRetry={() => void chart.refetch()}>
                <DataGrid rows={rows} rowKey={(a) => a.id} caption="Ledgers" empty="No ledgers match these filters." columns={[
                    { key: "c", header: "Code", cell: (a) => a.code },
                    { key: "n", header: "Ledger", cell: (a) => <Link className="text-blue-700 hover:underline" to={`/accounting/reports/general-ledger?account=${a.id}`}>{a.name}</Link> },
                    { key: "g", header: "Group", cell: (a) => a.group },
                    { key: "na", header: "Classification", cell: (a) => <span className="text-xs">{a.nature} · {a.report_head.replace(/_/g, " ").toLowerCase()}</span> },
                    { key: "k", header: "Kind", cell: (a) => KIND_LABEL[a.kind] ?? a.kind },
                    { key: "o", header: "Opening", numeric: true, cell: (a) => sideOf(byAccount.get(a.id)?.opening_debit, byAccount.get(a.id)?.opening_credit) },
                    { key: "cl", header: "Closing", numeric: true, cell: (a) => sideOf(byAccount.get(a.id)?.closing_debit, byAccount.get(a.id)?.closing_credit) },
                    { key: "s", header: "Status", cell: (a) => (a.is_active ? <span className="text-xs text-emerald-700">Active</span> : <span className="text-xs text-slate-500">Inactive</span>) },
                    { key: "r", header: "Posting role", cell: (a) => <code className="text-xs">{a.system_role ?? ""}</code> },
                    { key: "a", header: <span className="sr-only">Actions</span>, cell: (a) => <AccountRow key={`${a.id}-${a.name}-${a.is_active}`} account={a} onSaved={refresh} /> },
                ]} />
                {tb.error ? <p className="mt-2 text-xs text-red-700">Balances could not be loaded; ledgers are shown without them.</p> : null}
                <p className="mt-2 text-xs text-slate-500">Opening and closing balances are for the selected period, from the trial balance. Opening balances are entered as an OPENING voucher through the posting engine.</p>
            </QueryState>
        </Panel>
    );
}

function AccountGroups() {
    const chart = useChart();
    const counts = useMemo(() => {
        const m = new Map<number, number>();
        for (const a of chart.data?.accounts ?? []) m.set(a.group_id, (m.get(a.group_id) ?? 0) + 1);
        return m;
    }, [chart.data]);
    return (
        <Panel title="Account groups">
            <QueryState isLoading={chart.isLoading} error={chart.error} onRetry={() => void chart.refetch()}>
                <DataGrid rows={chart.data?.groups ?? []} rowKey={(g) => g.id} caption="Account groups" empty="No groups." columns={[
                    { key: "c", header: "Code", cell: (g) => g.code },
                    { key: "n", header: "Group", cell: (g) => g.name },
                    { key: "na", header: "Nature", cell: (g) => g.nature },
                    { key: "h", header: "Report head", cell: (g) => <span className="text-xs">{g.report_head.replace(/_/g, " ").toLowerCase()}</span> },
                    { key: "l", header: "Ledgers", numeric: true, cell: (g) => (
                        <Link className="text-blue-700 hover:underline" to={`/accounting/masters/accounts?group=${g.id}&status=all`}>{counts.get(g.id) ?? 0}</Link>) },
                ]} />
                <p className="mt-2 text-xs text-slate-500">Groups come from the seeded Indian trading chart and decide where each ledger appears in the P&amp;L and Balance Sheet. Adding or regrouping groups is not available in the API yet.</p>
            </QueryState>
        </Panel>
    );
}

function usePartySummary(search: string) {
    const { entityId, scope } = useAccounting();
    return useQuery({
        queryKey: acctKeys.of(entityId, "party-summary", scope.start, scope.end, search),
        queryFn: () => acctGet<PartySummary>("parties/summary/", { ...scope, search }),
    });
}

function TypeBadges({ row }: { row: PartySummaryRow }) {
    return (
        <span className="flex gap-1 text-[11px] font-semibold">
            {row.is_customer && <span className="rounded bg-sky-50 px-1.5 py-0.5 text-sky-700 ring-1 ring-sky-600/20">Customer</span>}
            {row.is_supplier && <span className="rounded bg-violet-50 px-1.5 py-0.5 text-violet-700 ring-1 ring-violet-600/20">Supplier</span>}
            {!row.is_customer && !row.is_supplier && <span className="text-slate-400">—</span>}
        </span>
    );
}

/** Parties with a ledger in these books (customers, suppliers or both). `side` fixes the classification. */
function PartyList({ side, title }: { side?: "customers" | "suppliers"; title: string }) {
    const [params, setParams] = useSearchParams();
    const search = params.get("search") ?? "";
    const kind = side ?? params.get("type") ?? "";
    const withBalance = params.get("open") === "1";
    const q = usePartySummary(search);
    const rows = (q.data?.parties ?? []).filter((p) =>
        (kind !== "customers" || p.is_customer) && (kind !== "suppliers" || p.is_supplier)
        && (!withBalance || !isZero(p.balance) || !isZero(p.receivable) || !isZero(p.payable)));
    const set = (patch: Record<string, string>) => setParams({ ...Object.fromEntries(params), ...patch });
    return (
        <Panel title={title} actions={<>
            <input className={inputCls} placeholder="Party name" aria-label="Search parties" defaultValue={search}
                   onKeyDown={(e) => { if (e.key === "Enter") set({ search: (e.target as HTMLInputElement).value }); }} />
            {!side && (
                <select className={inputCls} aria-label="Party type" value={kind} onChange={(e) => set({ type: e.target.value })}>
                    <option value="">Customers and suppliers</option><option value="customers">Customers</option><option value="suppliers">Suppliers</option>
                </select>)}
            <label className="flex items-center gap-1 text-xs text-slate-600"><input type="checkbox" checked={withBalance} onChange={(e) => set({ open: e.target.checked ? "1" : "" })} /> Only with a balance</label>
        </>}>
            <QueryState isLoading={q.isLoading} error={q.error} onRetry={() => void q.refetch()}>
                <DataGrid rows={rows} rowKey={(p) => p.party_id} caption={title}
                          empty="No party has a ledger in these books yet. Party ledgers are created when a bill, payment or trade is posted."
                          columns={[
                    { key: "p", header: "Party", cell: (p) => <Link className="font-medium text-blue-700 hover:underline" to={`/accounting/masters/parties/${p.party_id}`}>{p.party}</Link> },
                    { key: "g", header: "GSTIN", cell: (p) => <span className="text-xs">{p.gstin ?? ""}</span> },
                    { key: "t", header: "Type", cell: (p) => <TypeBadges row={p} /> },
                    { key: "b", header: "Ledger balance", numeric: true, cell: (p) => (
                        <Link className="hover:underline" to={`/accounting/reports/general-ledger?account=${p.account_id}`}>{drCr(p.balance)}</Link>) },
                    { key: "r", header: "Receivable", numeric: true, cell: (p) => <Amount value={p.receivable} blankZero /> },
                    { key: "py", header: "Payable", numeric: true, cell: (p) => <Amount value={p.payable} blankZero /> },
                    { key: "o", header: "Open bills", numeric: true, cell: (p) => (p.open_bills + p.open_payable_bills) || "" },
                ]} footer={q.data && !side && !search && !withBalance && !kind ? (
                    <tr><td className="px-3 py-1.5" colSpan={3}>Total</td>
                        <td className="px-3 py-1.5 text-right text-xs">{formatMoney(q.data.totals.debit_balance)} Dr / {formatMoney(q.data.totals.credit_balance)} Cr</td>
                        <td className="px-3 py-1.5 text-right"><Amount value={q.data.totals.receivable} /></td>
                        <td className="px-3 py-1.5 text-right"><Amount value={q.data.totals.payable} /></td><td /></tr>) : undefined} />
                <p className="mt-2 text-xs text-slate-500">Parties are the existing company master (no separate party master). Balances as of {q.data?.as_of ?? "the period end"}.</p>
            </QueryState>
        </Panel>
    );
}

function PartyDetail() {
    const { partyId } = useParams();
    const id = Number(partyId);
    const q = usePartySummary("");
    const row = q.data?.parties.find((p) => p.party_id === id);
    return (
        <div className="space-y-4">
            <QueryState isLoading={q.isLoading} error={q.error} onRetry={() => void q.refetch()}>
                <Panel title={row?.party ?? `Party #${id}`} actions={<Link className="text-sm text-blue-700 hover:underline" to="/accounting/masters/parties">← All parties</Link>}>
                    {row ? (
                        <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-6">
                            <div><dt className="text-xs text-slate-500">GSTIN</dt><dd>{row.gstin ?? "—"}</dd></div>
                            <div><dt className="text-xs text-slate-500">Type</dt><dd><TypeBadges row={row} /></dd></div>
                            <div><dt className="text-xs text-slate-500">Ledger</dt><dd>{row.account_code}</dd></div>
                            <div><dt className="text-xs text-slate-500">Ledger balance</dt><dd className="font-semibold">{drCr(row.balance)}</dd></div>
                            <div><dt className="text-xs text-slate-500">Receivable (open bills)</dt><dd><Amount value={row.receivable} /></dd></div>
                            <div><dt className="text-xs text-slate-500">Payable (open bills)</dt><dd><Amount value={row.payable} /></dd></div>
                        </dl>
                    ) : <p className="text-sm text-slate-500">This party has no ledger in the selected entity's books.</p>}
                </Panel>
            </QueryState>
            {Number.isFinite(id) && <PartyLedgerView partyId={id} partyName={row?.party ?? `Party #${id}`} />}
        </div>
    );
}

/** Customer / supplier ledger index: the party list, fixed to one side; each row opens that party's ledger. */
export function PartyLedgers({ side }: { side: "customers" | "suppliers" }) {
    return <PartyList side={side} title={side === "customers" ? "Customer ledgers" : "Supplier ledgers"} />;
}

export default function Masters() {
    return (
        <Routes>
            <Route index element={<ChartOfAccounts />} />
            <Route path="accounts" element={<ChartOfAccounts />} />
            <Route path="groups" element={<AccountGroups />} />
            <Route path="parties" element={<PartyList title="Parties (customers and suppliers)" />} />
            <Route path="parties/:partyId" element={<PartyDetail />} />
        </Routes>
    );
}
