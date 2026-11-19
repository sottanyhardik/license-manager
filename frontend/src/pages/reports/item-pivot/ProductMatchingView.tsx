/**
 * Product matching review (Item Pivot). Suggestions come from the deterministic
 * matcher plus persisted local-MiniLM semantic candidates; approvals are
 * separate audited decisions (LICENSE_MANAGER) that link import items to the
 * chosen master item. Nothing here changes HSN, SION rules or financial data.
 */
import { Fragment, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronRight, Loader2, Pause, Play, Search, X } from "lucide-react";
import { toast } from "sonner";

import api from "@/api/axios";
import { Button } from "@/components/ui/button";
import { EmptyState, InlineError, LoadingState, StatusBadge, type Tone } from "@/components/shared";
import { cn } from "@/lib/utils";

import MultiProductSelection from "./MultiProductSelection";
import { BAND, errorText, matchingQuery, ORDER, segmentSignature, type Band, type Health, type MatchCheck, type MatchSuggestion } from "./matchingShared";

export type { MatchSuggestion } from "./matchingShared";

function Checks({ checks }: { checks: MatchSuggestion["checks"] }) {
    const rows = Object.entries(checks ?? {}) as [string, MatchCheck][];
    if (!rows.length) return null;
    return (
        <ul className="space-y-0.5 text-xs" aria-label="Compatibility checks">
            {rows.map(([key, c]) => <li key={key} className={cn(c.ok ? "text-success" : "text-destructive")}>{c.ok ? "✓" : "✗"} <span className="font-medium uppercase">{key.replace("_", " ")}</span>: <span className="text-muted-foreground">{c.detail}</span></li>)}
        </ul>
    );
}

export default function ProductMatchingView({ query }: { query: string }) {
    const qc = useQueryClient();
    const [band, setBand] = useState<Band | "ALL">("ALL");
    const [q, setQ] = useState("");
    const [open, setOpen] = useState<string | null>(null);
    const [picked, setPicked] = useState<Record<string, number>>({});
    const [selected, setSelected] = useState<string[]>([]);
    const [history, setHistory] = useState<"ALL" | "APPROVED" | "REJECTED" | "DIFFERENT">("ALL");
    const filters = useMemo(() => Object.fromEntries(new URLSearchParams(query)), [query]);
    const matching = useQuery({
        ...matchingQuery(query),
        refetchInterval: (state) => (["QUEUED", "RUNNING"].includes(state.state.data?.latest_job?.status ?? "") ? 5000 : false),
    });
    const health = useQuery({ queryKey: ["item-pivot-matching-health"], queryFn: async () => (await api.get("item-pivot/matching/health/")).data as Health, staleTime: 30_000 });
    const refresh = () => { void qc.invalidateQueries({ queryKey: ["item-pivot-matching"] }); void qc.invalidateQueries({ queryKey: ["item-pivot-intelligence"] }); };
    const decide = useMutation({
        mutationFn: (body: { source_keys: string[]; decision: string; item_id?: number; replace_links?: boolean }) => api.post("item-pivot/matching/decide/", { ...body, filters }),
        onSuccess: (r, body) => {
            toast.success(`${body.decision.toLowerCase()} — ${body.source_keys.length} record group(s)`);
            const skipped = (r?.data as { alias_skipped?: { reason: string }[] } | undefined)?.alias_skipped ?? [];
            if (skipped.length) toast.warning(`Approved, but no alias was recorded: ${skipped[0].reason}`);
            setSelected([]); refresh();
        },
        onError: (err: unknown) => toast.error(errorText(err, "Decision failed")),
    });
    const alias = useMutation({
        mutationFn: (body: { text: string; item_id: number; sion: string | null }) => api.post("item-pivot/matching/aliases/", body),
        onSuccess: () => { toast.success("Alias saved — identical wording will be suggested at 100% (approval still required)"); refresh(); },
        onError: (err: unknown) => toast.error(errorText(err, "Alias not saved")),
    });
    const job = useMutation({
        mutationFn: (action: "start" | "pause" | "resume") => action === "start"
            ? api.post("item-pivot/matching/jobs/", { filters, batch_size: 4 })
            : api.post(`item-pivot/matching/jobs/${matching.data?.latest_job?.id}/${action}/`),
        onSuccess: () => refresh(),
        onError: (err: unknown) => toast.error(errorText(err, "Job request failed")),
    });

    if (matching.isPending) return <LoadingState variant="spinner" label="Loading product matching…" />;
    if (matching.isError) return <InlineError error={matching.error as Error} title="Could not load product matching" onRetry={() => void matching.refetch()} />;
    const data = matching.data;
    const rows = data.suggestions.filter((s) => (band === "ALL" || s.band === band)
        && (!q || `${s.description} ${s.hsn_code} ${s.suggestion?.name ?? ""}`.toLowerCase().includes(q.toLowerCase())));
    const visibleKeys = new Set(rows.map((r) => r.source_key));
    const visibleSelected = selected.filter((k) => visibleKeys.has(k)); // never bulk-approve rows hidden by a filter
    const latest = data.latest_job;
    const busy = latest && ["QUEUED", "RUNNING"].includes(latest.status);

    return (
        <div className="space-y-3">
            <section aria-label="Classification engine" className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-border/70 bg-card px-3 py-2 text-xs">
                <span className="font-semibold">Engine</span>
                <StatusBadge tone={health.data?.model.ok ? "success" : "warning"} label={health.data?.model.ok ? `Model ${health.data.model.variant}` : "Model not installed"} title={health.data?.model.version ?? health.data?.model.error} />
                <StatusBadge tone={health.data?.worker.ok ? "success" : "warning"} label={health.data?.worker.ok ? "Matching worker online" : "No matching worker"} />
                {health.data?.available_memory_mb != null && <span className="text-muted-foreground">RAM available {Math.round(health.data.available_memory_mb)} MB</span>}
                {latest && <span className="text-muted-foreground">Job #{latest.id}: {latest.status} · {latest.processed}/{latest.total}{latest.metrics?.paused_reason ? ` · ${String(latest.metrics.paused_reason)}` : ""}{latest.error ? ` · ${latest.error}` : ""}</span>}
                {data.can_approve && <div className="ml-auto flex gap-1.5">
                    {busy ? <Button size="sm" variant="outline" onClick={() => job.mutate("pause")} disabled={job.isPending}><Pause className="size-3.5" />Pause</Button>
                        : latest && ["PAUSED", "FAILED"].includes(latest.status) ? <Button size="sm" variant="outline" onClick={() => job.mutate("resume")} disabled={job.isPending}><Play className="size-3.5" />Resume</Button> : null}
                    <Button size="sm" onClick={() => job.mutate("start")} disabled={!!busy || job.isPending}>{job.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}Run semantic classification</Button>
                </div>}
            </section>

            <div className="flex flex-wrap items-center gap-2">
                <div role="group" aria-label="Band filter" className="flex flex-wrap gap-1">
                    <Button size="sm" variant={band === "ALL" ? "default" : "ghost"} onClick={() => { setBand("ALL"); setSelected([]); }}>All {data.suggestions.length}</Button>
                    {ORDER.filter((b) => data.summary[b]).map((b) => <Button key={b} size="sm" variant={band === b ? "default" : "ghost"} onClick={() => { setBand(b); setSelected([]); }}>{BAND[b].label} {data.summary[b]}</Button>)}
                </div>
                <div className="relative ml-auto w-full sm:w-64"><Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" aria-hidden="true" /><input aria-label="Search matches" value={q} onChange={(e) => { setQ(e.target.value); setSelected([]); }} placeholder="Description, HSN or product…" className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-2 text-sm" /></div>
                {data.can_approve && <Button size="sm" disabled={!visibleSelected.length || decide.isPending} onClick={() => decide.mutate({ source_keys: visibleSelected, decision: "APPROVED" })}><Check className="size-3.5" />Approve selected ({visibleSelected.length})</Button>}
            </div>

            <div className="max-h-[70vh] overflow-auto rounded-lg border border-border/70">
                <table className="w-full min-w-[1100px] text-sm" aria-label="Product matches">
                    <thead><tr className="sticky top-0 z-[1] bg-muted text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                        <th className="px-2 py-2"><span className="sr-only">Select</span></th><th className="px-2 py-2">Original description</th><th className="px-2 py-2">HSN</th><th className="px-2 py-2">Suggested product</th>
                        <th className="px-2 py-2">SION</th><th className="px-2 py-2">Entitlement</th><th className="px-2 py-2 text-right" title="Deterministic text / alias score (a trained model probability is shown separately when a model is active)">Match score</th><th className="px-2 py-2">Status</th></tr></thead>
                    <tbody>{rows.map((s) => {
                        const expanded = open === s.source_key;
                        const options = [...s.candidates, ...(s.semantic?.candidates ?? [])].filter((c, i, all) => all.findIndex((x) => x.item_id === c.item_id) === i);
                        const choice = picked[s.source_key] ?? s.suggestion?.item_id;
                        return (
                            <Fragment key={s.source_key}>
                                <tr className={cn("border-t border-border/50", expanded && "bg-muted/30")}>
                                    <td className="px-2 py-1.5 align-top">{data.can_approve && s.band === "HIGH" && <input type="checkbox" aria-label={`Select ${s.description}`} checked={selected.includes(s.source_key)} onChange={() => setSelected((sel) => sel.includes(s.source_key) ? sel.filter((k) => k !== s.source_key) : [...sel, s.source_key])} />}</td>
                                    <td className="max-w-[26rem] px-2 py-1.5 align-top">
                                        <button type="button" aria-expanded={expanded} onClick={() => setOpen(expanded ? null : s.source_key)} className="flex items-start gap-1 text-left">
                                            <ChevronRight className={cn("mt-0.5 size-3.5 shrink-0 transition-transform", expanded && "rotate-90")} aria-hidden="true" />
                                            <span className="line-clamp-2" title={s.description}>{s.description}</span>
                                        </button>
                                        <div className="ml-5 text-[11px] text-muted-foreground">{s.import_item_ids.length} source record{s.import_item_ids.length === 1 ? "" : "s"} · {s.license_numbers.slice(0, 3).join(", ")}{s.license_numbers.length > 3 ? "…" : ""}</div>
                                    </td>
                                    <td className="px-2 py-1.5 align-top font-mono text-xs">{s.hsn_code || "—"}</td>
                                    <td className="px-2 py-1.5 align-top font-medium">{s.suggestion?.name ?? "—"}{s.matcher && s.matcher !== "deterministic-v1" && <div className="text-[10px] font-normal text-muted-foreground">via {s.matcher.startsWith("sentence") ? "semantic MiniLM" : s.matcher}</div>}</td>
                                    <td className="px-2 py-1.5 align-top">{s.sion ?? "—"}</td>
                                    <td className="max-w-[14rem] px-2 py-1.5 align-top text-xs text-muted-foreground">{s.checks.entitlement?.detail ?? "—"}</td>
                                    <td className="px-2 py-1.5 text-right align-top tabular-nums">{s.suggestion ? `${s.confidence}%` : "—"}{s.semantic?.similarity != null && <div className="text-[10px] text-muted-foreground">sim {s.semantic.similarity.toFixed(2)}</div>}</td>
                                    <td className="px-2 py-1.5 align-top"><StatusBadge tone={BAND[s.band].tone} label={BAND[s.band].label} /></td>
                                </tr>
                                {expanded && (
                                    <tr className="bg-muted/20"><td colSpan={8} className="px-4 py-3">
                                        {s.segments && s.segments.length > 1 && (
                                            <div className="mb-3"><MultiProductSelection key={segmentSignature(s)} suggestion={s} filters={filters} canApprove={data.can_approve} /></div>
                                        )}
                                        <div className="grid gap-3 lg:grid-cols-2">
                                            <div className="space-y-2 text-sm">
                                                <p className="whitespace-pre-wrap break-words"><span className="text-xs font-semibold uppercase text-muted-foreground">Full description</span><br />{s.description}</p>
                                                {s.aliases.length > 1 && <p className="text-xs text-muted-foreground">Other source wording: {s.aliases.slice(1, 6).join(" · ")}</p>}
                                                <p className="text-xs"><span className="font-semibold">Explanation:</span> {s.explanation}</p>
                                                {s.alias_match && <p className="text-xs text-success">Matched an approved alias (human-curated).</p>}
                                                {s.model && <p className="text-xs"><span className="font-semibold">Model {s.model.version}</span> ({s.model.algorithm}) probability {(s.model.probability * 100).toFixed(1)}% · strongest evidence: {s.model.top_features.map(([f, v]) => `${f.replace(/_/g, " ")} ${v > 0 ? "+" : ""}${v.toFixed(2)}`).join(", ")}</p>}
                                                {s.conflicts.length > 0 && <ul role="alert" className="list-disc pl-4 text-xs text-destructive">{s.conflicts.map((c) => <li key={c}>{c}</li>)}</ul>}
                                                <Checks checks={s.checks} />
                                            </div>
                                            <div className="space-y-2 text-xs">
                                                <p className="font-semibold uppercase text-muted-foreground">Candidates</p>
                                                <ul className="space-y-1">{options.map((c) => <li key={c.item_id}><label className="flex items-center gap-2"><input type="radio" name={`pick-${s.source_key}`} checked={choice === c.item_id} onChange={() => setPicked((p) => ({ ...p, [s.source_key]: c.item_id }))} disabled={!data.can_approve} />{c.name}<span className="text-muted-foreground">{c.score != null ? `text ${c.score}%` : ""}{c.similarity != null ? ` semantic ${c.similarity.toFixed(2)}` : ""}</span></label></li>)}</ul>
                                                {data.can_approve && (s.ai_candidates ?? []).some((c) => !options.some((o) => o.item_id === c.item_id)) && (
                                                    <label className="flex flex-wrap items-center gap-2">Another {s.sion} product
                                                        <select aria-label={`Another canonical product for ${s.description}`} className="h-7 rounded-md border border-input bg-background px-1.5 text-xs" value={options.some((o) => o.item_id === choice) ? "" : String(choice ?? "")} onChange={(e) => e.target.value && setPicked((p) => ({ ...p, [s.source_key]: Number(e.target.value) }))}>
                                                            <option value="">Choose…</option>
                                                            {(s.ai_candidates ?? []).filter((c) => !options.some((o) => o.item_id === c.item_id)).map((c) => <option key={c.item_id} value={c.item_id}>{c.name}</option>)}
                                                        </select>
                                                        <span className="text-muted-foreground">re-validated on the server (SION, HSN, entitlement)</span>
                                                    </label>
                                                )}
                                                {s.history.length > 0 && <p className="text-muted-foreground">History: {s.history.map((h) => `${h.decision} ${h.item ?? ""} by ${h.by ?? "—"}`).join("; ")}</p>}
                                                {data.can_approve && s.band !== "APPROVED" && <div className="flex flex-wrap gap-1.5 pt-1">
                                                    {!(s.segments && s.segments.length > 1) && <Button size="sm" disabled={!choice || decide.isPending} onClick={() => {
                                                        // Ambiguous records already link several masters: replacing those links needs explicit confirmation.
                                                        if (s.kind === "AMBIGUOUS" && !window.confirm(`These records already link several master items (${s.description}). Replace those links with the chosen product? The previous links are kept in the audit.`)) return;
                                                        decide.mutate({ source_keys: [s.source_key], decision: "APPROVED", item_id: choice, ...(s.kind === "AMBIGUOUS" ? { replace_links: true } : {}) });
                                                    }}><Check className="size-3.5" />Approve{picked[s.source_key] && picked[s.source_key] !== s.suggestion?.item_id ? " selected product" : ""}</Button>}
                                                    <Button size="sm" variant="outline" disabled={decide.isPending || !s.suggestion} onClick={() => decide.mutate({ source_keys: [s.source_key], decision: "REJECTED" })}><X className="size-3.5" />Reject suggestion</Button>
                                                    <Button size="sm" variant="ghost" disabled={decide.isPending} onClick={() => decide.mutate({ source_keys: [s.source_key], decision: "DIFFERENT" })}>Mark distinct product</Button>
                                                    <Button size="sm" variant="ghost" disabled={!choice || alias.isPending || s.conflicts.length > 0} title={s.conflicts.length ? "Resolve conflicts first" : undefined} onClick={() => choice && alias.mutate({ text: s.description, item_id: choice, sion: s.sion })}>Save wording as alias</Button>
                                                </div>}
                                            </div>
                                        </div>
                                    </td></tr>
                                )}
                            </Fragment>
                        );
                    })}</tbody>
                </table>
                {!rows.length && <EmptyState title="Nothing to review" description="No unmapped or ambiguous products match this filter." />}
            </div>

            {data.decisions.length > 0 && (
                <section aria-label="Decision history" className="rounded-lg border border-border/70 bg-card">
                    <div className="flex flex-wrap items-center gap-2 border-b border-border/60 px-3 py-2">
                        <h3 className="text-sm font-semibold">Decision history (audited)</h3>
                        <div role="group" aria-label="Decision filter" className="ml-auto flex flex-wrap gap-1">
                            {(["ALL", "APPROVED", "REJECTED", "DIFFERENT"] as const).map((h) => <Button key={h} size="sm" variant={history === h ? "default" : "ghost"} aria-pressed={history === h} onClick={() => setHistory(h)}>{h === "ALL" ? "All" : h === "APPROVED" ? "Approved mappings" : h === "REJECTED" ? "Rejected suggestions" : "Distinct products"} {h === "ALL" ? data.decisions.length : data.decisions.filter((d) => d.decision === h).length}</Button>)}
                        </div>
                    </div>
                    <ul className="divide-y divide-border/50 text-xs">{data.decisions.filter((d) => history === "ALL" || d.decision === history).slice(0, 50).map((d) => <li key={d.id} className="flex flex-wrap gap-x-3 px-3 py-1.5"><StatusBadge tone={d.decision === "APPROVED" ? "success" : "neutral"} label={d.decision} /><span className="max-w-[28rem] truncate" title={d.source_description}>{d.source_description}</span><span>→ {d.chosen_item ?? d.suggested_item ?? "—"}</span><span className="text-muted-foreground">{d.sion} · HSN {d.hsn_code || "—"} · {d.confidence}% · {d.decided_by} · {new Date(d.decided_on).toLocaleString("en-IN")}</span></li>)}</ul>
                </section>
            )}
        </div>
    );
}
