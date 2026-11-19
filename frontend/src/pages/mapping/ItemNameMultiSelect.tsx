/** Searchable multi-select over the real Item Name master (existing ItemNameModel ids), selections shown as removable
 *  chips. Starts with whatever the caller passes (empty for a new description); never pre-fills a suggestion.
 *  ``single``: at most one value (a pick replaces it) — the Planning Target Item of a BOE / allotment is one FK.
 *  ``noun``: what the master is called on this table ("Item Name" / "Planning Target Item"). */
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";

import api from "@/api/axios";

import type { Master } from "./mappingSources";

export default function ItemNameMultiSelect({ label, value, onChange, masters, disabled, describedBy, single = false, noun = "Item Name" }: {
    label: string; value: Master[]; onChange: (next: Master[]) => void; masters: Master[]; disabled?: boolean; describedBy?: string; single?: boolean; noun?: string;
}) {
    const [q, setQ] = useState("");
    const [announce, setAnnounce] = useState("");
    const addRef = useRef<HTMLSelectElement>(null);
    const term = q.trim();
    const [remoteTerm, setRemoteTerm] = useState("");
    useEffect(() => { const t = setTimeout(() => setRemoteTerm(term), 250); return () => clearTimeout(t); }, [term]);
    const remote = useQuery({
        queryKey: ["item-name-search", remoteTerm],
        enabled: remoteTerm.length >= 2,
        queryFn: async ({ signal }) => (await api.get("item-pivot/matching/masters/", { params: { q: remoteTerm }, signal })).data as { masters: Master[] },
        staleTime: 60_000,
    });
    const chosen = new Set(value.map((v) => v.item_id));
    const pool = new Map<number, Master>();
    for (const m of [...masters, ...(remote.data?.masters ?? [])]) pool.set(m.item_id, m);
    const options = [...pool.values()].filter((m) => !chosen.has(m.item_id) && (!term || m.name.toLowerCase().includes(term.toLowerCase())))
        .sort((a, b) => a.name.localeCompare(b.name));
    return (
        <div className="min-w-[16rem] space-y-1">
            <span className="sr-only" aria-live="polite">{announce}</span>
            {value.length > 0 && (
                <ul aria-label={`Selected ${noun}s for ${label}`} className="flex flex-wrap gap-1">
                    {value.map((v) => (
                        <li key={v.item_id} className="inline-flex items-center gap-1 rounded-full border border-border bg-muted px-2 py-0.5 text-[11px]">
                            {v.name}
                            {!disabled && <button type="button" aria-label={`Remove ${v.name} from ${label}`} className="rounded-full text-muted-foreground hover:text-foreground"
                                onClick={() => { onChange(value.filter((x) => x.item_id !== v.item_id)); setAnnounce(`${v.name} removed`); addRef.current?.focus(); }}><X className="size-3" aria-hidden="true" /></button>}
                        </li>
                    ))}
                </ul>
            )}
            {!disabled && (
                <div className="flex flex-wrap items-center gap-1">
                    <input aria-label={`Search ${noun}s for ${label}`} value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Search ${noun}…`}
                        className="h-7 w-36 rounded-md border border-input bg-background px-2 text-xs" />
                    <select ref={addRef} aria-label={`${single && value.length ? "Change" : "Add"} ${noun} for ${label}`} aria-describedby={describedBy} value=""
                        onChange={(e) => { const m = pool.get(Number(e.target.value)); if (m) { onChange(single ? [m] : [...value, m]); setQ(""); setAnnounce(`${m.name} ${single ? "selected" : "added"}`); } }}
                        className="h-7 max-w-[14rem] rounded-md border border-input bg-background px-1.5 text-xs">
                        <option value="">{value.length ? (single ? "change…" : "+ add another…") : `— select ${noun} —`}</option>
                        {options.map((m) => <option key={m.item_id} value={m.item_id}>{m.name}</option>)}
                    </select>
                </div>
            )}
        </div>
    );
}
