import { ArrowRight, Network } from "lucide-react";
import { formatDate, formatDateTime } from "@/utils/dateFormatter";

import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, StatusBadge, type Tone } from "@/components/shared";

import type { LicenceOwnershipData } from "../types";


/** Same keyword buckets as before; only the visual tone vocabulary changed. */
function transferTone(status: string | null): Tone {
    const s = (status || "").toUpperCase();
    if (s.includes("COMPLETE") || s.includes("TRANSFER")) return "success";
    if (s.includes("PENDING") || s.includes("PROCESSING") || s.includes("INITIAT")) return "warning";
    if (s.includes("REJECT") || s.includes("CANCEL")) return "danger";
    return "neutral";
}

function Party({ label, name, iec }: { label: string; name: string | null; iec: string | null }) {
    return (
        <div className="min-w-0">
            <div className="text-xs text-muted-foreground">{label}</div>
            <div className="truncate text-sm font-medium text-foreground">{name || "—"}</div>
            {iec && <div className="font-mono text-xs text-muted-foreground">IEC: {iec}</div>}
        </div>
    );
}

interface HistoryTabProps {
    ownershipData: LicenceOwnershipData | null;
    loading: boolean;
}

/** History tab: `license-actions/:id/ownership-data/` (fetched by the card on first visit). */
export default function HistoryTab({ ownershipData, loading }: HistoryTabProps) {
    if (loading) {
        return (
            <div role="status" aria-label="Loading ownership history" className="space-y-2 py-2">
                {[1, 2, 3].map((i) => <Skeleton key={i} className="h-4 w-2/3" />)}
            </div>
        );
    }

    if (!ownershipData) {
        return (
            <EmptyState
                icon={Network}
                title="No ownership data"
                description="Use 'Fetch from DGFT' in the Actions menu to load ownership history."
            />
        );
    }

    const transfers = ownershipData.transfers ?? [];
    const owner = ownershipData.current_owner;

    return (
        <div className="space-y-3">
            {(owner || ownershipData.file_transfer_status) && (
                <dl className="grid grid-cols-1 gap-x-6 gap-y-2 rounded-lg border border-border px-3 py-2 md:grid-cols-2">
                    {owner && (
                        <div className="min-w-0">
                            <dt className="text-xs text-muted-foreground">Current Owner</dt>
                            <dd className="text-sm font-semibold text-foreground">{owner.name}</dd>
                            <dd className="font-mono text-xs text-muted-foreground">IEC: {owner.iec}</dd>
                            {owner.address && <dd className="text-xs text-muted-foreground">{owner.address}</dd>}
                            {ownershipData.last_ownership_fetch && (
                                <dd className="mt-1 text-xs text-muted-foreground">
                                    Last synced: {formatDateTime(ownershipData.last_ownership_fetch)}
                                </dd>
                            )}
                        </div>
                    )}
                    {ownershipData.file_transfer_status && (
                        <div className="min-w-0">
                            <dt className="text-xs text-muted-foreground">File Transfer Status</dt>
                            <dd className="text-sm font-medium text-foreground">{ownershipData.file_transfer_status}</dd>
                        </div>
                    )}
                </dl>
            )}

            {transfers.length === 0 ? (
                <EmptyState icon={Network} title="No transfer history" description="No ownership transfers recorded for this license." />
            ) : (
                <ol className="divide-y divide-border rounded-lg border border-border" aria-label="Ownership transfers">
                    {transfers.map((t, idx) => {
                        const date = t.transfer_acceptance_date || t.transfer_initiation_date;
                        return (
                            <li key={idx} className="grid grid-cols-1 items-start gap-2 px-3 py-2 md:grid-cols-[10rem_1fr_auto_1fr]">
                                <div className="flex flex-col items-start gap-1">
                                    <StatusBadge tone={transferTone(t.transfer_status)} label={t.transfer_status || "Unknown"} />
                                    {date && <span className="text-xs tabular-nums text-muted-foreground">{formatDate(date)}</span>}
                                    {t.transfer_initiation_date && (
                                        <span className="text-xs text-muted-foreground">
                                            Initiated: {formatDate(t.transfer_initiation_date)}
                                        </span>
                                    )}
                                </div>
                                <Party label="From" name={t.from_name} iec={t.from_iec} />
                                <ArrowRight className="mt-4 hidden size-4 text-muted-foreground md:block" aria-hidden="true" />
                                <Party label="To" name={t.to_name} iec={t.to_iec} />
                            </li>
                        );
                    })}
                </ol>
            )}
        </div>
    );
}
