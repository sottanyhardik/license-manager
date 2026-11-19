/**
 * Licence Import Item mapping — map each unique description ONCE (owner specs 2026-11-19: "automatic licence item name
 * mapping", "advanced filters & bulk update"). One row per unique (strictly normalised) original description:
 *   Original Item Description · HSN · SION · Select Item Name (multi-select chips) · Status · Action (Save).
 *
 * Saving applies the selected existing Item Name ids to every licence import item with exactly that description (REPLACE)
 * and to future ones automatically. No suggestion, no product review, nothing pre-filled for a new description.
 * Filter Conditions only SELECT rows (evaluated on the server — one implementation for the table and bulk updates);
 * a bulk update gives every selected description its OWN mapping. Bulk = preview (exact set + fingerprint) → confirm →
 * apply (refused if the set changed) → per-description results with Retry for failures. Classification only.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, RotateCcw, Save, Search } from "lucide-react";
import { toast } from "sonner";

import api from "@/api/axios";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, EmptyState, InlineError, LoadingState, StatusBadge, type Tone } from "@/components/shared";

import FilterConditions from "./FilterConditions";
import { describeFilters, EMPTY_FILTERS, type Filters } from "./filterModel";
import { invalidateMappingQueries } from "./invalidate";
import type { Master } from "./ItemNameSelect";
import ItemNameMultiSelect from "./ItemNameMultiSelect";
import LicenceRefs, { type LicenceRef } from "./LicenceRefs";
import { errorText } from "./matchingShared";

const PAGE = 50;
const BASE = "item-pivot/matching/item-name-mapping/import/descriptions/";

type DescriptionStatus = "MAPPING_REQUIRED" | "APPLIED" | "AUTO" | "CONFLICT" | "PARTIAL";
export type DescriptionRow = {
    key: string; description: string; wordings: number; records: number; licence_count: number; licence_numbers: string[];
    hsn_codes: string[]; sion: string[]; status: DescriptionStatus; counts: { applied: number; auto: number; conflict: number; stale: number; unverified?: number };
    conflicts: string[]; mapping: { id: number; version: number; items: Master[] } | null; licences: LicenceRef[];
};
type Listing = { rows: DescriptionRow[]; total: number; total_records: number; summary: Partial<Record<DescriptionStatus, number>>; offset: number; limit: number; can_apply: boolean };
type SaveResult = { action: string; applied: number; unchanged: number; conflicts: number; mapping: { id: number; version: number; items: Master[] } };
type Criteria = { search: string; status: DescriptionStatus | ""; filters: Filters };
type Selection = { mode: "none" } | { mode: "keys"; keys: string[] } | { mode: "filter"; criteria: Criteria; descriptions: number; records: number };
type Preview = { descriptions: number; records: number; licence_count: number; licences: LicenceRef[]; licences_truncated: boolean;
    fingerprint: string; sample: string[]; missing: string[]; limit: number; too_many: boolean };
type Outcome = { key: string; description: string; action?: string; applied?: number; conflicts?: number; reason?: string };
type BulkResult = { succeeded: Outcome[]; skipped: Outcome[]; failed: Outcome[]; descriptions: number; records: number };
type BulkBody = { mode: "keys"; keys: string[] } | { mode: "filter"; filters: Filters; status: string; q: string; sion?: string };

const STATUS: Record<DescriptionStatus, { label: string; tone: Tone }> = {
    MAPPING_REQUIRED: { label: "Mapping Required", tone: "warning" },
    APPLIED: { label: "Applied", tone: "success" },
    AUTO: { label: "Automatically Mapped", tone: "success" },
    CONFLICT: { label: "Conflict", tone: "danger" },
    PARTIAL: { label: "Partially applied", tone: "info" },
};
const sameSet = (a: Master[], b: Master[]) => a.length === b.length && a.every((x) => b.some((y) => y.item_id === x.item_id));
const criteriaBody = (c: Criteria) => ({ filters: c.filters, status: c.status, q: c.search });

export default function DescriptionMapping() {
    const qc = useQueryClient();
    const [q, setQ] = useState("");
    const [criteria, setCriteria] = useState<Criteria>({ search: "", status: "MAPPING_REQUIRED", filters: EMPTY_FILTERS });
    const [offset, setOffset] = useState(0);
    // Unsaved edits only, each tied to the mapping version it started from: if someone saves first, the edit is dropped.
    const [picked, setPicked] = useState<Record<string, { items: Master[]; base: number }>>({});
    const [errors, setErrors] = useState<Record<string, string>>({});
    const [selection, setSelection] = useState<Selection>({ mode: "none" });
    const [bulkItems, setBulkItems] = useState<Master[]>([]);
    const [pending, setPending] = useState<{ body: BulkBody; preview: Preview; items: Master[] } | null>(null);
    const [result, setResult] = useState<(BulkResult & { items: Master[] }) | null>(null); // items kept for "Retry failed"
    // Any change of the visible set clears the selection — a bulk update never silently targets a different set.
    const clearSelection = () => { setSelection({ mode: "none" }); setBulkItems([]); };
    const changeCriteria = (next: Partial<Criteria>) => { setCriteria((c) => ({ ...c, ...next })); setOffset(0); clearSelection(); };
    useEffect(() => {
        const term = q.trim();
        if (term === criteria.search) return undefined;
        const t = setTimeout(() => { setCriteria((c) => ({ ...c, search: term })); setOffset(0); setSelection({ mode: "none" }); setBulkItems([]); }, 300);
        return () => clearTimeout(t);
    }, [q, criteria.search]);
    const listing = useQuery({
        queryKey: ["item-name-mapping", "import-descriptions", criteria, offset],
        placeholderData: keepPreviousData,
        queryFn: async ({ signal }) => (await api.get(BASE, { signal, params: {
            ...(criteria.search ? { q: criteria.search } : {}), ...(criteria.status ? { status: criteria.status } : {}),
            ...(criteria.filters.conditions.length ? { filters: JSON.stringify(criteria.filters) } : {}), offset, limit: PAGE } })).data as Listing,
    });
    const masters = useQuery({
        queryKey: ["item-pivot-masters", "all"],
        queryFn: async ({ signal }) => (await api.get("item-pivot/matching/masters/", { signal })).data as { masters: Master[] },
        staleTime: 300_000,
    });
    const clearRow = (key: string) => {
        setPicked((p) => { const n = { ...p }; delete n[key]; return n; });
        setErrors((e) => { const n = { ...e }; delete n[key]; return n; });
    };
    const save = useMutation({
        // the selection is captured at click time (mutation variables)
        mutationFn: async ({ row, items }: { row: DescriptionRow; items: Master[] }) => (await api.post(`${BASE}save/`, {
            description: row.description, item_ids: items.map((i) => i.item_id), ...(row.mapping ? { expected_version: row.mapping.version } : {}) })).data as SaveResult,
        onSuccess: (r, { row }) => {
            toast.success(`${r.action === "UNCHANGED" ? "Mapping unchanged" : "Mapping saved"} — applied to ${r.applied} record(s)${r.unchanged ? `, ${r.unchanged} already current` : ""}${r.conflicts ? `; ${r.conflicts} conflict(s) flagged` : ""}. Future records with this description map automatically.`);
            clearRow(row.key);
            invalidateMappingQueries(qc);
        },
        onError: (err, { row }) => {
            const msg = errorText(err, "Save failed — nothing was changed");
            setErrors((e) => ({ ...e, [row.key]: msg }));
            toast.error(msg);
        },
    });
    const retry = useMutation({
        mutationFn: async (row: DescriptionRow) => (await api.post(`${BASE}${row.mapping?.id}/reapply/`, {})).data as SaveResult,
        onSuccess: (r, row) => { toast.success(`Re-applied to ${r.applied} record(s)`); clearRow(row.key); invalidateMappingQueries(qc); },
        onError: (err, row) => { const msg = errorText(err, "Retry failed"); setErrors((e) => ({ ...e, [row.key]: msg })); toast.error(msg); },
    });
    const preview = useMutation({
        mutationFn: async ({ body, items }: { body: BulkBody; items: Master[] }) => ({ body, items, preview: (await api.post(`${BASE}bulk/preview/`, body)).data as Preview }),
        onSuccess: (r) => setPending(r),
        onError: (err) => toast.error(errorText(err, "Could not prepare the bulk update")),
    });
    const applyBulk = useMutation({
        mutationFn: async ({ body, fingerprint, items }: { body: BulkBody; fingerprint: string; items: Master[] }) =>
            (await api.post(`${BASE}bulk/apply/`, { ...body, fingerprint, item_ids: items.map((i) => i.item_id) })).data as BulkResult,
        onSuccess: (r, { items }) => {
            setResult({ ...r, items });
            toast[r.failed.length ? "warning" : "success"](`Bulk update: ${r.succeeded.length} updated · ${r.skipped.length} unchanged / skipped · ${r.failed.length} failed`);
            clearSelection();
            invalidateMappingQueries(qc);
        },
        onError: (err) => toast.error(errorText(err, "Bulk update failed — nothing was changed")),
    });
    const startBulk = (body: BulkBody, items: Master[]) => preview.mutate({ body, items }); // the previous result stays until a new one exists
    const selectionBody = (): BulkBody | null => selection.mode === "keys" ? { mode: "keys", keys: selection.keys }
        : selection.mode === "filter" ? { mode: "filter", ...criteriaBody(selection.criteria) } : null;
    const selectedKeys = useMemo(() => new Set(selection.mode === "keys" ? selection.keys : []), [selection]);
    const toggleKey = (key: string, on: boolean) => setSelection((s) => {
        const keys = s.mode === "keys" ? s.keys : [];
        const next = on ? [...new Set([...keys, key])] : keys.filter((k) => k !== key);
        return next.length ? { mode: "keys", keys: next } : { mode: "none" };
    });

    const data = listing.data;
    const busy = save.isPending || retry.isPending || applyBulk.isPending;
    const hasCriteria = !!(criteria.filters.conditions.length || criteria.status || criteria.search);
    const selectedCount = selection.mode === "keys" ? selection.keys.length : selection.mode === "filter" ? selection.descriptions : 0;
    const toolbar = (
        <div className="flex flex-wrap items-center gap-2 text-xs">
            <div className="relative w-full sm:w-72"><Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" aria-hidden="true" />
                <input aria-label="Search licence import item descriptions" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Original description…"
                    className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-2 text-sm" /></div>
            <label className="flex items-center gap-1">Show
                <select aria-label="Filter by status" value={criteria.status} onChange={(e) => changeCriteria({ status: e.target.value as DescriptionStatus | "" })}
                    className="h-8 rounded-md border border-input bg-background px-1.5 text-xs">
                    {(["MAPPING_REQUIRED", "APPLIED", "AUTO", "CONFLICT", "PARTIAL"] as DescriptionStatus[]).map((s) =>
                        <option key={s} value={s}>{STATUS[s].label}{data?.summary[s] != null ? ` (${data.summary[s]})` : ""}</option>)}
                    <option value="">All descriptions</option>
                </select>
            </label>
            <Link to="/masters/item-names" className="ml-auto text-primary hover:underline">Item Name missing? Create it in Masters → Item Names</Link>
        </div>
    );
    if (listing.isPending) return <div className="space-y-2">{toolbar}<LoadingState variant="spinner" label="Loading import item descriptions…" /></div>;
    if (listing.isError && !data) return <div className="space-y-2">{toolbar}<InlineError error={listing.error as Error} title="Could not load import item descriptions" onRetry={() => void listing.refetch()} /></div>;
    if (!data) return null;
    return (
        <div className="space-y-2">
            {toolbar}
            <FilterConditions key={JSON.stringify(criteria.filters)} applied={criteria.filters} onApply={(f) => changeCriteria({ filters: f })} />
            {data.can_apply && (
                <section aria-label="Selection and bulk update" className="flex flex-wrap items-center gap-2 rounded-lg border border-border/70 bg-card px-3 py-2 text-xs">
                    <span><strong className="tabular-nums">{data.total}</strong> matching description(s) · <strong className="tabular-nums">{data.total_records}</strong> licence import record(s)</span>
                    <Button size="sm" variant="outline" disabled={!hasCriteria || !data.total || listing.isPlaceholderData} title={hasCriteria ? undefined : "Apply a filter, status or search first"}
                        onClick={() => setSelection({ mode: "filter", criteria, descriptions: data.total, records: data.total_records })}>Select All Matching</Button>
                    <Button size="sm" variant="ghost" disabled={selection.mode === "none"} onClick={clearSelection}>Clear Selection</Button>
                    <span role="status" aria-live="polite" className="font-medium">{selectedCount ? `${selectedCount} description(s) selected${selection.mode === "filter" ? " (all matching)" : ""}` : ""}</span>
                    {selection.mode !== "none" && (
                        <div className="flex w-full flex-wrap items-start gap-2 border-t border-border/60 pt-2">
                            <span className="pt-1 font-semibold">Bulk Update Item Names</span>
                            <ItemNameMultiSelect label="bulk update" value={bulkItems} onChange={setBulkItems} masters={masters.data?.masters ?? []} />
                            <span className="pt-1 text-muted-foreground">Behaviour: REPLACE — the selected Item Names replace each description's current ones.</span>
                            <Button size="sm" disabled={!bulkItems.length || preview.isPending || busy} onClick={() => { const b = selectionBody(); if (b) startBulk(b, bulkItems); }}>Apply Bulk Update</Button>
                        </div>
                    )}
                </section>
            )}
            {result && (
                <section role="status" aria-label="Bulk update result" className="space-y-1 rounded-lg border border-border/70 bg-card px-3 py-2 text-xs">
                    <p><strong>Bulk update finished</strong> ({result.items.map((m) => m.name).join(", ")}, REPLACE): {result.succeeded.length} updated · {result.skipped.length} unchanged / skipped · {result.failed.length} failed.</p>
                    {([["Updated", result.succeeded, ""], ["Unchanged / skipped", result.skipped, "text-muted-foreground"], ["Failed", result.failed, "text-destructive"]] as const).map(([title, list, tone]) => list.length > 0 && (
                        <details key={title} open={title === "Failed"} className={tone}>
                            <summary className="cursor-pointer">{title} ({list.length})</summary>
                            <ul className="max-h-40 list-disc overflow-auto pl-5">{list.map((o) => <li key={o.key}>{o.description}{o.reason ? `: ${o.reason}` : o.conflicts ? ` (${o.conflicts} conflict(s) flagged)` : ""}</li>)}</ul>
                        </details>
                    ))}
                    {result.failed.length > 0 && <Button size="sm" variant="outline" disabled={preview.isPending || busy}
                        onClick={() => startBulk({ mode: "keys", keys: result.failed.map((f) => f.key) }, result.items)}><RotateCcw className="size-3.5" />Retry failed</Button>}
                </section>
            )}
            {masters.isError && <p role="alert" className="text-[11px] text-destructive">The Item Name list could not be loaded — type in the search box to find Item Names.</p>}
            {listing.isError && <p role="alert" className="text-[11px] text-destructive">Could not refresh — showing the last loaded list.</p>}
            <p className="text-[11px] text-muted-foreground">Map each description once. Saving applies the selected Item Names to every licence with exactly this description and to future ones automatically.</p>
            <div className="max-h-[65vh] overflow-auto rounded-lg border border-border/70">
                <table className="w-full min-w-[1040px] text-xs" aria-label="Licence import item descriptions" aria-busy={busy || listing.isPlaceholderData || undefined}>
                    <thead><tr className="sticky top-0 z-[1] bg-muted text-left text-[11px] uppercase text-muted-foreground">
                        {data.can_apply && <th scope="col" className="w-8 px-2 py-2">
                            <input type="checkbox" aria-label="Select this page" disabled={selection.mode === "filter" || !data.rows.length}
                                checked={selection.mode === "filter" || (data.rows.length > 0 && data.rows.every((r) => selectedKeys.has(r.key)))}
                                onChange={(e) => data.rows.forEach((r) => toggleKey(r.key, e.target.checked))} />
                        </th>}
                        <th scope="col" className="px-2 py-2">Original Item Description</th><th scope="col" className="px-2">HSN</th><th scope="col" className="px-2">SION</th>
                        <th scope="col" className="px-2">Select Item Name</th><th scope="col" className="px-2">Status</th><th scope="col" className="px-2"><span className="sr-only">Action</span></th>
                    </tr></thead>
                    <tbody>{data.rows.map((row, i) => {
                        const saved = row.mapping?.items ?? [];
                        const edit = picked[row.key];
                        const live = edit && edit.base === (row.mapping?.version ?? 0) ? edit.items : null; // stale edits are ignored
                        const current = live ?? saved;
                        const dirty = !!live && !sameSet(current, saved);
                        const errId = `desc-err-${i}`;
                        return (
                            <tr key={row.key} className="border-t border-border/50 align-top">
                                {data.can_apply && <td className="px-2 py-1.5">
                                    <input type="checkbox" aria-label={`Select ${row.description}`} checked={selection.mode === "filter" || selectedKeys.has(row.key)}
                                        disabled={selection.mode === "filter"} onChange={(e) => toggleKey(row.key, e.target.checked)} />
                                </td>}
                                <th scope="row" className="max-w-[28rem] px-2 py-1.5 text-left font-normal">
                                    <span className="font-medium">{row.description}</span>
                                    <LicenceRefs refs={row.licences ?? []} records={row.records} label={row.description} />
                                    <div className="text-[10px] text-muted-foreground">{row.wordings > 1 ? `${row.wordings} identical wordings` : ""}{row.wordings > 1 && row.counts.auto ? " · " : ""}{row.counts.auto ? `${row.counts.auto} mapped automatically` : ""}
                                        {row.counts.unverified ? <span className="text-amber-700 dark:text-amber-400"> · {row.counts.unverified} not verified (no HSN / SION reference)</span> : null}</div>
                                    {row.conflicts.map((c, n) => <div key={n} className="mt-0.5 text-[11px] text-destructive">{c}</div>)}
                                </th>
                                <td className="px-2 py-1.5 font-mono" title={row.hsn_codes.join(", ")}>{row.hsn_codes.slice(0, 3).join(", ") || "—"}{row.hsn_codes.length > 3 ? ` +${row.hsn_codes.length - 3}` : ""}</td>
                                <td className="px-2 py-1.5">{row.sion.join(", ") || "—"}</td>
                                <td className="px-2 py-1.5">
                                    <ItemNameMultiSelect label={row.description} value={current} masters={masters.data?.masters ?? []} disabled={!data.can_apply}
                                        describedBy={errors[row.key] ? errId : undefined}
                                        onChange={(next) => { setPicked((p) => ({ ...p, [row.key]: { items: next, base: row.mapping?.version ?? 0 } })); setErrors((e) => { const n = { ...e }; delete n[row.key]; return n; }); }} />
                                    {errors[row.key] && <div role="alert" id={errId} className="mt-0.5 max-w-[22rem] text-[11px] text-destructive">{errors[row.key]}</div>}
                                </td>
                                <td className="px-2 py-1.5"><StatusBadge tone={dirty ? "primary" : STATUS[row.status].tone} label={dirty ? "Ready to save" : STATUS[row.status].label} /></td>
                                <td className="px-2 py-1.5 text-right">{data.can_apply && (row.status === "PARTIAL" && !dirty && row.mapping
                                    ? <Button size="sm" variant="outline" disabled={busy} aria-label={`Retry applying ${row.description}`} onClick={() => retry.mutate(row)}><RotateCcw className="size-3.5" />Retry</Button>
                                    : <Button size="sm" disabled={!dirty || !current.length || busy} aria-describedby={errors[row.key] ? errId : undefined}
                                        aria-label={`Save mapping for ${row.description}`} onClick={() => save.mutate({ row, items: current })}><Save className="size-3.5" />Save</Button>)}</td>
                            </tr>
                        );
                    })}</tbody>
                </table>
                {!data.rows.length && <EmptyState title="Nothing here" description={criteria.status === "MAPPING_REQUIRED" && !hasCriteria ? "Every licence import description has a saved mapping." : "No descriptions match these filters."} />}
            </div>
            {data.total > PAGE && (
                <nav aria-label="Description pages" className="flex items-center justify-end gap-2 text-xs">
                    <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE))}><ChevronLeft className="size-3.5" />Previous</Button>
                    <span className="tabular-nums">{offset + 1}–{Math.min(offset + PAGE, data.total)} of {data.total}</span>
                    <Button size="sm" variant="outline" disabled={offset + PAGE >= data.total} onClick={() => setOffset((o) => o + PAGE)}>Next<ChevronRight className="size-3.5" /></Button>
                </nav>
            )}
            <ConfirmDialog open={!!pending} onOpenChange={(o) => { if (!o) setPending(null); }}
                title="Confirm bulk update"
                description={pending ? <div className="space-y-1.5 text-sm">
                    <p><strong>{pending.preview.descriptions}</strong> unique description(s) · <strong>{pending.preview.records}</strong> existing licence import record(s) ·{" "}
                        <strong>{pending.preview.licence_count}</strong> distinct licence(s).</p>
                    <p>Item Names: {pending.items.map((m) => m.name).join(", ")}.</p>
                    <p>Behaviour: REPLACE — each description gets its own mapping; its records' current Item Names are replaced. Future records with those exact descriptions map automatically.</p>
                    {pending.body.mode === "filter" && <p>Filter: {describeFilters(pending.body.filters) || "(status / search only)"}.</p>}
                    {pending.preview.licences.length > 0 && <div><p className="text-xs font-semibold">Affected licences{pending.preview.licences_truncated ? ` (first ${pending.preview.licences.length} of ${pending.preview.licence_count})` : ""}</p>
                        <LicenceRefs refs={pending.preview.licences} total={pending.preview.licence_count} label="the bulk update" visible={12} /></div>}
                    {pending.preview.missing.length > 0 && <p>{pending.preview.missing.length} selected description(s) no longer exist and will be skipped.</p>}
                    {pending.preview.too_many && <p className="text-destructive">Too many: bulk updates are limited to {pending.preview.limit} descriptions — narrow the filter or select in batches.</p>}
                </div> : null}
                confirmLabel={pending?.preview.too_many ? "Cannot apply" : `Update ${pending?.preview.descriptions ?? 0} description(s)`}
                onConfirm={async () => {
                    if (!pending || pending.preview.too_many) return;
                    // ConfirmDialog does not catch: errors are reported by the mutation (toast) and nothing was changed.
                    await applyBulk.mutateAsync({ body: pending.body, fingerprint: pending.preview.fingerprint, items: pending.items }).catch(() => undefined);
                }} />
        </div>
    );
}
