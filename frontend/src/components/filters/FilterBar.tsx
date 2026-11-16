import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { Tone } from "@/components/shared/tone";
import { TONE_MAP } from "@/components/shared/tone";

export type FilterValue = string | number | string[] | undefined;
export type FilterValues = Record<string, FilterValue>;

export interface FilterOption { value: string; label: string }

export type FilterDef =
    | { kind: "text"; key: string; label: string; placeholder?: string }
    | { kind: "select"; key: string; label: string; options: FilterOption[] }
    | { kind: "multiSelect"; key: string; label: string; options: FilterOption[] }
    | { kind: "status"; key: string; label: string; options: (FilterOption & { tone: Tone })[] }
    | { kind: "dateRange"; key: string; label: string }
    | { kind: "numberRange"; key: string; label: string; min?: number; max?: number; step?: number };

export interface FilterBarProps {
    defs: FilterDef[];
    /** Applied filters, owned by the caller (URL / useListQuery). */
    value: FilterValues;
    /** Reset target (module defaults). Defaults to empty. */
    defaults?: FilterValues;
    onApply: (next: FilterValues) => void;
    /** 'instant' emits on change (text debounced); 'explicit' shows Apply. Default 'explicit'. */
    applyMode?: "instant" | "explicit";
    ariaLabel?: string;
    textDebounceMs?: number;
}

const isEmpty = (v: FilterValue): boolean =>
    v === undefined || v === "" || (Array.isArray(v) && v.length === 0);

/** Drops empty entries so emitted objects only contain active params. */
export function compactFilters(values: FilterValues): FilterValues {
    const out: FilterValues = {};
    for (const [k, v] of Object.entries(values)) if (!isEmpty(v)) out[k] = v;
    return out;
}

/** Param keys each def owns (preserves existing backend param names). */
export function keysOf(def: FilterDef): string[] {
    if (def.kind === "dateRange") return [`${def.key}_from`, `${def.key}_to`];
    if (def.kind === "numberRange") return [`${def.key}_min`, `${def.key}_max`];
    return [def.key];
}

const str = (v: FilterValue): string => (v === undefined || Array.isArray(v) ? "" : String(v));
const arr = (v: FilterValue): string[] => (Array.isArray(v) ? v : v === undefined || v === "" ? [] : [String(v)]);

const FIELD = "flex min-w-[10rem] flex-col gap-1 text-xs font-medium text-muted-foreground";
const SELECT_CLS = "h-10 rounded-lg border border-input bg-card px-3 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/30";

/** Declarative filter form. No data fetching; value is a plain object synced by the caller. */
export function FilterBar({ defs, value, defaults = {}, onApply, applyMode = "explicit", ariaLabel = "Filters", textDebounceMs = 300 }: FilterBarProps) {
    const uid = useId();
    const [draft, setDraft] = useState<FilterValues>(value);
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => { setDraft(value); }, [value]);
    useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

    const instant = applyMode === "instant";

    const change = (patch: FilterValues, debounced = false) => {
        const next = compactFilters({ ...draft, ...patch });
        setDraft(next);
        if (!instant) return;
        if (timer.current) clearTimeout(timer.current);
        if (debounced) timer.current = setTimeout(() => onApply(next), textDebounceMs);
        else onApply(next);
    };

    const clearField = (def: FilterDef) => {
        const patch: FilterValues = {};
        for (const k of keysOf(def)) patch[k] = undefined;
        change(patch);
    };

    const reset = () => {
        if (timer.current) clearTimeout(timer.current);
        const next = compactFilters(defaults);
        setDraft(next);
        onApply(next);
    };

    const activeCount = defs.filter((d) => keysOf(d).some((k) => !isEmpty(value[k]))).length;

    return (
        <form
            role="search"
            aria-label={ariaLabel}
            onSubmit={(e) => {
                e.preventDefault();
                if (!instant) onApply(compactFilters(draft));
            }}
            className="flex flex-wrap items-end gap-3"
        >
            {defs.map((def) => {
                const id = `${uid}-${def.key}`;
                const hasValue = keysOf(def).some((k) => !isEmpty(draft[k]));
                const clear = hasValue && (
                    <button type="button" aria-label={`Clear ${def.label}`} onClick={() => clearField(def)}
                        className="self-start text-xs text-muted-foreground underline hover:text-foreground cursor-pointer">
                        Clear
                    </button>
                );

                switch (def.kind) {
                    case "text":
                        return (
                            <div key={def.key} className={FIELD}>
                                <label htmlFor={id}>{def.label}</label>
                                <Input id={id} value={str(draft[def.key])} placeholder={def.placeholder}
                                    onChange={(e) => change({ [def.key]: e.target.value }, true)} />
                                {clear}
                            </div>
                        );
                    case "select":
                        return (
                            <div key={def.key} className={FIELD}>
                                <label htmlFor={id}>{def.label}</label>
                                <select id={id} className={SELECT_CLS} value={str(draft[def.key])}
                                    onChange={(e) => change({ [def.key]: e.target.value })}>
                                    <option value="">All</option>
                                    {def.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                                </select>
                                {clear}
                            </div>
                        );
                    case "multiSelect": {
                        const selected = arr(draft[def.key]);
                        return (
                            <fieldset key={def.key} className={FIELD}>
                                <legend>{def.label}</legend>
                                <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm font-normal text-foreground">
                                    {def.options.map((o) => (
                                        <label key={o.value} className="flex items-center gap-1.5">
                                            <input type="checkbox" checked={selected.includes(o.value)}
                                                onChange={(e) => change({ [def.key]: e.target.checked ? [...selected, o.value] : selected.filter((x) => x !== o.value) })} />
                                            {o.label}
                                        </label>
                                    ))}
                                </div>
                                {clear}
                            </fieldset>
                        );
                    }
                    case "status": {
                        const current = str(draft[def.key]);
                        return (
                            <fieldset key={def.key} className={FIELD}>
                                <legend>{def.label}</legend>
                                <div className="flex flex-wrap gap-1.5">
                                    {def.options.map((o) => {
                                        const pressed = current === o.value;
                                        return (
                                            <button key={o.value} type="button" aria-pressed={pressed}
                                                onClick={() => change({ [def.key]: pressed ? undefined : o.value })}
                                                className={cn("rounded-md border px-2 py-1 text-xs font-medium cursor-pointer focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40",
                                                    pressed ? TONE_MAP[o.tone].solid : cn("border-border bg-card text-foreground hover:bg-muted"))}>
                                                {o.label}
                                            </button>
                                        );
                                    })}
                                </div>
                            </fieldset>
                        );
                    }
                    case "dateRange": {
                        const [from, to] = [`${def.key}_from`, `${def.key}_to`];
                        return (
                            <fieldset key={def.key} className={FIELD}>
                                <legend>{def.label}</legend>
                                <div className="flex items-center gap-2">
                                    <Input type="date" aria-label={`${def.label} from`} value={str(draft[from])} className="w-auto"
                                        onChange={(e) => change({ [from]: e.target.value })} />
                                    <span aria-hidden="true">–</span>
                                    <Input type="date" aria-label={`${def.label} to`} value={str(draft[to])} className="w-auto"
                                        onChange={(e) => change({ [to]: e.target.value })} />
                                </div>
                                {clear}
                            </fieldset>
                        );
                    }
                    case "numberRange": {
                        const [min, max] = [`${def.key}_min`, `${def.key}_max`];
                        return (
                            <fieldset key={def.key} className={FIELD}>
                                <legend>{def.label}</legend>
                                <div className="flex items-center gap-2">
                                    <Input type="number" aria-label={`${def.label} min`} min={def.min} max={def.max} step={def.step}
                                        value={str(draft[min])} className="w-28" onChange={(e) => change({ [min]: e.target.value }, true)} />
                                    <span aria-hidden="true">–</span>
                                    <Input type="number" aria-label={`${def.label} max`} min={def.min} max={def.max} step={def.step}
                                        value={str(draft[max])} className="w-28" onChange={(e) => change({ [max]: e.target.value }, true)} />
                                </div>
                                {clear}
                            </fieldset>
                        );
                    }
                }
            })}
            <div className="flex items-center gap-2">
                {!instant && <Button type="submit">Apply</Button>}
                <Button type="button" variant="outline" onClick={reset}>Reset</Button>
            </div>
            <p aria-live="polite" className="sr-only">{activeCount} active {activeCount === 1 ? "filter" : "filters"}</p>
        </form>
    );
}
