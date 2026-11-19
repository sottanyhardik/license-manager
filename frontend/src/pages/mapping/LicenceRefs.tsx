/** Compact licence references for a description: "N records · M licences" + licence-number chips (first few, "+N more"
 *  expands). A chip opens the Licence List (standard filters) and that licence's existing workspace, identified by its
 *  real database id (owner spec 2026-11-19); the chip shows the licence number. */
import { useState } from "react";
import { Link } from "react-router-dom";

import { LICENCE_LIST_URL, requestOpenLicence } from "@/features/licenses/openLicenceTarget";

export type LicenceRef = { id: number; license_number: string };

export default function LicenceRefs({ refs, records, label, visible = 3, total }: {
    refs: LicenceRef[]; records?: number; label: string; visible?: number; total?: number;
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
                    <li key={r.id}><Link to={LICENCE_LIST_URL} onClick={(e) => {
                        // Plain click only: a modified click (new tab / window) opens the plain list and leaves nothing pending here.
                        if (e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) requestOpenLicence({ id: r.id, license_number: r.license_number });
                    }} className="rounded border border-border bg-muted/60 px-1.5 py-0.5 font-mono text-[10px] hover:border-primary hover:text-primary"
                        title={`Open licence ${r.license_number} in the Licence List`} aria-label={`Open licence ${r.license_number}`}>{r.license_number}</Link></li>
                ))}
            </ul>
            {more > 0 && <button type="button" className="text-primary hover:underline" aria-expanded={open} onClick={() => setOpen(true)}>+ {more} more</button>}
            {open && refs.length > visible && <button type="button" className="text-muted-foreground hover:underline" aria-expanded={open} onClick={() => setOpen(false)}>show less</button>}
        </div>
    );
}
