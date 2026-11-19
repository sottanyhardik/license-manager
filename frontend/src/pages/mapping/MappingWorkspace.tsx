/**
 * Mapping workspace (owner spec 2026-11-19) — Original Source Description → existing Item Name id.
 *
 * Exactly three primary tabs: Licence Import Item · BOE · Allotment. All three map to the SAME Item Name master
 * (`ItemNameModel` id) that Item Pivot (Classic Mode) groups by and Licence Planning consumes:
 * licence import items per unique description, mapped once and applied to all + future records (`DescriptionMapping`), BOE / allotment headers via
 * `planning_target_item` (`item-pivot/matching/item-name-mapping/<kind>/apply/`). Suggestions are never approvals;
 * every approval is validated on the server (SION rules, HSN, entitlement) and versioned for re-planning.
 * Descriptions, quantities, CIF and debit rows are never changed. A missing Item Name is created only through
 * Masters → Item Names (the authorised master workflow).
 */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { toast } from "sonner";

import api from "@/api/axios";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { EmptyState, InlineError, LoadingState } from "@/components/shared";
import { DetailTabs } from "@/components/workspace";

import type { Master } from "./ItemNameSelect";
import DescriptionMapping from "./DescriptionMapping";
import { invalidateMappingQueries } from "./invalidate";
import MappingChanges from "./MappingChanges";
import MappingTable from "./MappingTable";
import { rowStatus, type MappingRow } from "./mappingRow";
import { errorText } from "./matchingShared";

type Kind = "boe" | "allotment";
type Suggestion = { item_id: number; name: string | null; confidence: number; explanation: string };
type Conflict = { code: "SION" | "HSN" | "MULTI_PRODUCT"; detail: string };
export type MappingGroup = {
    key: string; description: string; record_ids: number[]; records: number; statuses: Record<string, number>; licence_count: number;
    licence_numbers: string[]; hsn_codes: string[]; sion: string[]; quantity: string; units: string[];
    legitimate: { item_id: number; name: string | null }[]; mappable: boolean; suggestion: Suggestion | null; similar: Suggestion[]; conflicts: Conflict[];
    boe_numbers?: string[]; latest_boe_date?: string | null;
};
type Queue = { kind: Kind; groups: MappingGroup[]; total_groups: number; total_records: number; offset: number; limit: number; can_apply: boolean };
type Counts = Record<"import" | Kind, { records: number; descriptions: number }>;
type HistoryRow = { id: number; description: string | null; item_id: number | null; item: string | null; hsn_codes: string[]; sion?: string | null;
    previous?: unknown; mapping_version?: number | null; by: string | null; on: string };

const PAGE = 50;
const LABEL: Record<Kind, string> = { boe: "BOE", allotment: "allotment" };

function HistoryTable({ kind }: { kind: "import" | Kind }) {
    const hist = useQuery({
        queryKey: ["item-name-mapping-history", kind],
        queryFn: async ({ signal }) => (await api.get(`item-pivot/matching/item-name-mapping/${kind}/history/`, { signal })).data as { rows: HistoryRow[]; total: number },
    });
    if (hist.isPending) return <LoadingState variant="spinner" label="Loading approved mappings…" />;
    if (hist.isError) return <InlineError error={hist.error as Error} title="Could not load approved mappings" onRetry={() => void hist.refetch()} />;
    if (!hist.data.rows.length) return <EmptyState title="No approved mappings yet" description="Approved mappings appear here with who approved them and when." />;
    return (
        <div className="max-h-[60vh] overflow-auto rounded-lg border border-border/70">
            <table className="w-full min-w-[760px] text-xs" aria-label={`Approved ${kind === "import" ? "licence import item" : LABEL[kind]} mappings`}>
                <thead><tr className="sticky top-0 bg-muted text-left text-[11px] uppercase text-muted-foreground">
                    <th scope="col" className="px-2 py-2">Record</th><th scope="col" className="px-2">Original description</th><th scope="col" className="px-2">Item Name</th>
                    <th scope="col" className="px-2">HSN</th><th scope="col" className="px-2">Version</th><th scope="col" className="px-2">Approved by</th><th scope="col" className="px-2">On</th>
                </tr></thead>
                <tbody>{hist.data.rows.map((r, i) => (
                    <tr key={`${r.id}-${i}`} className="border-t border-border/50">
                        <td className="px-2 py-1.5 font-mono">#{r.id}</td><td className="max-w-[28rem] px-2 py-1.5">{r.description || "—"}</td>
                        <td className="px-2 py-1.5 font-medium">{r.item ?? (r.item_id ? `#${r.item_id}` : "—")}</td><td className="px-2 py-1.5">{r.hsn_codes.join(", ") || "—"}</td>
                        <td className="px-2 py-1.5">{r.mapping_version ? `v${r.mapping_version}` : "—"}</td><td className="px-2 py-1.5">{r.by ?? "—"}</td>
                        <td className="px-2 py-1.5 whitespace-nowrap">{new Date(r.on).toLocaleString()}</td>
                    </tr>
                ))}</tbody>
            </table>
            <p className="px-2 py-1 text-[11px] text-muted-foreground">{hist.data.total} approval event(s)</p>
        </div>
    );
}

function debitRow(kind: Kind, g: MappingGroup): MappingRow {
    const n = g.records;
    const qty = `${g.quantity} ${g.units.join("/")}`.trim();
    const source = kind === "boe"
        ? `BOE ${(g.boe_numbers ?? []).slice(0, 3).join(", ")}${(g.boe_numbers?.length ?? 0) > 3 ? " …" : ""}${g.latest_boe_date ? ` · ${g.latest_boe_date}` : ""} · ${qty} · ${n} record${n === 1 ? "" : "s"}`
        : `Licence ${g.licence_numbers.slice(0, 3).join(", ")}${g.licence_count > 3 ? ` +${g.licence_count - 3}` : ""} · ${qty} · ${n} record${n === 1 ? "" : "s"}`;
    return {
        key: g.key, description: g.description, source, hsn: g.hsn_codes, sion: g.sion, recordIds: g.record_ids,
        suggestion: g.suggestion ? { name: g.suggestion.name, confidence: g.suggestion.confidence, explanation: g.suggestion.explanation } : null,
        legitimate: g.legitimate, conflicts: g.conflicts.filter((c) => g.mappable || c.code !== "SION").map((c) => c.detail),
        reviewRequired: g.mappable ? null : "No legitimate Item Name under the SION rules — configure the rule first",
        blocked: false, individualOnly: g.conflicts.some((c) => c.code === "MULTI_PRODUCT"),
    };
}

function DebitQueue({ kind }: { kind: Kind }) {
    const qc = useQueryClient();
    const label = LABEL[kind];
    const [q, setQ] = useState("");
    // search + page move together (one query key change per user action, never a stale-offset request)
    const [page, setPage] = useState<{ search: string; offset: number }>({ search: "", offset: 0 });
    const [filter, setFilter] = useState<"ALL" | "PENDING" | "CONFLICT" | "REVIEW">("ALL");
    const [choice, setChoice] = useState<Record<string, number | null>>({});
    const [selected, setSelected] = useState<string[]>([]);
    const [errors, setErrors] = useState<Record<string, string>>({});
    const { search, offset } = page;
    // Picks are keyed by the description group and kept across pages; selection and errors are per view.
    const goTo = (next: { search: string; offset: number }) => { setPage(next); setSelected([]); setErrors({}); };
    useEffect(() => {
        const term = q.trim();
        if (term === search) return undefined;
        const t = setTimeout(() => { setPage({ search: term, offset: 0 }); setSelected([]); setErrors({}); }, 300);
        return () => clearTimeout(t);
    }, [q, search]);
    const queue = useQuery({
        queryKey: ["item-name-mapping", kind, search, offset],
        placeholderData: keepPreviousData,
        queryFn: async ({ signal }) => (await api.get(`item-pivot/matching/item-name-mapping/${kind}/`, { params: { ...(search ? { q: search } : {}), offset, limit: PAGE }, signal })).data as Queue,
    });
    const masters = useQuery({
        queryKey: ["item-pivot-masters", "all"],
        queryFn: async ({ signal }) => (await api.get("item-pivot/matching/masters/", { signal })).data as { masters: Master[] },
        staleTime: 300_000,
    });
    const apply = useMutation({
        // ids are captured at click time (mutation variables), never re-read from render state
        mutationFn: async ({ entries }: { rows: MappingRow[]; entries: { record_ids: number[]; item_id: number }[] }) =>
            (await api.post(`item-pivot/matching/item-name-mapping/${kind}/apply/`, entries.length === 1 ? entries[0] : { entries })).data as { mapped: number; unchanged: number },
        onSuccess: (r, { rows }) => {
            toast.success(`${r.mapped} ${label} record(s) mapped${r.unchanged ? ` · ${r.unchanged} already mapped` : ""} — affected licences re-plan automatically`);
            setErrors((e) => { const next = { ...e }; rows.forEach((x) => delete next[x.key]); return next; });
            setChoice((c) => { const next = { ...c }; rows.forEach((x) => delete next[x.key]); return next; });
            setSelected([]);
            invalidateMappingQueries(qc);
        },
        onError: (err, { rows }) => {
            const msg = errorText(err, "Mapping failed — nothing was changed");
            setErrors((e) => ({ ...e, ...Object.fromEntries(rows.map((x) => [x.key, msg])) }));
            toast.error(msg);
        },
    });
    const rows = useMemo(() => (queue.data?.groups ?? []).map((g) => debitRow(kind, g)), [queue.data, kind])
        .filter((r) => filter === "ALL" || (filter === "PENDING" && ["PENDING", "READY"].includes(rowStatus(r, choice[r.key]))) || rowStatus(r, choice[r.key]) === filter);

    const toolbar = (
        <div className="flex flex-wrap items-center gap-2 text-xs">
            <div className="relative w-full sm:w-72"><Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" aria-hidden="true" />
                <input aria-label={`Search ${label} descriptions`} value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Original ${label} description…`} className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-2 text-sm" /></div>
            <label className="flex items-center gap-1">Show
                <select aria-label={`Filter ${label} queue`} value={filter} onChange={(e) => { setFilter(e.target.value as typeof filter); setSelected([]); }} className="h-8 rounded-md border border-input bg-background px-1.5 text-xs">
                    <option value="ALL">All pending</option><option value="PENDING">Pending / ready</option><option value="CONFLICT">Conflict</option><option value="REVIEW">Review required</option>
                </select>
            </label>
            {queue.data && <span className="text-muted-foreground">{queue.data.total_groups} pending description(s) · {queue.data.total_records} record(s){filter !== "ALL" ? " · filter applies to this page" : ""}</span>}
        </div>
    );
    if (queue.isPending) return <div className="space-y-2">{toolbar}<LoadingState variant="spinner" label={`Loading ${label} mapping queue…`} /></div>;
    if (queue.isError) return <div className="space-y-2">{toolbar}<InlineError error={queue.error as Error} title={`Could not load the ${label} queue`} onRetry={() => void queue.refetch()} /></div>;
    const data = queue.data;
    return (
        <div className="space-y-2">
            {toolbar}
            <MappingTable label={label} rows={rows} choice={choice} selected={selected} onSelect={setSelected}
                onChoose={(k, id) => { setChoice((c) => ({ ...c, [k]: id })); setErrors((e) => { const next = { ...e }; delete next[k]; return next; }); }}
                errors={errors} masters={masters.data?.masters ?? []} canApply={data.can_apply} busy={apply.isPending || queue.isPlaceholderData}
                onApprove={(rs) => apply.mutate({ rows: rs, entries: rs.map((r) => ({ record_ids: r.recordIds ?? [], item_id: choice[r.key] as number })) })} />
            {data.total_groups > PAGE && (
                <nav aria-label={`${label} queue pages`} className="flex items-center justify-end gap-2 text-xs">
                    <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => goTo({ search, offset: Math.max(0, offset - PAGE) })}><ChevronLeft className="size-3.5" />Previous</Button>
                    <span className="tabular-nums">{offset + 1}–{Math.min(offset + PAGE, data.total_groups)} of {data.total_groups}</span>
                    <Button size="sm" variant="outline" disabled={offset + PAGE >= data.total_groups} onClick={() => goTo({ search, offset: offset + PAGE })}>Next<ChevronRight className="size-3.5" /></Button>
                </nav>
            )}
        </div>
    );
}

/** Pending | Approved history switch + the Item Name master link, identical on all three tabs. */
function SourceTab({ kind, children }: { kind: "import" | Kind; children: ReactNode }) {
    const [view, setView] = useState<"pending" | "approved">("pending");
    const name = kind === "import" ? "Licence import item" : kind === "boe" ? "BOE" : "Allotment";
    return (
        <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-xs">
                <div role="group" aria-label={`${name} view`} className="inline-flex rounded-md border border-border p-0.5">
                    <Button size="sm" variant={view === "pending" ? "default" : "ghost"} aria-pressed={view === "pending"} onClick={() => setView("pending")}>Pending</Button>
                    <Button size="sm" variant={view === "approved" ? "default" : "ghost"} aria-pressed={view === "approved"} onClick={() => setView("approved")}>Approved history</Button>
                </div>
                <Link to="/masters/item-names" className="ml-auto text-primary hover:underline">Item Name missing? Create it in Masters → Item Names</Link>
            </div>
            {view === "approved" ? <HistoryTable kind={kind} /> : children}
        </div>
    );
}

export default function MappingWorkspace() {
    const [tab, setTab] = useState("import");
    const counts = useQuery({
        queryKey: ["item-name-mapping-counts"],
        queryFn: async ({ signal }) => (await api.get("item-pivot/matching/item-name-mapping/counts/", { signal })).data as Counts,
        staleTime: 30_000,
    });
    const n = (k: keyof Counts) => (counts.data ? ` (${counts.data[k].descriptions})` : "");
    return (
        <>
            <PageHeader title="Mapping" description="Map original source descriptions to existing Item Names — the same master Item Pivot and Licence Planning use. Suggestions are never approvals; descriptions, quantities, CIF and debits are never changed." />
            <div className="space-y-3">
                <DetailTabs recordKey="mapping-workspace" value={tab} onValueChange={setTab} ariaLabel="Mapping sources"
                    tabs={[
                        { id: "import", label: `Licence Import Item${n("import")}`, render: () => <DescriptionMapping /> },
                        { id: "boe", label: `BOE${n("boe")}`, render: () => <SourceTab kind="boe"><DebitQueue kind="boe" /></SourceTab> },
                        { id: "allotment", label: `Allotment${n("allotment")}`, render: () => <SourceTab kind="allotment"><DebitQueue kind="allotment" /></SourceTab> },
                    ]} />
                <details className="rounded-lg border border-border/70 bg-card px-3 py-2 text-xs">
                    <summary className="cursor-pointer font-semibold">Mapping versions &amp; re-planning status</summary>
                    <div className="pt-2"><MappingChanges /></div>
                </details>
            </div>
        </>
    );
}
