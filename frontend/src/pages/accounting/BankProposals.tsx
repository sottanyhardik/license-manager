import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { acctDelete, acctGet, acctKeys, acctPost, type BankAccount, type Money } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import PartyPicker, { type Party } from "./PartyPicker";
import { useAccountingAccess } from "./useAccountingAccess";
import { useGuardedAction } from "./useGuardedAction";
import { formatMoney, sumMoney } from "./money";
import { Amount, DataGrid, inputCls, notifyError, Panel, QueryState, ReadOnlyNote } from "./ui";

type Confidence = "high" | "medium" | "low" | "none";
type Direction = "RECEIPT" | "PAYMENT";

interface ProposalOption { id: number; name: string; gstin: string | null; score: number }
interface ProposalAllocation { invoice_id: number; number: string; date: string; due_date: string | null; outstanding: Money; amount: Money }
export interface Proposal {
    line: { id: number; txn_date: string; narration: string; reference: string; debit: Money; credit: Money; amount: Money; status: string };
    direction: Direction;
    counterparty: string;
    party: { id: number; name: string; gstin: string | null } | null;
    source: "alias" | "name" | "chosen" | "";
    score: number;
    confidence: Confidence;
    blocked: string | null;
    options: ProposalOption[];
    allocations: ProposalAllocation[];
    advance: Money;
    exact_bill: boolean;
    existing_candidates: number;
}
interface ProposalsResponse {
    bank_account_id: number;
    summary: Record<Confidence | "total", number>;
    proposals: Proposal[];
}
interface ConfirmResponse {
    confirmed: { line_id: number; payment_id: number; voucher: string }[];
    errors: { line_id: number; code: string; detail: string }[];
}
interface Alias { id: number; key: string; direction: Direction; party_id: number; party: string; hits: number; modified_on: string }

const CONFIDENCES: { id: Confidence; label: string }[] = [
    { id: "high", label: "High" }, { id: "medium", label: "Medium" }, { id: "low", label: "Low" }, { id: "none", label: "None" },
];
const CONF_TONE: Record<Confidence, string> = {
    high: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    medium: "bg-sky-50 text-sky-700 ring-sky-600/20",
    low: "bg-amber-50 text-amber-800 ring-amber-600/20",
    none: "bg-slate-100 text-slate-700 ring-slate-500/20",
};
const SOURCE_LABEL: Record<string, string> = { alias: "learned", name: "name match" };

/** Confirmed lines stay on screen as "Matched" this long, with Undo; then they leave the list. */
export const UNDO_SECONDS = 10;
interface Recent { proposal: Proposal; payment_id: number; voucher: string; until: number }

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

function AliasesPanel({ entityId }: { entityId: number | null }) {
    const { canApprove } = useAccountingAccess();
    const qc = useQueryClient();
    const { guard, dialog } = useGuardedAction();
    const q = useQuery({ queryKey: acctKeys.of(entityId, "narration-aliases"),
        queryFn: () => acctGet<{ aliases: Alias[] }>("narration-aliases/", { entity: entityId }) });
    const del = useMutation({
        mutationFn: (id: number) => acctDelete(`narration-aliases/${id}/`),
        onSuccess: () => { toast.success("Alias removed"); void qc.invalidateQueries({ queryKey: acctKeys.of(entityId, "narration-aliases") }); },
        onError: notifyError,
    });
    return (
        <Panel title="Learned party aliases">
            <p className="mb-2 text-xs text-slate-600">Narrations the books have learned to map to a party after an approver confirmed them.</p>
            <QueryState isLoading={q.isLoading} error={q.error} onRetry={() => void q.refetch()}>
                <DataGrid rows={q.data?.aliases ?? []} rowKey={(a) => a.id} empty="No aliases learned yet." caption="Learned party aliases" columns={[
                    { key: "k", header: "Narration key", cell: (a) => <code className="text-xs">{a.key}</code> },
                    { key: "d", header: "Direction", cell: (a) => (a.direction === "RECEIPT" ? "Receipt" : "Payment") },
                    { key: "p", header: "Party", cell: (a) => a.party },
                    { key: "h", header: "Hits", numeric: true, cell: (a) => a.hits },
                    { key: "m", header: "Last used", cell: (a) => a.modified_on?.slice(0, 10) },
                    ...(canApprove ? [{ key: "x", header: <span className="sr-only">Remove</span>, cell: (a: Alias) => (
                        <Button size="sm" variant="ghost" className="text-red-700" disabled={del.isPending} aria-label={`Delete alias ${a.key}`}
                                onClick={() => void guard({ title: "Delete alias", severity: "danger", confirmText: "Delete",
                                    message: `Forget that "${a.key}" means ${a.party}? Future lines will no longer be proposed to this party from this alias.` },
                                () => del.mutate(a.id))}>Delete</Button>) }] : []),
                ]} />
            </QueryState>
            {dialog}
        </Panel>
    );
}

function PartyCell({ p, canWrite, onPick, onReset, overridden, busy }: {
    p: Proposal; canWrite: boolean; onPick: (partyId: number) => void; onReset: () => void; overridden: boolean; busy: boolean;
}) {
    return (
        <div className="min-w-56 space-y-1">
            {p.party ? (
                <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium">{p.party.name}</span>
                    {SOURCE_LABEL[p.source] && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-600">{SOURCE_LABEL[p.source]}</span>}
                </div>
            ) : <span className="text-xs text-slate-500">No party proposed</span>}
            {p.party?.gstin && <div className="text-xs text-slate-500">{p.party.gstin}</div>}
            {p.blocked && <div className="text-xs text-red-700" role="note">{p.blocked}</div>}
            {canWrite && (
                <div className="space-y-1">
                    {p.options.length > 0 && (
                        <select className={`${inputCls} w-full`} aria-label={`Suggested parties for line ${p.line.id}`} disabled={busy}
                                value="" onChange={(e) => { if (e.target.value) onPick(Number(e.target.value)); }}>
                            <option value="">{p.party ? "Other suggestions…" : "Pick a suggestion…"}</option>
                            {p.options.filter((o) => o.id !== p.party?.id).map((o) => <option key={o.id} value={o.id}>{o.name}{o.gstin ? ` · ${o.gstin}` : ""}</option>)}
                        </select>
                    )}
                    <PartyPicker key={`${p.line.id}-${p.party?.id ?? 0}`} value={null} label={`Party for line ${p.line.id}`}
                                 onChange={(party: Party | null) => { if (party) onPick(party.id); }} />
                    {overridden && <button type="button" className="text-xs text-blue-700 hover:underline" onClick={onReset}>Reset to suggestion</button>}
                </div>
            )}
        </div>
    );
}

export default function BankProposals({ bank }: { bank: BankAccount }) {
    const { canApprove, canWrite } = useAccountingAccess();
    const { entityId } = useAccounting();
    const qc = useQueryClient();
    const { guard, dialog } = useGuardedAction();
    const [conf, setConf] = useState<Confidence[]>(["high", "medium"]);
    const [direction, setDirection] = useState<"" | Direction>("");
    const [overrides, setOverrides] = useState<Record<number, Proposal>>({});
    const [selected, setSelected] = useState<number[]>([]);
    const [result, setResult] = useState<ConfirmResponse | null>(null);
    const [showAliases, setShowAliases] = useState(false);
    const [recent, setRecent] = useState<Record<number, Recent>>({});
    const [now, setNow] = useState(() => Date.now());
    const hasRecent = Object.keys(recent).length > 0;
    useEffect(() => {
        if (!hasRecent) return undefined;
        const timer = window.setInterval(() => {
            const t = Date.now();
            setNow(t);
            setRecent((r) => {
                const kept = Object.entries(r).filter(([, v]) => v.until > t);
                return kept.length === Object.keys(r).length ? r : Object.fromEntries(kept);
            });
        }, 250);
        return () => window.clearInterval(timer);
    }, [hasRecent]);
    const confParam = CONFIDENCES.filter((c) => conf.includes(c.id)).map((c) => c.id).join(",");

    const q = useQuery({
        queryKey: acctKeys.of(entityId, "proposals", bank.id, confParam, direction),
        queryFn: () => acctGet<ProposalsResponse>(`bank-accounts/${bank.id}/proposals/`, { confidence: confParam, direction }),
    });

    const preview = useMutation({
        mutationFn: ({ lineId, partyId }: { lineId: number; partyId: number }) =>
            acctGet<Proposal>(`statement-lines/${lineId}/proposal/`, { party_id: partyId }),
        onSuccess: (p) => setOverrides((o) => ({ ...o, [p.line.id]: p })),
        onError: notifyError,
    });
    const confirm = useMutation({
        mutationFn: (items: { line_id: number; party_id: number }[]) =>
            acctPost<ConfirmResponse>(`bank-accounts/${bank.id}/proposals/confirm/`, { items }),
        onSuccess: (r) => {
            setResult(r);
            const done = new Set(r.confirmed.map((c) => c.line_id));
            const byLine = new Map(effective.map((p) => [p.line.id, p]));
            const until = Date.now() + UNDO_SECONDS * 1000;
            setNow(Date.now());
            setRecent((cur) => ({ ...cur, ...Object.fromEntries(r.confirmed.flatMap((c) => {
                const proposal = byLine.get(c.line_id);
                return proposal ? [[c.line_id, { proposal, payment_id: c.payment_id, voucher: c.voucher, until }]] : [];
            })) }));
            setSelected((s) => s.filter((id) => !done.has(id)));
            setOverrides((o) => Object.fromEntries(Object.entries(o).filter(([id]) => !done.has(Number(id)))));
            if (r.confirmed.length) toast.success(`${plural(r.confirmed.length, "line")} posted`);
            void qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) });
        },
        onError: notifyError,
    });
    const undo = useMutation({
        mutationFn: (r: Recent) => acctPost<{ line_id: number; status: string }>(`bank-proposals/${r.payment_id}/undo/`, {}),
        onSuccess: (res, r) => {
            setRecent((cur) => Object.fromEntries(Object.entries(cur).filter(([id]) => Number(id) !== res.line_id)));
            toast.success(`${r.voucher} reversed — the bank line is unmatched again`);
            void qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) });
        },
        onError: notifyError,
    });

    const effective = (q.data?.proposals ?? []).map((p) => overrides[p.line.id] ?? p);
    const recentRows = Object.values(recent).map((r) => r.proposal);
    const rows = [...recentRows, ...effective.filter((p) => !recent[p.line.id])];
    const eligible = (p: Proposal) => !!p.party && !p.blocked && !recent[p.line.id];
    const chosen = effective.filter((p) => selected.includes(p.line.id) && eligible(p));
    const receipts = chosen.filter((p) => p.direction === "RECEIPT");
    const payments = chosen.filter((p) => p.direction === "PAYMENT");
    const eligibleIds = effective.filter(eligible).map((p) => p.line.id);
    const allSelected = eligibleIds.length > 0 && eligibleIds.every((id) => selected.includes(id));

    const toggleConf = (c: Confidence) => setConf((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]));
    const toggleRow = (id: number) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

    const onConfirm = () => void guard({
        title: "Confirm proposed payments", confirmText: "Post",
        message: `This will post ${plural(receipts.length, "receipt")} (₹ ${formatMoney(sumMoney(receipts.map((p) => p.line.amount)))}) and `
            + `${plural(payments.length, "payment")} (₹ ${formatMoney(sumMoney(payments.map((p) => p.line.amount)))}), `
            + `total ₹ ${formatMoney(sumMoney(chosen.map((p) => p.line.amount)))}. Bills are settled oldest first and any remainder is booked as an advance.`,
    }, () => confirm.mutate(chosen.map((p) => ({ line_id: p.line.id, party_id: (p.party as { id: number }).id }))));

    const summary = q.data?.summary;
    return (
        <div className="space-y-4">
            <Panel title={`Invoice proposals — ${bank.bank_name} ${bank.account_number}`} actions={<>
                <select className={inputCls} aria-label="Direction" value={direction} onChange={(e) => setDirection(e.target.value as "" | Direction)}>
                    <option value="">Receipts and payments</option><option value="RECEIPT">Receipts</option><option value="PAYMENT">Payments</option>
                </select>
                <Button size="sm" variant="outline" aria-expanded={showAliases} onClick={() => setShowAliases((v) => !v)}>
                    {showAliases ? "Hide learned aliases" : "Learned aliases"}
                </Button>
                {canApprove && <Button size="sm" disabled={chosen.length === 0 || confirm.isPending} onClick={onConfirm}>Confirm selected ({chosen.length})</Button>}
            </>}>
                <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Filter by confidence">
                    {CONFIDENCES.map((c) => (
                        <button key={c.id} type="button" aria-pressed={conf.includes(c.id)} onClick={() => toggleConf(c.id)}
                                className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${CONF_TONE[c.id]} ${conf.includes(c.id) ? "outline outline-2 outline-blue-500" : "opacity-60"}`}>
                            {c.label} {summary ? summary[c.id] : ""}
                        </button>
                    ))}
                </div>
                {!canApprove && <div className="mb-3"><ReadOnlyNote need="the Accounts Approver role to confirm proposals" /></div>}
                {result && (
                    <div className="mb-3 rounded-md bg-slate-50 p-3 text-sm" role="status">
                        <b>{plural(result.confirmed.length, "line")} confirmed</b>
                        {result.errors.length > 0 && <>, {plural(result.errors.length, "line")} failed:
                            <ul className="mt-1 list-disc pl-5 text-red-700">{result.errors.map((e) => <li key={e.line_id}>Line {e.line_id}: {e.detail} ({e.code})</li>)}</ul></>}
                    </div>
                )}
                <QueryState isLoading={q.isLoading} error={q.error} onRetry={() => void q.refetch()}>
                    <DataGrid rows={rows} rowKey={(p) => p.line.id} caption="Invoice proposals"
                        empty="No unmatched lines need a party — try Auto-match on Bank Transactions." columns={[
                        ...(canApprove ? [{ key: "sel", header: (
                            <input type="checkbox" aria-label="Select all proposals" checked={allSelected}
                                   onChange={() => setSelected(allSelected ? [] : eligibleIds)} />),
                            cell: (p: Proposal) => (
                                <input type="checkbox" aria-label={`Select line ${p.line.id}`} checked={selected.includes(p.line.id)}
                                       disabled={!eligible(p)} onChange={() => toggleRow(p.line.id)} />) }] : []),
                        { key: "d", header: "Date", cell: (p) => p.line.txn_date },
                        { key: "n", header: "Narration", cell: (p) => (
                            <div className="max-w-xs"><span className="line-clamp-2">{p.line.narration}</span>
                                {p.counterparty && <span className="text-xs text-slate-500">{p.counterparty}</span>}</div>) },
                        { key: "a", header: "Amount", numeric: true, cell: (p) => (
                            <span><Amount value={p.line.amount} /> <span className="text-xs text-slate-500">{p.direction === "RECEIPT" ? "Cr" : "Dr"}</span></span>) },
                        { key: "p", header: "Proposed party", cell: (p) => (
                            <PartyCell p={p} canWrite={canWrite && !recent[p.line.id]} overridden={!!overrides[p.line.id]} busy={preview.isPending}
                                       onPick={(partyId) => preview.mutate({ lineId: p.line.id, partyId })}
                                       onReset={() => setOverrides((o) => Object.fromEntries(Object.entries(o).filter(([id]) => Number(id) !== p.line.id)))} />) },
                        { key: "b", header: "Bills to settle", cell: (p) => (
                            <div className="space-y-0.5 text-xs">
                                {p.allocations.map((a) => <div key={a.invoice_id}>{a.number} · <Amount value={a.amount} /></div>)}
                                {formatMoney(p.advance, { blankZero: true }) && <div className="text-amber-700">Advance <Amount value={p.advance} /></div>}
                                {p.allocations.length === 0 && !p.party && <span className="text-slate-400">—</span>}
                            </div>) },
                        { key: "c", header: "Confidence", cell: (p) => {
                            const r = recent[p.line.id];
                            if (!r) return <span className={`inline-flex rounded-md px-1.5 py-0.5 text-[11px] font-semibold uppercase ring-1 ring-inset ${CONF_TONE[p.confidence]}`}>{p.confidence}</span>;
                            const left = Math.max(0, Math.ceil((r.until - now) / 1000));
                            return (
                                <div className="flex flex-col items-start gap-1" role="status" aria-live="polite">
                                    <span className="inline-flex rounded-md bg-emerald-600 px-1.5 py-0.5 text-[11px] font-semibold uppercase text-white">Matched · {r.voucher}</span>
                                    {canApprove && <Button size="sm" variant="outline" disabled={undo.isPending} aria-label={`Undo line ${p.line.id}`}
                                                           onClick={() => undo.mutate(r)}>Undo ({left}s)</Button>}
                                </div>);
                        } },
                    ]} />
                </QueryState>
            </Panel>
            {showAliases && <AliasesPanel entityId={entityId} />}
            {dialog}
        </div>
    );
}
