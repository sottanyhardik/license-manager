import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { acctGet, acctKeys } from "@/api/accountingApi";

import { inputCls } from "./ui";

export interface Party { id: number; name: string; gstin: string | null; pan: string | null }

/** Party search over the existing company master (no separate party master). */
export default function PartyPicker({ value, onChange, label = "Party" }: {
    value: Party | null;
    onChange: (p: Party | null) => void;
    label?: string;
}) {
    const [term, setTerm] = useState("");
    const q = useQuery({
        queryKey: [...acctKeys.all, "parties", term],
        queryFn: () => acctGet<Party[]>("parties/", { search: term }),
        enabled: term.length >= 2,
    });
    if (value) {
        return (
            <div className="flex h-9 items-center justify-between rounded-md border border-slate-300 bg-slate-50 px-2 text-sm">
                <span className="truncate">{value.name}{value.gstin ? ` · ${value.gstin}` : ""}</span>
                <button type="button" className="text-xs text-blue-700 hover:underline" onClick={() => onChange(null)}>Change</button>
            </div>
        );
    }
    return (
        <div className="relative">
            <input className={`${inputCls} w-full`} placeholder="Type 2+ letters of the company name" aria-label={label}
                   value={term} onChange={(e) => setTerm(e.target.value)} />
            {term.length >= 2 && (q.data?.length ?? 0) > 0 && (
                <ul role="listbox" className="absolute z-30 mt-1 max-h-60 w-full overflow-auto rounded-md border border-slate-200 bg-white shadow-lg">
                    {q.data!.map((p) => (
                        <li key={p.id} role="option" aria-selected={false}>
                            <button type="button" className="w-full px-2 py-1.5 text-left text-sm hover:bg-blue-50"
                                    onClick={() => { onChange(p); setTerm(""); }}>
                                {p.name} <span className="text-xs text-slate-500">{p.gstin ?? ""}</span>
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
