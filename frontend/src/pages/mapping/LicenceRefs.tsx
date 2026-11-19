/** Compact licence references for a description: "N records · M licences" + licence-number chips (first few, "+N more"
 *  expands). Chips open the existing licence page by the real licence id (`/licenses/:id/overview`). */
import { useState } from "react";
import { Link } from "react-router-dom";

export type LicenceRef = { id: number; license_number: string };

export default function LicenceRefs({ refs, records, label, visible = 3, total, newTab = false }: {
    refs: LicenceRef[]; records?: number; label: string; visible?: number; total?: number; newTab?: boolean;
}) {
    const [open, setOpen] = useState(false);
    const count = total ?? refs.length; // exact distinct licence count, even when the list itself is truncated
    const shown = open ? refs : refs.slice(0, visible);
    const more = refs.length - shown.length;
    return (
        <div className="flex flex-wrap items-center gap-1 text-[10px]">
            {records != null && <span className="text-muted-foreground">{records} record{records === 1 ? "" : "s"} · {count} licence{count === 1 ? "" : "s"}</span>}
            <ul aria-label={`Licences for ${label}`} className="flex max-h-32 flex-wrap gap-1 overflow-auto">
                {shown.map((r) => (
                    <li key={r.id}><Link to={`/licenses/${r.id}/overview`} {...(newTab ? { target: "_blank", rel: "noopener noreferrer" } : {})} className="rounded border border-border bg-muted/60 px-1.5 py-0.5 font-mono text-[10px] hover:border-primary hover:text-primary"
                        title={`Open licence ${r.license_number}`}>{r.license_number}</Link></li>
                ))}
            </ul>
            {more > 0 && <button type="button" className="text-primary hover:underline" aria-expanded={open} onClick={() => setOpen(true)}>+ {more} more</button>}
            {open && refs.length > visible && <button type="button" className="text-muted-foreground hover:underline" aria-expanded={open} onClick={() => setOpen(false)}>show less</button>}
        </div>
    );
}
