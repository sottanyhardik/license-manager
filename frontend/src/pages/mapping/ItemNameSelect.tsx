/** Searchable picker over the real Item Name master (ItemNameModel ids); legitimate targets listed first.
 *  Typing searches the server-side master too, so names beyond the preloaded list are reachable. */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import api from "@/api/axios";

export type Master = { item_id: number; name: string };

export default function ItemNameSelect({ label, value, onChange, legitimate, masters, disabled, describedBy }: { label: string; value: number | null; onChange: (id: number | null) => void;
    legitimate: { item_id: number; name: string | null }[]; masters: Master[]; disabled?: boolean; describedBy?: string }) {
    const [q, setQ] = useState("");
    const term = q.trim();
    const [remoteTerm, setRemoteTerm] = useState("");
    useEffect(() => { const t = setTimeout(() => setRemoteTerm(term), 250); return () => clearTimeout(t); }, [term]);
    const remote = useQuery({
        queryKey: ["item-name-search", remoteTerm],
        enabled: remoteTerm.length >= 2,
        queryFn: async ({ signal }) => (await api.get("item-pivot/matching/masters/", { params: { q: remoteTerm }, signal })).data as { masters: Master[] },
        staleTime: 60_000,
    });
    const legitIds = new Set(legitimate.map((l) => l.item_id));
    const pool = new Map<number, Master>();
    for (const m of masters) pool.set(m.item_id, m);
    for (const m of remote.data?.masters ?? []) pool.set(m.item_id, m);
    const match = (name: string | null) => !term || (name ?? "").toLowerCase().includes(term.toLowerCase());
    const others = [...pool.values()].filter((m) => (!legitIds.has(m.item_id) || m.item_id === value) && (match(m.name) || m.item_id === value))
        .sort((a, b) => a.name.localeCompare(b.name));
    return (
        <div className="flex flex-wrap items-center gap-1">
            <input aria-label={`Search Item Names for ${label}`} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search Item Name…" disabled={disabled}
                className="h-7 w-36 rounded-md border border-input bg-background px-2 text-xs" />
            <select aria-label={`Item Name for ${label}`} aria-describedby={describedBy} value={value ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
                className="h-7 max-w-[16rem] rounded-md border border-input bg-background px-1.5 text-xs">
                <option value="">— choose Item Name —</option>
                {legitimate.length > 0 && <optgroup label="Legitimate for these records (SION rules)">{legitimate.filter((l) => match(l.name) || l.item_id === value).map((l) => <option key={`l${l.item_id}`} value={l.item_id}>{l.name}</option>)}</optgroup>}
                <optgroup label="All Item Names (validated on approval)">{others.map((m) => <option key={m.item_id} value={m.item_id}>{m.name}</option>)}</optgroup>
            </select>
        </div>
    );
}
