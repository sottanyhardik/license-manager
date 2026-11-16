import { memo, useCallback, useEffect, useRef, useState, type MouseEvent } from "react";
import { BookCheck, Calendar, CalendarX, ChevronRight, MapPin } from "lucide-react";
import { toast } from "sonner";

import api from "@/api/axios";
import { cn } from "@/lib/utils";
import { ActionMenu, StatusBadge } from "@/components/shared";
import OverUtilisedBadge from "@/components/OverUtilisedBadge";
import IndividualItemCifSwitch from "@/components/IndividualItemCifSwitch";

import LicenseRecordWorkspace, { type LicenseRecordTabId } from "./LicenseRecordWorkspace";
import HistoryTab from "./tabs/HistoryTab";
import { buildLicenceActionItems } from "./licenceActionItems";
import { deriveStatus, formatCifUsd, isLicenceExpired, isNegativeValue } from "./licenceFormat";
import { useLicenceRowActions, type LicenceRowActionContext } from "./useLicenceRowActions";
import type { LicenceOwnershipData, LicenseListItem } from "./types";

export interface LicenceCardProps extends LicenceRowActionContext {
    item: LicenseListItem;
    expanded: boolean;
    /** Stable callback (receives the id) so memoised cards only re-render when their own props change. */
    onToggle: (id: number) => void;
    canWrite: boolean;
    onDelete: (item: LicenseListItem) => void;
    isFetchingDGFT: boolean;
    onFetchDGFT: (item: LicenseListItem) => void;
    onDGFTComplete?: (licenseId: number) => void;
}

/** Header detail field (expanded only). Missing values keep the existing "—". */
function HeaderField({ label, value, mono = false }: { label: string; value?: string | null; mono?: boolean }) {
    return (
        <div className="min-w-0">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd
                className={cn("truncate text-sm font-medium text-foreground", mono && "font-mono", !value && "text-muted-foreground")}
                title={value || ""}
            >
                {value || "—"}
            </dd>
        </div>
    );
}

function MetaItem({ icon: Icon, label, children, className }: { icon: typeof Calendar; label: string; children: React.ReactNode; className?: string }) {
    return (
        <span className={cn("inline-flex items-center gap-1 whitespace-nowrap", className)}>
            <Icon className="size-3.5" aria-hidden="true" />
            <span className="sr-only">{label} </span>
            {children}
        </span>
    );
}

/** Elements that handle their own clicks inside the header; clicks on them never toggle the card. */
const INTERACTIVE = "button, a, input, [role=menuitem]";

/**
 * One licence in the register: a compact header row (always visible) and, when
 * expanded, the record workspace. One card is open at a time (owned by the list).
 */
export const LicenceCard = memo(function LicenceCard({
    item,
    expanded,
    onToggle,
    canWrite,
    onDelete,
    isFetchingDGFT,
    onFetchDGFT,
    onDGFTComplete,
    entityName,
    filterParams,
    currentPage,
    pageSize,
    navigate,
}: LicenceCardProps) {
    const prevFetchingDGFT = useRef(isFetchingDGFT);
    const [activeTab, setActiveTab] = useState<LicenseRecordTabId>("overview");
    const [ownershipData, setOwnershipData] = useState<LicenceOwnershipData | null>(null);
    const [ownershipLoading, setOwnershipLoading] = useState(false);

    const actions = useLicenceRowActions(item, { entityName, filterParams, currentPage, pageSize, navigate });
    const status = deriveStatus(item);
    const expired = isLicenceExpired(item);
    const displayNumber = item.license_number || String(item.id);
    const hasDocuments = item.has_tl || item.has_copy;
    const regionId = `license-content-${item.id}`;

    const toggle = useCallback(() => onToggle(item.id), [onToggle, item.id]);
    const onHeaderClick = useCallback((e: MouseEvent<HTMLDivElement>) => {
        if ((e.target as HTMLElement).closest(INTERACTIVE)) return;
        toggle();
    }, [toggle]);

    const handleTabChange = useCallback((t: LicenseRecordTabId) => {
        setActiveTab(t);
        // Lazy-fetch ownership on first visit to the History tab (unchanged).
        if (t === "history" && !ownershipData && !ownershipLoading) {
            setOwnershipLoading(true);
            api.get(`license-actions/${item.id}/ownership-data/`)
                .then(({ data }) => setOwnershipData(data))
                .catch(() => toast.error("Failed to load ownership data"))
                .finally(() => setOwnershipLoading(false));
        }
    }, [item.id, ownershipData, ownershipLoading]);

    // Clear ownership cache when a DGFT fetch completes so History reflects new data (unchanged).
    useEffect(() => {
        if (prevFetchingDGFT.current && !isFetchingDGFT && ownershipData) {
            setOwnershipData(null);
            onDGFTComplete?.(item.id);
        }
        prevFetchingDGFT.current = isFetchingDGFT;
    }, [isFetchingDGFT, ownershipData, item.id, onDGFTComplete]);

    const actionItems = buildLicenceActionItems({
        canWrite,
        isPlanning: actions.isPlanning,
        isFetchingDGFT,
        openOverview: actions.openOverview,
        editLicence: actions.editLicence,
        autoPlan: () => { void actions.autoPlan(); },
        fetchFromDgft: () => onFetchDGFT(item),
        downloadPdf: () => { void actions.downloadPdf(); },
        downloadExcel: () => { void actions.downloadExcel(); },
        deleteLicence: () => onDelete(item),
    });

    return (
        <article
            aria-label={`License ${displayNumber}`}
            className={cn(
                "min-w-0 overflow-hidden rounded-lg border bg-card transition-colors",
                expanded ? "border-ring/40" : "border-border hover:border-foreground/20",
            )}
        >
            {/* Header row. Mouse: anywhere toggles. Keyboard: the chevron button (aria-expanded). */}
            <div
                onClick={onHeaderClick}
                className={cn("flex cursor-pointer flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2 md:px-4", expanded && "bg-muted/40")}
            >
                <div className="flex min-w-0 items-center gap-2">
                    <button
                        type="button"
                        onClick={toggle}
                        aria-expanded={expanded}
                        aria-controls={regionId}
                        aria-label={`${expanded ? "Collapse" : "Expand"} license ${displayNumber}`}
                        className="inline-flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
                    >
                        <ChevronRight
                            className={cn("size-4 transition-transform duration-150 motion-reduce:transition-none", expanded && "rotate-90")}
                            aria-hidden="true"
                        />
                    </button>
                    {/* Licence number opens the merged licence documents (unchanged behaviour). */}
                    <button
                        type="button"
                        onClick={actions.openMergedDocuments}
                        aria-label={`View documents for license ${item.license_number}`}
                        className={cn(
                            "rounded-sm font-mono text-base font-semibold tracking-tight underline-offset-2 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                            hasDocuments ? "cursor-pointer text-primary hover:underline" : "cursor-default text-foreground",
                        )}
                    >
                        {item.license_number || "—"}
                    </button>
                </div>

                <div className="order-3 flex min-w-0 basis-full flex-wrap items-center gap-x-3 gap-y-0.5 pl-9 text-xs text-muted-foreground lg:order-none lg:basis-auto lg:flex-1 lg:pl-0">
                    {item.license_date && <MetaItem icon={Calendar} label="Issue date">{item.license_date}</MetaItem>}
                    {item.license_expiry_date && (
                        <MetaItem icon={CalendarX} label="Expiry date" className={cn(expired && "text-destructive")}>
                            Exp: {item.license_expiry_date}
                        </MetaItem>
                    )}
                    {item.ledger_date && <MetaItem icon={BookCheck} label="Ledger date" className="text-success">Ledger: {item.ledger_date}</MetaItem>}
                    {item.port_name && <MetaItem icon={MapPin} label="Port">{item.port_name}</MetaItem>}
                    {item.purchase_status_label && (
                        <span className="rounded-sm border border-border px-1.5 py-px text-xs text-foreground/80">
                            <span className="sr-only">Licence type </span>{item.purchase_status_label}
                        </span>
                    )}
                </div>

                <div className="ml-auto flex shrink-0 items-center gap-3">
                    <StatusBadge tone={status.tone} label={status.label} />
                    <div className="flex items-baseline gap-1.5 text-sm tabular-nums">
                        <span className="text-xs text-muted-foreground">Balance CIF</span>
                        <span className={cn("min-w-[6.5rem] text-right font-semibold text-foreground", isNegativeValue(item.get_balance_cif) && "text-destructive")}>
                            {formatCifUsd(item.get_balance_cif)}
                        </span>
                    </div>
                    <OverUtilisedBadge balance={item.get_balance_cif} isOverUtilised={item.is_over_utilised} className="ml-0" />
                </div>
            </div>

            {expanded && (
                <div id={regionId} role="region" aria-label={`License ${displayNumber} details`} className="border-t border-border">
                    <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 border-b border-border/60 px-3 py-2 md:px-4">
                        <dl className="grid min-w-0 flex-1 grid-cols-2 gap-x-6 gap-y-1.5 md:grid-cols-4">
                            <HeaderField label="Norm Class" value={item.get_norm_class} mono />
                            <HeaderField label="Exporter" value={item.exporter_name} />
                            <HeaderField label="IEC" value={item.exporter_iec} mono />
                            <HeaderField label="Transfer Status" value={item.latest_transfer} />
                        </dl>
                        <div className="flex shrink-0 items-center gap-3">
                            <IndividualItemCifSwitch licenseId={item.id} override={item.individual_item_cif_override} canWrite={canWrite} />
                            <ActionMenu items={actionItems} label={`Actions for license ${displayNumber}`} trigger="button" />
                        </div>
                    </div>
                    <div className="min-w-0 px-3 pb-3 pt-2 md:px-4">
                        <LicenseRecordWorkspace
                            licenseId={item.id}
                            licenseNumber={item.license_number}
                            canWrite={canWrite}
                            activeTab={activeTab}
                            onTabChange={handleTabChange}
                            renderHistory={() => <HistoryTab ownershipData={ownershipData} loading={ownershipLoading} />}
                        />
                    </div>
                </div>
            )}
        </article>
    );
});
