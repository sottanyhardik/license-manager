/**
 * Approved (Description + HSN) — global decisions made in Licence Detail → Import Items (owner decision 2026-11-20).
 * Each row is one strictly-normalised description + HSN combination approved for every licence: either an Item Name
 * (`USER_APPROVED`) or deliberately none (`USER_APPROVED_CLEAR`). Approved combinations are not pending description
 * work. Revise (optimistic-locked by version), Revoke (back to pending / its description mapping) and History.
 * All counts come from the backend; nothing is derived here.
 */
import { useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, History, Pencil, Search, Undo2 } from "lucide-react";
import { toast } from "sonner";

import api from "@/api/axios";
import { ItemNameAsyncSelect } from "@/components/item-async-select";
import { ConfirmDialog, EmptyState, InlineError, LoadingState, StatusBadge } from "@/components/shared";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

import { invalidateMappingQueries } from "./invalidate";
import { APPROVALS_BASE } from "./mappingSources";
import { errorText } from "./matchingShared";

const PAGE = 50;

type ApprovalStatus = "USER_APPROVED" | "USER_APPROVED_CLEAR";
type ApprovalRow = {
    id: number; description: string; hsn_code: string | null; status: ApprovalStatus; item: { id: number; name: string } | null; version: number;
    records: number; licences: number; overridden: number; updated_by: string | null; updated_on: string | null; source?: string;
};
type Listing = { rows: ApprovalRow[]; total: number; counts: { approved: number; cleared: number }; can_apply: boolean };
type Propagation = { records: number; licences: number; applied: number; unchanged: number; overridden: number; conflicts: number; conflict_licences: { id: number; license_number: string }[] };
type HistoryEvent = {
    version: number; action: string; item: { id: number; name: string } | null; previous_item: { id: number; name: string } | null;
    status: string; previous_status: string | null; records: number; licences: number; user: string | null; time: string;
};

const itemText = (item: { name: string } | null, status?: string | null) => item ? item.name : status === "USER_APPROVED_CLEAR" ? "Cleared" : "Not mapped";
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

function summary(p: Propagation): string {
    return `Applied to ${plural(p.applied, "record")} on ${plural(p.licences, "licence")}`
        + (p.overridden ? `; ${p.overridden} overridden` : "") + (p.conflicts ? `; ${plural(p.conflicts, "conflict")}` : "");
}

export default function ApprovedMappings() {
    const qc = useQueryClient();
    const [q, setQ] = useState("");
    const [search, setSearch] = useState("");
    const [status, setStatus] = useState<ApprovalStatus | "">("");
    const [offset, setOffset] = useState(0);
    const [revising, setRevising] = useState<ApprovalRow | null>(null);
    const [revoking, setRevoking] = useState<ApprovalRow | null>(null);
    const [history, setHistory] = useState<ApprovalRow | null>(null);

    useEffect(() => {
        const term = q.trim();
        if (term === search) return undefined;
        const t = setTimeout(() => { setSearch(term); setOffset(0); }, 300);
        return () => clearTimeout(t);
    }, [q, search]);

    const listing = useQuery({
        queryKey: ["item-name-mapping", "import-approvals", search, status, offset],
        placeholderData: keepPreviousData,
        queryFn: async ({ signal }) => (await api.get(APPROVALS_BASE, { signal, params: {
            ...(search ? { q: search } : {}), ...(status ? { status } : {}), offset, limit: PAGE } })).data as Listing,
    });

    const revoke = useMutation({
        mutationFn: async (row: ApprovalRow) => (await api.post(`${APPROVALS_BASE}${row.id}/revoke/`, {})).data,
        onSuccess: () => { toast.success("Approval revoked — the combination is pending or follows its description mapping again."); invalidateMappingQueries(qc); },
        onError: (err) => toast.error(errorText(err, "Revoke failed — nothing was changed")),
    });

    const data = listing.data;
    const toolbar = (
        <div className="flex flex-wrap items-center gap-2 text-xs">
            <div className="relative w-full sm:w-72">
                <Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" aria-hidden="true" />
                <input aria-label="Search approved combinations" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Description or HSN…"
                    className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-2 text-sm" />
            </div>
            <label className="flex items-center gap-1">Show
                <select aria-label="Filter approvals by status" value={status} onChange={(e) => { setStatus(e.target.value as ApprovalStatus | ""); setOffset(0); }}
                    className="h-8 rounded-md border border-input bg-background px-1.5 text-xs">
                    <option value="">All approvals</option>
                    <option value="USER_APPROVED">Approved{data ? ` (${data.counts.approved})` : ""}</option>
                    <option value="USER_APPROVED_CLEAR">Cleared{data ? ` (${data.counts.cleared})` : ""}</option>
                </select>
            </label>
            {data && <span role="status" className="text-muted-foreground"><strong className="tabular-nums">{data.counts.approved}</strong> approved · <strong className="tabular-nums">{data.counts.cleared}</strong> cleared</span>}
        </div>
    );
    if (listing.isPending) return <div className="space-y-2">{toolbar}<LoadingState variant="spinner" label="Loading approved combinations…" /></div>;
    if (listing.isError && !data) return <div className="space-y-2">{toolbar}<InlineError error={listing.error as Error} title="Could not load approved combinations" onRetry={() => void listing.refetch()} /></div>;
    if (!data) return null;
    return (
        <div className="space-y-2">
            {toolbar}
            <p className="text-[11px] text-muted-foreground">
                Item Name decisions made in Licence Detail apply to every import item with the same Description + HSN on every licence. They are not pending description work.
                A “This record only” override beats an approval.
            </p>
            {listing.isError && <p role="alert" className="text-[11px] text-destructive">Could not refresh — showing the last loaded list.</p>}
            <div className="max-h-[65vh] overflow-auto rounded-lg border border-border/70">
                <table className="w-full min-w-[1040px] text-xs" aria-label="Approved Description + HSN combinations" aria-busy={listing.isPlaceholderData || undefined}>
                    <thead><tr className="sticky top-0 z-[1] bg-muted text-left text-[11px] uppercase text-muted-foreground">
                        <th scope="col" className="px-2 py-2">Description</th><th scope="col" className="px-2">HSN</th><th scope="col" className="px-2">Item Name</th>
                        <th scope="col" className="px-2 text-right">Records</th><th scope="col" className="px-2 text-right">Licences</th><th scope="col" className="px-2 text-right">Overridden</th>
                        <th scope="col" className="px-2 text-right">Version</th><th scope="col" className="px-2">Updated by</th><th scope="col" className="px-2">Updated on</th>
                        <th scope="col" className="px-2"><span className="sr-only">Actions</span></th>
                    </tr></thead>
                    <tbody>{data.rows.map((row) => (
                        <tr key={row.id} className="border-t border-border/50 align-top">
                            <th scope="row" className="max-w-[24rem] truncate px-2 py-1.5 text-left font-medium" title={row.description}>{row.description}</th>
                            <td className="px-2 py-1.5 font-mono">{row.hsn_code || "—"}</td>
                            <td className="px-2 py-1.5">{row.status === "USER_APPROVED_CLEAR" || !row.item
                                ? <StatusBadge tone="neutral" label="Cleared" title="Deliberately no Item Name" />
                                : <span className="inline-block max-w-[14rem] truncate align-bottom" title={row.item.name}>{row.item.name}</span>}</td>
                            <td className="px-2 py-1.5 text-right tabular-nums">{row.records}</td>
                            <td className="px-2 py-1.5 text-right tabular-nums">{row.licences}</td>
                            <td className="px-2 py-1.5 text-right tabular-nums">{row.overridden}</td>
                            <td className="px-2 py-1.5 text-right tabular-nums">v{row.version}</td>
                            <td className="px-2 py-1.5">{row.updated_by ?? "—"}</td>
                            <td className="px-2 py-1.5 whitespace-nowrap">{row.updated_on ?? "—"}</td>
                            <td className="px-2 py-1.5 text-right whitespace-nowrap">
                                {data.can_apply && <Button size="sm" variant="outline" aria-label={`Revise approval for ${row.description}`} onClick={() => setRevising(row)}><Pencil className="size-3.5" />Revise</Button>}{" "}
                                {data.can_apply && <Button size="sm" variant="outline" disabled={revoke.isPending} aria-label={`Revoke approval for ${row.description}`} onClick={() => setRevoking(row)}><Undo2 className="size-3.5" />Revoke</Button>}{" "}
                                <Button size="sm" variant="ghost" aria-label={`History for ${row.description}`} onClick={() => setHistory(row)}><History className="size-3.5" />History</Button>
                            </td>
                        </tr>
                    ))}</tbody>
                </table>
                {!data.rows.length && <EmptyState title="No approved combinations" description={search || status ? "No approvals match these filters." : "Item Name changes saved from Licence Detail appear here."} />}
            </div>
            {data.total > PAGE && (
                <nav aria-label="Approved combination pages" className="flex items-center justify-end gap-2 text-xs">
                    <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE))}><ChevronLeft className="size-3.5" />Previous</Button>
                    <span className="tabular-nums">{offset + 1}–{Math.min(offset + PAGE, data.total)} of {data.total}</span>
                    <Button size="sm" variant="outline" disabled={offset + PAGE >= data.total} onClick={() => setOffset((o) => o + PAGE)}>Next<ChevronRight className="size-3.5" /></Button>
                </nav>
            )}
            {revising && <ReviseDialog row={revising} onClose={() => setRevising(null)} />}
            {history && <HistoryDialog row={history} onClose={() => setHistory(null)} />}
            <ConfirmDialog open={!!revoking} onOpenChange={(o) => { if (!o) setRevoking(null); }} tone="danger"
                title="Revoke this approval?"
                description={revoking ? <p className="text-sm">“{revoking.description}” (HSN {revoking.hsn_code || "none"}) is no longer approved. It returns to pending Product Mapping work, or to its description mapping.
                    Row-level overrides are kept.</p> : null}
                confirmLabel="Revoke"
                onConfirm={async () => { if (revoking) await revoke.mutateAsync(revoking).catch(() => undefined); }} />
        </div>
    );
}

function ReviseDialog({ row, onClose }: { row: ApprovalRow; onClose: () => void }) {
    const qc = useQueryClient();
    const [itemId, setItemId] = useState<number | null>(row.item?.id ?? null);
    const [clear, setClear] = useState(row.status === "USER_APPROVED_CLEAR");
    const [stale, setStale] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<Propagation | null>(null);
    const unchanged = clear ? row.status === "USER_APPROVED_CLEAR" : itemId === (row.item?.id ?? null);
    const save = useMutation({
        mutationFn: async () => (await api.post(`${APPROVALS_BASE}save/`, {
            description: row.description, hsn_code: row.hsn_code, item_id: clear ? null : itemId, expected_version: row.version })).data as Propagation,
        onSuccess: (r) => {
            setResult(r);
            toast.success(summary(r));
            invalidateMappingQueries(qc);
            if (!r.conflicts) onClose();
        },
        onError: (err) => {
            const status = (err as { response?: { status?: number } }).response?.status;
            setStale(status === 409);
            setError(status === 409 ? errorText(err, "This approval was changed by someone else.") : errorText(err, "Save failed — nothing was changed"));
        },
    });
    return (
        <Dialog open onOpenChange={(o) => { if (!o && !save.isPending) onClose(); }}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Revise approval</DialogTitle>
                    <DialogDescription>
                        <span className="block truncate" title={row.description}>{row.description}</span>
                        HSN {row.hsn_code || "none"} · version {row.version} · {plural(row.records, "record")} on {plural(row.licences, "licence")}
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-2">
                    <ItemNameAsyncSelect value={clear ? null : itemId} disabled={clear} ariaLabel="Item Name for this approval" portalMenu
                        onChange={(id) => { setItemId(id); setError(null); setStale(false); }} />
                    <Button type="button" size="sm" variant="outline" aria-pressed={clear} onClick={() => { setClear((c) => !c); setError(null); setStale(false); }}>
                        Clear (deliberately no Item Name)
                    </Button>
                </div>
                {error && (
                    <Alert variant="destructive" role="alert"><AlertDescription className="flex flex-wrap items-center gap-2">
                        <span>{error}</span>
                        {stale && <Button type="button" size="sm" variant="outline" onClick={() => { invalidateMappingQueries(qc); onClose(); }}>Reload</Button>}
                    </AlertDescription></Alert>
                )}
                {result && result.conflicts > 0 && (
                    <Alert role="status"><AlertDescription>
                        <p>{summary(result)}.</p>
                        <p className="text-xs">Conflicts: {result.conflict_licences.map((l) => l.license_number).join(", ")}</p>
                    </AlertDescription></Alert>
                )}
                <DialogFooter>
                    <Button variant="outline" onClick={onClose} disabled={save.isPending}>{result ? "Close" : "Cancel"}</Button>
                    {!result && <Button onClick={() => save.mutate()} disabled={save.isPending || unchanged || (!clear && itemId === null)}>Save revision</Button>}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

function HistoryDialog({ row, onClose }: { row: ApprovalRow; onClose: () => void }) {
    const { data, isLoading, isError, error } = useQuery({
        queryKey: ["item-name-mapping-history", "import-approval", row.id],
        queryFn: async ({ signal }) => (await api.get(`${APPROVALS_BASE}${row.id}/history/`, { signal })).data as { events: HistoryEvent[] },
        staleTime: 0,
    });
    return (
        <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Approval history</DialogTitle>
                    <DialogDescription><span className="block truncate" title={row.description}>{row.description}</span>HSN {row.hsn_code || "none"}</DialogDescription>
                </DialogHeader>
                {isLoading && <LoadingState variant="spinner" label="Loading history…" />}
                {isError && <Alert variant="destructive"><AlertDescription>{errorText(error, "Failed to load history.")}</AlertDescription></Alert>}
                {data && data.events.length === 0 && <p className="text-sm text-muted-foreground">No history yet.</p>}
                {data && data.events.length > 0 && (
                    <ul className="max-h-80 space-y-2 overflow-auto text-sm">
                        {data.events.map((ev) => (
                            <li key={`${ev.version}-${ev.time}`} className="rounded-md border border-border/70 p-2">
                                <div className="flex justify-between gap-2 text-xs text-muted-foreground">
                                    <span className="font-medium text-foreground">v{ev.version} · {ev.action}</span>
                                    <span>{ev.user ?? "system"} · {ev.time}</span>
                                </div>
                                <div>{itemText(ev.previous_item, ev.previous_status)} → {itemText(ev.item, ev.status)}</div>
                                <div className="text-xs text-muted-foreground">{plural(ev.records, "record")} on {plural(ev.licences, "licence")}</div>
                            </li>
                        ))}
                    </ul>
                )}
            </DialogContent>
        </Dialog>
    );
}
