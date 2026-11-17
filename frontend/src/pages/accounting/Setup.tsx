import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { acctGet, acctKeys, acctPatch, acctPost, type EntityBooks } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { useAccountingAccess } from "./useAccountingAccess";
import { useGuardedAction } from "./useGuardedAction";
import { DataGrid, Field, inputCls, notifyError, Panel, QueryState, ReadOnlyNote, StatusBadge } from "./ui";

function ActivateBooks() {
    const { canApprove } = useAccountingAccess();
    const { discovered, refetchEntities } = useAccounting();
    const qc = useQueryClient();
    const [dates, setDates] = useState<Record<number, string>>({});
    const activate = useMutation({
        mutationFn: (companyId: number) => acctPost<EntityBooks>("entities/", { company_id: companyId, books_start_date: dates[companyId] }),
        onSuccess: (b) => { toast.success(`Books started for ${b.name}`); refetchEntities(); void qc.invalidateQueries({ queryKey: acctKeys.all }); },
        onError: notifyError,
    });
    return (
        <Panel title="Entities discovered from Trade">
            <p className="mb-3 text-sm text-slate-600">
                These companies are the own side of trade documents (buyer on purchases, seller on sales). Start books only for the
                group's own legal entities. Counterparties appear here only through copied paired legs. Entity ids are the existing company ids.
            </p>
            <DataGrid rows={discovered} rowKey={(d) => d.company_id} empty="No trades yet." caption="Discovered entities" columns={[
                { key: "n", header: "Company", cell: (d) => d.name },
                { key: "g", header: "GSTIN", cell: (d) => d.gstin ?? "—" },
                { key: "c", header: "Own-side documents", numeric: true, cell: (d) => d.own_side_documents },
                { key: "b", header: "Books", cell: (d) => d.has_books ? <StatusBadge status="POSTED" /> : <StatusBadge status="NOT_ACCOUNTED" /> },
                { key: "a", header: "Start books", cell: (d) => d.has_books ? `since ${d.books_start_date}` : !canApprove ? "—" : (
                    <div className="flex items-center gap-1">
                        <input type="date" className={`${inputCls} w-40`} aria-label={`Books start date for ${d.name}`} value={dates[d.company_id] ?? ""}
                               onChange={(e) => setDates({ ...dates, [d.company_id]: e.target.value })} />
                        <Button size="sm" disabled={!dates[d.company_id] || activate.isPending} onClick={() => activate.mutate(d.company_id)}>Start books</Button>
                    </div>) },
            ]} />
        </Panel>
    );
}

function EntitySettings() {
    const { canApprove } = useAccountingAccess();
    const { entityId } = useAccounting();
    const { guard, dialog } = useGuardedAction();
    const qc = useQueryClient();
    const q = useQuery({ queryKey: acctKeys.of(entityId, "entity"), queryFn: () => acctGet<EntityBooks>(`entities/${entityId}/`), enabled: !!entityId });
    const save = useMutation({
        mutationFn: (body: Record<string, unknown>) => acctPatch(`entities/${entityId}/`, body),
        onSuccess: () => { toast.success("Saved"); void qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) }); }, onError: notifyError,
    });
    const lock = useMutation({
        mutationFn: ({ id, locked }: { id: number; locked: boolean }) => acctPost(`periods/${id}/lock/`, { locked }),
        onSuccess: () => { void qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) }); }, onError: notifyError,
    });
    if (!entityId) return <p className="text-sm text-slate-600">Start books for an entity above to configure it.</p>;
    const e = q.data;
    const saveIfChanged = (field: "default_credit_days" | "state_code", value: string) => {
        if (e && String(e[field] ?? "") !== value) save.mutate({ [field]: value });
    };
    return (
        <QueryState isLoading={q.isLoading} error={q.error}>
            {e && (
                <Panel title={`Books settings — ${e.name}`}>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
                        <Field label="Books start date"><span className="h-9 py-2 text-sm">{e.books_start_date}</span></Field>
                        <Field label="Default credit days"><input key={`cd-${e.id}`} inputMode="numeric" className={inputCls} disabled={!canApprove} defaultValue={e.default_credit_days}
                            onBlur={(ev) => saveIfChanged("default_credit_days", ev.target.value)} /></Field>
                        <Field label="GST state code" hint="From GSTIN; drives CGST+SGST vs IGST"><input key={`sc-${e.id}`} className={inputCls} disabled={!canApprove} defaultValue={e.state_code}
                            onBlur={(ev) => saveIfChanged("state_code", ev.target.value)} /></Field>
                        <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={e.require_maker_checker} disabled={!canApprove || save.isPending}
                            onChange={(ev) => save.mutate({ require_maker_checker: ev.target.checked })} /> Maker-checker (bills, manual vouchers, reversals)</label>
                    </div>
                    {dialog}
                    {(e.financial_years ?? []).map((fy) => (
                        <div key={fy.id} className="mt-4">
                            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">FY {fy.label} periods</h3>
                            <div className="flex flex-wrap gap-1">{fy.periods.map((p) => (
                                <button key={p.id} type="button" aria-pressed={p.status === "LOCKED"} disabled={!canApprove || lock.isPending}
                                        aria-label={`${p.start_date.slice(0, 7)} ${p.status === "LOCKED" ? "locked" : "open"}`}
                                        onClick={() => p.status === "LOCKED"
                                            ? void guard({ title: "Unlock period", severity: "danger", confirmText: "Unlock",
                                                message: `Unlock ${p.start_date.slice(0, 7)}? Postings into this month become possible again.` },
                                            () => lock.mutate({ id: p.id, locked: false }))
                                            : lock.mutate({ id: p.id, locked: true })}
                                        className={`rounded-md border px-2 py-1 text-xs ${p.status === "LOCKED" ? "border-red-300 bg-red-50 text-red-700" : "border-slate-200 bg-white text-slate-700 hover:border-slate-400"}`}
                                        title={p.status === "LOCKED" ? "Locked — click to unlock" : "Open — click to lock"}>
                                    {p.start_date.slice(0, 7)}<span aria-hidden="true">{p.status === "LOCKED" ? " 🔒" : ""}</span></button>))}</div>
                        </div>
                    ))}
                </Panel>
            )}
        </QueryState>
    );
}

/** The chart itself is managed under Masters → Chart of Accounts (one screen, no duplicate editor). */
function ChartLink() {
    return (
        <Panel title="Chart of accounts">
            <p className="text-sm text-slate-600">Ledgers, groups and opening balances are managed under{" "}
                <Link className="font-medium text-blue-700 hover:underline" to="/accounting/masters/accounts">Masters → Chart of Accounts</Link>.</p>
        </Panel>
    );
}

interface TdsSection { id: number; code: string; description: string; rate_individual: string; rate_other: string; rate_no_pan: string;
    threshold_single: string; threshold_aggregate: string; threshold_mode: string; effective_from: string; effective_to: string | null }

function TdsSections() {
    const { canApprove } = useAccountingAccess();
    const qc = useQueryClient();
    const q = useQuery({ queryKey: [...acctKeys.all, "tds"], queryFn: () => acctGet<TdsSection[]>("tds-sections/") });
    const blank = { code: "", description: "", rate_individual: "", rate_other: "", rate_no_pan: "", threshold_single: "0", threshold_aggregate: "0", threshold_mode: "FULL", effective_from: "" };
    const [f, setF] = useState(blank);
    const add = useMutation({
        mutationFn: () => acctPost("tds-sections/", f),
        onSuccess: () => { toast.success("TDS section version saved"); setF(blank); void qc.invalidateQueries({ queryKey: [...acctKeys.all, "tds"] }); },
        onError: notifyError,
    });
    return (
        <Panel title="TDS sections (dated configuration — nothing is pre-filled)">
            <p className="mb-3 text-xs text-slate-500">Enter each section with the rates and thresholds your CA has confirmed. A new effective date creates a new version, and old invoices keep the rate that applied on their date.</p>
            <DataGrid rows={q.data ?? []} rowKey={(s) => s.id} empty="No TDS sections configured — invoices carry no TDS until one is added." caption="TDS sections" columns={[
                { key: "c", header: "Section", cell: (s) => s.code },
                { key: "d", header: "Description", cell: (s) => s.description },
                { key: "ri", header: "Indiv./HUF %", numeric: true, cell: (s) => s.rate_individual },
                { key: "ro", header: "Others %", numeric: true, cell: (s) => s.rate_other },
                { key: "rn", header: "No PAN %", numeric: true, cell: (s) => s.rate_no_pan },
                { key: "t", header: "Threshold (FY)", numeric: true, cell: (s) => `${s.threshold_aggregate} (${s.threshold_mode})` },
                { key: "e", header: "Effective", cell: (s) => `${s.effective_from} → ${s.effective_to ?? "open"}` },
            ]} />
            {canApprove && <form className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-9" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
                {(["code", "description", "rate_individual", "rate_other", "rate_no_pan", "threshold_single", "threshold_aggregate"] as const).map((k) => (
                    <Field key={k} label={k.replace(/_/g, " ")}><input className={inputCls} required={k !== "threshold_single"} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></Field>))}
                <Field label="mode"><select className={inputCls} value={f.threshold_mode} onChange={(e) => setF({ ...f, threshold_mode: e.target.value })}>
                    <option value="FULL">Whole amount</option><option value="EXCESS">Only above threshold</option></select></Field>
                <Field label="effective from"><input type="date" className={inputCls} required value={f.effective_from} onChange={(e) => setF({ ...f, effective_from: e.target.value })} /></Field>
                <Button className="self-end" type="submit" disabled={add.isPending}>Save</Button>
            </form>}
        </Panel>
    );
}

export default function Setup() {
    const { canApprove } = useAccountingAccess();
    return (
        <div className="space-y-4">
            {!canApprove && <ReadOnlyNote need="the accounts approver role to change books, periods, chart or TDS" />}
            <ActivateBooks />
            <EntitySettings />
            <ChartLink />
            <TdsSections />
        </div>
    );
}
