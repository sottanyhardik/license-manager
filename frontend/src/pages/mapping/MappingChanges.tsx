/**
 * Mapping changes (Part 15): every approved product / debit-item mapping change is a version whose affected
 * licences re-plan automatically. Shows propagation status (PROPAGATING → PUBLISHED, or FAILED with retry) and
 * the before / after impact: archived (superseded) plan lines vs the published plan per debit item, with actual
 * utilisation and active planning kept separate. Display only — every figure comes from the backend.
 */
import { Fragment, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import api from "@/api/axios";
import { Button } from "@/components/ui/button";
import { EmptyState, InlineError, LoadingState, StatusBadge, type Tone } from "@/components/shared";
import { cn } from "@/lib/utils";
import { errorText } from "./matchingShared";

type ChangeStatus = "PROPAGATING" | "PUBLISHED" | "FAILED" | "NO_PLANNING_IMPACT";
type Change = { version: number; kind: string; status: ChangeStatus; source_refs: number[]; import_items: number; licences: number; error: string; retries: number;
    created_by: string | null; created_on: string; completed_on: string | null; detail: Record<string, unknown> };
type Impact = {
    change: Change; provisional: boolean; totals: Record<string, string>;
    licences: { license_id: number; license_number: string | null; stale: boolean; superseded_lines: number; active_lines: number;
        items: { item: string; before_qty: string; after_qty: string; before_cif: string; after_cif: string; changed: boolean }[];
        actual: Record<"boe_cif" | "allotment_cif" | "available_cif", { before: string | null; after: string | null }>;
        replan: { status: string | null; error: string; failures: unknown[] } }[];
};
const TONE: Record<ChangeStatus, Tone> = { PROPAGATING: "warning", PUBLISHED: "success", FAILED: "danger", NO_PLANNING_IMPACT: "neutral" };
const LABEL: Record<ChangeStatus, string> = { PROPAGATING: "Re-planning…", PUBLISHED: "Published", FAILED: "Propagation failed", NO_PLANNING_IMPACT: "Item Pivot only" };
const fmt = (v: string | null | undefined) => (v == null ? "—" : Number(v).toLocaleString("en-IN", { maximumFractionDigits: 3 }));

function ImpactView({ version }: { version: number }) {
    const impact = useQuery({ queryKey: ["mapping-change-impact", version], queryFn: async ({ signal }) => (await api.get(`item-pivot/matching/mapping-changes/${version}/`, { signal })).data as Impact });
    if (impact.isPending) return <LoadingState variant="spinner" label="Loading impact…" />;
    if (impact.isError) return <InlineError error={impact.error as Error} title="Impact report failed" onRetry={() => void impact.refetch()} />;
    const d = impact.data;
    const t = d.totals;
    return (
        <div className="space-y-2 text-xs">
            {d.provisional && <p role="status" className="rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1">Provisional — the affected licences have not all re-planned yet; "after" shows the current state, not the published result.</p>}
            <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-3" aria-label="Impact totals">
                <div><dt className="text-muted-foreground">Active planning (planned CIF)</dt><dd className="tabular-nums">{fmt(t.before_planned_cif)} → {fmt(t.after_planned_cif)}</dd></div>
                <div><dt className="text-muted-foreground">Actual BOE CIF</dt><dd className="tabular-nums">{fmt(t.before_boe_cif)} → {fmt(t.after_boe_cif)}</dd></div>
                <div><dt className="text-muted-foreground">Outstanding allotment CIF</dt><dd className="tabular-nums">{fmt(t.before_allotment_cif)} → {fmt(t.after_allotment_cif)}</dd></div>
            </dl>
            {d.licences.map((lic) => (
                <div key={lic.license_id} className="rounded-md border border-border/60">
                    <div className="flex flex-wrap items-center gap-x-3 border-b border-border/50 px-2 py-1">
                        <span className="font-mono font-semibold">{lic.license_number ?? lic.license_id}</span>
                        {lic.stale ? <StatusBadge tone="warning" label="Re-planning" /> : <StatusBadge tone="success" label="Current" />}
                        <span className="text-muted-foreground">{lic.superseded_lines} archived line(s) → {lic.active_lines} active · re-plan {lic.replan.status ?? "—"}</span>
                        {lic.replan.error && <span className="text-destructive">{lic.replan.error}</span>}
                        <span className="ml-auto text-muted-foreground">available CIF {fmt(lic.actual.available_cif.before)} → {fmt(lic.actual.available_cif.after)}</span>
                    </div>
                    <table className="w-full text-xs" aria-label={`Plan impact for ${lic.license_number ?? lic.license_id}`}>
                        <thead><tr className="text-left text-muted-foreground"><th scope="col" className="px-2 py-1">Debit item</th><th scope="col" className="px-2 text-right">Planned qty before</th><th scope="col" className="px-2 text-right">After</th><th scope="col" className="px-2 text-right">Planned CIF before</th><th scope="col" className="px-2 text-right">After</th></tr></thead>
                        <tbody>{lic.items.map((i) => <tr key={i.item} className={cn("border-t border-border/40", i.changed && "bg-primary/5")}><td className="px-2 py-1">{i.item}</td><td className="px-2 text-right tabular-nums">{fmt(i.before_qty)}</td><td className="px-2 text-right tabular-nums">{fmt(i.after_qty)}</td><td className="px-2 text-right tabular-nums">{fmt(i.before_cif)}</td><td className="px-2 text-right tabular-nums">{fmt(i.after_cif)}</td></tr>)}</tbody>
                    </table>
                </div>
            ))}
        </div>
    );
}

export default function MappingChanges() {
    const qc = useQueryClient();
    const [open, setOpen] = useState<number | null>(null);
    const list = useQuery({
        queryKey: ["mapping-changes"],
        queryFn: async ({ signal }) => (await api.get("item-pivot/matching/mapping-changes/", { signal })).data as { changes: Change[]; can_retry: boolean },
        refetchInterval: (q) => (q.state.data?.changes.some((c) => c.status === "PROPAGATING") ? 10_000 : false),
    });
    const retry = useMutation({
        mutationFn: (version: number) => api.post(`item-pivot/matching/mapping-changes/${version}/retry/`),
        onSuccess: () => { toast.success("Re-planning re-requested"); void qc.invalidateQueries({ queryKey: ["mapping-changes"] }); void qc.invalidateQueries({ queryKey: ["mapping-change-impact"] }); },
        onError: (err) => toast.error(errorText(err, "Retry failed")),
    });
    if (list.isPending) return <LoadingState variant="spinner" label="Loading mapping changes…" />;
    if (list.isError) return <InlineError error={list.error as Error} title="Could not load mapping changes" onRetry={() => void list.refetch()} />;
    const rows = list.data.changes;
    if (!rows.length) return <EmptyState title="No mapping changes yet" description="Approvals, classifications, consolidations and debit-target changes appear here with their re-planning status." />;
    return (
        <div className="overflow-x-auto rounded-lg border border-border/70">
            <table className="w-full min-w-[900px] text-xs" aria-label="Mapping changes">
                <thead><tr className="bg-muted text-left text-[11px] uppercase text-muted-foreground"><th scope="col" className="px-2 py-2">Version</th><th scope="col" className="px-2">Change</th><th scope="col" className="px-2">Status</th><th scope="col" className="px-2 text-right">Records</th><th scope="col" className="px-2 text-right">Licences</th><th scope="col" className="px-2">By / when</th><th scope="col" className="px-2"><span className="sr-only">Actions</span></th></tr></thead>
                <tbody>{rows.map((c) => (
                    <Fragment key={c.version}>
                        <tr className="border-t border-border/50 align-top">
                            <td className="px-2 py-1.5"><button type="button" aria-expanded={open === c.version} aria-label={`Impact of version ${c.version}`} onClick={() => setOpen(open === c.version ? null : c.version)} className="inline-flex items-center gap-1 font-mono"><ChevronRight className={cn("size-3.5 transition-transform", open === c.version && "rotate-90")} aria-hidden="true" />v{c.version}</button></td>
                            <td className="px-2 py-1.5">{c.kind.replace(/_/g, " ").toLowerCase()}</td>
                            <td className="px-2 py-1.5"><StatusBadge tone={TONE[c.status]} label={LABEL[c.status]} />{c.error && <div className="mt-0.5 max-w-[24rem] text-[11px] text-destructive">{c.error}</div>}</td>
                            <td className="px-2 py-1.5 text-right tabular-nums">{c.import_items}</td><td className="px-2 py-1.5 text-right tabular-nums">{c.licences}</td>
                            <td className="px-2 py-1.5 text-muted-foreground">{c.created_by ?? "system"} · {new Date(c.created_on).toLocaleString("en-IN")}</td>
                            <td className="px-2 py-1.5 text-right">{list.data.can_retry && (c.status === "FAILED" || c.status === "PROPAGATING") && <Button size="sm" variant="ghost" disabled={retry.isPending} onClick={() => retry.mutate(c.version)}><RotateCcw className="size-3.5" />Retry</Button>}</td>
                        </tr>
                        {open === c.version && <tr className="bg-muted/20"><td colSpan={7} className="px-3 py-2">{c.status === "NO_PLANNING_IMPACT" ? <p className="text-xs text-muted-foreground">Classification only — Item Pivot grouping changed; no licence plan depends on it.</p> : <ImpactView version={c.version} />}</td></tr>}
                    </Fragment>
                ))}</tbody>
            </table>
        </div>
    );
}
