/**
 * Product Intelligence administration: historical inventory, verified labels, model
 * lifecycle (dataset → train → evaluate → promote / reject → rollback), approved
 * aliases and the audit trail. Training runs in the background `matching` queue; this
 * page only requests it. No model ever approves a match.
 */
import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Loader2, RotateCcw, Search, ShieldCheck, Undo2 } from "lucide-react";
import { toast } from "sonner";

import api from "@/api/axios";
import { Button } from "@/components/ui/button";
import { InlineError, LoadingState, StatusBadge, type Tone } from "@/components/shared";
import { cn } from "@/lib/utils";
import { errorText, type AliasRow, type IntelAdmin, type IntelModel } from "./matchingShared";

const MODEL_TONE: Record<IntelModel["status"], Tone> = { ACTIVE: "success", CANDIDATE: "primary", RETIRED: "neutral", REJECTED: "danger", INSUFFICIENT_LABELS: "warning" };
const pct = (v: unknown) => (typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "—");
const n = (v: unknown) => (typeof v === "number" ? v.toLocaleString("en-IN") : "—");

function Card({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
    return (
        <section aria-label={title} className={cn("rounded-lg border border-border/70 bg-card p-3", className)}>
            <h3 className="mb-2 text-sm font-semibold">{title}</h3>
            {children}
        </section>
    );
}

function Aliases({ canManage }: { canManage: boolean }) {
    const qc = useQueryClient();
    const [q, setQ] = useState("");
    const aliases = useQuery({ queryKey: ["product-aliases", q], queryFn: async ({ signal }) => (await api.get("item-pivot/matching/aliases/", { params: q ? { q } : {}, signal })).data as { aliases: AliasRow[] } });
    const deactivate = useMutation({
        mutationFn: (id: number) => api.post(`item-pivot/matching/aliases/${id}/deactivate/`),
        onSuccess: () => { toast.success("Alias deactivated"); void qc.invalidateQueries({ queryKey: ["product-aliases"] }); void qc.invalidateQueries({ queryKey: ["item-pivot-matching"] }); },
        onError: (err) => toast.error(errorText(err, "Could not deactivate alias")),
    });
    return (
        <Card title="Approved alias registry">
            <div className="relative mb-2 w-full sm:w-72"><Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" aria-hidden="true" /><input aria-label="Search aliases" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Alias or product…" className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-2 text-sm" /></div>
            <p className="mb-2 text-[11px] text-muted-foreground">Matching only — aliases turn identical wording into a 100% suggestion that still needs approval. Planning-rule input aliases are configured separately.</p>
            <div className="max-h-72 overflow-auto">
                <table className="w-full [&_td]:px-2 [&_th]:px-2 [&_th]:font-medium text-xs" aria-label="Aliases">
                    <thead><tr className="text-left text-muted-foreground"><th className="py-1">Alias</th><th>Product</th><th>SION</th><th>Source</th><th>By</th><th><span className="sr-only">Actions</span></th></tr></thead>
                    <tbody>{(aliases.data?.aliases ?? []).map((a) => (
                        <tr key={a.id} className="border-t border-border/40">
                            <td className="py-1">{a.alias}</td><td className="font-medium">{a.item}</td><td>{a.sion ?? "any"}</td>
                            <td>{a.source === "DECISION" ? "Approved decision" : "Reviewer"}</td><td>{a.created_by ?? "—"}</td>
                            <td className="text-right">{canManage && <Button size="sm" variant="ghost" disabled={deactivate.isPending} onClick={() => deactivate.mutate(a.id)}>Deactivate</Button>}</td>
                        </tr>
                    ))}</tbody>
                </table>
                {aliases.isFetched && !aliases.data?.aliases.length && <p className="py-2 text-xs text-muted-foreground">No approved aliases yet — approving a match records its wording here.</p>}
            </div>
        </Card>
    );
}

export default function ProductIntelligenceAdmin() {
    const qc = useQueryClient();
    const admin = useQuery({ queryKey: ["product-intel-admin"], queryFn: async ({ signal }) => (await api.get("item-pivot/matching/admin/", { signal })).data as IntelAdmin, staleTime: 30_000 });
    const refresh = () => { void qc.invalidateQueries({ queryKey: ["product-intel-admin"] }); void qc.invalidateQueries({ queryKey: ["item-pivot-matching"] }); };
    const train = useMutation({
        mutationFn: (withTraining: boolean) => api.post("item-pivot/matching/admin/train/", { train: withTraining }),
        onSuccess: (_r, withTraining) => { toast.success(withTraining ? "Dataset + candidate training queued (matching worker)" : "Dataset generation queued"); refresh(); },
        onError: (err) => toast.error(errorText(err, "Request failed")),
    });
    const modelAction = useMutation({
        mutationFn: ({ id, command }: { id: number; command: "promote" | "reject" }) => api.post(`item-pivot/matching/admin/models/${id}/${command}/`),
        onSuccess: (_r, v) => { toast.success(v.command === "promote" ? "Model promoted" : "Candidate rejected"); refresh(); },
        onError: (err) => toast.error(errorText(err, "Model action failed")),
    });
    const rollback = useMutation({
        mutationFn: () => api.post("item-pivot/matching/admin/rollback/"),
        onSuccess: () => { toast.success("Rolled back"); refresh(); },
        onError: (err) => toast.error(errorText(err, "Rollback failed")),
    });
    if (admin.isPending) return <LoadingState variant="spinner" label="Loading product intelligence…" />;
    if (admin.isError) return <InlineError error={admin.error as Error} title="Could not load product intelligence" onRetry={() => void admin.refetch()} />;
    const d = admin.data;
    const active = d.active_model;
    const labelShare = d.labels.required.total > 0 ? Math.min(100, (d.labels.verified / d.labels.required.total) * 100) : 100;
    return (
        <div className="space-y-3">
            <section aria-label="Model status" className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-md border border-border/70 bg-card px-3 py-2"><div className="text-[11px] uppercase text-muted-foreground">Active model</div><div className="mt-0.5 font-mono text-sm font-semibold">{active ? `${active.version} (${active.algorithm})` : "None — deterministic + alias matching"}</div></div>
                <div className="rounded-md border border-border/70 bg-card px-3 py-2"><div className="text-[11px] uppercase text-muted-foreground">Holdout precision / recall</div><div className="mt-0.5 text-sm font-semibold tabular-nums">{active ? `${pct(active.metrics.holdout?.precision)} / ${pct(active.metrics.holdout?.recall)}` : "—"}</div></div>
                <div className="rounded-md border border-border/70 bg-card px-3 py-2"><div className="text-[11px] uppercase text-muted-foreground">False-merge rate</div><div className="mt-0.5 text-sm font-semibold tabular-nums">{active ? pct(active.metrics.holdout?.false_merge_rate) : "—"}</div></div>
                <div className="rounded-md border border-border/70 bg-card px-3 py-2"><div className="text-[11px] uppercase text-muted-foreground">Verified labels</div><div className="mt-0.5 text-sm font-semibold tabular-nums">{d.labels.verified} / {d.labels.required.total} ({d.labels.positive} match · {d.labels.negative} not)</div>
                    <div className="mt-1 h-1.5 rounded bg-muted" role="progressbar" aria-label="Labels collected towards first training" aria-valuenow={Math.round(labelShare)} aria-valuemin={0} aria-valuemax={100} aria-valuetext={`${d.labels.verified} of ${d.labels.required.total} verified labels`}><div className="h-1.5 rounded bg-primary" style={{ width: `${labelShare}%` }} /></div></div>
            </section>

            {d.can_manage && (
                <div className="flex flex-wrap items-center gap-2">
                    <Button size="sm" variant="outline" onClick={() => train.mutate(false)} disabled={train.isPending}><Database className="size-3.5" />Generate dataset</Button>
                    <Button size="sm" onClick={() => train.mutate(true)} disabled={train.isPending}>{train.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <ShieldCheck className="size-3.5" />}Generate dataset + train candidate</Button>
                    <Button size="sm" variant="ghost" onClick={() => rollback.mutate()} disabled={!active || rollback.isPending}><Undo2 className="size-3.5" />Roll back active model</Button>
                    <Button size="sm" variant="ghost" onClick={() => refresh()}><RotateCcw className="size-3.5" />Refresh</Button>
                    <span className="text-[11px] text-muted-foreground">{d.labels.new_since_last_dataset} new verified label(s) since the last dataset · training needs ≥{d.labels.required.total} with ≥{d.labels.required.per_class} per class</span>
                </div>
            )}

            <Card title="Models (candidate → evaluated on held-out human decisions → promoted explicitly)">
                <p className="mb-2 text-[11px] text-muted-foreground">Promotion gate: precision ≥ {pct(d.promotion_gate.precision)}, false merges ≤ {pct(d.promotion_gate.false_merge_rate)}, recall ≥ {pct(d.promotion_gate.recall)}, calibration error ≤ {pct(d.promotion_gate.ece)}, and no worse than the active model.</p>
                <div className="overflow-x-auto">
                    <table className="w-full [&_td]:px-2 [&_th]:px-2 [&_th]:font-medium min-w-[860px] text-xs" aria-label="Models">
                        <thead><tr className="text-left text-muted-foreground"><th className="py-1">Version</th><th>Status</th><th>Algorithm</th><th>Dataset</th><th className="text-right">Labels</th><th className="text-right">Precision</th><th className="text-right">Recall</th><th className="text-right">False merges</th><th className="text-right">ECE</th><th>Gate</th><th><span className="sr-only">Actions</span></th></tr></thead>
                        <tbody>{d.models.map((m) => (
                            <tr key={m.id} className="border-t border-border/40 align-top">
                                <td className="py-1 font-mono">{m.version}</td><td><StatusBadge tone={MODEL_TONE[m.status]} label={m.status.replace("_", " ")} /></td><td>{m.algorithm || "—"}</td><td className="font-mono">{m.dataset}</td>
                                <td className="text-right tabular-nums">{n(m.metrics.labels)}</td>
                                <td className="text-right tabular-nums">{pct(m.metrics.holdout?.precision)}</td><td className="text-right tabular-nums">{pct(m.metrics.holdout?.recall)}</td>
                                <td className="text-right tabular-nums">{pct(m.metrics.holdout?.false_merge_rate)}</td><td className="text-right tabular-nums">{pct(m.metrics.holdout?.ece)}</td>
                                <td className="max-w-[18rem]">{m.metrics.gate ? (m.metrics.gate.passed ? <span className="text-success">passed</span> : <span className="text-destructive">{(m.metrics.gate.failures ?? []).join("; ")}</span>) : <span className="text-muted-foreground">{m.notes || "—"}</span>}</td>
                                <td className="whitespace-nowrap text-right">{d.can_manage && m.status === "CANDIDATE" && <>
                                    <Button size="sm" disabled={!m.metrics.gate?.passed || modelAction.isPending} onClick={() => modelAction.mutate({ id: m.id, command: "promote" })}>Promote</Button>
                                    <Button size="sm" variant="ghost" disabled={modelAction.isPending} onClick={() => modelAction.mutate({ id: m.id, command: "reject" })}>Reject</Button></>}</td>
                            </tr>
                        ))}</tbody>
                    </table>
                    {!d.models.length && <p className="py-2 text-xs text-muted-foreground">No model trained yet.</p>}
                </div>
            </Card>

            <div className="grid gap-3 xl:grid-cols-2">
                <Card title="Historical product knowledge (inventory)">
                    <div className="overflow-x-auto">
                        <table className="w-full [&_td]:px-2 [&_th]:px-2 [&_th]:font-medium min-w-[620px] text-xs" aria-label="Inventory">
                            <thead><tr className="text-left text-muted-foreground"><th className="py-1">Source</th><th className="text-right">Records</th><th className="text-right">Unique</th><th className="text-right">Duplicates</th><th className="text-right">No description</th><th className="text-right">No HSN</th><th>Label trust</th></tr></thead>
                            <tbody>{d.inventory.map((r) => (
                                <tr key={r.source} className="border-t border-border/40 align-top">
                                    <td className="py-1 font-medium">{r.source.replace(/_/g, " ")}</td><td className="text-right tabular-nums">{n(r.records)}</td><td className="text-right tabular-nums">{n(r.unique_normalised)}</td>
                                    <td className="text-right tabular-nums">{n(r.duplicate_observations)}</td><td className="text-right tabular-nums">{n(r.missing_description)}</td><td className="text-right tabular-nums">{n(r.missing_hsn)}</td>
                                    <td className="text-muted-foreground">{r.trust}{r.labels && <div>{Object.entries(r.labels).map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join(" · ")}</div>}{r.master_links && <div>master links: {Object.entries(r.master_links).map(([k, v]) => `${k} ${v}`).join(" · ")}</div>}</td>
                                </tr>
                            ))}</tbody>
                        </table>
                    </div>
                </Card>
                <Aliases canManage={d.can_manage} />
            </div>

            <div className="grid gap-3 xl:grid-cols-2">
                <Card title="Datasets (versioned, financial fields excluded)">
                    <ul className="divide-y divide-border/50 text-xs">{d.datasets.map((ds) => <li key={ds.id} className="flex flex-wrap gap-x-3 py-1"><span className="font-mono">{ds.version}</span><span>{n(ds.observations)} observations · {n(ds.unique)} unique · {ds.labels} labels</span><span className="font-mono text-muted-foreground" title={ds.sha256}>sha {ds.sha256.slice(0, 10)}…</span></li>)}</ul>
                    {!d.datasets.length && <p className="text-xs text-muted-foreground">No dataset generated yet.</p>}
                </Card>
                <Card title="Audit trail">
                    <ul className="max-h-64 divide-y divide-border/50 overflow-auto text-xs">{d.events.map((e) => <li key={e.id} className="flex flex-wrap gap-x-3 py-1"><span className="font-medium">{e.action.replace(/_/g, " ")}</span><span className="text-muted-foreground">{e.user ?? "system"} · {new Date(e.on).toLocaleString("en-IN")}</span><span className="max-w-full truncate text-muted-foreground" title={JSON.stringify(e.detail)}>{JSON.stringify(e.detail)}</span></li>)}</ul>
                    {!d.events.length && <p className="text-xs text-muted-foreground">No administrative actions yet.</p>}
                </Card>
            </div>
        </div>
    );
}
