import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { acctGet, acctKeys, acctPost, type BankAccount, type Money } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { useAccountingAccess } from "./useAccountingAccess";
import { Amount, DataGrid, Field, inputCls, notifyError, Panel, QueryState, ReadOnlyNote, StatusBadge } from "./ui";

interface Item { source_type: string; source_id: number; classification: string; outcome: string; reasons: string[]; amount: Money; financial_year: string }
interface Run { id: number; mode: string; created_on: string; created_by: string | null; summary: Record<string, unknown>; items?: Item[] }

export default function MigrationCenter() {
    const { entityId, entity } = useAccounting();
    const { canApprove } = useAccountingAccess();
    const qc = useQueryClient();
    const [run, setRun] = useState<Run | null>(null);
    const [bankId, setBankId] = useState("");
    const [confirmText, setConfirmText] = useState("");
    const [filter, setFilter] = useState("");
    const data = useQuery({ queryKey: acctKeys.of(entityId, "migration"),
        queryFn: () => acctGet<{ runs: Run[]; reconciliation: Record<string, { source_total: Money; accounted_total: Money; difference: Money }> }>("migration/", { entity: entityId }) });
    const banks = useQuery({ queryKey: acctKeys.of(entityId, "banks"), queryFn: () => acctGet<BankAccount[]>("bank-accounts/", { entity: entityId }) });
    const go = useMutation({
        mutationFn: (mode: "DRY_RUN" | "EXECUTE") => acctPost<Run>("migration/", { entity: entityId, mode, confirm: mode === "EXECUTE", bank_account_id: bankId || null }),
        onSuccess: (r) => { setRun(r); setConfirmText(""); toast.success(r.mode === "DRY_RUN" ? "Dry run complete — nothing was posted" : "Migration executed"); void qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) }); },
        onError: notifyError,
    });
    const items = (run?.items ?? []).filter((i) => !filter || i.classification === filter || i.outcome === filter);
    const recon = Object.entries(data.data?.reconciliation ?? {});
    return (
        <div className="space-y-4">
            <Panel title="Historical data migration — existing trades and trade payments">
                <ol className="mb-3 list-decimal space-y-1 pl-5 text-sm text-slate-600">
                    <li><b>Dry run</b> classifies every record as Ready, Needs review, Already accounted or Exception, with reasons. Nothing is posted.</li>
                    <li><b>Execute</b> posts Ready records through the same posting engine as live entries, and each record at most once. Payments need a mapped bank account.</li>
                    <li>The reconciliation below compares source trade totals with accounted totals by financial year. Differences stay visible.</li>
                </ol>
                {!canApprove && <ReadOnlyNote need="the accounts approver role to run or execute migrations" />}
                {canApprove && <div className="flex flex-wrap items-end gap-3">
                    <Button onClick={() => go.mutate("DRY_RUN")} disabled={go.isPending}>Run dry run</Button>
                    <Field label="Bank for historical payments"><select className={inputCls} value={bankId} onChange={(e) => setBankId(e.target.value)}>
                        <option value="">None (payments skipped)</option>{(banks.data ?? []).map((b) => <option key={b.id} value={b.id}>{b.bank_name} {b.account_number}</option>)}</select></Field>
                    <Field label={`Type the entity name to confirm posting into ${entity?.name ?? ""}'s books`}>
                        <input className={`${inputCls} w-72`} value={confirmText} onChange={(e) => setConfirmText(e.target.value)} /></Field>
                    <Button variant="destructive" disabled={confirmText.trim() !== entity?.name || go.isPending} onClick={() => go.mutate("EXECUTE")}>Execute migration</Button>
                </div>}
            </Panel>
            <Panel title="Source vs accounted, by financial year">
                <QueryState isLoading={data.isLoading} error={data.error}>
                    <DataGrid rows={recon} rowKey={([fy]) => fy} empty="No trades for this entity." caption="Reconciliation" columns={[
                        { key: "fy", header: "FY", cell: ([fy]) => fy },
                        { key: "s", header: "Trade totals", numeric: true, cell: ([, r]) => <Amount value={r.source_total} /> },
                        { key: "a", header: "Accounted", numeric: true, cell: ([, r]) => <Amount value={r.accounted_total} /> },
                        { key: "d", header: "Difference", numeric: true, cell: ([, r]) => <Amount value={r.difference} /> },
                    ]} />
                </QueryState>
            </Panel>
            {run && (
                <Panel title={`Run #${run.id} — ${run.mode === "DRY_RUN" ? "dry run" : "execution"}`} actions={
                    <select className={inputCls} aria-label="Filter" value={filter} onChange={(e) => setFilter(e.target.value)}>
                        <option value="">All</option>{["READY", "NEEDS_REVIEW", "ALREADY_ACCOUNTED", "EXCEPTION", "MIGRATED", "SKIPPED", "FAILED"].map((s) => <option key={s}>{s}</option>)}</select>}>
                    <DataGrid rows={items} rowKey={(i) => `${i.source_type}-${i.source_id}`} caption="Migration items" columns={[
                        { key: "t", header: "Record", cell: (i) => `${i.source_type === "TRADE" ? "Trade" : "Trade payment"} #${i.source_id}` },
                        { key: "fy", header: "FY", cell: (i) => i.financial_year },
                        { key: "a", header: "Amount", numeric: true, cell: (i) => <Amount value={i.amount} /> },
                        { key: "c", header: "Classification", cell: (i) => <StatusBadge status={i.classification} /> },
                        { key: "o", header: "Outcome", cell: (i) => <StatusBadge status={i.outcome || null} /> },
                        { key: "r", header: "Reasons", cell: (i) => <span className="text-xs text-slate-600">{i.reasons.join("; ")}</span> },
                    ]} />
                </Panel>
            )}
        </div>
    );
}
