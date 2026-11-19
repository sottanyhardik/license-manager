/**
 * One simple mapping table for all three Mapping tabs (Licence Import Item · BOE · Allotment).
 *
 * Business rule (owner spec 2026-11-19): a suggested Item Name is a reference only. Selectors start empty, a
 * suggestion never satisfies the selection requirement, and bulk approval is enabled only when EVERY selected row has
 * its own explicitly selected Item Name id. The server re-validates every row atomically.
 */
import { Fragment, useEffect, useId, useRef } from "react";
import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState, StatusBadge } from "@/components/shared";

import ItemNameSelect, { type Master } from "./ItemNameSelect";
import { approvable, rowStatus, STATUS, type MappingRow } from "./mappingRow";

export default function MappingTable({ label, rows, choice, onChoose, selected, onSelect, errors, masters, canApply, busy, onApprove, expanded, onExpand, bulk = true }: {
    label: string; rows: MappingRow[]; choice: Record<string, number | null>; onChoose: (key: string, id: number | null) => void;
    selected: string[]; onSelect: (keys: string[]) => void; errors: Record<string, string>; masters: Master[]; canApply: boolean; busy: boolean;
    onApprove: (rows: MappingRow[]) => void; expanded?: string | null; onExpand?: (key: string | null) => void;
    /** Row checkboxes + "Approve selected" (BOE / Allotment). Off → exactly the seven spec columns (Licence Import Item). */
    bulk?: boolean;
}) {
    const uid = useId();
    const selectable = rows.filter((r) => !r.reviewRequired);
    const chosen = rows.filter((r) => selected.includes(r.key));
    const missing = chosen.filter((r) => !approvable(r, choice[r.key]));
    const individual = chosen.length > 1 ? chosen.filter((r) => r.individualOnly) : [];
    const hint = !chosen.length ? "" : missing.length
        ? `${missing.length} selected row(s) have no Item Name selected — select one for every row (suggestions do not count)`
        : individual.length ? `${individual.length} selected row(s) name several products — approve those individually` : "";
    const select = canApply && bulk;
    const cols = (canApply ? 7 : 5) + (select ? 1 : 0);
    const allBox = useRef<HTMLInputElement>(null);
    const allChecked = selectable.length > 0 && selectable.every((r) => selected.includes(r.key));
    useEffect(() => {
        if (allBox.current) allBox.current.indeterminate = chosen.length > 0 && !allChecked;
    }, [chosen.length, allChecked]);
    const errId = (i: number) => `${uid}-err-${i}`;
    return (
        <div className="space-y-2">
            {select && (
                <div className="flex flex-wrap items-center justify-end gap-2 text-xs">
                    <span id={`${uid}-hint`} role="status" aria-live="polite" className="text-amber-700 dark:text-amber-400">{hint}</span>
                    <Button size="sm" disabled={!chosen.length || missing.length > 0 || individual.length > 0 || busy} aria-describedby={`${uid}-hint`} onClick={() => onApprove(chosen)}>
                        <Check className="size-3.5" />Approve selected ({chosen.length})
                    </Button>
                </div>
            )}
            <div className="max-h-[65vh] overflow-auto rounded-lg border border-border/70">
                <table className="w-full min-w-[1080px] text-xs" aria-label={`Pending ${label} mappings`} aria-busy={busy || undefined}>
                    <thead><tr className="sticky top-0 z-[1] bg-muted text-left text-[11px] uppercase text-muted-foreground">
                        {select && <th scope="col" className="w-8 px-2 py-2">
                            <input ref={allBox} type="checkbox" aria-label={`Select all approvable ${label} rows`} checked={allChecked} disabled={!selectable.length}
                                onChange={(e) => onSelect(e.target.checked ? selectable.map((r) => r.key) : [])} />
                        </th>}
                        <th scope="col" className="px-2 py-2">Original Item Description</th>
                        <th scope="col" className="px-2">HSN</th>
                        <th scope="col" className="px-2">SION</th>
                        <th scope="col" className="px-2">Suggested Item Name</th>
                        {canApply && <th scope="col" className="px-2">Select Item Name</th>}
                        <th scope="col" className="px-2">Status</th>
                        {canApply && <th scope="col" className="px-2">{bulk ? <span className="sr-only">Action</span> : "Action"}</th>}
                    </tr></thead>
                    <tbody>{rows.map((r, i) => {
                        const pick = choice[r.key] ?? null;
                        const status = rowStatus(r, pick);
                        const isOpen = expanded === r.key;
                        return (
                            <Fragment key={r.key}>
                                <tr className="border-t border-border/50 align-top">
                                    {select && <td className="px-2 py-1.5"><input type="checkbox" aria-label={`Select ${r.description || r.key}`} checked={selected.includes(r.key)} disabled={!!r.reviewRequired}
                                        onChange={(e) => onSelect(e.target.checked ? [...selected, r.key] : selected.filter((k) => k !== r.key))} /></td>}
                                    <th scope="row" className="max-w-[26rem] px-2 py-1.5 text-left font-normal">
                                        <span className="font-medium">{r.description || <span className="italic text-muted-foreground">(no description)</span>}</span>
                                        <div className="text-[10px] text-muted-foreground">{r.source}</div>
                                        {r.conflicts.map((c, n) => <div key={n} className="mt-0.5 text-[11px] text-amber-700 dark:text-amber-400">{c}</div>)}
                                        {r.reviewRequired && <div className="mt-0.5 text-[11px] text-destructive">{r.reviewRequired}</div>}
                                    </th>
                                    <td className="px-2 py-1.5 font-mono">{r.hsn.slice(0, 3).join(", ") || "—"}</td>
                                    <td className="px-2 py-1.5">{r.sion.join(", ") || "—"}</td>
                                    <td className="max-w-[16rem] px-2 py-1.5" title={r.suggestion?.explanation}>
                                        {r.suggestion?.name ? <><span>{r.suggestion.name}</span>{r.suggestion.confidence != null && <span className="ml-1 tabular-nums text-muted-foreground">{r.suggestion.confidence}%</span>}
                                            <div className="text-[10px] text-muted-foreground">Suggestion only — select below</div></> : <span className="text-muted-foreground">—</span>}
                                    </td>
                                    {canApply && <td className="px-2 py-1.5">
                                        {r.reviewRequired ? <span className="text-muted-foreground">—</span>
                                            : <ItemNameSelect label={r.description || r.key} value={pick} onChange={(id) => onChoose(r.key, id)} legitimate={r.legitimate} masters={masters}
                                                describedBy={errors[r.key] ? errId(i) : undefined} />}
                                        {errors[r.key] && <div role="alert" id={errId(i)} className="mt-0.5 max-w-[22rem] text-[11px] text-destructive">{errors[r.key]}</div>}
                                    </td>}
                                    <td className="px-2 py-1.5"><StatusBadge tone={STATUS[status].tone} label={STATUS[status].label} /></td>
                                    {canApply && <td className="px-2 py-1.5 text-right">
                                        {r.review && onExpand
                                            ? <Button size="sm" variant="outline" aria-expanded={isOpen} aria-label={`${isOpen ? "Hide" : "Review"} products of ${r.description || r.key}`}
                                                onClick={() => onExpand(isOpen ? null : r.key)}>{isOpen ? "Hide review" : "Review products"}</Button>
                                            : <Button size="sm" disabled={!approvable(r, pick) || busy} aria-describedby={errors[r.key] ? errId(i) : undefined}
                                                aria-label={`Approve ${r.description || r.key}`} onClick={() => onApprove([r])}><Check className="size-3.5" />Approve</Button>}
                                    </td>}
                                </tr>
                                {r.review && isOpen && <tr className="bg-muted/20"><td colSpan={cols} className="px-4 py-3">{r.review}</td></tr>}
                            </Fragment>
                        );
                    })}</tbody>
                </table>
                {!rows.length && <EmptyState title="Nothing pending" description={`No pending ${label} descriptions for this filter.`} />}
            </div>
            <p className="text-[11px] text-muted-foreground">Suggestions are references only. Select the actual Item Name for every row you approve; the server re-validates each one.</p>
        </div>
    );
}
