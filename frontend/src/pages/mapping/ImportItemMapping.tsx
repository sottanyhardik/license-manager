/**
 * Licence Import Item mapping — two tables on one page (owner spec 2026-11-19, final):
 *   1. Approved Mappings (top): active approvals, one Undo each (confirmed; server-side idempotent and audited).
 *   2. Pending Mappings (below): Original Item Description · HSN · SION · Suggested Item Name · Select Item Name ·
 *      Status · Action. The selector is empty by default; a suggestion is a reference only and never an approval.
 *
 * Backend: `item-pivot/matching/` (pending, per SION) + `matching/decide/` (approval, explicit Item Name id) and
 * `matching/item-name-mapping/import/approved/` (+ `<id>/undo/`). Undo restores the records' pre-approval links; the
 * approval itself, mapping versions and audit history are kept. Quantities / CIF are never touched.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search, Undo2 } from "lucide-react";
import { toast } from "sonner";

import api from "@/api/axios";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, EmptyState, InlineError, LoadingState, StatusBadge } from "@/components/shared";

import { invalidateMappingQueries } from "./invalidate";
import { errorText } from "./matchingShared";
import ProductMatchingView from "./ProductMatchingView";

const PAGE = 50;

export type ApprovedRow = { id: number; description: string; hsn_code: string | null; sion: string | null; item_id: number; item: string;
    records: number; status: "APPROVED"; by: string | null; on: string };
type Approved = { rows: ApprovedRow[]; total: number; offset: number; limit: number; can_undo: boolean };

function ApprovedMappings() {
    const qc = useQueryClient();
    const [q, setQ] = useState("");
    const [page, setPage] = useState<{ search: string; offset: number }>({ search: "", offset: 0 });
    const [confirm, setConfirm] = useState<ApprovedRow | null>(null);
    // Undone rows leave the table at once; the stamp drops the filter when fresh data arrives.
    const [gone, setGone] = useState<{ ids: Set<number>; at: number }>({ ids: new Set(), at: 0 });
    const { search, offset } = page;
    useEffect(() => {
        const term = q.trim();
        if (term === search) return undefined;
        const t = setTimeout(() => setPage({ search: term, offset: 0 }), 300);
        return () => clearTimeout(t);
    }, [q, search]);
    const approved = useQuery({
        queryKey: ["item-name-mapping-import-approved", search, offset],
        placeholderData: keepPreviousData,
        queryFn: async ({ signal }) => (await api.get("item-pivot/matching/item-name-mapping/import/approved/", { params: { ...(search ? { q: search } : {}), offset, limit: PAGE }, signal })).data as Approved,
    });
    const undo = useMutation({
        mutationFn: async (row: ApprovedRow) => (await api.post(`item-pivot/matching/item-name-mapping/import/approved/${row.id}/undo/`, {})).data as { undone: boolean; already_undone: boolean },
        onSuccess: (r, row) => {
            if (r.already_undone) toast.info("This mapping was already undone — it is Pending");
            else toast.success(`Mapping undone — "${row.description.slice(0, 60)}" is Pending again; select an Item Name to re-approve`);
            setGone((g) => ({ ids: new Set([...(approved.dataUpdatedAt <= g.at ? g.ids : []), row.id]), at: Date.now() }));
            invalidateMappingQueries(qc);
        },
        onError: (err) => toast.error(errorText(err, "Undo failed — nothing was changed")),
    });
    const hidden = approved.dataUpdatedAt <= gone.at ? gone.ids : null;
    const rows = useMemo(() => (approved.data?.rows ?? []).filter((r) => !hidden?.has(r.id)), [approved.data, hidden]);
    const data = approved.data;
    const total = data ? data.total - (data.rows.length - rows.length) : 0;
    // After an Undo empties the last page, step back to the last page that still has rows.
    useEffect(() => {
        if (data && !approved.isPlaceholderData && offset > 0 && offset >= data.total) setPage({ search, offset: Math.max(0, Math.floor(Math.max(data.total - 1, 0) / PAGE) * PAGE) });
    }, [data, approved.isPlaceholderData, offset, search]);
    return (
        <section aria-labelledby="approved-import-mappings" className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-xs">
                <h2 id="approved-import-mappings" className="text-sm font-semibold">Approved Mappings{data ? ` (${total})` : ""}</h2>
                <div className="relative w-full sm:ml-auto sm:w-72"><Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" aria-hidden="true" />
                    <input aria-label="Search approved mappings" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Description, HSN, SION or Item Name…"
                        className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-2 text-sm" /></div>
            </div>
            {approved.isPending ? <LoadingState variant="spinner" label="Loading approved mappings…" />
                : approved.isError ? <InlineError error={approved.error as Error} title="Could not load approved mappings" onRetry={() => void approved.refetch()} />
                    : (
                        <div className="max-h-[45vh] overflow-auto rounded-lg border border-border/70">
                            <table className="w-full min-w-[860px] text-xs" aria-label="Approved licence import item mappings" aria-busy={approved.isPlaceholderData || undefined}>
                                <thead><tr className="sticky top-0 z-[1] bg-muted text-left text-[11px] uppercase text-muted-foreground">
                                    <th scope="col" className="px-2 py-2">Original Item Description</th><th scope="col" className="px-2">HSN</th><th scope="col" className="px-2">SION</th>
                                    <th scope="col" className="px-2">Approved Item Name</th><th scope="col" className="px-2">Status</th><th scope="col" className="px-2">Action</th>
                                </tr></thead>
                                <tbody>{rows.map((r) => (
                                    <tr key={r.id} className="border-t border-border/50 align-top">
                                        <th scope="row" className="max-w-[28rem] px-2 py-1.5 text-left font-normal">
                                            <span className="font-medium">{r.description || <span className="italic text-muted-foreground">(no description)</span>}</span>
                                            <div className="text-[10px] text-muted-foreground">{r.records} source record{r.records === 1 ? "" : "s"}{r.by ? ` · approved by ${r.by}` : ""} · {new Date(r.on).toLocaleString()}</div>
                                        </th>
                                        <td className="px-2 py-1.5 font-mono">{r.hsn_code || "—"}</td>
                                        <td className="px-2 py-1.5">{r.sion || "—"}</td>
                                        <td className="px-2 py-1.5 font-medium">{r.item}</td>
                                        <td className="px-2 py-1.5"><StatusBadge tone="success" label="Approved" /></td>
                                        <td className="px-2 py-1.5">
                                            {data?.can_undo ? <Button size="sm" variant="outline" disabled={undo.isPending} aria-label={`Undo mapping of ${r.description || `#${r.id}`}`} onClick={() => setConfirm(r)}>
                                                <Undo2 className="size-3.5" />Undo</Button> : <span className="text-muted-foreground">—</span>}
                                        </td>
                                    </tr>
                                ))}</tbody>
                            </table>
                            {!rows.length && <EmptyState title="No approved mappings" description={search ? "No approved mapping matches this search." : "Approved licence import item mappings appear here."} />}
                        </div>
                    )}
            {data && (data.total > PAGE || offset > 0) && (
                <nav aria-label="Approved mappings pages" className="flex items-center justify-end gap-2 text-xs">
                    <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setPage({ search, offset: Math.max(0, offset - PAGE) })}><ChevronLeft className="size-3.5" />Previous</Button>
                    <span className="tabular-nums">{offset + 1}–{Math.min(offset + PAGE, data.total)} of {data.total}</span>
                    <Button size="sm" variant="outline" disabled={offset + PAGE >= data.total} onClick={() => setPage({ search, offset: offset + PAGE })}>Next<ChevronRight className="size-3.5" /></Button>
                </nav>
            )}
            <ConfirmDialog open={!!confirm} onOpenChange={(o) => { if (!o) setConfirm(null); }} tone="danger" title="Undo this mapping?" confirmLabel="Undo mapping"
                description={confirm && (
                    <div className="space-y-2 text-sm">
                        <p><strong>{confirm.description}</strong> → {confirm.item}</p>
                        <p className="text-xs">The {confirm.records} source record(s) return to Pending and need a fresh Item Name selection. The approval stays in the audit history; affected licences re-plan. Quantities and CIF are not changed.</p>
                    </div>
                )}
                onConfirm={() => { if (confirm && !undo.isPending) undo.mutate(confirm); setConfirm(null); }} />
        </section>
    );
}

function PendingMappings() {
    const norms = useQuery({
        queryKey: ["item-pivot-available-norms"],
        queryFn: async ({ signal }) => (await api.get("item-pivot/available-norms/", { signal })).data as { norm_class: string; description?: string }[],
        staleTime: 300_000,
    });
    const [sion, setSion] = useState("");
    const [allLicences, setAllLicences] = useState(false);
    // Every licence of the SION regardless of remaining balance (mapping is classification, not availability).
    const query = useMemo(() => new URLSearchParams({ sion_norm: sion, license_status: allLicences ? "all" : "active", min_balance: "-1000000000" }).toString(), [sion, allLicences]);
    return (
        <section aria-labelledby="pending-import-mappings" className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-xs">
                <h2 id="pending-import-mappings" className="text-sm font-semibold">Pending Mappings</h2>
                <label className="flex items-center gap-1">SION norm
                    <select aria-label="SION norm" value={sion} onChange={(e) => setSion(e.target.value)} className="h-8 rounded-md border border-input bg-background px-1.5 text-xs">
                        <option value="">— choose —</option>
                        {(Array.isArray(norms.data) ? norms.data : []).map((n) => <option key={n.norm_class} value={n.norm_class}>{n.norm_class}{n.description ? ` — ${n.description.slice(0, 40)}` : ""}</option>)}
                    </select>
                </label>
                <label className="flex items-center gap-1"><input type="checkbox" checked={allLicences} onChange={(e) => setAllLicences(e.target.checked)} />Include inactive / expired licences</label>
                <Link to="/masters/item-names" className="ml-auto text-primary hover:underline">Item Name missing? Create it in Masters → Item Names</Link>
            </div>
            {sion ? <ProductMatchingView key={query} query={query} />
                : norms.isError ? <InlineError error={norms.error as Error} title="Could not load SION norms" onRetry={() => void norms.refetch()} />
                    : <EmptyState title="Choose a SION norm" description="Pending licence import descriptions are listed per SION norm, so the selector and validation use that norm's Item Names and rules." />}
        </section>
    );
}

export default function ImportItemMapping() {
    return (
        <div className="space-y-5">
            <ApprovedMappings />
            <PendingMappings />
        </div>
    );
}
