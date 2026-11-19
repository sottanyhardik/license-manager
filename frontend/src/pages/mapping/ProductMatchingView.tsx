/**
 * Licence Import Item mapping queue (Mapping workspace). Same simple table as BOE / Allotment.
 *
 * Data: the existing deterministic + alias + semantic matching backend (`item-pivot/matching/`, per SION) — unchanged.
 * Approval: `item-pivot/matching/decide/` with the explicitly selected Item Name id per row (`item_id` / `item_ids`);
 * the server re-validates every row (SION, HSN, entitlement, conflicts) atomically and versions the change for
 * re-planning. Multi-product wordings are classified per product in the inline product review.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { toast } from "sonner";

import api from "@/api/axios";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, InlineError, LoadingState } from "@/components/shared";

import { invalidateMappingQueries } from "./invalidate";
import type { Master } from "./ItemNameSelect";
import MappingTable from "./MappingTable";
import { approvable, rowStatus, type MappingRow } from "./mappingRow";
import { errorText, matchingQuery, segmentSignature, type MatchSuggestion } from "./matchingShared";
import MultiProductSelection from "./MultiProductSelection";

export type { MatchSuggestion } from "./matchingShared";

const PAGE = 50;
const NONE: string[] = []; // no row checkboxes on this table (bulk = "Approve N ready rows")
const noop = () => {};

function toRow(s: MatchSuggestion, filters: Record<string, string>, canApprove: boolean): MappingRow {
    const multi = (s.segments?.length ?? 0) > 1;
    const legitimate = [...s.candidates, ...(s.semantic?.candidates ?? [])]
        .filter((c, i, all) => all.findIndex((x) => x.item_id === c.item_id) === i)
        .map((c) => ({ item_id: c.item_id, name: c.name }));
    const n = s.import_item_ids.length;
    return {
        key: s.source_key, description: s.description,
        source: `${n} source record${n === 1 ? "" : "s"} · ${s.license_numbers.slice(0, 3).join(", ")}${s.license_numbers.length > 3 ? " …" : ""}${s.kind === "AMBIGUOUS" ? " · currently linked to several Item Names" : ""}`,
        hsn: s.hsn_codes?.length ? s.hsn_codes : s.hsn_code ? [s.hsn_code] : [], sion: s.sion ? [s.sion] : [],
        suggestion: s.suggestion ? { name: s.suggestion.name, confidence: s.confidence, explanation: s.explanation } : null,
        legitimate, conflicts: multi ? [] : s.conflicts,
        reviewRequired: multi ? `Names ${s.segments?.length ?? 0} products — classify each product in the product review` : null,
        blocked: s.band === "CONFLICT" && !multi,
        review: multi ? <MultiProductSelection key={segmentSignature(s)} suggestion={s} filters={filters} canApprove={canApprove} /> : undefined,
    };
}

export default function ProductMatchingView({ query }: { query: string }) {
    const qc = useQueryClient();
    const filters = useMemo(() => Object.fromEntries(new URLSearchParams(query)), [query]);
    const [q, setQ] = useState("");
    const [filter, setFilter] = useState<"ALL" | "PENDING" | "CONFLICT" | "REVIEW">("ALL");
    const [offset, setOffset] = useState(0);
    const [choice, setChoice] = useState<Record<string, number | null>>({});
    const [errors, setErrors] = useState<Record<string, string>>({});
    const [expanded, setExpanded] = useState<string | null>(null);
    // Rows approved in this view leave Pending at once; the stamp drops the filter as soon as fresh data arrives
    // (so a row returned to Pending by Undo reappears).
    const [done, setDone] = useState<{ keys: Set<string>; at: number }>({ keys: new Set(), at: 0 });
    const [confirm, setConfirm] = useState<{ rows: MappingRow[]; ambiguous: MappingRow[]; left: MappingRow[] } | null>(null);
    const matching = useQuery(matchingQuery(query));
    const masters = useQuery({
        queryKey: ["item-pivot-masters", filters.sion_norm ?? ""],
        queryFn: async ({ signal }) => (await api.get("item-pivot/matching/masters/", { params: filters.sion_norm ? { sion: filters.sion_norm } : {}, signal })).data as { masters: Master[] },
        staleTime: 300_000,
    });
    const byKey = useMemo(() => new Map((matching.data?.suggestions ?? []).map((s) => [s.source_key, s])), [matching.data]);
    const masterName = (id: number | null | undefined) => (masters.data?.masters ?? []).find((m) => m.item_id === id)?.name
        ?? [...byKey.values()].flatMap((x) => [...x.candidates, ...(x.semantic?.candidates ?? [])]).find((c) => c.item_id === id)?.name ?? (id ? `#${id}` : "—");
    const decide = useMutation({
        // ids + replace flag are captured at click time (mutation variables), never re-read from render state
        mutationFn: async ({ rows, ids, replace }: { rows: MappingRow[]; ids: Record<string, number>; replace: boolean }) => {
            const body = rows.length === 1
                ? { source_keys: [rows[0].key], decision: "APPROVED", item_id: ids[rows[0].key] }
                : { source_keys: rows.map((r) => r.key), decision: "APPROVED", item_ids: ids };
            return (await api.post("item-pivot/matching/decide/", { ...body, ...(replace ? { replace_links: true } : {}), filters })).data as { recorded: number[] };
        },
        onSuccess: (r, { rows }) => {
            toast.success(`${rows.length} description(s) mapped — affected licences re-plan automatically`);
            setErrors((e) => { const next = { ...e }; rows.forEach((x) => delete next[x.key]); return next; });
            setChoice((c) => { const next = { ...c }; rows.forEach((x) => delete next[x.key]); return next; });
            setDone((d) => ({ keys: new Set([...(matching.dataUpdatedAt <= d.at ? d.keys : []), ...rows.map((x) => x.key)]), at: Date.now() }));
            setExpanded(null);
            invalidateMappingQueries(qc);
        },
        onError: (err, { rows }) => {
            const msg = errorText(err, "Approval failed — nothing was changed");
            setErrors((e) => ({ ...e, ...Object.fromEntries(rows.map((x) => [x.key, msg])) }));
            toast.error(msg);
        },
    });
    const hidden = matching.dataUpdatedAt <= done.at ? done.keys : null;
    const all = useMemo(() => (matching.data?.suggestions ?? []).filter((s) => s.band !== "APPROVED" && s.band !== "CLASSIFIED" && !hidden?.has(s.source_key))
        .map((s) => toRow(s, filters, matching.data?.can_approve ?? false)), [matching.data, filters, hidden]);
    const term = q.trim().toLowerCase();
    const rows = all.filter((r) => (!term || `${r.description} ${r.hsn.join(" ")} ${r.suggestion?.name ?? ""}`.toLowerCase().includes(term))
        && (filter === "ALL" || (filter === "PENDING" && ["PENDING", "READY"].includes(rowStatus(r, choice[r.key]))) || rowStatus(r, choice[r.key]) === filter));
    const start = offset < rows.length ? offset : Math.max(0, Math.floor(Math.max(rows.length - 1, 0) / PAGE) * PAGE); // clamp after the list shrinks
    const page = rows.slice(start, start + PAGE);
    const reset = () => setOffset(0);

    if (matching.isPending) return <LoadingState variant="spinner" label="Loading licence import item mappings…" />;
    if (matching.isError) return <InlineError error={matching.error as Error} title="Could not load licence import item mappings" onRetry={() => void matching.refetch()} />;
    const ambiguous = (rs: MappingRow[]) => rs.filter((r) => byKey.get(r.key)?.kind === "AMBIGUOUS");
    const submit = (rs: MappingRow[], replace: boolean) =>
        decide.mutate({ rows: rs, ids: Object.fromEntries(rs.map((r) => [r.key, choice[r.key] as number])), replace });
    // Bulk = only the rows on this page with their OWN explicitly selected Item Name; the dialog names what stays Pending.
    const ready = page.filter((r) => !r.review && approvable(r, choice[r.key]));
    const approve = (rs: MappingRow[], fromBulk: boolean) => {
        const amb = ambiguous(rs);
        if (fromBulk || amb.length) setConfirm({ rows: rs, ambiguous: amb, left: fromBulk ? page.filter((r) => !rs.includes(r)) : [] });
        else submit(rs, false);
    };
    return (
        <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-xs">
                <div className="relative w-full sm:w-72"><Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" aria-hidden="true" />
                    <input aria-label="Search licence import item descriptions" value={q} onChange={(e) => { setQ(e.target.value); reset(); }} placeholder="Original description, HSN or Item Name…"
                        className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-2 text-sm" /></div>
                <label className="flex items-center gap-1">Show
                    <select aria-label="Filter licence import item queue" value={filter} onChange={(e) => { setFilter(e.target.value as typeof filter); reset(); }} className="h-8 rounded-md border border-input bg-background px-1.5 text-xs">
                        <option value="ALL">All pending</option><option value="PENDING">Pending / ready</option><option value="CONFLICT">Conflict</option><option value="REVIEW">Review required</option>
                    </select>
                </label>
                <span className="text-muted-foreground">{all.length} pending description(s)</span>
                {matching.data.can_approve && ready.length > 1 && (
                    <Button size="sm" className="ml-auto" disabled={decide.isPending} onClick={() => approve(ready, true)}>
                        <Check className="size-3.5" />Approve {ready.length} ready rows
                    </Button>
                )}
            </div>
            <MappingTable label="licence import item" rows={page} choice={choice} bulk={false}
                onChoose={(k, id) => { setChoice((c) => ({ ...c, [k]: id })); setErrors((e) => { const next = { ...e }; delete next[k]; return next; }); }}
                selected={NONE} onSelect={noop} errors={errors} masters={masters.data?.masters ?? []} canApply={matching.data.can_approve} busy={decide.isPending}
                expanded={expanded} onExpand={setExpanded} onApprove={(rs) => approve(rs, false)} />
            <ConfirmDialog open={!!confirm} onOpenChange={(o) => { if (!o) setConfirm(null); }}
                title={confirm && confirm.rows.length > 1 ? `Approve ${confirm.rows.length} mappings?` : "Approve this mapping?"}
                confirmLabel="Approve"
                description={confirm && (
                    <div className="space-y-2 text-sm">
                        <p>Each row is approved with the Item Name you selected for it (suggestions are not used). The server re-validates every row; if any fails, nothing is approved.</p>
                        <ul className="max-h-48 list-disc overflow-auto pl-5 text-xs">
                            {confirm.rows.map((r) => <li key={r.key}>{r.description} → <strong>{masterName(choice[r.key])}</strong></li>)}
                        </ul>
                        {confirm.left.length > 0 && <p className="text-xs text-amber-700 dark:text-amber-400">{confirm.left.length} other row(s) on this page have no Item Name selected (or need a product review) and stay Pending: {confirm.left.slice(0, 5).map((r) => r.description).join("; ")}{confirm.left.length > 5 ? " …" : ""}</p>}
                        {confirm.ambiguous.length > 0 && <p className="text-xs text-amber-700 dark:text-amber-400">{confirm.ambiguous.length} row(s) are already linked to several Item Names; approving replaces those links (the previous links are kept in the audit).</p>}
                    </div>
                )}
                onConfirm={() => { if (confirm && !decide.isPending) submit(confirm.rows, confirm.ambiguous.length > 0); setConfirm(null); }} />
            {rows.length > PAGE && (
                <nav aria-label="Licence import item queue pages" className="flex items-center justify-end gap-2 text-xs">
                    <Button size="sm" variant="outline" disabled={start === 0} onClick={() => setOffset(Math.max(0, start - PAGE))}><ChevronLeft className="size-3.5" />Previous</Button>
                    <span className="tabular-nums">{start + 1}–{Math.min(start + PAGE, rows.length)} of {rows.length}</span>
                    <Button size="sm" variant="outline" disabled={start + PAGE >= rows.length} onClick={() => setOffset(start + PAGE)}>Next<ChevronRight className="size-3.5" /></Button>
                </nav>
            )}
        </div>
    );
}
