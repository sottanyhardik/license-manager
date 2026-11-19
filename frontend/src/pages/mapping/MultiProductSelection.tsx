/**
 * Multi-product selection for one source description (owner spec 2026-11-19).
 *
 * Each detected product is reviewed on its own: the reviewer ticks the products that belong to the final
 * classification, may change each one's canonical master or add a product manually, and approves. Nothing is
 * pre-selected except products already approved for this record. The server re-validates every selection
 * (SION, HSN, entitlement, duplicates) and approves nothing that fails; the record's shared quantity / CIF is
 * never attributed to the products.
 */
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import api from "@/api/axios";
import { Button } from "@/components/ui/button";
import { StatusBadge, type Tone } from "@/components/shared";
import { cn } from "@/lib/utils";
import { invalidateMappingQueries } from "./invalidate";
import { errorText, type DetectedProduct, type MatchSuggestion, type SelectionResult } from "./matchingShared";

type Choice = { key: string; index: number | null; phrase: string; itemId: number | null };
const BAND_TONE: Record<DetectedProduct["band"], Tone> = { HIGH: "primary", REVIEW: "warning", LOW: "neutral", CONFLICT: "danger", UNMATCHED: "neutral" };

const defaultChoice = (s: DetectedProduct): Choice => ({ key: `seg-${s.index}`, index: s.index, phrase: s.phrase, itemId: s.approved?.item_id ?? s.suggestion?.item_id ?? null });
const samePhrase = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

export default function MultiProductSelection({ suggestion, filters, canApprove }: { suggestion: MatchSuggestion; filters: Record<string, string>; canApprove: boolean }) {
    const qc = useQueryClient();
    const segments = useMemo(() => suggestion.segments ?? [], [suggestion.segments]);
    // Overrides only; rows are always derived from the current segments, so a refetch can never leave a hole.
    const [choices, setChoices] = useState<Record<string, Choice>>({});
    const manualSeq = useRef(0);
    const [selected, setSelected] = useState<Set<string>>(() => new Set(segments.filter((s) => s.approved).map((s) => `seg-${s.index}`)));
    const [manual, setManual] = useState<Choice[]>([]);
    const [newPhrase, setNewPhrase] = useState("");
    const [masterQuery, setMasterQuery] = useState("");
    const [rejected, setRejected] = useState<SelectionResult[] | null>(null);
    const masters = useQuery({
        queryKey: ["item-pivot-masters", suggestion.sion],
        enabled: canApprove && !!suggestion.sion,
        queryFn: async ({ signal }) => (await api.get("item-pivot/matching/masters/", { params: { sion: suggestion.sion }, signal })).data as { masters: { item_id: number; name: string }[] },
        staleTime: 300_000,
    });
    const allMasters = masters.data?.masters ?? [];
    const searchable = masterQuery ? allMasters.filter((m) => m.name.toLowerCase().includes(masterQuery.toLowerCase())) : allMasters;
    const choiceOf = (s: DetectedProduct) => choices[`seg-${s.index}`] ?? defaultChoice(s);
    const rows = [...segments.map(choiceOf), ...manual];
    const segmentOf = (c: Choice) => (c.index != null ? segments.find((s) => s.index === c.index) : undefined);
    // Server compatibility was computed for the SUGGESTED master — a changed master is unvalidated until approval.
    const isChanged = (s: DetectedProduct) => choiceOf(s).itemId !== (s.approved?.item_id ?? s.suggestion?.item_id ?? null);
    const compatibleKeys = segments.filter((s) => s.compatible && s.suggestion && !isChanged(s)).map((s) => `seg-${s.index}`);
    const approvedCount = segments.filter((s) => s.approved).length;
    const blocking = segments.filter((s) => s.conflicts.length > 0).length;
    const needsReview = segments.filter((s) => s.conflicts.length > 0 || s.band !== "HIGH").length;
    const selectedDetected = segments.filter((s) => selected.has(`seg-${s.index}`)).length;

    const toggle = (key: string) => setSelected((prev) => { const next = new Set(prev); if (next.has(key)) next.delete(key); else next.add(key); return next; });
    const setItem = (c: Choice, itemId: number | null) => {
        setRejected(null);
        if (c.index != null) setChoices((prev) => ({ ...prev, [c.key]: { ...c, itemId } }));
        else setManual((prev) => prev.map((m) => (m.key === c.key ? { ...m, itemId } : m)));
    };
    const addManual = () => {
        const phrase = newPhrase.trim();
        if (!phrase) return;
        if (rows.some((r) => samePhrase(r.phrase, phrase))) {
            toast.error(`'${phrase}' is already listed — select that row instead`);
            return;
        }
        manualSeq.current += 1;
        const key = `manual-${manualSeq.current}`;
        setManual((prev) => [...prev, { key, index: null, phrase, itemId: null }]);
        setSelected((prev) => new Set(prev).add(key));
        setNewPhrase("");
    };
    const removeManual = (key: string) => {
        setManual((prev) => prev.filter((m) => m.key !== key));
        setSelected((prev) => { const next = new Set(prev); next.delete(key); return next; });
    };

    const submit = useMutation({
        mutationFn: async (mode: "all" | "partial" | "clear") => {
            const selections = mode === "clear" ? [] : rows.filter((c) => selected.has(c.key)).map((c) => (c.index != null ? { index: c.index, item_id: c.itemId } : { phrase: c.phrase, item_id: c.itemId }));
            const extra = mode === "partial" ? { partial: true } : mode === "clear" ? { clear: true } : {};
            return (await api.post("item-pivot/matching/decide-products/", { source_key: suggestion.source_key, selections, filters, ...extra })).data as { results: SelectionResult[]; created: number[]; revoked: number[] };
        },
        onSuccess: (data, mode) => {
            const failed = data.results.filter((r) => !r.ok);
            setRejected(failed.length ? failed : null);
            if (mode === "clear") toast.success(`Approved classification removed (${data.revoked.length} product(s))`);
            else toast.success(`Classification saved — ${data.results.length - failed.length} product(s) approved${data.revoked.length ? `, ${data.revoked.length} deselected` : ""}`);
            if (failed.length) toast.warning(`Not approved: ${failed.map((f) => `${f.phrase} (${f.reasons[0] ?? "invalid"})`).join("; ")}`, { duration: 12_000 });
            invalidateMappingQueries(qc);
        },
        onError: (err: unknown) => {
            const results = (err as { response?: { data?: { results?: SelectionResult[] } } })?.response?.data?.results;
            setRejected(results ? results.filter((r) => !r.ok) : null);
            toast.error(errorText(err, "Classification failed"));
        },
    });
    const pendingSelections = rows.filter((c) => selected.has(c.key));
    const missingMaster = pendingSelections.some((c) => c.itemId == null);
    const compatibleAfterRejection = rejected ? pendingSelections.length - rejected.length : 0;

    return (
        <section aria-label={`Products detected in ${suggestion.description}`} className="space-y-2 rounded-md border border-border/70 bg-card p-2">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs" role="status" aria-label="Selection summary">
                <span className="font-semibold">Multi-product description — select the products that belong to the final classification</span>
                <span>Detected <strong>{segments.length}</strong></span>
                <span>Selected <strong>{pendingSelections.length}</strong></span>
                <span>Compatible <strong>{compatibleKeys.length}</strong></span>
                <span>Excluded <strong>{segments.length - selectedDetected}</strong></span>
                <span>Requiring review <strong>{needsReview}</strong></span>
                <span>Blocking conflicts <strong>{blocking}</strong></span>
            </div>
            <p className="text-[11px] text-muted-foreground">The record has one shared quantity / CIF: approved products are a classification only — the amount is not split between them and the master links used by Auto Plan are not changed.</p>

            <div className="overflow-x-auto">
                <table className="w-full min-w-[960px] text-xs" aria-label="Detected products">
                    <thead><tr className="text-left text-[11px] uppercase text-muted-foreground"><th scope="col" className="px-1.5 py-1"><span className="sr-only">Select</span></th><th scope="col" className="px-1.5">Detected product</th><th scope="col" className="px-1.5">Canonical product</th><th scope="col" className="px-1.5 text-right" title="Deterministic text score — not a probability">Match score</th><th scope="col" className="px-1.5">HSN</th><th scope="col" className="px-1.5">SION</th><th scope="col" className="px-1.5">Entitlement</th><th scope="col" className="px-1.5">Status / explanation</th></tr></thead>
                    <tbody>{rows.map((c) => {
                        const seg = segmentOf(c);
                        // Candidates first, then the masters matching the search box (the current choice always stays listed).
                        const options = [...(seg?.candidates ?? []), ...searchable, ...allMasters.filter((m) => m.item_id === c.itemId)].filter((o, i, all) => all.findIndex((x) => x.item_id === o.item_id) === i);
                        const changed = seg && c.itemId != null && c.itemId !== seg.suggestion?.item_id;
                        const rejection = rejected?.find((r) => (c.index != null ? r.index === c.index : r.index == null && samePhrase(r.phrase, c.phrase)));
                        return (
                            <tr key={c.key} className={cn("border-t border-border/40 align-top", selected.has(c.key) && "bg-primary/5", rejection && "bg-destructive/5")}>
                                <td className="px-1.5 py-1"><input type="checkbox" aria-label={`Select ${c.phrase}`} checked={selected.has(c.key)} disabled={!canApprove} onChange={() => { setRejected(null); toggle(c.key); }} /></td>
                                <td className="px-1.5 py-1 font-medium">{c.phrase}{c.index == null && <div className="text-[10px] font-normal text-muted-foreground">added manually {canApprove && <button type="button" className="ml-1 inline-flex items-center text-destructive" aria-label={`Remove ${c.phrase}`} onClick={() => removeManual(c.key)}><Trash2 className="size-3" aria-hidden="true" /></button>}</div>}{seg?.approved && <div className="text-[10px] font-normal text-success">approved → {seg.approved.name}</div>}</td>
                                <td className="px-1.5 py-1">
                                    <select aria-label={`Canonical product for ${c.phrase}`} disabled={!canApprove} value={c.itemId ?? ""} onChange={(e) => setItem(c, e.target.value ? Number(e.target.value) : null)} className="h-7 max-w-[14rem] rounded-md border border-input bg-background px-1.5 text-xs">
                                        <option value="">— choose —</option>
                                        {options.map((o) => <option key={o.item_id} value={o.item_id}>{o.name}{"score" in o && o.score != null ? ` (${o.score}%)` : ""}</option>)}
                                    </select>
                                    {changed && <div className="text-[10px] text-amber-600">changed from {seg?.suggestion?.name ?? "no suggestion"} — not yet validated (checked on approval)</div>}
                                </td>
                                <td className="px-1.5 py-1 text-right tabular-nums">{seg?.suggestion ? `${seg.confidence}%` : "—"}</td>
                                <td className="px-1.5 py-1 font-mono">{suggestion.hsn_code || "—"}</td>
                                <td className={cn("px-1.5 py-1", seg?.checks.sion && (seg.checks.sion.ok ? "text-success" : "text-destructive"))}>{seg?.checks.sion ? (seg.checks.sion.ok ? "✓" : "✗") : ""} {suggestion.sion ?? "—"}</td>
                                <td className={cn("px-1.5 py-1", seg?.checks.entitlement && !seg.checks.entitlement.ok && "text-destructive")}>{seg?.entitlement ?? "—"}</td>
                                <td className="max-w-[22rem] px-1.5 py-1">
                                    {seg ? <StatusBadge tone={BAND_TONE[seg.band]} label={seg.band === "CONFLICT" ? "Conflict" : seg.band === "UNMATCHED" ? "No candidate" : seg.band === "HIGH" ? "Strong" : seg.band === "REVIEW" ? "Review" : "Low"} /> : <StatusBadge tone="neutral" label="Manual" />}
                                    {seg && <div className="mt-0.5 text-[11px] text-muted-foreground">{seg.explanation}</div>}
                                    {seg?.conflicts.map((x) => <div key={x} className="text-[11px] text-destructive">{x}</div>)}
                                    {rejection && <ul aria-label={`Rejected: ${c.phrase}`} className="mt-0.5 list-disc pl-4 text-[11px] text-destructive">{rejection.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
                                </td>
                            </tr>
                        );
                    })}</tbody>
                </table>
            </div>

            {canApprove && (
                <div className="flex flex-wrap items-center gap-2">
                    <Button size="sm" variant="outline" disabled={!compatibleKeys.length} onClick={() => { setRejected(null); setSelected((prev) => new Set([...prev, ...compatibleKeys])); }}>Select all compatible ({compatibleKeys.length})</Button>
                    <Button size="sm" variant="ghost" disabled={!selected.size} onClick={() => { setRejected(null); setSelected(new Set()); }}>Clear selection</Button>
                    <span className="mx-1 h-5 w-px bg-border" aria-hidden="true" />
                    <input aria-label="Add a product manually" value={newPhrase} onChange={(e) => setNewPhrase(e.target.value)} placeholder="Add product…" className="h-7 w-40 rounded-md border border-input bg-background px-2 text-xs" />
                    <Button size="sm" variant="ghost" disabled={!newPhrase.trim()} onClick={addManual}><Plus className="size-3.5" />Add</Button>
                    <input aria-label="Search canonical masters" value={masterQuery} onChange={(e) => setMasterQuery(e.target.value)} placeholder={`Search ${suggestion.sion ?? ""} masters…`} className="h-7 w-44 rounded-md border border-input bg-background px-2 text-xs" />
                    {masterQuery && <span className="text-[11px] text-muted-foreground">{searchable.length} matching master(s) listed in the product selectors</span>}
                    {masters.isError && <span className="text-[11px] text-destructive">Masters could not be loaded — only suggested candidates are available</span>}
                    <Button size="sm" className="ml-auto" disabled={!pendingSelections.length || missingMaster || submit.isPending} title={missingMaster ? "Choose a canonical product for every selected row" : undefined}
                        onClick={() => submit.mutate("all")}><Check className="size-3.5" />Approve selected ({pendingSelections.length})</Button>
                    {approvedCount > 0 && pendingSelections.length === 0 && (
                        <Button size="sm" variant="outline" disabled={submit.isPending} onClick={() => { if (window.confirm("Remove the approved classification of this record? Every product approval is revoked (audited).")) submit.mutate("clear"); }}>Remove approved classification ({approvedCount})</Button>
                    )}
                </div>
            )}
            {rejected && rejected.length > 0 && (
                <div role="alert" className="flex flex-wrap items-center gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-2 py-1.5 text-xs">
                    <span><strong>{rejected.length}</strong> selected product(s) failed validation — nothing was approved for them. Fix or deselect them, or approve only the compatible ones.</span>
                    {canApprove && compatibleAfterRejection > 0 && <Button size="sm" variant="outline" disabled={submit.isPending} onClick={() => submit.mutate("partial")}>Approve the {compatibleAfterRejection} compatible only</Button>}
                </div>
            )}
        </section>
    );
}
