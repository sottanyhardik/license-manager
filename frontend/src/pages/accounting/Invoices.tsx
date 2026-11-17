import { useState } from "react";
import { Link, Route, Routes, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { acctGet, acctKeys, acctPost, type Account, type Invoice, type Paged } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { formatMoney } from "./money";
import { useGuardedAction } from "./useGuardedAction";
import { isMoneyInput, sumMoney } from "./money";
import PartyPicker, { type Party } from "./PartyPicker";
import { Pager } from "./TradeTracking";
import { Amount, DataGrid, Field, inputCls, notifyError, Panel, QueryState, StatusBadge } from "./ui";

const KINDS = [
    { value: "EXPENSE", label: "Expense bill" }, { value: "PURCHASE", label: "Purchase invoice (non-trade)" },
    { value: "SALES", label: "Sales invoice (non-trade)" }, { value: "COMMISSION_PAYABLE", label: "Commission payable" },
    { value: "COMMISSION_RECEIVABLE", label: "Commission receivable" }, { value: "DEBIT_NOTE", label: "Debit note (to supplier)" },
    { value: "CREDIT_NOTE", label: "Credit note (to customer)" },
];

function InvoiceList() {
    const { entityId, fyRange } = useAccounting();
    const [params, setParams] = useSearchParams();
    const f = { kind: params.get("kind") ?? "", status: params.get("status") ?? "", search: params.get("search") ?? "",
        page: Math.max(1, Number(params.get("page")) || 1) };
    const set = (p: Record<string, string>) => setParams({ ...Object.fromEntries(params), page: "1", ...p });
    const q = useQuery({ queryKey: acctKeys.of(entityId, "invoices", f, fyRange.start),
        queryFn: () => acctGet<Paged<Invoice>>("invoices/", { entity: entityId, ...f, ...fyRange, page_size: 50 }) });
    return (
        <Panel title="Bills, invoices, expenses and notes" actions={<>
            <input className={inputCls} placeholder="Number" defaultValue={f.search} aria-label="Search bills"
                   onKeyDown={(e) => { if (e.key === "Enter") set({ search: (e.target as HTMLInputElement).value }); }} />
            <select className={inputCls} value={f.kind} aria-label="Kind" onChange={(e) => set({ kind: e.target.value })}>
                <option value="">All kinds</option>{KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
            </select>
            <select className={inputCls} value={f.status} aria-label="Status" onChange={(e) => set({ status: e.target.value })}>
                {["", "DRAFT", "CONFIRMED", "POSTED", "CANCELLED", "REVERSED"].map((s) => <option key={s} value={s}>{s || "All statuses"}</option>)}
            </select>
            <Link to="new"><Button size="sm">New bill / expense</Button></Link>
        </>}>
            <QueryState isLoading={q.isLoading} error={q.error}>
                <DataGrid rows={q.data?.results ?? []} rowKey={(i) => i.id} caption="Bills" columns={[
                    { key: "date", header: "Date", cell: (i) => i.date },
                    { key: "no", header: "Number", cell: (i) => <Link className="font-medium text-blue-700 hover:underline" to={String(i.id)}>{i.number}</Link> },
                    { key: "kind", header: "Kind", cell: (i) => i.kind.replace(/_/g, " ") },
                    { key: "party", header: "Party", cell: (i) => i.party },
                    { key: "gross", header: "Gross", numeric: true, cell: (i) => <Amount value={i.gross_amount} /> },
                    { key: "tds", header: "TDS", numeric: true, cell: (i) => <Amount value={i.tds_amount} blankZero /> },
                    { key: "net", header: "Net", numeric: true, cell: (i) => <Amount value={i.net_amount} /> },
                    { key: "out", header: "Outstanding", numeric: true, cell: (i) => <Amount value={i.outstanding} blankZero /> },
                    { key: "due", header: "Due", cell: (i) => i.due_date ?? "—" },
                    { key: "st", header: "Status", cell: (i) => <StatusBadge status={i.payment_status} /> },
                ]} />
                <Pager page={f.page} hasNext={!!q.data?.next} onPage={(p) => set({ page: String(p) })} />
            </QueryState>
        </Panel>
    );
}

function InvoiceDetail() {
    const { id } = useParams();
    const { entityId } = useAccounting();
    const qc = useQueryClient();
    const [reason, setReason] = useState("");
    const { guard, dialog } = useGuardedAction();
    const q = useQuery({ queryKey: acctKeys.of(entityId, "invoice", id), queryFn: () => acctGet<Invoice>(`invoices/${id}/`) });
    const act = useMutation({
        mutationFn: (action: string) => acctPost<Invoice>(`invoices/${id}/${action}/`, { reason }),
        onSuccess: (_d, action) => { toast.success(`${action} done`); void qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) }); },
        onError: notifyError,
    });
    const i = q.data;
    return (
        <QueryState isLoading={q.isLoading} error={q.error}>
            {i && (
                <Panel title={<span>{i.kind.replace(/_/g, " ")} {i.number} <StatusBadge status={i.status} /> <StatusBadge status={i.payment_status} /></span>}
                       actions={<>
                           {i.status === "DRAFT" && <Button size="sm" variant="outline" disabled={act.isPending} onClick={() => act.mutate("confirm")}>Confirm</Button>}
                           {(i.status === "DRAFT" || i.status === "CONFIRMED") && <Button size="sm" disabled={act.isPending} onClick={() => void guard({
                               title: "Post bill", confirmText: "Post",
                               message: `Post ${i.number} for ${i.party}: net ₹ ${formatMoney(i.net_amount)} (TDS ₹ ${formatMoney(i.tds_amount)})? Posted bills can only be reversed.`,
                           }, () => act.mutate("post"))}>Post</Button>}
                           {(i.status === "DRAFT" || i.status === "CONFIRMED") && <Button size="sm" variant="ghost" disabled={act.isPending} onClick={() => void guard({
                               title: "Cancel bill", severity: "danger", confirmText: "Cancel bill", message: `Cancel the unposted bill ${i.number}?`,
                           }, () => act.mutate("cancel"))}>Cancel</Button>}
                           {i.status === "POSTED" && (<>
                               <input className={inputCls} placeholder="Reversal reason" value={reason} aria-label="Reversal reason" onChange={(e) => setReason(e.target.value)} />
                               <Button size="sm" variant="destructive" disabled={!reason.trim() || act.isPending} onClick={() => void guard({
                                   title: "Reverse bill", severity: "danger", confirmText: "Reverse",
                                   message: `Reverse ${i.number} (₹ ${formatMoney(i.net_amount)})? Its settlements must be reversed first.`,
                               }, () => act.mutate("reverse"))}>Reverse</Button>
                           </>)}
                       </>}>
                    <dl className="mb-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-6">
                        <div><dt className="text-xs text-slate-500">Party</dt><dd>{i.party}</dd></div>
                        <div><dt className="text-xs text-slate-500">Date / due</dt><dd>{i.date} / {i.due_date ?? "—"}</dd></div>
                        <div><dt className="text-xs text-slate-500">Taxable</dt><dd><Amount value={i.taxable_amount} /></dd></div>
                        <div><dt className="text-xs text-slate-500">GST</dt><dd><Amount value={sumMoney([i.cgst, i.sgst, i.igst])} /></dd></div>
                        <div><dt className="text-xs text-slate-500">TDS {i.tds_section ?? ""}</dt><dd><Amount value={i.tds_amount} /></dd></div>
                        <div><dt className="text-xs text-slate-500">Net / outstanding</dt><dd><Amount value={i.net_amount} /> / <Amount value={i.outstanding} /></dd></div>
                        {i.voucher_id && <div><dt className="text-xs text-slate-500">Voucher</dt><dd><Link className="text-blue-700" to={`/accounting/vouchers/${i.voucher_id}`}>{i.voucher_number}</Link></dd></div>}
                        {i.trade_id && <div><dt className="text-xs text-slate-500">Trade</dt><dd><Link className="text-blue-700" to={`/trades/${i.trade_id}/edit`}>#{i.trade_id}</Link></dd></div>}
                    </dl>
                    <DataGrid rows={i.lines ?? []} rowKey={(l) => l.line_no} caption="Lines" columns={[
                        { key: "acct", header: "Account", cell: (l) => l.account },
                        { key: "desc", header: "Description", cell: (l) => l.description },
                        { key: "trade", header: "Trade", cell: (l) => (l.trade_id ? `#${l.trade_id}` : "") },
                        { key: "amt", header: "Taxable", numeric: true, cell: (l) => <Amount value={l.amount} /> },
                        { key: "rate", header: "GST %", numeric: true, cell: (l) => l.gst_rate },
                        { key: "gst", header: "GST", numeric: true, cell: (l) => <Amount value={sumMoney([l.cgst, l.sgst, l.igst])} blankZero /> },
                    ]} />
                    <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Settlements</h3>
                    <DataGrid rows={i.settlements ?? []} rowKey={(s) => s.id} empty="Not settled yet." caption="Settlements" columns={[
                        { key: "date", header: "Date", cell: (s) => s.date },
                        { key: "v", header: "Voucher", cell: (s) => <Link className="text-blue-700" to={`/accounting/vouchers/${s.voucher_id}`}>{s.voucher_number}</Link> },
                        { key: "a", header: "Amount", numeric: true, cell: (s) => <Amount value={s.amount} /> },
                        { key: "s", header: "Active", cell: (s) => (s.is_active ? "Yes" : "Reversed") },
                    ]} />
                </Panel>
            )}
            {dialog}
        </QueryState>
    );
}

interface Line { account_id: string; description: string; amount: string; gst_rate: string; trade_ids: string; method: string }

function NewInvoice() {
    const { entityId } = useAccounting();
    const qc = useQueryClient();
    const navigate = useNavigate();
    const [party, setParty] = useState<Party | null>(null);
    const [head, setHead] = useState({ kind: "EXPENSE", number: "", party_reference: "", date: new Date().toISOString().slice(0, 10),
        credit_days: "0", tds_section_id: "", against_invoice_id: "", narration: "" });
    const [lines, setLines] = useState<Line[]>([{ account_id: "", description: "", amount: "", gst_rate: "0", trade_ids: "", method: "VALUE" }]);
    const accounts = useQuery({ queryKey: acctKeys.of(entityId, "accounts"), queryFn: () => acctGet<{ accounts: Account[] }>("accounts/", { entity: entityId }) });
    const tds = useQuery({ queryKey: [...acctKeys.all, "tds"], queryFn: () => acctGet<{ id: number; code: string; description: string; effective_from: string }[]>("tds-sections/") });
    const setLine = (i: number, p: Partial<Line>) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...p } : l)));
    const plAccounts = (accounts.data?.accounts ?? []).filter((a) => a.is_active && (a.nature === "EXPENSE" || a.nature === "INCOME" || a.kind === "GENERAL"));
    const valid = party && head.number.trim() && lines.every((l) => l.account_id && isMoneyInput(l.amount));
    const save = useMutation({
        mutationFn: () => acctPost<Invoice>("invoices/", {
            entity: entityId, ...head, party_id: party?.id, credit_days: Number(head.credit_days || 0),
            tds_section_id: head.tds_section_id || null, against_invoice_id: head.against_invoice_id || null,
            lines: lines.map((l) => ({ account_id: Number(l.account_id), description: l.description, amount: l.amount, gst_rate: l.gst_rate || "0",
                allocation: l.trade_ids.trim() ? { method: l.method, trade_ids: l.trade_ids.split(",").map((t) => Number(t.trim())).filter(Boolean) } : null })),
        }),
        onSuccess: (inv) => { toast.success("Draft saved"); void qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) }); navigate(`/accounting/invoices/${inv.id}`); },
        onError: notifyError,
    });
    return (
        <Panel title="New bill / expense / note (draft)">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
                <Field label="Kind"><select className={inputCls} value={head.kind} onChange={(e) => setHead({ ...head, kind: e.target.value })}>
                    {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}</select></Field>
                <div className="sm:col-span-2"><Field label="Party"><PartyPicker value={party} onChange={setParty} /></Field></div>
                <Field label="Date"><input type="date" className={inputCls} value={head.date} onChange={(e) => setHead({ ...head, date: e.target.value })} /></Field>
                <Field label="Our number"><input className={inputCls} value={head.number} onChange={(e) => setHead({ ...head, number: e.target.value })} /></Field>
                <Field label="Party's bill no."><input className={inputCls} value={head.party_reference} onChange={(e) => setHead({ ...head, party_reference: e.target.value })} /></Field>
                <Field label="Credit days"><input inputMode="numeric" className={inputCls} value={head.credit_days} onChange={(e) => setHead({ ...head, credit_days: e.target.value })} /></Field>
                <Field label="TDS section" hint="Rates come from configured TDS sections">
                    <select className={inputCls} value={head.tds_section_id} onChange={(e) => setHead({ ...head, tds_section_id: e.target.value })}>
                        <option value="">No TDS</option>{(tds.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.code} — {s.description} (from {s.effective_from})</option>)}
                    </select></Field>
                {(head.kind === "DEBIT_NOTE" || head.kind === "CREDIT_NOTE") && (
                    <Field label="Adjusts bill id"><input inputMode="numeric" className={inputCls} value={head.against_invoice_id} onChange={(e) => setHead({ ...head, against_invoice_id: e.target.value.replace(/\D/g, "") })} /></Field>)}
            </div>
            <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[760px] text-sm">
                <caption className="sr-only">Bill lines</caption>
                <thead className="text-left text-xs text-slate-500"><tr><th className="py-1">Account / category</th><th>Description</th><th className="text-right">Taxable</th><th className="text-right">GST %</th><th>Allocate to trade ids</th><th>By</th></tr></thead>
                <tbody>{lines.map((l, i) => (
                    <tr key={i}>
                        <td className="py-1 pr-2"><select className={`${inputCls} w-full`} value={l.account_id} aria-label={`Account line ${i + 1}`} onChange={(e) => setLine(i, { account_id: e.target.value })}>
                            <option value="">Select…</option>{plAccounts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></td>
                        <td className="pr-2"><input className={`${inputCls} w-full`} value={l.description} aria-label={`Description line ${i + 1}`} onChange={(e) => setLine(i, { description: e.target.value })} /></td>
                        <td className="pr-2"><input inputMode="decimal" className={`${inputCls} w-32 text-right`} value={l.amount} aria-label={`Amount line ${i + 1}`} onChange={(e) => setLine(i, { amount: e.target.value })} /></td>
                        <td className="pr-2"><input inputMode="decimal" className={`${inputCls} w-20 text-right`} value={l.gst_rate} aria-label={`GST rate line ${i + 1}`} onChange={(e) => setLine(i, { gst_rate: e.target.value })} /></td>
                        <td className="pr-2"><input className={`${inputCls} w-40`} placeholder="e.g. 12, 15" value={l.trade_ids} aria-label={`Trades line ${i + 1}`} onChange={(e) => setLine(i, { trade_ids: e.target.value })} /></td>
                        <td><select className={inputCls} value={l.method} aria-label={`Allocation method line ${i + 1}`} onChange={(e) => setLine(i, { method: e.target.value })}>
                            <option value="VALUE">Value</option><option value="QUANTITY">Quantity / weight (kg)</option></select></td>
                    </tr>))}</tbody>
            </table></div>
            <div className="mt-3 flex items-center justify-between">
                <Button size="sm" variant="ghost" onClick={() => setLines([...lines, { account_id: "", description: "", amount: "", gst_rate: "0", trade_ids: "", method: "VALUE" }])}>+ Line</Button>
                <span className="text-sm text-slate-600">Taxable total <Amount value={sumMoney(lines.map((l) => (isMoneyInput(l.amount) ? l.amount : "0")))} /> · GST is split CGST/SGST or IGST from GSTIN state codes on save</span>
                <Button disabled={!valid || save.isPending} onClick={() => save.mutate()}>Save draft</Button>
            </div>
        </Panel>
    );
}

export default function Invoices() {
    return (
        <Routes>
            <Route index element={<InvoiceList />} />
            <Route path="new" element={<NewInvoice />} />
            <Route path=":id" element={<InvoiceDetail />} />
        </Routes>
    );
}
