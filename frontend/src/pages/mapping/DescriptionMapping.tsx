/**
 * Licence Import Item mapping — map each unique description ONCE (owner spec 2026-11-19, "automatic licence item name
 * mapping"). One row per unique (strictly normalised) original description:
 *   Original Item Description · HSN · SION · Select Item Name (multi-select chips) · Status · Action (Save).
 *
 * Saving applies the selected existing Item Name ids to every licence import item with exactly that description (REPLACE)
 * and to future ones automatically. No suggestion, no product review, nothing pre-filled for a new description.
 * HSN / SION-incompatible records are flagged as conflicts and left unchanged. Classification only — quantities and CIF
 * are never touched. Backend: `item-pivot/matching/item-name-mapping/import/descriptions/` (+ `save/`, `<id>/reapply/`).
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, RotateCcw, Save, Search } from "lucide-react";
import { toast } from "sonner";

import api from "@/api/axios";
import { Button } from "@/components/ui/button";
import { EmptyState, InlineError, LoadingState, StatusBadge, type Tone } from "@/components/shared";

import { invalidateMappingQueries } from "./invalidate";
import type { Master } from "./ItemNameSelect";
import ItemNameMultiSelect from "./ItemNameMultiSelect";
import { errorText } from "./matchingShared";

const PAGE = 50;

type DescriptionStatus = "MAPPING_REQUIRED" | "APPLIED" | "CONFLICT" | "PARTIAL";
export type DescriptionRow = {
    key: string; description: string; wordings: number; records: number; licence_count: number; licence_numbers: string[];
    hsn_codes: string[]; sion: string[]; status: DescriptionStatus; counts: { applied: number; auto: number; conflict: number; stale: number };
    conflicts: string[]; mapping: { id: number; version: number; items: Master[] } | null;
};
type Listing = { rows: DescriptionRow[]; total: number; summary: Partial<Record<DescriptionStatus, number>>; offset: number; limit: number; can_apply: boolean };
type SaveResult = { action: string; applied: number; unchanged: number; conflicts: number; mapping: { id: number; version: number; items: Master[] } };

const STATUS: Record<DescriptionStatus, { label: string; tone: Tone }> = {
    MAPPING_REQUIRED: { label: "Mapping Required", tone: "warning" },
    APPLIED: { label: "Applied", tone: "success" },
    CONFLICT: { label: "Conflict", tone: "danger" },
    PARTIAL: { label: "Partially applied", tone: "info" },
};
const sameSet = (a: Master[], b: Master[]) => a.length === b.length && a.every((x) => b.some((y) => y.item_id === x.item_id));

export default function DescriptionMapping() {
    const qc = useQueryClient();
    const [q, setQ] = useState("");
    const [view, setView] = useState<{ search: string; status: DescriptionStatus | ""; offset: number }>({ search: "", status: "MAPPING_REQUIRED", offset: 0 });
    // Unsaved edits only, each tied to the mapping version it started from: if someone saves first, the edit is dropped.
    const [picked, setPicked] = useState<Record<string, { items: Master[]; base: number }>>({});
    const [errors, setErrors] = useState<Record<string, string>>({});
    useEffect(() => {
        const term = q.trim();
        if (term === view.search) return undefined;
        const t = setTimeout(() => setView((v) => ({ ...v, search: term, offset: 0 })), 300);
        return () => clearTimeout(t);
    }, [q, view.search]);
    const listing = useQuery({
        queryKey: ["item-name-mapping", "import-descriptions", view],
        placeholderData: keepPreviousData,
        queryFn: async ({ signal }) => (await api.get("item-pivot/matching/item-name-mapping/import/descriptions/", {
            params: { ...(view.search ? { q: view.search } : {}), ...(view.status ? { status: view.status } : {}), offset: view.offset, limit: PAGE }, signal })).data as Listing,
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
        mutationFn: async ({ row, items }: { row: DescriptionRow; items: Master[] }) => (await api.post("item-pivot/matching/item-name-mapping/import/descriptions/save/", {
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
        mutationFn: async (row: DescriptionRow) => (await api.post(`item-pivot/matching/item-name-mapping/import/descriptions/${row.mapping?.id}/reapply/`, {})).data as SaveResult,
        onSuccess: (r, row) => { toast.success(`Re-applied to ${r.applied} record(s)`); clearRow(row.key); invalidateMappingQueries(qc); },
        onError: (err, row) => { const msg = errorText(err, "Retry failed"); setErrors((e) => ({ ...e, [row.key]: msg })); toast.error(msg); },
    });

    const data = listing.data;
    const busy = save.isPending || retry.isPending;
    const toolbar = (
        <div className="flex flex-wrap items-center gap-2 text-xs">
            <div className="relative w-full sm:w-72"><Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" aria-hidden="true" />
                <input aria-label="Search licence import item descriptions" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Original description…"
                    className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-2 text-sm" /></div>
            <label className="flex items-center gap-1">Show
                <select aria-label="Filter by status" value={view.status} onChange={(e) => setView((v) => ({ ...v, status: e.target.value as DescriptionStatus | "", offset: 0 }))}
                    className="h-8 rounded-md border border-input bg-background px-1.5 text-xs">
                    <option value="MAPPING_REQUIRED">Mapping Required{data?.summary.MAPPING_REQUIRED != null ? ` (${data.summary.MAPPING_REQUIRED})` : ""}</option>
                    <option value="APPLIED">Applied{data?.summary.APPLIED != null ? ` (${data.summary.APPLIED})` : ""}</option>
                    <option value="CONFLICT">Conflict{data?.summary.CONFLICT != null ? ` (${data.summary.CONFLICT})` : ""}</option>
                    <option value="PARTIAL">Partially applied{data?.summary.PARTIAL != null ? ` (${data.summary.PARTIAL})` : ""}</option>
                    <option value="">All descriptions</option>
                </select>
            </label>
            <Link to="/masters/item-names" className="ml-auto text-primary hover:underline">Item Name missing? Create it in Masters → Item Names</Link>
        </div>
    );
    if (listing.isPending) return <div className="space-y-2">{toolbar}<LoadingState variant="spinner" label="Loading import item descriptions…" /></div>;
    if (listing.isError || !data) return <div className="space-y-2">{toolbar}<InlineError error={listing.error as Error} title="Could not load import item descriptions" onRetry={() => void listing.refetch()} /></div>;
    return (
        <div className="space-y-2">
            {toolbar}
            {masters.isError && <p role="alert" className="text-[11px] text-destructive">The Item Name list could not be loaded — type in the search box to find Item Names.</p>}
            {listing.isError && <p role="alert" className="text-[11px] text-destructive">Could not refresh — showing the last loaded list.</p>}
            <p className="text-[11px] text-muted-foreground">Map each description once. Saving applies the selected Item Names to every licence with exactly this description and to future ones automatically.</p>
            <div className="max-h-[65vh] overflow-auto rounded-lg border border-border/70">
                <table className="w-full min-w-[1000px] text-xs" aria-label="Licence import item descriptions" aria-busy={busy || listing.isPlaceholderData || undefined}>
                    <thead><tr className="sticky top-0 z-[1] bg-muted text-left text-[11px] uppercase text-muted-foreground">
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
                                <th scope="row" className="max-w-[28rem] px-2 py-1.5 text-left font-normal">
                                    <span className="font-medium">{row.description}</span>
                                    <div className="text-[10px] text-muted-foreground">{row.records} record{row.records === 1 ? "" : "s"} on {row.licence_count} licence{row.licence_count === 1 ? "" : "s"}
                                        {row.wordings > 1 ? ` · ${row.wordings} identical wordings` : ""}{row.counts.auto ? ` · ${row.counts.auto} mapped automatically` : ""}</div>
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
                {!data.rows.length && <EmptyState title="Nothing here" description={view.status === "MAPPING_REQUIRED" ? "Every licence import description has a saved mapping." : "No descriptions match this filter."} />}
            </div>
            {data.total > PAGE && (
                <nav aria-label="Description pages" className="flex items-center justify-end gap-2 text-xs">
                    <Button size="sm" variant="outline" disabled={view.offset === 0} onClick={() => setView((v) => ({ ...v, offset: Math.max(0, v.offset - PAGE) }))}><ChevronLeft className="size-3.5" />Previous</Button>
                    <span className="tabular-nums">{view.offset + 1}–{Math.min(view.offset + PAGE, data.total)} of {data.total}</span>
                    <Button size="sm" variant="outline" disabled={view.offset + PAGE >= data.total} onClick={() => setView((v) => ({ ...v, offset: v.offset + PAGE }))}>Next<ChevronRight className="size-3.5" /></Button>
                </nav>
            )}
        </div>
    );
}
