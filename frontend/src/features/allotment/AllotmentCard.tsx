import { memo, useCallback, useState, type MouseEvent, type ReactNode } from "react";
import { Building2, Calendar, ChevronRight, FileText, MapPin, Package } from "lucide-react";

import { cn } from "@/lib/utils";
import { ActionMenu, StatusBadge } from "@/components/shared";
import { formatTruthyIndianNumber } from "@/pages/masters/masterDisplayFormatters";
import { formatCifUsd } from "@/features/licenses/licenceFormat";
import { AllotmentRecordWorkspace, type AllotmentTabId } from "./AllotmentRecordWorkspace";
import { buildAllotmentActions, toActionMenuItems } from "./allotmentCardActions";
import type { AllotmentActionContext, AllotmentRecord } from "./types";

const qty = (v: unknown) => formatTruthyIndianNumber(v as string, { maximumFractionDigits: 3 });
/** `required_value` / `allotted_value` / `balanced_value` are FC (USD) amounts: qty × unit value and Σ cif_fc. */
const usd = (v: unknown) => formatCifUsd(v);
const text = (v: unknown) => (v == null || v === "" ? "" : String(v));

/** Elements that handle their own clicks inside the header; clicks on them never toggle the row. */
const INTERACTIVE = "button, a, input, [role=menuitem]";

function Meta({ icon: Icon, label, children, className }: { icon: typeof Calendar; label: string; children: ReactNode; className?: string }) {
    return (
        <span className={cn("inline-flex min-w-0 items-center gap-1 whitespace-nowrap", className)}>
            <Icon className="size-3.5 shrink-0" aria-hidden="true" />
            <span className="sr-only">{label} </span>
            {children}
        </span>
    );
}

function Figure({ label, value, tone }: { label: string; value: string; tone?: "success" | "danger" }) {
    return (
        <div className="flex min-w-[5.5rem] flex-col items-end leading-tight tabular-nums">
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</span>
            <span className={cn("text-sm font-semibold text-foreground", tone === "success" && "text-success", tone === "danger" && "text-destructive")}>{value}</span>
        </div>
    );
}

function Stage({ step, title, children, className }: { step: number; title: string; children: ReactNode; className?: string }) {
    return (
        <section aria-label={title} className={cn("min-w-0 rounded-md border border-border/60 bg-muted/20 px-2.5 py-1.5", className)}>
            <p className="mb-1 text-[11px] font-semibold uppercase leading-tight tracking-wide text-muted-foreground"><span className="mr-1 tabular-nums text-foreground/60">{step}</span>{title}</p>
            <dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm">{children}</dl>
        </section>
    );
}
const Pair = ({ label, value, tone }: { label: string; value: string; tone?: "success" }) => (
    <div className="flex items-baseline gap-1.5"><dt className="text-xs text-muted-foreground">{label}</dt><dd className={cn("font-semibold tabular-nums", tone === "success" && "text-success")}>{value}</dd></div>
);

/**
 * The three distinct stages, never mixed: (1) the allotment requested for the
 * customer, (2) what is allocated to licences (allocation records) and what
 * remains unallocated, (3) BOE utilisation — a BOE-linked allotment is consumed
 * by its BOE (amounts on the BOE tab). All values are backend fields.
 */
function AllocationSummary({ item, licenceCount }: { item: AllotmentRecord; licenceCount: number }) {
    const remainingQty = Number(item.balanced_quantity ?? 0);
    return (
        <div className="grid min-w-0 flex-1 gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)_minmax(0,0.9fr)]">
            <Stage step={1} title="Allotment (customer)">
                <Pair label="Qty" value={qty(item.required_quantity) } />
                <Pair label="Value" value={usd(item.required_value)} />
            </Stage>
            <Stage step={2} title="Allocated to licences">
                <Pair label="Qty" value={qty(item.alloted_quantity) || "0"} />
                <Pair label="CIF" value={usd(item.allotted_value)} />
                <Pair label="Licences" value={String(licenceCount)} />
                <Pair label="Unallocated qty" value={qty(item.balanced_quantity) || "0"} tone={remainingQty > 0 ? "success" : undefined} />
                <Pair label="Unallocated value" value={usd(item.balanced_value)} />
            </Stage>
            <Stage step={3} title="BOE utilisation">
                <div className="flex items-center gap-1.5"><dt className="sr-only">Status</dt><dd><StatusBadge tone={item.is_boe ? "success" : "neutral"} label={item.is_boe ? "Linked to BOE" : "Not linked"} /></dd></div>
            </Stage>
        </div>
    );
}

export interface AllotmentCardProps {
    item: AllotmentRecord;
    expanded: boolean;
    /** Stable callback (receives the id) so memoised rows only re-render when their own props change. */
    onToggle: (id: number) => void;
    ctx: AllotmentActionContext;
}

/**
 * One allotment in the register — the Licence register's compact header row
 * (`LicenceCard`) with the record workspace expanded inline below it.
 * Every figure is the backend value from `allotments/`; nothing is computed here.
 */
export const AllotmentCard = memo(function AllotmentCard({ item, expanded, onToggle, ctx }: AllotmentCardProps) {
    const [activeTab, setActiveTab] = useState<AllotmentTabId>("overview");
    const regionId = `allotment-content-${item.id}`;
    const label = `#${item.id}`;
    const toggle = useCallback(() => onToggle(item.id), [onToggle, item.id]);
    const onHeaderClick = useCallback((e: MouseEvent<HTMLDivElement>) => {
        if ((e.target as HTMLElement).closest(INTERACTIVE)) return;
        toggle();
    }, [toggle]);

    const licences = text(item.dfia_list).split(",").map((s) => s.trim()).filter(Boolean);
    const balanced = Number(item.balanced_quantity ?? 0);
    const actions = buildAllotmentActions(item, ctx);
    // Edit opens the record's Edit tab inline (no edit page): list filters, page and scroll are kept.
    // Allocate opens the inline Allocate Licence tab (the same allocation workflow, no page change).
    const menuItems = toActionMenuItems(actions, { Edit: () => setActiveTab("edit"), Allocate: () => setActiveTab("allocate") });
    const licenceCount = new Set((item.allotment_details ?? []).map((d) => d.license_number).filter(Boolean)).size;

    return (
        <article
            aria-label={`Allotment ${label}`}
            className={cn("min-w-0 overflow-hidden rounded-lg border bg-card transition-colors", expanded ? "border-ring/40" : "border-border hover:border-foreground/20")}
        >
            <div onClick={onHeaderClick} className={cn("flex cursor-pointer flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2 md:px-4", expanded && "bg-muted/40")}>
                <div className="flex min-w-0 items-center gap-2">
                    <button
                        type="button"
                        onClick={toggle}
                        aria-expanded={expanded}
                        aria-controls={regionId}
                        aria-label={`${expanded ? "Collapse" : "Expand"} allotment ${label}`}
                        className="inline-flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
                    >
                        <ChevronRight className={cn("size-4 transition-transform duration-150 motion-reduce:transition-none", expanded && "rotate-90")} aria-hidden="true" />
                    </button>
                    <span className="flex min-w-0 flex-col leading-tight">
                        <span className="truncate font-mono text-base font-semibold tracking-tight" title={text(item.invoice) || undefined}>
                            {text(item.invoice) || <span className="font-sans text-sm font-normal italic text-muted-foreground">No invoice</span>}
                        </span>
                        <span className="text-[11px] text-muted-foreground">Allotment {label}</span>
                    </span>
                </div>

                <div className="order-3 flex min-w-0 basis-full flex-wrap items-center gap-x-3 gap-y-0.5 pl-9 text-xs text-muted-foreground lg:order-none lg:basis-auto lg:flex-1 lg:pl-0">
                    {text(item.estimated_arrival_date) && <Meta icon={Calendar} label="Estimated arrival">{text(item.estimated_arrival_date)}</Meta>}
                    {licences.length > 0 && (
                        <Meta icon={FileText} label="Licences" className="font-mono text-foreground/80">
                            <span className="max-w-[14rem] truncate" title={licences.join(", ")}>{licences[0]}{licences.length > 1 ? ` +${licences.length - 1}` : ""}</span>
                        </Meta>
                    )}
                    {text(item.company_name) && (
                        <Meta icon={Building2} label="Company" className="max-w-[14rem] text-foreground/80"><span className="truncate" title={text(item.company_name)}>{text(item.company_name)}</span></Meta>
                    )}
                    {text(item.item_name) && (
                        <Meta icon={Package} label="Item" className="max-w-[14rem]"><span className="truncate" title={text(item.item_name)}>{text(item.item_name)}</span></Meta>
                    )}
                    {text(item.port_name) && <Meta icon={MapPin} label="Port">{text(item.port_name)}</Meta>}
                    {text(item.bl_detail) && <span className="max-w-[10rem] truncate" title={`BL ${text(item.bl_detail)}`}>BL {text(item.bl_detail)}</span>}
                </div>

                <div className="order-4 flex min-w-0 basis-full flex-wrap items-center justify-between gap-x-4 gap-y-1 pl-9 lg:order-none lg:ml-auto lg:basis-auto lg:shrink-0 lg:justify-end lg:pl-0">
                    <div className="flex items-center gap-1.5">
                        <StatusBadge tone={item.is_boe ? "success" : "neutral"} label={item.is_boe ? "BOE linked" : "No BOE"} />
                        {item.is_approved ? <StatusBadge tone="info" label="Approved" /> : null}
                    </div>
                    <Figure label="Req Qty" value={qty(item.required_quantity)} />
                    <Figure label="Allotted Qty" value={qty(item.alloted_quantity)} />
                    <Figure label="Balance Qty" value={qty(item.balanced_quantity)} tone={balanced < 0 ? "danger" : balanced > 0 ? "success" : undefined} />
                    <Figure label="Req Value" value={usd(item.required_value)} />
                </div>
            </div>

            {expanded && (
                <div id={regionId} role="region" aria-label={`Allotment ${label} details`} className="border-t border-border">
                    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1.5 border-b border-border/60 px-3 py-1.5 md:px-4">
                        <AllocationSummary item={item} licenceCount={licenceCount} />
                        <ActionMenu items={menuItems} label={`Actions for allotment ${label}`} trigger="button" />
                    </div>
                    <div className="min-w-0 px-3 pb-2 pt-1.5 md:px-4">
                        <AllotmentRecordWorkspace item={item} actions={actions} canWrite={ctx.canWrite} activeTab={activeTab} onTabChange={setActiveTab} />
                    </div>
                </div>
            )}
        </article>
    );
});
