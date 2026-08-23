import { useState, useEffect } from "react";
import { Network, Loader2, TriangleAlert } from "lucide-react";

import api from "../api/axios";
import { toast } from "sonner";
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

function fmtDateTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function CompanyLabel({ iec, name }) {
    if (!iec && !name) return <span className="text-muted-foreground">—</span>;
    return (
        <span>
            <span className="font-mono">{iec || "—"}</span>
            {name ? <span className="text-muted-foreground"> ({name})</span> : null}
        </span>
    );
}

function SectionBanner({ children }) {
    return (
        <div className="rounded-t-lg px-4 py-3 text-[15px] font-semibold text-white" style={{ background: "linear-gradient(135deg, var(--tb-brand-hover), var(--tb-brand-active))" }}>
            {children}
        </div>
    );
}

export default function OwnershipDetailsModal({ show, onHide, licenseId, licenseNumber }) {
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!show || !licenseId) return;
        let cancelled = false;
        setLoading(true);
        setError(null);
        setData(null);
        api.get(`license-actions/${licenseId}/ownership-data/`)
            .then((r) => { if (!cancelled) setData(r.data); })
            .catch((err) => {
                if (cancelled) return;
                const msg = err?.response?.data?.error || err?.message || "Failed to load ownership data";
                setError(msg);
                toast.error(msg);
            })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [show, licenseId]);

    const owner = data?.current_owner;
    const transfers = data?.transfers || [];

    return (
        <Dialog open={show} onOpenChange={(o) => !o && onHide()}>
            <DialogContent className="max-h-[90vh] w-[95vw] max-w-5xl overflow-hidden">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Network className="size-4 text-primary" />
                        Ownership Details{licenseNumber ? ` — ${licenseNumber}` : ""}
                    </DialogTitle>
                </DialogHeader>

                <div className="max-h-[70vh] overflow-y-auto">
                    {loading && (
                        <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
                            <Loader2 className="size-4 animate-spin" />Loading ownership data…
                        </div>
                    )}

                    {!loading && error && (
                        <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive">
                            <TriangleAlert className="size-4 shrink-0" />{error}
                        </div>
                    )}

                    {!loading && !error && data && (
                        <>
                            {/* Current owner */}
                            <div className="mb-6">
                                <SectionBanner>Current Owner&apos;s Details</SectionBanner>
                                <div className="rounded-b-lg border border-t-0 border-border bg-card p-4">
                                    {owner ? (
                                        <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
                                            <div>
                                                <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">IEC</div>
                                                <div className="mt-1 font-mono">{owner.iec || "—"}</div>
                                            </div>
                                            <div>
                                                <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Firm / Company</div>
                                                <div className="mt-1">{owner.name || "—"}</div>
                                            </div>
                                            <div className="sm:col-span-2">
                                                <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Address</div>
                                                <div className="mt-1">{owner.address || "—"}</div>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="text-muted-foreground">No current owner recorded.</div>
                                    )}
                                    <div className="mt-4 flex justify-between border-t border-dashed border-border pt-3 text-[12.5px] text-muted-foreground">
                                        <span>Last fetched: {fmtDateTime(data.last_ownership_fetch)}</span>
                                        {data.file_transfer_status && <span><strong>File transfer:</strong> {data.file_transfer_status}</span>}
                                    </div>
                                </div>
                            </div>

                            {/* Transfers */}
                            <div>
                                <SectionBanner>
                                    Transfer Details {transfers.length > 0 && <span className="font-normal opacity-85">({transfers.length})</span>}
                                </SectionBanner>
                                <div className="overflow-x-auto rounded-b-lg border border-t-0 border-border bg-card">
                                    {transfers.length === 0 ? (
                                        <div className="p-4 text-muted-foreground">No transfers recorded.</div>
                                    ) : (
                                        <table className="w-full text-[13.5px]">
                                            <thead>
                                                <tr className="bg-destructive/10 text-left">
                                                    <th scope="col" className="px-3 py-2.5 font-semibold">Initiation Date</th>
                                                    <th scope="col" className="px-3 py-2.5 font-semibold">Acceptance Date</th>
                                                    <th scope="col" className="px-3 py-2.5 font-semibold">From IEC</th>
                                                    <th scope="col" className="px-3 py-2.5 font-semibold">To IEC</th>
                                                    <th scope="col" className="px-3 py-2.5 font-semibold">Status</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {transfers.map((t, i) => {
                                                    const approved = (t.transfer_status || "").toLowerCase() === "approved";
                                                    return (
                                                        <tr key={i} className="border-t border-border/60">
                                                            <td className="px-3 py-2.5">{fmtDateTime(t.transfer_initiation_date)}</td>
                                                            <td className="px-3 py-2.5">{fmtDateTime(t.transfer_acceptance_date)}</td>
                                                            <td className="px-3 py-2.5"><CompanyLabel iec={t.from_iec} name={t.from_name} /></td>
                                                            <td className="px-3 py-2.5"><CompanyLabel iec={t.to_iec} name={t.to_name} /></td>
                                                            <td className="px-3 py-2.5">
                                                                <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${approved ? "bg-success/15 text-success" : "bg-warning/15 text-warning"}`}>
                                                                    {t.transfer_status || "—"}
                                                                </span>
                                                            </td>
                                                        </tr>
                                                    );
                                                })}
                                            </tbody>
                                        </table>
                                    )}
                                </div>
                            </div>
                        </>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={onHide}>Close</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
