/**
 * Item Pivot — Licence Utilization & Planning Intelligence.
 *
 * Read-only views over `item-pivot/intelligence/` (same filters as the classic
 * pivot). Every figure is a backend Decimal string; this component never does
 * money arithmetic — it only formats values for display.
 */
import { Fragment, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, FileSpreadsheet, Loader2, Search, Sparkles, X } from "lucide-react";
import { toast } from "sonner";

import api from "@/api/axios";
import { Button } from "@/components/ui/button";
import { EmptyState, InlineError, LoadingState, StatusBadge, type Tone } from "@/components/shared";
import { DetailTabs } from "@/components/workspace";
import { cn } from "@/lib/utils";
import { openAuthedFile } from "@/utils/documentDownload";
import { EntitlementPlanningReport } from "@/pages/planning/EntitlementPlanningReport";
import BulkConsolidation from "./BulkConsolidation";
import MappingChanges from "./MappingChanges";
import ProductIntelligenceAdmin from "./ProductIntelligenceAdmin";
import ProductMatchingView from "./ProductMatchingView";

import { fmt, neg, NUM, STATUS, TD, TH, usd, type IntelCell, type IntelLicence, type IntelProduct, type IntelReport, type Integrity, type IntegrityField, type Recommendation, type Selection, type Status } from "./intelligenceShared";
import ProductAnalysisView from "./ProductAnalysisView";

export type { IntelCell, IntelLicence, IntelProduct, IntelReport } from "./intelligenceShared";

function Metric({ label, value, tone, hint }: { label: string; value: string; tone?: "blue" | "green" | "red" | "amber"; hint?: string }) {
    return (
        <div className="min-w-0 rounded-md border border-border/70 bg-card px-3 py-2" title={hint}>
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
            <div className={cn("mt-0.5 truncate text-base font-semibold tabular-nums", tone === "blue" && "text-primary", tone === "green" && "text-success", tone === "red" && "text-destructive", tone === "amber" && "text-amber-600")}>{value}</div>
        </div>
    );
}

function Waterfall({ o }: { o: IntelReport["overview"] }) {
    const steps: [string, string, string][] = [
        ["Original entitlement", String(o.original_cif), "bg-muted-foreground/40"],
        ["Actual BOE debits", `−${o.boe_cif}`, "bg-foreground/60"],
        ["Outstanding allotments", `−${o.allotment_cif}`, "bg-foreground/45"],
        ["Billed without BOE", `−${o.billed_cif}`, "bg-foreground/30"],
        ["Available CIF (actual)", String(o.available_cif), "bg-success"],
        ["Planned CIF (proposed)", `−${o.planned_cif}`, "bg-primary"],
        ["Final balance", String(o.final_balance_cif), neg(String(o.final_balance_cif)) ? "bg-destructive" : "bg-success/70"],
    ];
    const base = Math.max(Number(o.original_cif) || 0, 1);
    return (
        <section aria-label="Utilization waterfall" className="rounded-lg border border-border/70 bg-card p-3">
            <h3 className="mb-2 text-sm font-semibold">Original entitlement → actual utilization → planning → final balance</h3>
            <ol className="space-y-1.5">
                {steps.map(([label, value, color]) => (
                    <li key={label} className="grid grid-cols-[minmax(9rem,14rem)_minmax(0,1fr)_7.5rem] items-center gap-2 text-xs">
                        <span className="text-muted-foreground">{label}</span>
                        <span className="h-2.5 rounded-sm bg-muted"><span className={cn("block h-2.5 rounded-sm", color)} style={{ width: `${Math.min(100, (Math.abs(Number(value.replace("−", "-"))) / base) * 100)}%` }} /></span>
                        <span className={cn(NUM, "font-medium", label.startsWith("Planned") && "text-primary")}>{usd(value.replace("−", "-"))}</span>
                    </li>
                ))}
            </ol>
            <p className="mt-2 text-[11px] text-muted-foreground">Planned CIF is a proposal and is never counted as an actual debit.</p>
        </section>
    );
}

function OverviewView({ data }: { data: IntelReport }) {
    const o = data.overview;
    const c = o.consolidation;
    return (
        <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-6">
                <Metric label="Licences" value={fmt(String(o.licence_count), 0)} />
                <Metric label="Original CIF" value={usd(String(o.original_cif))} />
                <Metric label="Actual BOE CIF" value={usd(String(o.boe_cif))} />
                <Metric label="Outstanding allotment" value={usd(String(o.allotment_cif))} />
                <Metric label="Available CIF" value={usd(String(o.available_cif))} tone="green" />
                <Metric label="Planned CIF" value={usd(String(o.planned_cif))} tone="blue" />
                <Metric label="Final balance" value={usd(String(o.final_balance_cif))} tone={neg(String(o.final_balance_cif)) ? "red" : "green"} />
                <Metric label="Utilization" value={o.utilisation_percent ? `${o.utilisation_percent}%` : "—"} />
                <Metric label="Eligible products" value={fmt(String(o.eligible_product_count), 0)} tone="green" />
                <Metric label="Underutilized licences" value={fmt(String(o.underutilised_licence_count), 0)} tone="blue" />
                <Metric label="Planning warnings" value={fmt(String(o.warning_count), 0)} tone="amber" />
                <Metric label="Products needing attention" value={fmt(String(o.attention_product_count), 0)} tone="amber" />
            </div>
            <div className="grid gap-3 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
                <Waterfall o={o} />
                <section aria-label="Product consolidation audit" className="rounded-lg border border-border/70 bg-card p-3 text-sm">
                    <h3 className="mb-2 font-semibold">Product consolidation</h3>
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                        <dt className="text-muted-foreground">Master-item products</dt><dd className={NUM}>{c.mapped}</dd>
                        <dt className="text-muted-foreground">Source records merged</dt><dd className={NUM}>{c.merged_source_records}</dd>
                        <dt className="text-muted-foreground">Ambiguous (not merged)</dt><dd className={cn(NUM, c.ambiguous && "text-amber-600")}>{c.ambiguous}</dd>
                        <dt className="text-muted-foreground">Unmapped (kept separate)</dt><dd className={cn(NUM, c.unmapped && "text-amber-600")}>{c.unmapped}</dd>
                        <dt className="text-muted-foreground">Mixed-HSN reviews</dt><dd className={cn(NUM, c.mapping_review && "text-amber-600")}>{c.mapping_review}</dd>
                        <dt className="text-muted-foreground">Unreconciled licences</dt><dd className={cn(NUM, Number(o.unreconciled_licence_count) && "text-destructive")}>{String(o.unreconciled_licence_count ?? 0)}</dd>
                    </dl>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                        {(Object.keys(STATUS) as Status[]).map((s) => <StatusBadge key={s} tone={STATUS[s].tone} label={`${STATUS[s].label} ${o.status_counts[s] ?? 0}`} />)}
                    </div>
                    <p className="mt-3 text-[11px] text-muted-foreground"><strong>Licence figures:</strong> {o.bases.licence}<br /><strong>Product quantities:</strong> {o.bases.item}</p>
                </section>
            </div>
            {o.integrity && <IntegrityPanel integrity={o.integrity} />}
        </div>
    );
}

const INTEGRITY_ROWS: [IntegrityField, string, boolean][] = [
    ["entitlement_qty", "Total entitlement qty", false], ["allotted_qty", "Allotted qty", false], ["debited_qty", "Debited qty (BOE)", false],
    ["billed_qty", "Billed without BOE qty", false], ["balance_qty", "Available qty", false], ["planned_qty", "Planned qty", false], ["planned_cif", "Planned CIF", true],
];

/** Before (one row per source record) vs after (consolidated products): totals must match exactly. */
function IntegrityPanel({ integrity: g }: { integrity: Integrity }) {
    return (
        <section aria-label="Consolidation integrity" className="rounded-lg border border-border/70 bg-card p-3 text-sm">
            <div className="mb-2 flex flex-wrap items-center gap-2">
                <h3 className="font-semibold">Consolidation integrity — source records vs consolidated products</h3>
                <StatusBadge tone={g.preserved ? "success" : "danger"} label={g.preserved ? "Consolidation preserved every record and total" : "Totals differ — investigate"} />
            </div>
            <p className="mb-2 text-[11px] text-muted-foreground">Checks that grouping into products loses or duplicates nothing. The figures themselves come from the canonical engine and item-level records described above.</p>
            <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-xs" aria-label="Consolidation totals">
                    <thead><tr className="text-left text-muted-foreground"><th className="py-1 font-medium">Measure</th><th className="py-1 text-right font-medium">Source records</th><th className="py-1 text-right font-medium">Consolidated</th><th className="py-1 text-right font-medium">Difference</th></tr></thead>
                    <tbody>
                        <tr className="border-t border-border/40"><td className="py-1">Rows</td><td className={NUM}>{fmt(String(g.source_record_count), 0)}</td><td className={NUM}>{fmt(String(g.consolidated_product_count), 0)} products ({g.pending_mapping_count} pending mapping)</td><td className={cn(NUM, g.source_record_count !== g.consolidated_source_record_count && "text-destructive")}>{g.source_record_count === g.consolidated_source_record_count ? "all records kept" : `${g.source_record_count - g.consolidated_source_record_count} missing`}</td></tr>
                        {INTEGRITY_ROWS.map(([field, label, money]) => {
                            const same = g.source_totals[field] === g.consolidated_totals[field];
                            return <tr key={field} className="border-t border-border/40"><td className="py-1">{label}</td><td className={NUM}>{money ? usd(g.source_totals[field]) : fmt(g.source_totals[field], 3)}</td><td className={NUM}>{money ? usd(g.consolidated_totals[field]) : fmt(g.consolidated_totals[field], 3)}</td><td className={cn(NUM, same ? "text-success" : "text-destructive")}>{same ? "0" : "mismatch"}</td></tr>;
                        })}
                    </tbody>
                </table>
            </div>
        </section>
    );
}


function LicencesView({ data, selection, onSelect }: { data: IntelReport; selection: Selection; onSelect: (s: Partial<Selection>) => void }) {
    const [open, setOpen] = useState<number | null>(null);
    const [splitOpen, setSplitOpen] = useState<number | null>(null);
    const [onlyMatching, setOnlyMatching] = useState(false);
    const cellsByLicence = useMemo(() => {
        const map = new Map<number, IntelCell[]>();
        data.eligibility.forEach((c) => map.set(c.license_id, [...(map.get(c.license_id) ?? []), c]));
        return map;
    }, [data.eligibility]);
    const matchCell = (lic: IntelLicence) => {
        if (!selection.product) return null;
        const cell = cellsByLicence.get(lic.license_id)?.find((c) => c.product_key === selection.product) ?? null;
        if (!cell) return null;
        return selection.mode === "planning" ? (cell.planning_eligible ? cell : null) : cell;
    };
    const product = data.products.find((p) => p.key === selection.product);
    const rows = data.licences.filter((lic) => !onlyMatching || !selection.product || matchCell(lic));
    return (
        <div className="space-y-2">
            {product && (
                <div role="status" className="flex flex-wrap items-center gap-2 rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-sm">
                    <span>Highlighting licences for <strong>{product.product}</strong> ({product.sion})</span>
                    <div role="group" aria-label="Selection mode" className="inline-flex rounded-md border p-0.5">
                        <Button size="sm" variant={selection.mode === "entitlement" ? "default" : "ghost"} aria-pressed={selection.mode === "entitlement"} onClick={() => onSelect({ mode: "entitlement" })}>Entitlement</Button>
                        <Button size="sm" variant={selection.mode === "planning" ? "default" : "ghost"} aria-pressed={selection.mode === "planning"} onClick={() => onSelect({ mode: "planning" })}>Planning</Button>
                    </div>
                    <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={onlyMatching} onChange={(e) => setOnlyMatching(e.target.checked)} />Only matching</label>
                    <Button size="sm" variant="ghost" onClick={() => onSelect({ product: null })}><X className="size-3.5" />Clear</Button>
                </div>
            )}
            <ul aria-label="Licences" className="flex flex-col gap-1.5">
                {rows.map((lic) => {
                    const match = matchCell(lic);
                    const highlighted = !!match;
                    const muted = !!selection.product && !match;
                    const expanded = open === lic.license_id;
                    return (
                        <li key={lic.license_id}>
                            <article aria-label={`Licence ${lic.license_number}`} className={cn("overflow-hidden rounded-lg border bg-card", expanded ? "border-ring/40" : "border-border", highlighted && "border-primary/60 ring-1 ring-primary/30", muted && "opacity-45")}>
                                <div className={cn("flex cursor-pointer flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2", expanded && "bg-muted/40")} onClick={(e) => { if (!(e.target as HTMLElement).closest("button,a")) setOpen(expanded ? null : lic.license_id); }}>
                                    <button type="button" aria-expanded={expanded} aria-label={`${expanded ? "Collapse" : "Expand"} licence ${lic.license_number}`} onClick={() => setOpen(expanded ? null : lic.license_id)} className="rounded-md p-1 text-muted-foreground hover:bg-muted"><ChevronRight className={cn("size-4 transition-transform", expanded && "rotate-90")} /></button>
                                    <span className="font-mono text-base font-semibold">{lic.license_number}</span>
                                    <span className="text-xs text-muted-foreground">{lic.sion} · {lic.company ?? "—"} · Exp {lic.expiry_date ?? "—"}</span>
                                    {match && <span className="text-xs text-primary">{selection.mode === "planning" ? "Eligible for more planning" : "Entitlement includes product"}: {fmt(match.balance_qty, 3)} qty · max {match.max_unit_price ? usd(match.max_unit_price) : "—"}</span>}
                                    <div className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-1 text-right text-xs tabular-nums">
                                        {lic.planning_stale && <StatusBadge tone="warning" label="Re-planning" title="A mapping change is being applied — planned figures are provisional" />}
                                        {lic.is_over_utilised && <StatusBadge tone="danger" label="Over-utilised" />}
                                        {!lic.components_reconcile && <StatusBadge tone="warning" label="Reconcile" />}
                                        {([["Original", lic.original_cif, ""], ["BOE", lic.boe_cif, ""], ["Allotment", lic.allotment_cif, ""], ["Available", lic.available_cif, "text-success"], ["Planned", lic.planned_cif, "text-primary"], ["Final", lic.final_balance_cif, neg(lic.final_balance_cif) ? "text-destructive" : "text-success"]] as const).map(([label, value, tone]) => (
                                            <span key={label} className="flex min-w-[5.5rem] flex-col leading-tight"><span className="text-[10px] uppercase text-muted-foreground">{label}</span><span className={cn("text-sm font-semibold", tone)}>{usd(value)}</span></span>
                                        ))}
                                        <span className="flex min-w-[3.5rem] flex-col leading-tight"><span className="text-[10px] uppercase text-muted-foreground">Util.</span><span className="text-sm font-semibold">{lic.utilisation_percent ? `${lic.utilisation_percent}%` : "—"}</span></span>
                                    </div>
                                </div>
                                {expanded && (
                                    <div role="region" aria-label={`Licence ${lic.license_number} products`} className="border-t border-border px-3 pb-3 pt-2">
                                        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                                            <Button size="sm" variant="outline" onClick={() => onSelect({ licence: lic.license_id, product: null })}>Highlight this licence's products</Button>
                                            <Link className="text-primary hover:underline" to={`/licenses/${lic.license_id}/overview?tab=planning`}>Open licence planning</Link>
                                            {lic.sion && <Button size="sm" variant="ghost" aria-pressed={splitOpen === lic.license_id} onClick={() => setSplitOpen(splitOpen === lic.license_id ? null : lic.license_id)}>{splitOpen === lic.license_id ? "Hide" : "Show"} entitlement split</Button>}
                                            {Number(lic.other_adjustments_cif) !== 0 && <span className="text-muted-foreground">Opening / purchase-credit adjustments {usd(lic.other_adjustments_cif)}</span>}
                                        </div>
                                        {/* Per-entitlement balances (e.g. E126 PKO vs Olive + Sunflower) from the existing entitlement planner — never recomputed here. */}
                                        {splitOpen === lic.license_id && lic.sion && <div className="mb-2"><EntitlementPlanningReport licenseNumber={lic.license_number} sion={lic.sion.split(",")[0].trim()} /></div>}
                                        <CellTable cells={cellsByLicence.get(lic.license_id) ?? []} />
                                    </div>
                                )}
                            </article>
                        </li>
                    );
                })}
            </ul>
            {!rows.length && <EmptyState title="No matching licences" description="No licence matches the selected product in this mode." />}
        </div>
    );
}

function CellTable({ cells }: { cells: IntelCell[] }) {
    return (
        <div className="overflow-x-auto rounded-md border border-border/60">
            <table className="w-full min-w-[1080px] text-xs" aria-label="Licence products">
                <thead><tr><th className={TH}>Product</th><th className={`${TH} text-right`}>Entitlement</th><th className={`${TH} text-right`}>BOE debited</th><th className={`${TH} text-right`}>Allotted</th><th className={`${TH} text-right`}>Remaining</th><th className={`${TH} text-right`}>Max price</th><th className={`${TH} text-right`}>Planned qty</th><th className={`${TH} text-right`}>Planned CIF</th><th className={TH}>Status / reason</th><th className={TH}>Sources</th></tr></thead>
                <tbody>{cells.map((c) => (
                    <tr key={c.product_key} className="border-t border-border/40">
                        <td className={cn(TD, "font-medium")}>{c.product}</td>
                        <td className={cn(TD, NUM)}>{fmt(c.entitlement_qty, 3)}</td>
                        <td className={cn(TD, NUM)}>{fmt(c.debited_qty, 3)}</td>
                        <td className={cn(TD, NUM)}>{fmt(c.allotted_qty, 3)}</td>
                        <td className={cn(TD, NUM, neg(c.balance_qty) && "text-destructive")}>{fmt(c.balance_qty, 3)}</td>
                        <td className={cn(TD, NUM)}>{c.max_unit_price ? usd(c.max_unit_price) : "—"}</td>
                        <td className={cn(TD, NUM, "text-primary")}>{fmt(c.planned_qty, 3)}</td>
                        <td className={cn(TD, NUM, "text-primary")}>{usd(c.planned_cif)}</td>
                        <td className={TD}><StatusBadge tone={STATUS[c.status].tone} label={STATUS[c.status].label} />{c.reasons.map((r) => <div key={r} className="mt-0.5 text-[11px] text-muted-foreground">{r}</div>)}</td>
                        <td className={cn(TD, "max-w-[14rem] text-[11px] text-muted-foreground")}>{[...c.references.boes.map((b) => `BOE ${b}`), ...c.references.allotments].slice(0, 6).join(", ") || "—"}</td>
                    </tr>
                ))}</tbody>
            </table>
            <p className="px-2 py-1 text-[10px] text-muted-foreground">Quantities are item-level records; licence CIF above is the canonical balance.</p>
        </div>
    );
}

function PlanningView({ data, query }: { data: IntelReport; query: string }) {
    const candidates = useMemo(() => data.eligibility.filter((c) => c.planning_eligible), [data.eligibility]);
    const licenceIds = useMemo(() => [...new Set(candidates.map((c) => c.license_id))], [candidates]);
    const [selected, setSelected] = useState<number[]>([]);
    const [run, setRun] = useState<number[] | null>(null);
    const recs = useQuery({
        queryKey: ["item-pivot-recommendations", run],
        enabled: !!run?.length,
        queryFn: async ({ signal }) => (await api.get("item-pivot/recommendations/", { params: { license_ids: run!.join(",") }, signal })).data as { recommendations: Recommendation[]; errors: { license_id: number; error: string }[] },
    });
    const toggle = (id: number) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length >= 25 ? s : [...s, id]));
    const licence = (id: number) => data.licences.find((l) => l.license_id === id);
    return (
        <div className="space-y-3">
            <section aria-label="Additional planning capacity" className="rounded-lg border border-border/70 bg-card">
                <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 px-3 py-2">
                    <div><h3 className="text-sm font-semibold">Products eligible for additional debit</h3><p className="text-xs text-muted-foreground">{candidates.length} licence × product combinations with valid unplanned entitlement and licence CIF.</p></div>
                    <div className="flex items-center gap-2">
                        <Button size="sm" variant="outline" onClick={() => setSelected(licenceIds.slice(0, 25))} disabled={!licenceIds.length}>Select top 25 licences</Button>
                        <Button size="sm" onClick={() => setRun(selected)} disabled={!selected.length || recs.isFetching}>{recs.isFetching ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}Simulate recommendations ({selected.length})</Button>
                    </div>
                </header>
                <div className="max-h-[45vh] overflow-auto">
                    <table className="w-full min-w-[980px] text-xs" aria-label="Planning candidates">
                        <thead><tr><th className={TH}><span className="sr-only">Select</span></th><th className={TH}>Licence</th><th className={TH}>Product</th><th className={`${TH} text-right`}>Remaining qty</th><th className={`${TH} text-right`}>Max price</th><th className={`${TH} text-right`}>Existing planned</th><th className={`${TH} text-right`}>Licence available CIF</th><th className={`${TH} text-right`}>Unplanned CIF</th><th className={TH}>Why</th></tr></thead>
                        <tbody>{candidates.map((c) => (
                            <tr key={`${c.license_id}-${c.product_key}`} className={cn("border-t border-border/40", selected.includes(c.license_id) && "bg-primary/5")}>
                                <td className={TD}><input type="checkbox" aria-label={`Select licence ${c.license_number}`} checked={selected.includes(c.license_id)} onChange={() => toggle(c.license_id)} /></td>
                                <td className={cn(TD, "font-mono")}>{c.license_number}</td>
                                <td className={TD}>{c.product}</td>
                                <td className={cn(TD, NUM, "text-success")}>{fmt(c.balance_qty, 3)}</td>
                                <td className={cn(TD, NUM)}>{c.max_unit_price ? usd(c.max_unit_price) : "—"}</td>
                                <td className={cn(TD, NUM, "text-primary")}>{fmt(c.planned_qty, 3)}</td>
                                <td className={cn(TD, NUM)}>{usd(c.licence_available_cif)}</td>
                                <td className={cn(TD, NUM, "text-success")}>{usd(c.licence_final_balance_cif)}</td>
                                <td className={cn(TD, "text-[11px] text-muted-foreground")}>{c.reasons.join("; ")}</td>
                            </tr>
                        ))}</tbody>
                    </table>
                    {!candidates.length && <EmptyState title="No additional planning capacity" description="Every eligible entitlement is planned, exhausted or blocked." />}
                </div>
            </section>

            {run && (
                <section aria-label="Recommendations" className="rounded-lg border border-primary/30 bg-card">
                    <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 px-3 py-2">
                        <div><h3 className="text-sm font-semibold">Recommended plan (simulation — nothing saved)</h3><p className="text-xs text-muted-foreground">From the existing Auto Plan engine in read-only preview: SION rules, splits, caps and the licence CIF budget are enforced by the engine. Save through the licence's planning workflow.</p></div>
                        <Button size="sm" variant="outline" onClick={() => openAuthedFile(`item-pivot/recommendations/?license_ids=${run.join(",")}&format=excel`, "item_pivot_recommendations.xlsx").catch(() => toast.error("Export failed"))}><FileSpreadsheet className="size-4" />Excel</Button>
                    </header>
                    {recs.isPending ? <LoadingState variant="spinner" label="Simulating Auto Plan…" /> : recs.isError ? <InlineError error={recs.error as Error} title="Simulation failed" onRetry={() => void recs.refetch()} /> : (
                        <div className="overflow-x-auto">
                            {recs.data.errors.length > 0 && <p role="alert" className="px-3 py-2 text-xs text-destructive">{recs.data.errors.length} licence(s) could not be simulated: {recs.data.errors.map((e) => `${licence(e.license_id)?.license_number ?? e.license_id}: ${e.error}`).join("; ")}</p>}
                            <table className="w-full min-w-[1180px] text-xs" aria-label="Recommended plan">
                                <thead><tr><th className={TH}>#</th><th className={TH}>Licence</th><th className={TH}>Product</th><th className={`${TH} text-right`}>Unit price</th><th className={`${TH} text-right`}>Recommended qty</th><th className={`${TH} text-right`}>Recommended CIF</th><th className={`${TH} text-right`}>Existing CIF</th><th className={`${TH} text-right`}>Additional CIF</th><th className={`${TH} text-right`}>Licence CIF before → after</th><th className={TH}>Reason / alternatives</th><th className={TH}><span className="sr-only">Save</span></th></tr></thead>
                                <tbody>{recs.data.recommendations.map((r) => (
                                    <tr key={`${r.license_id}-${r.rank}`} className="border-t border-border/40">
                                        <td className={cn(TD, NUM)}>{r.rank}</td>
                                        <td className={cn(TD, "font-mono")}>{r.license_number}<div className="text-[10px] text-muted-foreground">Exp {r.expiry_date ?? "—"}</div></td>
                                        <td className={TD}>{r.product ?? "—"}<div className="text-[10px] text-muted-foreground">{r.sion} · rule {r.rule_priority ?? "—"}{r.cif_status ? ` · ${r.cif_status}` : ""}</div></td>
                                        <td className={cn(TD, NUM)}>{usd(r.unit_price)}</td>
                                        <td className={cn(TD, NUM, "text-primary")}>{fmt(r.recommended_qty, 3)}</td>
                                        <td className={cn(TD, NUM, "text-primary")}>{usd(r.recommended_cif)}</td>
                                        <td className={cn(TD, NUM)}>{usd(r.existing_cif)}</td>
                                        <td className={cn(TD, NUM, neg(r.additional_cif) ? "text-destructive" : "text-primary")}>{usd(r.additional_cif)}</td>
                                        <td className={cn(TD, NUM)}>{usd(r.licence_available_cif)} → <span className={neg(r.remaining_licence_cif_after) ? "text-destructive" : "text-success"}>{usd(r.remaining_licence_cif_after)}</span></td>
                                        <td className={cn(TD, "max-w-[18rem] text-[11px] text-muted-foreground")}>{r.reason}{r.alternatives.length ? ` · Alternatives: ${r.alternatives.join(", ")}` : ""}</td>
                                        <td className={TD}><Link className="whitespace-nowrap text-primary hover:underline" to={`/licenses/${r.license_id}/overview?tab=planning`}>Review &amp; save</Link></td>
                                    </tr>
                                ))}</tbody>
                            </table>
                            {!recs.data.recommendations.length && <EmptyState title="No recommendations" description="The planning engine proposes no lines for the selected licences." />}
                        </div>
                    )}
                </section>
            )}
            <p className="text-[11px] text-muted-foreground">Recommendations are ranked by licence expiry (use entitlement before it lapses), then SION rule priority. Filters: {decodeURIComponent(query)}</p>
        </div>
    );
}

export type IntelligenceQuery = string;

/** Part 15: never present planned figures as current while a mapping change is still re-planning (or failed). */
function PropagationBanner({ overview, onOpen }: { overview: IntelReport["overview"]; onOpen: () => void }) {
    const stale = Number(overview.planning_stale_licence_count ?? 0);
    const prop = (overview.mapping_propagation ?? { propagating: 0, failed: 0 }) as { propagating: number; failed: number };
    if (!stale && !prop.propagating && !prop.failed) return null;
    return (
        <div role="status" className={cn("flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm", prop.failed ? "border-destructive/40 bg-destructive/5" : "border-amber-500/40 bg-amber-500/10")}>
            <span>{prop.failed ? `${prop.failed} mapping change(s) failed to re-plan — the previous plans are still in place. ` : ""}
                {stale ? `${stale} licence(s) are being re-planned after a mapping change — their planned quantities and CIF are provisional.` : prop.propagating ? `${prop.propagating} mapping change(s) are re-planning.` : ""}</span>
            <Button size="sm" variant="outline" onClick={onOpen}>View mapping changes</Button>
        </div>
    );
}

/** Four views over one report payload; selection highlights flow between Products and Licences. */
export default function ItemPivotIntelligence({ query }: { query: IntelligenceQuery }) {
    const [tab, setTab] = useState("overview");
    const [selection, setSelectionState] = useState<Selection>({ product: null, licence: null, mode: "entitlement" });
    const [exporting, setExporting] = useState(false);
    const report = useQuery({
        queryKey: ["item-pivot-intelligence", query],
        queryFn: async ({ signal }) => (await api.get(`item-pivot/intelligence/?${query}`, { signal })).data as IntelReport,
        staleTime: 60_000,
    });
    const setSelection = (next: Partial<Selection>) => {
        setSelectionState((s) => ({ ...s, ...next }));
        if (next.product) setTab("licences");
        if (next.licence != null) setTab("products");
    };
    if (report.isPending) return <LoadingState variant="spinner" label="Building utilization intelligence…" />;
    if (report.isError) return <InlineError error={report.error as Error} title="Could not load the intelligence report" onRetry={() => void report.refetch()} />;
    const data = report.data;
    if (!data.licences.length) return <EmptyState title="No licences match" description="Adjust the norm or filters." />;
    return (
        <div className="space-y-2">
            <PropagationBanner overview={data.overview} onOpen={() => setTab("mapping-changes")} />
            <div className="flex flex-wrap items-center justify-end gap-2">
                <Button size="sm" variant="outline" disabled={exporting} onClick={async () => {
                    setExporting(true);
                    try { await openAuthedFile(`item-pivot/intelligence/?${query}&format=excel`, "item_pivot_intelligence.xlsx"); } catch { toast.error("Export failed"); } finally { setExporting(false); }
                }}>{exporting ? <Loader2 className="size-4 animate-spin" /> : <FileSpreadsheet className="size-4" />}Excel (products, licences, eligibility, exceptions)</Button>
            </div>
            <DetailTabs
                recordKey="item-pivot-intelligence"
                value={tab}
                onValueChange={setTab}
                ariaLabel="Item pivot views"
                className="min-w-0 [&_[role=tablist]]:flex-nowrap [&_[role=tablist]]:overflow-x-auto [&_[role=tab]]:shrink-0"
                tabs={[
                    { id: "overview", label: "Overview", render: () => <OverviewView data={data} /> },
                    { id: "products", label: `Product Analysis (${data.products.length})`, render: () => <ProductAnalysisView data={data} query={query} selection={selection} onSelect={setSelection} /> },
                    { id: "licences", label: `Licence Analysis (${data.licences.length})`, render: () => <LicencesView data={data} selection={selection} onSelect={setSelection} /> },
                    { id: "planning", label: "Planning & Optimization", render: () => <PlanningView data={data} query={query} /> },
                    { id: "matching", label: `Product Matching (${data.overview.consolidation.unmapped + data.overview.consolidation.ambiguous})`, render: () => <ProductMatchingView query={query} /> },
                    { id: "mapping-changes", label: "Mapping changes", render: () => <MappingChanges /> },
                    { id: "bulk-consolidation", label: "Bulk consolidation", render: () => <BulkConsolidation defaultSion={new URLSearchParams(query).get("sion_norm") ?? ""} /> },
                    { id: "intelligence-admin", label: "Intelligence admin", render: () => <ProductIntelligenceAdmin /> },
                ]}
            />
        </div>
    );
}
