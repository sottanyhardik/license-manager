import { useId, useState, type KeyboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";

import { acctGet, acctKeys } from "@/api/accountingApi";

import { inputCls } from "./ui";

export interface Party { id: number; name: string; gstin: string | null; pan: string | null }

/**
 * Party search over the existing company master (no separate party master).
 * ARIA 1.2 combobox: arrow keys move, Enter selects, Escape closes.
 */
export default function PartyPicker({ value, onChange, label = "Party" }: {
    value: Party | null;
    onChange: (p: Party | null) => void;
    label?: string;
}) {
    const [term, setTerm] = useState("");
    const [active, setActive] = useState(0);
    const [open, setOpen] = useState(true);
    const listId = useId();
    const q = useQuery({
        queryKey: [...acctKeys.all, "parties", term],
        queryFn: () => acctGet<Party[]>("parties/", { search: term }),
        enabled: term.length >= 2,
    });
    const options = q.data ?? [];
    const expanded = open && term.length >= 2;
    const choose = (p: Party) => { onChange(p); setTerm(""); setActive(0); };
    const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((i) => Math.min(i + 1, options.length - 1)); }
        else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
        else if (e.key === "Enter" && expanded && options[active]) { e.preventDefault(); choose(options[active]); }
        else if (e.key === "Escape") { setOpen(false); }
    };
    if (value) {
        return (
            <div className="flex h-9 items-center justify-between rounded-md border border-slate-300 bg-slate-50 px-2 text-sm">
                <span className="truncate">{value.name}{value.gstin ? ` · ${value.gstin}` : ""}</span>
                <button type="button" className="text-xs text-blue-700 hover:underline" onClick={() => onChange(null)}
                        aria-label={`Change ${label.toLowerCase()} (${value.name})`}>Change</button>
            </div>
        );
    }
    return (
        <div className="relative">
            <input className={`${inputCls} w-full`} placeholder="Type 2+ letters of the company name" aria-label={label}
                   role="combobox" aria-expanded={expanded} aria-controls={listId} aria-autocomplete="list"
                   aria-activedescendant={expanded && options[active] ? `${listId}-${options[active].id}` : undefined}
                   value={term} onKeyDown={onKeyDown} onChange={(e) => { setTerm(e.target.value); setActive(0); setOpen(true); }} />
            {expanded && (
                <ul id={listId} role="listbox" aria-label={`${label} matches`}
                    className="absolute z-30 mt-1 max-h-60 w-full overflow-auto rounded-md border border-slate-200 bg-white shadow-lg">
                    {q.isLoading && <li className="px-2 py-1.5 text-sm text-slate-500" role="presentation">Searching…</li>}
                    {!q.isLoading && options.length === 0 && <li className="px-2 py-1.5 text-sm text-slate-500" role="presentation">No company matches “{term}”.</li>}
                    {options.map((p, i) => (
                        <li key={p.id} id={`${listId}-${p.id}`} role="option" aria-selected={i === active}
                            className={`cursor-pointer px-2 py-1.5 text-sm ${i === active ? "bg-blue-50" : "hover:bg-blue-50"}`}
                            onMouseDown={(e) => { e.preventDefault(); choose(p); }} onMouseEnter={() => setActive(i)}>
                            {p.name} <span className="text-xs text-slate-500">{p.gstin ?? ""}</span>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
