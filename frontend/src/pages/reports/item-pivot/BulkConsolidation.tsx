/**
 * Bulk canonical-product consolidation (e.g. every verified Polypropylene wording under E1 → "PP").
 *
 * Preview first: every candidate group of the norm with its current master(s), HSN, record count, status and
 * reason. Only ELIGIBLE groups (one product, same identity, compatible HSN, single or no current link) can be
 * selected; multi-product, extra-word, HSN-conflict and multi-link groups are listed for human review and are
 * never consolidated here. Apply re-validates everything on the server, records each previous mapping, and can
 * be reverted per batch. No quantity, CIF or debit changes; the affected licences re-plan automatically (Part 15).
 */
import { Fragment, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Loader2, Undo2 } from "lucide-react";
import { toast } from "sonner";

import api from "@/api/axios";
import { Button } from "@/components/ui/button";
import { EmptyState, InlineError, LoadingState, StatusBadge, type Tone } from "@/components/shared";
import { cn } from "@/lib/utils";
import { errorText } from "./matchingShared";

type Status = "ELIGIBLE" | "REVIEW" | "ALREADY_CONSOLIDATED" | "EXCLUDED";
type Row = {
    key: string; description: string; hsn_code: string; sion: string; status: Status; selectable: boolean; reasons: string[]; record_count: number;
    eligible_record_ids: number[]; record_ids: number[]; license_numbers: string[]; current_masters: Record<string, number>; proposed: string;
};
type Batch = { batch: string; sion: string; target: string; records: number; reason: string; user: string | null; on: string; reverted: boolean };
type Preview = { sion: string; target: { item_id: number; name: string; chapters: string[] }; summary: { groups: Partial<Record<Status, number>>; records: Partial<Record<Status, number>> };
    rows: Row[]; can_apply: boolean; batches: Batch[] };

const STATUS: Record<Status, { tone: Tone; label: string }> = {
    ELIGIBLE: { tone: "primary", label: "Eligible" }, REVIEW: { tone: "warning", label: "Needs review" },
    ALREADY_CONSOLIDATED: { tone: "success", label: "Already consolidated" }, EXCLUDED: { tone: "neutral", label: "Excluded" },
};

export default function BulkConsolidation({ defaultSion }: { defaultSion: string }) {
    const qc = useQueryClient();
    const [sion, setSion] = useState(defaultSion);
    const [targetId, setTargetId] = useState<number | null>(null);
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [open, setOpen] = useState<string | null>(null);
    const [reason, setReason] = useState("");
    const [show, setShow] = useState<"ALL" | Status>("ALL");
    const masters = useQuery({
        queryKey: ["item-pivot-masters", sion],
        enabled: !!sion,
        queryFn: async ({ signal }) => (await api.get("item-pivot/matching/masters/", { params: { sion }, signal })).data as { masters: { item_id: number; name: string }[] },
        staleTime: 300_000,
    });
    const preview = useQuery({
        queryKey: ["item-pivot-consolidation", sion, targetId],
        enabled: !!sion && targetId != null,
        queryFn: async ({ signal }) => (await api.get("item-pivot/matching/consolidation/", { params: { sion, target_id: targetId }, signal })).data as Preview,
    });
    const refresh = () => {
        setSelected(new Set());
        void qc.invalidateQueries({ queryKey: ["item-pivot-consolidation"] });
        void qc.invalidateQueries({ queryKey: ["item-pivot-intelligence"] });
        void qc.invalidateQueries({ queryKey: ["item-pivot-matching"] });
    };
    const applyMutation = useMutation({
        mutationFn: async () => (await api.post("item-pivot/matching/consolidation/apply/", { sion, target_id: targetId, keys: [...selected], reason })).data as { batch: string; records: number; skipped_aliases: unknown[] },
        onSuccess: (r) => { toast.success(`Consolidated ${r.records} record(s) into ${preview.data?.target.name} (batch ${r.batch.slice(0, 8)})`); setReason(""); refresh(); },
        onError: (err) => toast.error(errorText(err, "Consolidation failed — nothing was changed")),
    });
    const revertMutation = useMutation({
        mutationFn: async (batch: string) => (await api.post("item-pivot/matching/consolidation/revert/", { batch })).data as { restored: number; conflicts: unknown[] },
        onSuccess: (r) => { toast.success(`Reverted — ${r.restored} record(s) restored${r.conflicts.length ? `, ${r.conflicts.length} left as changed since` : ""}`); refresh(); },
        onError: (err) => toast.error(errorText(err, "Revert failed")),
    });

    const data = preview.data;
    const rows = useMemo(() => (data?.rows ?? []).filter((r) => show === "ALL" || r.status === show), [data, show]);
    const eligible = (data?.rows ?? []).filter((r) => r.selectable);
    const selectedRecords = eligible.filter((r) => selected.has(r.key)).reduce((n, r) => n + r.eligible_record_ids.length, 0);
    const toggle = (key: string) => setSelected((prev) => { const next = new Set(prev); if (next.has(key)) next.delete(key); else next.add(key); return next; });

    return (
        <div className="space-y-3">
            <section aria-label="Consolidation target" className="flex flex-wrap items-end gap-3 rounded-lg border border-border/70 bg-card px-3 py-2 text-sm">
                <label className="flex flex-col text-xs">SION norm
                    <input aria-label="SION norm" value={sion} onChange={(e) => { setSion(e.target.value.trim().toUpperCase()); setTargetId(null); setSelected(new Set()); }} className="mt-0.5 h-8 w-28 rounded-md border border-input bg-background px-2 text-sm" />
                </label>
                <label className="flex flex-col text-xs">Canonical product
                    <select aria-label="Canonical product" value={targetId ?? ""} onChange={(e) => { setTargetId(e.target.value ? Number(e.target.value) : null); setSelected(new Set()); }} className="mt-0.5 h-8 min-w-[14rem] rounded-md border border-input bg-background px-2 text-sm">
                        <option value="">— choose the master to consolidate into —</option>
                        {(masters.data?.masters ?? []).map((m) => <option key={m.item_id} value={m.item_id}>{m.name}</option>)}
                    </select>
                </label>
                {masters.isError && <span className="text-xs text-destructive">Masters could not be loaded</span>}
                <p className="max-w-xl text-[11px] text-muted-foreground">Master links change (audited, reversible per batch); descriptions, HSN, quantities, CIF and debits never change. Affected licences re-plan automatically — follow progress under Mapping changes.</p>
            </section>

            {targetId == null ? <EmptyState title="Choose a canonical product" description="The preview lists every record of the norm whose wording names that product." />
                : preview.isPending ? <LoadingState variant="spinner" label="Building the consolidation preview…" />
                    : preview.isError ? <InlineError error={preview.error as Error} title="Preview failed" onRetry={() => void preview.refetch()} />
                        : data && (
                            <>
                                <div role="group" aria-label="Status filter" className="flex flex-wrap items-center gap-1 text-xs">
                                    <Button size="sm" variant={show === "ALL" ? "default" : "ghost"} onClick={() => setShow("ALL")}>All {data.rows.length}</Button>
                                    {(Object.keys(STATUS) as Status[]).map((s) => <Button key={s} size="sm" variant={show === s ? "default" : "ghost"} onClick={() => setShow(s)}>{STATUS[s].label} {data.summary.groups[s] ?? 0} groups · {data.summary.records[s] ?? 0} records</Button>)}
                                    <span className="ml-auto text-muted-foreground">Target {data.target.name} · HSN chapters {data.target.chapters.join(", ") || "—"}</span>
                                </div>
                                <div className="max-h-[60vh] overflow-auto rounded-lg border border-border/70">
                                    <table className="w-full min-w-[1100px] text-xs" aria-label="Consolidation candidates">
                                        <thead><tr className="sticky top-0 z-[1] bg-muted text-left text-[11px] uppercase text-muted-foreground">
                                            <th scope="col" className="px-2 py-2"><span className="sr-only">Select</span></th><th scope="col" className="px-2">Original item name</th><th scope="col" className="px-2">Current master(s)</th>
                                            <th scope="col" className="px-2">SION</th><th scope="col" className="px-2">HSN</th><th scope="col" className="px-2 text-right">Records</th><th scope="col" className="px-2">Proposed</th><th scope="col" className="px-2">Status / compatibility</th></tr></thead>
                                        <tbody>{rows.map((r) => (
                                            <Fragment key={r.key}>
                                                <tr className={cn("border-t border-border/50 align-top", selected.has(r.key) && "bg-primary/5")}>
                                                    <td className="px-2 py-1.5">{data.can_apply && r.selectable && <input type="checkbox" aria-label={`Select ${r.description}`} checked={selected.has(r.key)} onChange={() => toggle(r.key)} />}</td>
                                                    <td className="max-w-[26rem] px-2 py-1.5">
                                                        <button type="button" aria-expanded={open === r.key} onClick={() => setOpen(open === r.key ? null : r.key)} className="flex items-start gap-1 text-left">
                                                            <ChevronRight className={cn("mt-0.5 size-3.5 shrink-0 transition-transform", open === r.key && "rotate-90")} aria-hidden="true" />{r.description}
                                                        </button>
                                                    </td>
                                                    <td className="px-2 py-1.5">{Object.entries(r.current_masters).map(([n, c]) => `${n} (${c})`).join(", ") || "unlinked"}</td>
                                                    <td className="px-2 py-1.5">{r.sion}</td><td className="px-2 py-1.5 font-mono">{r.hsn_code || "—"}</td>
                                                    <td className="px-2 py-1.5 text-right tabular-nums">{r.record_count}{r.selectable && r.eligible_record_ids.length !== r.record_count && <div className="text-[10px] text-muted-foreground">{r.eligible_record_ids.length} to change</div>}</td>
                                                    <td className="px-2 py-1.5 font-medium">{r.proposed}</td>
                                                    <td className="max-w-[24rem] px-2 py-1.5"><StatusBadge tone={STATUS[r.status].tone} label={STATUS[r.status].label} />{r.reasons.map((x) => <div key={x} className="text-[11px] text-muted-foreground">{x}</div>)}</td>
                                                </tr>
                                                {open === r.key && <tr className="bg-muted/20"><td colSpan={8} className="px-6 py-2 text-[11px]">
                                                    <div><span className="font-semibold">Source records:</span> {r.record_ids.map((id) => `#${id}`).join(", ")}</div>
                                                    <div><span className="font-semibold">Licences:</span> {r.license_numbers.join(", ")}</div>
                                                </td></tr>}
                                            </Fragment>
                                        ))}</tbody>
                                    </table>
                                    {!rows.length && <EmptyState title="No candidates" description="No record of this norm names the chosen product." />}
                                </div>
                                {data.can_apply && (
                                    <div className="flex flex-wrap items-end gap-2 rounded-lg border border-border/70 bg-card px-3 py-2">
                                        <Button size="sm" variant="outline" disabled={!eligible.length} onClick={() => setSelected(new Set(eligible.map((r) => r.key)))}>Select all eligible ({eligible.length})</Button>
                                        <Button size="sm" variant="ghost" disabled={!selected.size} onClick={() => setSelected(new Set())}>Clear selection</Button>
                                        <label className="flex min-w-[18rem] flex-1 flex-col text-xs">Reason (recorded in the audit)
                                            <input aria-label="Consolidation reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder={`e.g. ${data.sion} ${data.target.name} cleanup`} className="mt-0.5 h-8 rounded-md border border-input bg-background px-2 text-sm" />
                                        </label>
                                        <Button size="sm" disabled={!selected.size || !reason.trim() || applyMutation.isPending}
                                            onClick={() => { if (window.confirm(`Consolidate ${selectedRecords} record(s) in ${selected.size} group(s) into ${data.target.name} under ${data.sion}? Previous links are recorded and can be reverted.`)) applyMutation.mutate(); }}>
                                            {applyMutation.isPending && <Loader2 className="size-3.5 animate-spin" />}Consolidate {selectedRecords} record(s) into {data.target.name}
                                        </Button>
                                    </div>
                                )}
                                {data.batches.length > 0 && (
                                    <section aria-label="Consolidation batches" className="rounded-lg border border-border/70 bg-card">
                                        <h3 className="border-b border-border/60 px-3 py-2 text-sm font-semibold">Consolidation batches (audited)</h3>
                                        <ul className="divide-y divide-border/50 text-xs">{data.batches.map((b) => (
                                            <li key={b.batch} className="flex flex-wrap items-center gap-x-3 px-3 py-1.5">
                                                <span className="font-mono">{b.batch.slice(0, 8)}</span><span>{b.sion} → {b.target} · {b.records} record(s)</span>
                                                <span className="text-muted-foreground">{b.reason} · {b.user} · {new Date(b.on).toLocaleString("en-IN")}</span>
                                                {b.reverted ? <StatusBadge tone="neutral" label="Reverted" /> : <Button size="sm" variant="ghost" className="ml-auto" disabled={revertMutation.isPending}
                                                    onClick={() => { if (window.confirm("Revert this batch? Links still unchanged since the consolidation are restored.")) revertMutation.mutate(b.batch); }}><Undo2 className="size-3.5" />Revert</Button>}
                                            </li>
                                        ))}</ul>
                                    </section>
                                )}
                            </>
                        )}
        </div>
    );
}
