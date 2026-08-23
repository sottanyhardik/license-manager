import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Info, Loader2 } from "lucide-react";
import api from "@/api/axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fmtNum } from "@/pages/license-balance/licenseBalanceHelpers";
import QuantityUtilization from "./QuantityUtilization";

interface CustomsImportItem {
    id: number;
    description?: string | null;
    hs_code?: string | null;
    items_detail?: { id: number; name: string }[];
    quantity?: number | null;
    allotted_quantity?: number | null;
    debited_quantity?: number | null;
    /** Informational only — from the Planning module (`plan_reporting.
     * plan_map_for_import_items`), never a component of `available_quantity`. */
    planned_quantity?: number | null;
    available_quantity?: number | null;
    unit?: string | null;
    cif_fc?: number | null;
    balance_cif_fc?: number | null;
}

interface CustomsLedgerSectionProps {
    licenseId: string | number;
}

function itemLabel(item: CustomsImportItem): string {
    if (item.items_detail && item.items_detail.length > 0) {
        return item.items_detail.map((d) => d.name).join(", ");
    }
    return item.description || "-";
}

function display(value: number | null | undefined, digits = 3): string {
    return value === null || value === undefined ? "—" : fmtNum(value, digits);
}

function Metric({ label, value, description, emphasize }: { label: string; value: string; description: string; emphasize?: boolean }) {
    return (
        <div className={cn("min-w-0 border-l border-border/60 pl-3 first:border-l-0 first:pl-0", emphasize && "text-primary")} title={description}>
            <dt className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</dt>
            <dd className="mt-0.5 truncate text-[13px] font-semibold tabular-nums">{value}</dd>
        </div>
    );
}

function ExpandedItemDetails({ item }: { item: CustomsImportItem }) {
    return (
        <div className="grid gap-3 border-t border-border/60 bg-muted/20 px-3 py-3 lg:grid-cols-2">
            <section aria-label="Quantity reconciliation">
                <h4 className="mb-2 text-xs font-semibold text-foreground">Quantity reconciliation</h4>
                <dl className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-3">
                    <Metric label="Total" value={display(item.quantity)} description="Original eligible quantity." />
                    <Metric label="BOE debited" value={display(item.debited_quantity)} description="Quantity actually debited through BOEs." />
                    <Metric label="Allotted" value={display(item.allotted_quantity)} description="Quantity assigned through allotments." />
                    <Metric label="Planned" value={item.planned_quantity == null ? "Not planned" : display(item.planned_quantity)} description="Planning information; not an actual debit." />
                    <Metric label="Actual available" value={display(item.available_quantity)} description="Server-authoritative current available quantity." emphasize />
                    <Metric label="Plan remaining" value="—" description="Not supplied by this licence-detail response." />
                </dl>
            </section>
            <section aria-label="CIF reconciliation">
                <h4 className="mb-2 text-xs font-semibold text-foreground">CIF reconciliation</h4>
                <dl className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-3">
                    <Metric label="Opening CIF" value={display(item.cif_fc, 2)} description="CIF returned for this import item." />
                    <Metric label="BOE debited" value="—" description="Not supplied per item by this response." />
                    <Metric label="Allotted" value="—" description="Not supplied per item by this response." />
                    <Metric label="Planned" value="—" description="Not supplied per item by this response." />
                    <Metric label="Actual balance" value={display(item.balance_cif_fc, 2)} description="Server-authoritative balance CIF returned for this item." emphasize />
                    <Metric label="Plan remaining" value="—" description="Not supplied by this response." />
                </dl>
            </section>
            <section className="lg:col-span-2" aria-label="Item supporting information">
                <h4 className="mb-1 text-xs font-semibold text-foreground">Supporting information</h4>
                <p className="text-xs text-muted-foreground">Item names: {itemLabel(item)} · HS code: {item.hs_code || "—"} · Unit: {item.unit || "—"}</p>
            </section>
        </div>
    );
}

/**
 * Overview tab's Customs Ledger — Item Detail ("Quantity Summary") section.
 *
 * `LicenseBalanceModal.tsx`'s Export/Import item tables are tightly coupled
 * to that modal's local inline-editing state (item tags, condition-type
 * select, expand/usage-fetch) — extracting them cleanly without dragging
 * that state along would be a much larger refactor than this workspace
 * warrants. Per the brief's explicit fallback, this renders a simplified,
 * REAL (not placeholder) view of the same `licenses/{id}/` data: per-item
 * Total/Debited/Allotted/Planned/Available Qty + Balance CIF, read-only.
 *
 * Available Qty = Total − Debited − Allotted (outstanding, BOE-unlinked
 * only) — the same Balance Engine formula everywhere else in the app.
 * Planned Qty is purely informational (from the Planning module) and never
 * reduces Available Qty.
 *
 * Relocated (unchanged) from `pages/license-balance/`.
 */
export default function CustomsLedgerSection({ licenseId }: CustomsLedgerSectionProps) {
    const [expandedItem, setExpandedItem] = useState<number | null>(null);
    const { data, isLoading, isError } = useQuery({
        queryKey: ["license-balance-customs-ledger", String(licenseId)],
        queryFn: async () => {
            const { data } = await api.get(`licenses/${licenseId}/`);
            return data as { import_license?: CustomsImportItem[] };
        },
    });

    if (isLoading) {
        return <div className="flex items-center gap-2 py-5 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Loading import-item utilization…</div>;
    }
    if (isError) {
        return <p className="py-4 text-sm text-destructive">Failed to load customs ledger data.</p>;
    }

    const items = data?.import_license ?? [];

    return (
        <section aria-labelledby="import-item-utilization-heading" className="space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
                <div><h3 id="import-item-utilization-heading" className="text-sm font-semibold text-foreground">Import-item utilization</h3><p className="mt-0.5 text-xs text-muted-foreground">Quantity, CIF, BOE, allotment, and planning dimensions are shown separately.</p></div>
                <Badge variant="outline" className="tabular-nums">{items.length} {items.length === 1 ? "item" : "items"}</Badge>
            </div>
            {items.length > 0 && <div className="rounded-lg border border-primary/15 bg-primary/[0.025] p-2"><div className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground"><Info className="size-3.5" /> Quantity availability is server-authoritative</div><div className="grid gap-2 xl:grid-cols-2">{items.map((item) => <QuantityUtilization key={`utilization-${item.id}`} label={`${itemLabel(item)} quantity utilization`} unit={item.unit} values={{ totalQuantity: item.quantity, boeDebitedQuantity: item.debited_quantity, allottedQuantity: item.allotted_quantity, plannedQuantity: item.planned_quantity, actualAvailableQuantity: item.available_quantity }} />)}</div></div>}
            <div className="overflow-x-auto rounded-lg border border-border/70" tabIndex={0} aria-label="Import-item utilization table; scroll horizontally to view all columns">
                <table className="min-w-[1700px] w-full text-[13px]">
                    <thead className="sticky top-0 z-[1] bg-muted/95 text-[10px] uppercase tracking-wide text-muted-foreground">
                        <tr className="border-b border-border/70"><th colSpan={4} className="sticky left-0 z-[2] bg-muted/95 px-3 py-2 text-left font-semibold">Import item</th><th colSpan={6} className="border-l border-border/70 px-3 py-2 text-center font-semibold">Quantity</th><th colSpan={7} className="border-l border-border/70 px-3 py-2 text-center font-semibold">CIF (FC)</th><th colSpan={2} className="border-l border-border/70 px-3 py-2 text-center font-semibold">Status</th></tr>
                        <tr className="border-b border-border/70"><th className="sticky left-0 z-[2] bg-muted/95 px-3 py-2 text-left font-semibold">Description</th><th className="px-3 py-2 text-left font-semibold">Item name</th><th className="px-3 py-2 text-left font-semibold">HS code</th><th className="px-3 py-2 text-left font-semibold">Unit</th><th className="border-l border-border/70 px-3 py-2 text-right font-semibold">Total</th><th className="px-3 py-2 text-right font-semibold">BOE debited</th><th className="px-3 py-2 text-right font-semibold">Allotted</th><th className="px-3 py-2 text-right font-semibold">Planned</th><th className="px-3 py-2 text-right font-semibold">Actual available</th><th className="px-3 py-2 text-right font-semibold">Plan remaining</th><th className="border-l border-border/70 px-3 py-2 text-right font-semibold">Opening</th><th className="px-3 py-2 text-right font-semibold">BOE debited</th><th className="px-3 py-2 text-right font-semibold">Allotted</th><th className="px-3 py-2 text-right font-semibold">Planned</th><th className="px-3 py-2 text-right font-semibold">Actual balance</th><th className="px-3 py-2 text-right font-semibold">Operational available</th><th className="px-3 py-2 text-right font-semibold">Plan remaining</th><th className="border-l border-border/70 px-3 py-2 text-left font-semibold">Planning</th><th className="px-3 py-2 text-center font-semibold">Details</th></tr>
                    </thead>
                    <tbody>
                        {items.length === 0 ? <tr><td colSpan={19} className="px-3 py-8 text-center text-sm text-muted-foreground">No import items on this licence.</td></tr> : items.map((item) => {
                            const expanded = expandedItem === item.id;
                            return <Fragment key={item.id}>
                                <tr key={item.id} className="border-b border-border/50 bg-card hover:bg-muted/25"><td className="sticky left-0 z-[1] max-w-[240px] bg-card px-3 py-2 align-middle font-medium" title={item.description || undefined}>{item.description || "—"}</td><td className="max-w-[220px] truncate px-3 py-2" title={itemLabel(item)}>{itemLabel(item)}</td><td className="px-3 py-2 tabular-nums">{item.hs_code || "—"}</td><td className="px-3 py-2">{item.unit || "—"}</td><td className="border-l border-border/50 px-3 py-2 text-right tabular-nums">{display(item.quantity)}</td><td className="px-3 py-2 text-right tabular-nums">{display(item.debited_quantity)}</td><td className="px-3 py-2 text-right tabular-nums">{display(item.allotted_quantity)}</td><td className="px-3 py-2 text-right tabular-nums">{item.planned_quantity == null ? "Not planned" : display(item.planned_quantity)}</td><td className="px-3 py-2 text-right font-semibold tabular-nums">{display(item.available_quantity)}</td><td className="px-3 py-2 text-right tabular-nums">—</td><td className="border-l border-border/50 px-3 py-2 text-right tabular-nums">{display(item.cif_fc, 2)}</td><td className="px-3 py-2 text-right tabular-nums">—</td><td className="px-3 py-2 text-right tabular-nums">—</td><td className="px-3 py-2 text-right tabular-nums">—</td><td className="px-3 py-2 text-right font-semibold tabular-nums">{display(item.balance_cif_fc, 2)}</td><td className="px-3 py-2 text-right tabular-nums">—</td><td className="px-3 py-2 text-right tabular-nums">—</td><td className="border-l border-border/50 px-3 py-2"><Badge variant={item.planned_quantity == null ? "outline" : "secondary"}>{item.planned_quantity == null ? "Not planned" : "Planned"}</Badge></td><td className="px-3 py-1.5 text-center"><Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => setExpandedItem(expanded ? null : item.id)} aria-expanded={expanded} aria-label={`${expanded ? "Collapse" : "Expand"} ${itemLabel(item)} details`}>{expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}</Button></td></tr>
                                {expanded && <tr key={`${item.id}-details`}><td colSpan={19} className="p-0"><ExpandedItemDetails item={item} /></td></tr>}
                            </Fragment>;
                        })}
                    </tbody>
                </table>
            </div>
            <p className="text-[11px] text-muted-foreground">An em dash means the canonical licence-detail response does not supply that metric; it is never interpreted as zero.</p>
        </section>
    );
}
