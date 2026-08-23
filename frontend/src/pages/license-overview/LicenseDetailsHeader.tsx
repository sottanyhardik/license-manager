import type { LucideIcon } from "lucide-react";
import { Anchor, Building2, CalendarClock, CalendarDays, FileText, Folder, Loader2, Pencil, RefreshCw, Tag, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import HybridSelect from "@/components/HybridSelect";
import { cn } from "@/lib/utils";

import { fmtDate, licenseOverviewStatusVariant } from "./licenseOverviewHelpers";
import type { LicenseOverviewSummary } from "./types";

interface LicenseDetailsHeaderProps {
    summary: LicenseOverviewSummary;
    canRecalculate: boolean;
    recalculating: boolean;
    onRecalculate: () => void;
    canEditPurchaseStatus: boolean;
    editingPurchaseStatus: boolean;
    setEditingPurchaseStatus: (value: boolean) => void;
    updatingPurchaseStatus: boolean;
    onPurchaseStatusChange: (value: unknown) => void;
}

/**
 * Premium glass header card for the Overview tab — replaces the old plain
 * bordered info row. Renders License Number, File Number, Port Code,
 * License Date, Expiry Date, Importer, Purchase Status (in that order —
 * "Authorisation Number" is intentionally NOT rendered here per the latest
 * spec, though `authorisation_number` stays in the API/types untouched),
 * plus the Active Status badge and Recalculate button.
 *
 * The Recalculate and Purchase Status *behavior* (state + handlers) still
 * lives in `OverviewTab.tsx` and is passed down as props — only the
 * rendering moved here, so nothing about what the buttons/editor actually
 * do has changed.
 */
export default function LicenseDetailsHeader({
    summary,
    canRecalculate,
    recalculating,
    onRecalculate,
    canEditPurchaseStatus,
    editingPurchaseStatus,
    setEditingPurchaseStatus,
    updatingPurchaseStatus,
    onPurchaseStatusChange,
}: LicenseDetailsHeaderProps) {
    return (
        <section aria-label="Licence identity and status" className="overflow-hidden rounded-xl border border-border/70 bg-card px-4 py-3 shadow-sm sm:px-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="grid flex-1 grid-cols-2 gap-x-5 gap-y-3 sm:grid-cols-3 lg:grid-cols-7">
                    <HeaderField icon={FileText} label="License Number" value={summary.license_number ?? "—"} />
                    <HeaderField icon={Folder} label="File Number" value={summary.file_number ?? "—"} />
                    <HeaderField
                        icon={Anchor}
                        label="Port Code"
                        value={summary.port_code ?? "—"}
                        title={summary.port_name ?? undefined}
                    />
                    <HeaderField icon={CalendarDays} label="License Date" value={fmtDate(summary.license_date)} />
                    <HeaderField icon={CalendarClock} label="Expiry Date" value={fmtDate(summary.license_expiry_date)} />
                    <HeaderField icon={Building2} label="Importer" value={summary.importer ?? "—"} />

                    <div className="col-span-2 sm:col-span-2 lg:col-span-1">
                        <FieldLabel icon={Tag} label="Purchase Status" />
                        {canEditPurchaseStatus && editingPurchaseStatus ? (
                            <div className="mt-0.5 flex w-full items-center gap-1.5">
                                <div className="w-full">
                                    <HybridSelect
                                        fieldMeta={{
                                            endpoint: "/masters/purchase-statuses/",
                                            label_field: "label",
                                        }}
                                        value={summary.purchase_status_id}
                                        onChange={onPurchaseStatusChange}
                                        isClearable={true}
                                        isDisabled={updatingPurchaseStatus}
                                        placeholder="Set status…"
                                        className="w-full"
                                    />
                                </div>
                                <button
                                    type="button"
                                    className="shrink-0 text-muted-foreground hover:text-foreground"
                                    onClick={() => setEditingPurchaseStatus(false)}
                                    disabled={updatingPurchaseStatus}
                                    aria-label="Cancel editing purchase status"
                                >
                                    <X className="size-4" aria-hidden="true" />
                                </button>
                            </div>
                        ) : (
                            <button
                                type="button"
                                className={cn(
                                    "mt-0.5 flex w-full items-center gap-1.5 truncate text-left text-sm font-medium text-foreground",
                                    canEditPurchaseStatus && "cursor-pointer hover:text-primary"
                                )}
                                onClick={() => canEditPurchaseStatus && setEditingPurchaseStatus(true)}
                                disabled={!canEditPurchaseStatus}
                            >
                                <span className="truncate">{summary.purchase_status_label ?? "—"}</span>
                                {canEditPurchaseStatus && (
                                    <Pencil className="size-3 shrink-0 text-muted-foreground" aria-hidden="true" />
                                )}
                            </button>
                        )}
                    </div>
                </div>

                <div className="flex shrink-0 items-center gap-2 self-start">
                    <Badge variant={licenseOverviewStatusVariant(summary.status)}>{summary.status}</Badge>
                    {canRecalculate && (
                        <Button size="sm" variant="outline" onClick={onRecalculate} disabled={recalculating}>
                            {recalculating ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                            Recalculate
                        </Button>
                    )}
                </div>
            </div>
        </section>
    );
}

function FieldLabel({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
    return (
        <div className="flex items-center gap-1 text-[10.5px] font-semibold uppercase tracking-widest text-muted-foreground">
            <Icon className="size-3" aria-hidden="true" />
            {label}
        </div>
    );
}

function HeaderField({ icon, label, value, title }: { icon: LucideIcon; label: string; value: string; title?: string }) {
    return (
        <div className="min-w-0">
            <FieldLabel icon={icon} label={label} />
            <div className="mt-0.5 truncate text-[13px] font-semibold text-foreground" title={title}>
                {value}
            </div>
        </div>
    );
}
