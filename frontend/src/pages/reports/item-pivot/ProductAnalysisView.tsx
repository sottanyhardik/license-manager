/**
 * Item Pivot — Product Analysis: one consolidated row per canonical product
 * (master item × SION). Expanding a row shows the entitlement summary, the
 * licences whose own entitlement lists the product (never "historically
 * imported"), an on-demand Auto Plan recommendation per licence (read-only
 * preview from the planning engine), and every original source record with its
 * matching decision. Display only — every figure is a backend Decimal string.
 */
import { Fragment, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ChevronRight, Filter, Loader2, Search, Sparkles, X } from "lucide-react";

import api from "@/api/axios";
import { Button } from "@/components/ui/button";
import { EmptyState, StatusBadge } from "@/components/shared";
import { cn } from "@/lib/utils";
import { fmt, neg, NUM, STATUS, TD, TH, usd, type IntelCell, type IntelProduct, type IntelReport, type Recommendation, type Selection, type Status } from "./intelligenceShared";
import { BAND, matchingQuery, type MatchSuggestion } from "./matchingShared";

type SortKey = "default" | "product" | "balance_qty" | "planned_cif" | "utilisation_percent";
const SORTS: [SortKey, string][] = [["default", "Mapped first"], ["product", "Product"], ["balance_qty", "Available qty"], ["planned_cif", "Planned CIF"], ["utilisation_percent", "Utilization"]];
const num = (v: string | null | undefined): number | null => (v == null || v === "" ? null : Number(v));
/** Null-safe numeric comparison for display sorting; empty values always sort last. */
const compareNullable = (a: number | null, b: number | null, dir: 1 | -1) => {
    if (a == null || b == null) return a == null && b == null ? 0 : a == null ? 1 : -1;
    return (a < b ? -1 : a > b ? 1 : 0) * dir;
};

function SortHeader({ k, label, sort, onSort }: { k: SortKey; label: string; sort: { key: SortKey; dir: 1 | -1 }; onSort: (k: SortKey) => void }) {
    const active = sort.key === k;
    return (
        <th className={`${TH} text-right`} aria-sort={active ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
            <button type="button" onClick={() => onSort(k)} className="inline-flex items-center gap-0.5 uppercase hover:text-foreground">
                {label}{active && (sort.dir === 1 ? <ArrowUp className="size-3" aria-hidden="true" /> : <ArrowDown className="size-3" aria-hidden="true" />)}
            </button>
        </th>
    );
}

function eligibilityReason(cell: IntelCell, p: IntelProduct): string {
    const base = `Licence entitlement lists ${p.product} under ${cell.sion ?? p.sion ?? "its SION"}`;
    if (cell.status === "UNDERUTILIZED") return `${base}; ${fmt(cell.balance_qty, 3)} qty unplanned and licence CIF available — eligible for more planning`;
    if (cell.status === "CORRECT") return `${base}; fully planned within entitlement`;
    return [base, ...cell.reasons].join("; ");
}

function ProductDetail({ p, cells, match }: { p: IntelProduct; cells: IntelCell[]; match: MatchSuggestion | undefined }) {
    const [recRun, setRecRun] = useState(false);
    const licenceIds = useMemo(() => [...new Set(cells.map((c) => c.license_id))].slice(0, 25), [cells]);
    const recs = useQuery({
        queryKey: ["item-pivot-recommendations", licenceIds],
        enabled: recRun && licenceIds.length > 0 && p.item_name_id != null,
        queryFn: async ({ signal }) => (await api.get("item-pivot/recommendations/", { params: { license_ids: licenceIds.join(",") }, signal })).data as { recommendations: Recommendation[]; errors: { license_id: number; error: string }[] },
        staleTime: 60_000,
    });
    const recFor = (licenceId: number) => recs.data?.recommendations.filter((r) => r.license_id === licenceId && (r.item_name_id != null ? r.item_name_id === p.item_name_id : r.product?.toUpperCase() === p.product.toUpperCase()));
    const summary: [string, string, string?][] = [
        ["Canonical product", p.product], ["SION", p.sion ?? "—"], ["HSN codes", p.hsn_codes.join(", ") || "—"],
        ["Max unit price", p.max_unit_price ? usd(p.max_unit_price) : "No active planning rule"],
        ["Total entitlement qty", fmt(p.entitlement_qty, 3)],
        ["Actual utilized qty", `${fmt(p.debited_qty, 3)} BOE · ${fmt(p.allotted_qty, 3)} allotted · ${fmt(p.billed_qty, 3)} billed`],
        ["Available qty", fmt(p.balance_qty, 3), neg(p.balance_qty) ? "text-destructive" : "text-success"],
        ["Planned qty / CIF", `${fmt(p.planned_qty, 3)} · ${usd(p.planned_cif)}`, "text-primary"],
        ["Licence CIF available → after plans", `${usd(p.licences_available_cif)} → ${usd(p.licences_remaining_cif)}`],
    ];
    return (
        <div className="space-y-3">
            <section aria-label={`Entitlement summary of ${p.product}`}>
                <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">A. Entitlement summary</h4>
                <dl className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2 xl:grid-cols-3">
                    {summary.map(([k, v, tone]) => <div key={k} className="flex justify-between gap-2 border-b border-border/30 py-0.5"><dt className="text-muted-foreground">{k}</dt><dd className={cn("text-right tabular-nums", tone)}>{v}</dd></div>)}
                </dl>
                <p className="mt-1 text-xs text-muted-foreground"><span className="font-medium text-foreground">Approved aliases / source wording:</span> {p.aliases.join(" · ") || "—"}</p>
                <p className="text-[11px] text-muted-foreground">{p.mapping_basis}. Licence CIF is shared with each licence's other products and is not additive across product rows.</p>
            </section>

            <section aria-label={`Eligible licences for ${p.product}`}>
                <div className="mb-1 flex flex-wrap items-center gap-2">
                    <h4 className="text-xs font-semibold uppercase text-muted-foreground">{p.kind === "MAPPED" ? `B. Eligible licences (${cells.length})` : `B. Licences listing these records (${cells.length}) — not plannable until mapped`}</h4>
                    {p.kind === "MAPPED" && <Button size="sm" variant="outline" onClick={() => setRecRun(true)} disabled={recs.isFetching || !cells.length}>{recs.isFetching ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}Compute recommended plan</Button>}
                    {cells.length > 25 && recRun && <span className="text-[11px] text-muted-foreground">Recommendations computed for the first 25 licences.</span>}
                    <span className="text-[11px] text-muted-foreground">Recommendations are a rolled-back Auto Plan preview — save them in licence planning.</span>
                </div>
                <div className="overflow-x-auto rounded-md border border-border/60">
                    <table className="w-full min-w-[1040px] text-xs" aria-label={`Licences for ${p.product}`}>
                        <thead><tr className="bg-muted/60 text-left text-[11px] uppercase text-muted-foreground"><th className="px-2 py-1">Licence</th><th className="px-2 py-1">Company</th><th className="px-2 py-1 text-right">Available qty</th><th className="px-2 py-1 text-right">Available CIF</th><th className="px-2 py-1 text-right">Max unit price</th><th className="px-2 py-1 text-right">Existing plan</th><th className="px-2 py-1 text-right">Recommended plan</th><th className="px-2 py-1">Status / why eligible</th></tr></thead>
                        <tbody>{cells.map((c) => {
                            const rec = recFor(c.license_id);
                            return (
                                <tr key={c.license_id} className={cn("border-t border-border/40", c.status === "UNDERUTILIZED" && "bg-primary/5")}>
                                    <td className="px-2 py-1 font-mono"><Link className="text-primary hover:underline" to={`/licenses/${c.license_id}/overview?tab=planning`}>{c.license_number}</Link></td>
                                    <td className="px-2 py-1">{c.company ?? "—"}</td>
                                    <td className={cn("px-2 py-1", NUM, neg(c.balance_qty) && "text-destructive")}>{fmt(c.balance_qty, 3)}</td>
                                    <td className={cn("px-2 py-1", NUM, neg(c.licence_available_cif) && "text-destructive")}>{usd(c.licence_available_cif)}</td>
                                    <td className={cn("px-2 py-1", NUM)}>{c.max_unit_price ? usd(c.max_unit_price) : "—"}</td>
                                    <td className={cn("px-2 py-1", NUM, "text-primary")}>{fmt(c.planned_qty, 3)} · {usd(c.planned_cif)}</td>
                                    <td className={cn("px-2 py-1", NUM)}>{!recRun ? "—" : recs.isFetching ? "…" : recs.isError ? <span className="text-destructive">failed</span> : rec?.length ? rec.map((r) => <div key={`${r.rank}-${r.unit_price}`}>{fmt(r.recommended_qty, 3)} · {usd(r.recommended_cif)}{Number(r.additional_cif) !== 0 && <span className="text-muted-foreground"> (+{usd(r.additional_cif)})</span>}</div>) : <span className="text-muted-foreground">none</span>}</td>
                                    <td className="px-2 py-1"><StatusBadge tone={STATUS[c.status].tone} label={STATUS[c.status].label} /><div className="mt-0.5 text-[11px] text-muted-foreground">{eligibilityReason(c, p)}</div></td>
                                </tr>
                            );
                        })}</tbody>
                    </table>
                </div>
                {recs.isError && <p role="alert" className="mt-1 text-[11px] text-destructive">Recommendations could not be computed — <button type="button" className="underline" onClick={() => void recs.refetch()}>retry</button>.</p>}
                {recs.data?.errors.length ? <p className="mt-1 text-[11px] text-destructive">{recs.data.errors.length} licence(s) could not be simulated: {recs.data.errors.map((e) => e.error).join("; ").slice(0, 300)}</p> : null}
            </section>

            <section aria-label={`Source records of ${p.product} section`}>
                <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">C. Source records ({p.source_record_count})</h4>
                <div className="overflow-x-auto">
                    <table className="w-full min-w-[820px] text-xs" aria-label={`Source records of ${p.product}`}><thead><tr className="text-left text-muted-foreground"><th className="py-1">Licence</th><th>Sl#</th><th>HSN</th><th>Original description</th><th>Item identity</th><th>SION</th><th>Matching</th></tr></thead>
                        <tbody>{p.source_records.map((r) => (
                            <tr key={r.import_item_id} className="border-t border-border/40">
                                <td className="py-1 font-mono">{r.license_number}</td><td>{r.serial_number}</td><td className="font-mono">{r.hsn_code ?? "—"}</td><td>{r.description ?? "—"}</td>
                                <td className="font-mono text-[11px]">#{r.import_item_id}{r.item_name_ids?.length ? ` → master ${r.item_name_ids.join(", ")}` : " → no master"}</td>
                                <td>{r.sion ?? p.sion ?? "—"}</td>
                                <td>{p.kind === "MAPPED" ? <span className="text-success">Master-item link</span> : match ? `${BAND[match.band].label}${match.suggestion ? ` → ${match.suggestion.name}` : ""}` : "Pending review"}</td>
                            </tr>
                        ))}</tbody></table>
                </div>
            </section>
        </div>
    );
}

export default function ProductAnalysisView({ data, query, selection, onSelect }: { data: IntelReport; query: string; selection: Selection; onSelect: (s: Partial<Selection>) => void }) {
    const [q, setQ] = useState("");
    const [kind, setKind] = useState("all");
    const [status, setStatus] = useState<Status | "all">("all");
    const [filtersOpen, setFiltersOpen] = useState(false);
    const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "default", dir: 1 });
    const [open, setOpen] = useState<string | null>(null);
    const needsMatching = data.products.some((p) => p.kind !== "MAPPED");
    const matching = useQuery({ ...matchingQuery(query), enabled: needsMatching });
    const matchByProduct = useMemo(() => new Map((matching.data?.suggestions ?? []).flatMap((s) => (s.product_keys ?? (s.product_key ? [s.product_key] : [])).map((k) => [k, s] as const))), [matching.data]);
    const cellsByProduct = useMemo(() => {
        const map = new Map<string, IntelCell[]>();
        data.eligibility.forEach((c) => map.set(c.product_key, [...(map.get(c.product_key) ?? []), c]));
        return map;
    }, [data.eligibility]);
    const licenceProducts = selection.licence != null ? new Set(data.licences.find((l) => l.license_id === selection.licence)?.products ?? []) : null;
    const rows = useMemo(() => {
        const needle = q.trim().toLowerCase();
        const filtered = data.products.filter((p) => (kind === "all" || p.kind === kind) && (status === "all" || p.status === status)
            && (!needle || `${p.product} ${p.sion} ${p.hsn_codes.join(" ")} ${p.aliases.join(" ")}`.toLowerCase().includes(needle)));
        if (sort.key === "default") return sort.dir === 1 ? filtered : [...filtered].reverse(); // backend order: mapped products first
        const key = sort.key;
        const cmp = (a: IntelProduct, b: IntelProduct) => key === "product" ? a.product.localeCompare(b.product) * sort.dir : compareNullable(num(a[key]), num(b[key]), sort.dir);
        return [...filtered].sort(cmp);
    }, [data.products, q, kind, status, sort]);
    const onSort = (key: SortKey) => setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: key === "product" ? 1 : -1 }));
    const activeFilters = (kind !== "all" ? 1 : 0) + (status !== "all" ? 1 : 0);
    const licence = selection.licence != null ? data.licences.find((l) => l.license_id === selection.licence) : null;
    return (
        <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
                <div className="relative w-full sm:w-72"><Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" aria-hidden="true" /><input aria-label="Search products" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Product, alias or HSN…" className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-2 text-sm" /></div>
                <Button size="sm" variant="outline" aria-expanded={filtersOpen} aria-controls="product-filters" onClick={() => setFiltersOpen((v) => !v)}><Filter className="size-3.5" />Filters{activeFilters ? ` (${activeFilters})` : ""}</Button>
                <span className="text-xs text-muted-foreground">{rows.length} of {data.products.length} products</span>
                {licence && <span role="status" className="text-xs text-primary">Products permitted by {licence.license_number}</span>}
                {selection.licence != null && <Button size="sm" variant="ghost" onClick={() => onSelect({ licence: null })}><X className="size-3.5" />Clear licence highlight</Button>}
            </div>
            {filtersOpen && (
                <div id="product-filters" className="flex flex-wrap items-center gap-2 rounded-md border border-border/60 bg-muted/30 px-2 py-1.5">
                    <select aria-label="Mapping kind" value={kind} onChange={(e) => setKind(e.target.value)} className="h-8 rounded-md border border-input bg-background px-2 text-xs"><option value="all">All mappings</option><option value="MAPPED">Master item</option><option value="AMBIGUOUS">Ambiguous</option><option value="UNMAPPED">Unmapped</option><option value="MULTI_PRODUCT">Multi-product classified</option></select>
                    <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value as Status | "all")} className="h-8 rounded-md border border-input bg-background px-2 text-xs"><option value="all">All statuses</option>{(Object.keys(STATUS) as Status[]).map((s) => <option key={s} value={s}>{STATUS[s].label}</option>)}</select>
                    <select aria-label="Sort by" value={`${sort.key}:${sort.dir}`} onChange={(e) => { const [key, dir] = e.target.value.split(":"); setSort({ key: key as SortKey, dir: Number(dir) as 1 | -1 }); }} className="h-8 rounded-md border border-input bg-background px-2 text-xs">
                        <option value="default:1">Mapped first</option>{SORTS.filter(([k]) => k !== "default").flatMap(([k, label]) => [<option key={`${k}:1`} value={`${k}:1`}>{label} ↑</option>, <option key={`${k}:-1`} value={`${k}:-1`}>{label} ↓</option>])}
                    </select>
                    {activeFilters > 0 && <Button size="sm" variant="ghost" onClick={() => { setKind("all"); setStatus("all"); }}>Reset</Button>}
                </div>
            )}
            <div className="max-h-[70vh] overflow-auto rounded-lg border border-border/70">
                <table className="w-full min-w-[1180px] text-sm" aria-label="Products">
                    <thead><tr>
                        <th className={TH} aria-sort={sort.key === "product" ? (sort.dir === 1 ? "ascending" : "descending") : "none"}><button type="button" onClick={() => onSort("product")} className="uppercase hover:text-foreground">Product</button></th>
                        <th className={TH}>SION</th><th className={TH}>HSN codes</th><th className={`${TH} text-right`}>Licences</th><th className={`${TH} text-right`}>Total qty</th><th className={`${TH} text-right`}>Allotted qty</th><th className={`${TH} text-right`}>Debited qty</th>
                        <SortHeader k="balance_qty" label="Available qty" sort={sort} onSort={onSort} />
                        <th className={`${TH} text-right`}>Planned qty</th>
                        <SortHeader k="planned_cif" label="Planned CIF" sort={sort} onSort={onSort} />
                        <SortHeader k="utilisation_percent" label="Util." sort={sort} onSort={onSort} />
                        <th className={TH}>Status</th>
                    </tr></thead>
                    <tbody>
                        {rows.map((p) => {
                            const highlighted = licenceProducts ? licenceProducts.has(p.key) : selection.product === p.key;
                            const muted = licenceProducts ? !licenceProducts.has(p.key) : false;
                            const usable = p.kind === "MAPPED" && Number(p.balance_qty) > 0;
                            const match = matchByProduct.get(p.key);
                            const headline = p.status ?? null;
                            const counts = (Object.keys(STATUS) as Status[]).filter((s) => p.status_counts[s]).map((s) => `${STATUS[s].label} ${p.status_counts[s]}`).join(" · ");
                            return (
                                <Fragment key={p.key}>
                                    <tr className={cn("border-t border-border/50", highlighted && "bg-primary/10", muted && "opacity-40", usable && !highlighted && "hover:bg-success/5")}>
                                        <td className={TD}>
                                            <div className="flex items-start gap-1">
                                                <button type="button" aria-expanded={open === p.key} aria-label={`${open === p.key ? "Collapse" : "Expand"} ${p.product}`} onClick={() => setOpen(open === p.key ? null : p.key)} className="mt-0.5 rounded p-0.5 text-muted-foreground hover:bg-muted"><ChevronRight className={cn("size-3.5 transition-transform", open === p.key && "rotate-90")} aria-hidden="true" /></button>
                                                <button type="button" onClick={() => onSelect({ product: selection.product === p.key ? null : p.key, licence: null })} className="line-clamp-2 max-w-[22rem] text-left font-medium hover:underline" title={p.product} aria-pressed={selection.product === p.key}>{p.product}</button>
                                            </div>
                                            {p.kind !== "MAPPED" && (
                                                <div className="ml-5 flex flex-wrap items-center gap-1 text-[11px]">
                                                    <div className="text-amber-600">{p.kind === "AMBIGUOUS" ? "Ambiguous mapping" : p.kind === "MULTI_PRODUCT" ? "Multi-product — allocation pending" : "Unmapped"}</div>
                                                    {match ? <StatusBadge tone={BAND[match.band].tone} label={`${BAND[match.band].label}${match.suggestion ? ` → ${match.suggestion.name}` : ""}`} /> : matching.isFetching ? <span className="text-muted-foreground">matching…</span> : matching.isError ? <span className="text-destructive">match suggestions unavailable</span> : <span className="text-muted-foreground">Pending match review</span>}
                                                </div>
                                            )}
                                            {p.mapping_review && <div className="ml-5 text-[11px] text-amber-600">{p.mapping_review}</div>}
                                        </td>
                                        <td className={TD}>{p.sion ?? "—"}</td>
                                        <td className={cn(TD, "max-w-[12rem] truncate font-mono text-[11px]")} title={p.hsn_codes.join(", ")}>{p.hsn_codes.join(", ") || "—"}</td>
                                        <td className={cn(TD, NUM)}>{p.eligible_licences}</td>
                                        <td className={cn(TD, NUM)}>{fmt(p.entitlement_qty, 3)}</td>
                                        <td className={cn(TD, NUM)}>{fmt(p.allotted_qty, 3)}</td>
                                        <td className={cn(TD, NUM)}>{fmt(p.debited_qty, 3)}</td>
                                        <td className={cn(TD, NUM, usable && "font-semibold text-success", neg(p.balance_qty) && "text-destructive")}>{fmt(p.balance_qty, 3)}</td>
                                        <td className={cn(TD, NUM, "text-primary")}>{fmt(p.planned_qty, 3)}</td>
                                        <td className={cn(TD, NUM, "text-primary")}>{usd(p.planned_cif)}</td>
                                        <td className={cn(TD, NUM)}>{p.utilisation_percent ? `${p.utilisation_percent}%` : "—"}</td>
                                        <td className={TD} title={counts}>{headline ? <StatusBadge tone={STATUS[headline].tone} label={STATUS[headline].label} /> : "—"}{counts && Object.keys(p.status_counts).length > 1 && <div className="mt-0.5 text-[10px] text-muted-foreground">{counts}</div>}</td>
                                    </tr>
                                    {open === p.key && (
                                        <tr className="bg-muted/20"><td colSpan={12} className="px-4 py-3">
                                            <ProductDetail p={p} cells={cellsByProduct.get(p.key) ?? []} match={match} />
                                        </td></tr>
                                    )}
                                </Fragment>
                            );
                        })}
                    </tbody>
                </table>
                {!rows.length && <EmptyState title="No products" description="Adjust the search or filters." />}
            </div>
        </div>
    );
}
