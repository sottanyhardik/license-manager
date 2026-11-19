/** Nested filter-condition builder for the mapping tables (licence import descriptions, BOE / allotment names) — same layout and interaction as the
 *  Licence Planning rule builder (`pages/planning/ExpressionTreeEditor`): a root group, nested groups with their own
 *  ALL / ANY logic, + Condition / + Group, remove (populated groups ask first), indentation per level.
 *  Filters only select rows; matching is evaluated on the server (one implementation for the table and bulk updates). */
import { useState } from "react";
import { ChevronDown, ChevronRight, Plus, Trash2, X } from "lucide-react";

import { ConfirmDialog } from "@/components/shared";
import { Button } from "@/components/ui/button";

import {
    blank, blankGroup, countConditions, EMPTY_FILTERS, FIELD_LABEL, isGroup, MAX_DEPTH, NO_VALUE, OP_LABEL, sameFilters, stripIds, validFilters, withIds,
    type Condition, type FilterField, type FilterGroup, type FilterOp, type Filters,
} from "./filterModel";

/** Field → label of the fields a table can filter on (default: description, HSN, SION). */
export type FieldLabels = Partial<Record<FilterField, string>>;
type GroupProps = { group: FilterGroup; onChange: (g: FilterGroup) => void; depth: number; path: string; onRemove?: () => void; labels: FieldLabels };

function GroupNode({ group, onChange, depth, path, onRemove, labels }: GroupProps) {
    const isRoot = depth === 0;
    const [expanded, setExpanded] = useState(true);
    const [confirm, setConfirm] = useState(false);
    const count = countConditions(group);
    const replace = (index: number, node: Condition | FilterGroup) => onChange({ ...group, conditions: group.conditions.map((c, i) => (i === index ? node : c)) });
    const removeAt = (index: number) => onChange({ ...group, conditions: group.conditions.filter((_, i) => i !== index) });
    const label = isRoot ? "Root filter group" : `Filter group ${path}`;
    return (
        <div className={isRoot ? "space-y-2" : "border-l border-border pl-3"} data-filter-group={isRoot ? "root" : "nested"} role="group" aria-label={label}>
            <div className="flex min-h-9 flex-wrap items-center gap-2 rounded-md bg-muted/45 px-2 py-1">
                {!isRoot && <Button type="button" variant="ghost" size="icon" className="size-7 shrink-0" aria-expanded={expanded}
                    aria-label={`${expanded ? "Collapse" : "Expand"} ${label}`} onClick={() => setExpanded((e) => !e)}>
                    {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}</Button>}
                <select aria-label={`${label} logic`} value={group.operator} onChange={(e) => onChange({ ...group, operator: e.target.value as FilterGroup["operator"] })}
                    className="h-8 rounded-md border bg-background px-2 text-xs font-semibold">
                    <option value="AND">ALL (AND)</option><option value="OR">ANY (OR)</option>
                </select>
                <span className="text-xs text-muted-foreground">{count} {count === 1 ? "condition" : "conditions"}</span>
                <div className="ml-auto flex items-center gap-1">
                    <Button type="button" size="sm" variant="ghost" className="h-8" aria-label={`Add condition to ${label}`}
                        onClick={() => onChange({ ...group, conditions: [...group.conditions, blank()] })}><Plus className="size-3.5" />Condition</Button>
                    <Button type="button" size="sm" variant="ghost" className="h-8" aria-label={`Add group to ${label}`} disabled={depth + 1 >= MAX_DEPTH}
                        onClick={() => onChange({ ...group, conditions: [...group.conditions, blankGroup()] })}><Plus className="size-3.5" />Group</Button>
                    {!isRoot && <Button type="button" size="icon" variant="ghost" className="size-8 text-muted-foreground hover:text-destructive" aria-label={`Remove ${label}`}
                        onClick={() => (group.conditions.length ? setConfirm(true) : onRemove?.())}><Trash2 className="size-4" /></Button>}
                </div>
            </div>
            {(isRoot || expanded) && (
                <div className="space-y-2">
                    {group.conditions.map((node, index) => {
                        const childPath = isRoot ? `${index + 1}` : `${path}.${index + 1}`;
                        if (isGroup(node)) return <GroupNode key={node.id ?? `g${index}`} group={node} labels={labels} depth={depth + 1} path={childPath} onChange={(next) => replace(index, next)} onRemove={() => removeAt(index)} />;
                        const name = `Condition ${childPath}`;
                        return (
                            <div key={node.id ?? `c${index}`} className="grid min-h-10 items-center gap-2 border-l border-border pl-3 sm:grid-cols-[minmax(150px,0.9fr)_minmax(150px,0.9fr)_minmax(180px,1.5fr)_32px]">
                                <select aria-label={`${name} field`} value={node.field} onChange={(e) => replace(index, { ...node, field: e.target.value as FilterField })} className="h-9 rounded-md border bg-background px-2 text-sm">
                                    {(Object.keys(labels) as FilterField[]).map((f) => <option key={f} value={f}>{labels[f]}</option>)}
                                </select>
                                <select aria-label={`${name} operator`} value={node.op} onChange={(e) => replace(index, { ...node, op: e.target.value as FilterOp })} className="h-9 rounded-md border bg-background px-2 text-sm">
                                    {(Object.keys(OP_LABEL) as FilterOp[]).map((o) => <option key={o} value={o}>{OP_LABEL[o]}</option>)}
                                </select>
                                {NO_VALUE.includes(node.op) ? <span className="text-xs text-muted-foreground">no value needed</span>
                                    : <input aria-label={`${name} value`} value={node.value} maxLength={200} onChange={(e) => replace(index, { ...node, value: e.target.value })}
                                        placeholder={node.field === "description" ? "e.g. DIETARY" : node.field === "hsn" ? "e.g. 0802" : "e.g. E126"} className="h-9 min-w-0 rounded-md border bg-background px-2 text-sm" />}
                                <Button type="button" size="icon" variant="ghost" className="size-8 text-muted-foreground hover:text-destructive" aria-label={`Remove ${name}`} onClick={() => removeAt(index)}>
                                    <X className="size-4" /></Button>
                            </div>
                        );
                    })}
                    {!group.conditions.length && <div className="rounded-md border border-dashed px-3 py-3 text-center text-xs text-muted-foreground">
                        {isRoot ? "No filter conditions — every description is shown." : "Empty group — it is ignored when the filter is applied."}</div>}
                </div>
            )}
            <ConfirmDialog open={confirm} onOpenChange={setConfirm} title="Remove populated group?" description="This removes the group and every condition or nested group inside it."
                confirmLabel="Remove Group" tone="danger" onConfirm={() => { onRemove?.(); setConfirm(false); }} />
        </div>
    );
}

export default function FilterConditions({ applied, onApply, labels = FIELD_LABEL }: { applied: Filters; onApply: (f: Filters) => void; labels?: FieldLabels }) {
    const [open, setOpen] = useState(applied.conditions.length > 0);
    const [draft, setDraft] = useState<Filters>(() => withIds(applied));
    const valid = validFilters(draft);
    const total = countConditions(applied);
    return (
        <section aria-label="Filter conditions" className="rounded-lg border border-border/70 bg-card px-3 py-2 text-xs">
            <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="flex items-center gap-1 font-semibold">
                {open ? <ChevronDown className="size-3.5" aria-hidden="true" /> : <ChevronRight className="size-3.5" aria-hidden="true" />}
                Filter Conditions{total ? ` (${total} applied)` : ""}
            </button>
            {open && (
                <div className="mt-2 space-y-2">
                    <GroupNode group={draft} depth={0} path="" onChange={setDraft} labels={labels} />
                    <div className="flex flex-wrap items-center gap-1.5">
                        <Button size="sm" disabled={!valid} onClick={() => onApply(stripIds(draft))}>Apply Filters</Button>
                        <Button size="sm" variant="ghost" disabled={!draft.conditions.length && !applied.conditions.length} onClick={() => { setDraft(EMPTY_FILTERS); onApply(EMPTY_FILTERS); }}>Clear Filters</Button>
                        {!valid && <span className="text-destructive">Every condition needs a value (except Is Empty / Is Not Empty).</span>}
                        {valid && !sameFilters(draft, applied) && <span role="status" className="text-amber-700 dark:text-amber-400">Unapplied changes — click Apply Filters.</span>}
                    </div>
                </div>
            )}
        </section>
    );
}
