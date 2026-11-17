import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { acctDelete, acctGet, acctKeys, acctPost, type BankAccount, type Money } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import BankLineSplit, { type SplitResult } from "./BankLineSplit";
import PartyPicker, { type Party } from "./PartyPicker";
import { useAccountingAccess } from "./useAccountingAccess";
import { useGuardedAction } from "./useGuardedAction";
import { formatMoney } from "./money";
import { Amount, DataGrid, inputCls, notifyError, Panel, QueryState, ReadOnlyNote } from "./ui";

type Confidence = "high" | "medium" | "low" | "none" | "bulk";
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
    is_bulk: boolean;
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
    { id: "high", label: "High" }, { id: "medium", label: "Medium" }, { id: "bulk", label: "Bulk (BU)" }, { id: "low", label: "Low" }, { id: "none", label: "None" },
];
const CONF_TONE: Record<Confidence, string> = {
    high: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    medium: "bg-sky-50 text-sky-700 ring-sky-600/20",
    low: "bg-amber-50 text-amber-800 ring-amber-600/20",
    none: "bg-slate-100 text-slate-700 ring-slate-500/20",
    bulk: "bg-violet-50 text-violet-700 ring-violet-600/20",
};
const SOURCE_LABEL: Record<string, string> = { alias: "learned", name: "name match" };

/** Confirmed lines stay on screen as "Matched" this long, with Undo; then they leave the list. */
export const UNDO_SECONDS = 10;
interface Recent { kind: "proposal" | "split"; proposal: Proposal; payment_id: number; voucher: string; until: number }


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

type PickedParty = { id: number; name: string; gstin: string | null };

function PartyCell({ p, canSave, onSave, busy }: {
    p: Proposal; canSave: boolean; onSave: (party: PickedParty) => void; busy: boolean;
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
            {canSave && (
                <div className="space-y-1">
                    {p.options.filter((o) => o.id !== p.party?.id).length > 0 && (
                        <select className={`${inputCls} w-full`} aria-label={`Suggested parties for line ${p.line.id}`} disabled={busy}
                                value="" onChange={(e) => {
                                    const o = p.options.find((x) => x.id === Number(e.target.value));
                                    if (o) onSave({ id: o.id, name: o.name, gstin: o.gstin });
                                }}>
                            <option value="">{p.party ? "Other suggestions…" : "Pick a suggestion…"}</option>
                            {p.options.filter((o) => o.id !== p.party?.id).map((o) => <option key={o.id} value={o.id}>{o.name}{o.gstin ? ` · ${o.gstin}` : ""}</option>)}
                        </select>
                    )}
                    <PartyPicker key={`${p.line.id}-${p.party?.id ?? 0}`} value={null} label={`Party for line ${p.line.id}`}
                                 onChange={(party: Party | null) => { if (party) onSave({ id: party.id, name: party.name, gstin: party.gstin ?? null }); }} />
                </div>
            )}
        </div>
    );
}

export default function BankProposals({ bank }: { bank: BankAccount }) {
    const { canApprove } = useAccountingAccess();
    const { entityId } = useAccounting();
    const qc = useQueryClient();
    const [conf, setConf] = useState<Confidence[]>(["high", "medium", "bulk"]);
    const [splitting, setSplitting] = useState<Proposal | null>(null);
    const [direction, setDirection] = useState<"" | Direction>("");
    const [errors, setErrors] = useState<Record<number, string>>({});
    const [saving, setSaving] = useState<number[]>([]);
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

    /** Saving = booking: one line, posted and matched at once; Undo is the safety net for 10 s. */
    const save = useMutation({
        mutationFn: ({ p, party }: { p: Proposal; party: PickedParty }) =>
            acctPost<ConfirmResponse>(`bank-accounts/${bank.id}/proposals/confirm/`, { items: [{ line_id: p.line.id, party_id: party.id }] }),
        onMutate: ({ p }) => {
            setSaving((s) => [...s, p.line.id]);
            setErrors((e) => Object.fromEntries(Object.entries(e).filter(([id]) => Number(id) !== p.line.id)));
        },
        onSuccess: (r, { p, party }) => {
            const done = r.confirmed.find((c) => c.line_id === p.line.id);
            if (done) {
                const samePerson = p.party?.id === party.id;
                const snapshot: Proposal = samePerson ? p : { ...p, party, source: "", allocations: [], advance: "0.00" };
                setNow(Date.now());
                setRecent((cur) => ({ ...cur, [p.line.id]: { kind: "proposal", proposal: snapshot, payment_id: done.payment_id, voucher: done.voucher,
                    until: Date.now() + UNDO_SECONDS * 1000 } }));
                toast.success(`${done.voucher} posted for ${party.name}`);
                void qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) });
            }
            const failed = r.errors.find((e) => e.line_id === p.line.id);
            if (failed) setErrors((e) => ({ ...e, [p.line.id]: failed.detail }));
        },
        onError: notifyError,
        onSettled: (_r, _e, { p }) => setSaving((s) => s.filter((id) => id !== p.line.id)),
    });
    const undo = useMutation({
        mutationFn: (r: Recent) => (r.kind === "split"
            ? acctDelete<{ line_id: number; status: string }>(`statement-lines/${r.proposal.line.id}/split/`)
            : acctPost<{ line_id: number; status: string }>(`bank-proposals/${r.payment_id}/undo/`, {})),
        onSuccess: (res, r) => {
            setRecent((cur) => Object.fromEntries(Object.entries(cur).filter(([id]) => Number(id) !== res.line_id)));
            toast.success(`${r.voucher} reversed — the bank line is unmatched again`);
            void qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) });
        },
        onError: notifyError,
    });

    const onSplit = (p: Proposal, r: SplitResult) => {
        const names = r.payments.map((x) => x.party).join(", ");
        const snapshot: Proposal = { ...p, party: { id: -1, name: names, gstin: null }, source: "", allocations: [], advance: "0.00" };
        setNow(Date.now());
        setRecent((cur) => ({ ...cur, [p.line.id]: { kind: "split", proposal: snapshot, payment_id: r.payments[0]?.id ?? 0,
            voucher: `${r.payments.length} ${p.direction === "PAYMENT" ? "payments" : "receipts"}`, until: Date.now() + UNDO_SECONDS * 1000 } }));
        setSplitting(null);
        toast.success(`Split into ${r.payments.length} entries: ${r.payments.map((x) => x.voucher).join(", ")}`);
        void qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) });
    };

    const proposals = q.data?.proposals ?? [];
    const rows = [...Object.values(recent).map((r) => r.proposal), ...proposals.filter((p) => !recent[p.line.id])];
    const toggleConf = (c: Confidence) => setConf((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]));
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
            </>}>
                <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Filter by confidence">
                    {CONFIDENCES.map((c) => (
                        <button key={c.id} type="button" aria-pressed={conf.includes(c.id)} onClick={() => toggleConf(c.id)}
                                className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${CONF_TONE[c.id]} ${conf.includes(c.id) ? "outline outline-2 outline-blue-500" : "opacity-60"}`}>
                            {c.label} {summary ? summary[c.id] : ""}
                        </button>
                    ))}
                </div>
                {canApprove
                    ? <p className="mb-3 text-xs text-slate-600">Picking a company or pressing Confirm books the line at once (bills oldest first, any remainder as advance) and marks it matched. Undo is available for {UNDO_SECONDS} seconds.</p>
                    : <div className="mb-3"><ReadOnlyNote need="the Accounts Approver role to confirm proposals" /></div>}
                {splitting && (
                    <div className="mb-4">
                        <BankLineSplit key={splitting.line.id} onCancel={() => setSplitting(null)} onDone={(r) => onSplit(splitting, r)}
                                       line={{ id: splitting.line.id, txn_date: splitting.line.txn_date, narration: splitting.line.narration,
                                               amount: splitting.line.amount, direction: splitting.direction }} />
                    </div>
                )}
                <QueryState isLoading={q.isLoading} error={q.error} onRetry={() => void q.refetch()}>
                    <DataGrid rows={rows} rowKey={(p) => p.line.id} caption="Invoice proposals"
                        empty="No unmatched lines need a party — try Auto-match on Bank Transactions." columns={[
                        { key: "d", header: "Date", cell: (p) => p.line.txn_date },
                        { key: "n", header: "Narration", cell: (p) => (
                            <div className="max-w-xs"><span className="line-clamp-2">{p.line.narration}</span>
                                {p.counterparty && <span className="text-xs text-slate-500">{p.counterparty}</span>}</div>) },
                        { key: "a", header: "Amount", numeric: true, cell: (p) => (
                            <span><Amount value={p.line.amount} /> <span className="text-xs text-slate-500">{p.direction === "RECEIPT" ? "Cr" : "Dr"}</span></span>) },
                        { key: "p", header: "Party", cell: (p) => (
                            <PartyCell p={p} canSave={canApprove && !recent[p.line.id] && !p.blocked} busy={saving.includes(p.line.id)}
                                       onSave={(party) => save.mutate({ p, party })} />) },
                        { key: "b", header: "Bills to settle", cell: (p) => recent[p.line.id] && !p.allocations.length ? (
                            <span className="text-xs text-slate-500">Settled oldest first</span>) : (
                            <div className="space-y-0.5 text-xs">
                                {p.allocations.map((a) => <div key={a.invoice_id}>{a.number} · <Amount value={a.amount} /></div>)}
                                {formatMoney(p.advance, { blankZero: true }) && <div className="text-amber-700">Advance <Amount value={p.advance} /></div>}
                                {p.allocations.length === 0 && !p.party && <span className="text-slate-400">—</span>}
                            </div>) },
                        { key: "c", header: "Status", cell: (p) => {
                            const r = recent[p.line.id];
                            if (r) {
                                const left = Math.max(0, Math.ceil((r.until - now) / 1000));
                                return (
                                    <div className="flex flex-col items-start gap-1" role="status" aria-live="polite">
                                        <span className="inline-flex rounded-md bg-emerald-600 px-1.5 py-0.5 text-[11px] font-semibold uppercase text-white">Matched · {r.voucher}</span>
                                        {canApprove && <Button size="sm" variant="outline" disabled={undo.isPending} aria-label={`Undo line ${p.line.id}`}
                                                               onClick={() => undo.mutate(r)}>Undo ({left}s)</Button>}
                                    </div>);
                            }
                            return (
                                <div className="flex flex-col items-start gap-1">
                                    <span className={`inline-flex rounded-md px-1.5 py-0.5 text-[11px] font-semibold uppercase ring-1 ring-inset ${CONF_TONE[p.confidence]}`}>{p.confidence}</span>
                                    {canApprove && p.party && !p.blocked && (
                                        <Button size="sm" disabled={saving.includes(p.line.id)} aria-label={`Confirm line ${p.line.id}`}
                                                onClick={() => save.mutate({ p, party: p.party as PickedParty })}>
                                            {saving.includes(p.line.id) ? "Saving…" : "Confirm"}</Button>)}
                                    {canApprove && !p.blocked && (
                                        <Button size="sm" variant={p.is_bulk ? "default" : "outline"} aria-label={`Split line ${p.line.id}`}
                                                onClick={() => setSplitting(p)}>Split</Button>)}
                                    {errors[p.line.id] && <span className="max-w-48 text-xs text-red-700" role="alert">{errors[p.line.id]}</span>}
                                </div>);
                        } },
                    ]} />
                </QueryState>
            </Panel>
            {showAliases && <AliasesPanel entityId={entityId} />}
        </div>
    );
}
