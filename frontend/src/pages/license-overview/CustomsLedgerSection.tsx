import { Fragment, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { useLicenseDetail } from "./useLicenseDetail";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fmtNum } from "@/pages/license-balance/licenseBalanceHelpers";
import ItemUsageDrill from "./ItemUsageDrill";
import { ItemTagsEditor, LicenceMarkingControl } from "./ItemRowControls";
import { useCanEditLicence } from "./useLicenceModalParity";

type Canonical = { id: number; name: string; sion_norm_class?: { id: number; norm_class: string } | null };
type Item = { id: number; serial_number?: number | null; description?: string | null; hs_code?: string | null; hs_code_label?: string | null; unit?: string | null; items_detail?: Canonical[]; quantity?: number | null; debited_quantity?: number | null; boe_debited_quantity?: number | null; allotted_quantity?: number | null; planned_quantity?: number | null; available_quantity?: number | null; actual_available_quantity?: number | null; remaining_planned_quantity?: number | null; cif_fc?: number | null; debited_value?: number | null; allotted_value?: number | null; planned_cif_fc?: number | null; balance_cif_fc?: number | null; remaining_planned_cif_fc?: number | null; billed_no_boe?: number | null; billed_no_boe_qty?: number | null; condition_type?: string | null };

const number = (value: number | null | undefined, digits: number) => value == null ? "—" : fmtNum(value, digits);
const actualAvailableQuantity = (item: Item) => Number(item.quantity ?? 0) - Number(item.boe_debited_quantity ?? 0) - Number(item.allotted_quantity ?? 0) - Number(item.billed_no_boe_qty ?? 0);
const status = (item: Item) => item.actual_available_quantity == null ? "Unavailable" : item.actual_available_quantity === 0 ? "Exhausted" : (item.planned_quantity ?? 0) > 0 ? "Planned" : ((item.debited_quantity ?? 0) > 0 || (item.allotted_quantity ?? 0) > 0) ? "Partially Used" : "Available";
const product = (item: Item) => item.items_detail?.map((entry) => entry.name).join(", ") || item.description || "Unmapped product";
function Identity({ item }: { item: Item }) { return <><p className="font-medium">{product(item)}</p><ul className="mt-1 flex flex-wrap gap-1" aria-label="Canonical product and SION identities">{item.items_detail?.map((entry) => <li key={`${entry.id}-${entry.sion_norm_class?.id ?? "none"}`} className="rounded bg-muted px-1.5 py-0.5 text-[11px]">{entry.name} · SION {entry.sion_norm_class?.norm_class ?? "—"}</li>) || <li>Product/SION mapping unavailable</li>}</ul></>; }
const quantityFields: [string, keyof Item][] = [["Total", "quantity"], ["BOE Debited", "boe_debited_quantity"], ["Allotted", "allotted_quantity"], ["Billed (No BOE)", "billed_no_boe_qty"], ["Planned", "planned_quantity"], ["Actual Available", "actual_available_quantity"], ["Plan Remaining", "remaining_planned_quantity"]];
const cifFields: [string, keyof Item][] = [["Opening", "cif_fc"], ["BOE Debited", "debited_value"], ["Allotted", "allotted_value"], ["Billed (No BOE)", "billed_no_boe"], ["Planned", "planned_cif_fc"], ["Actual Balance", "balance_cif_fc"], ["Plan Remaining", "remaining_planned_cif_fc"]];
function Card({ item, children }: { item: Item; children?: ReactNode }) { const currentStatus = status(item); return <article className="space-y-3 rounded-xl border border-border/70 bg-card p-3 shadow-sm" aria-label={`SR ${item.serial_number ?? "unknown"}: ${product(item)}`}><header><p className="text-xs font-semibold text-primary">SR {item.serial_number ?? "—"} · {product(item)}</p><p className="text-sm text-muted-foreground">{item.description ?? "—"}</p><p className="text-xs text-muted-foreground">HSN {item.hs_code_label ?? "—"} · Unit {item.unit ?? "—"}</p><Identity item={item}/></header>{[["Quantity", quantityFields, 3], ["CIF (FC)", cifFields, 2]].map(([title, fields, digits]) => <section key={title as string}><h4 className="mb-2 text-xs font-semibold uppercase tracking-wide">{title as string}</h4><dl className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-3">{(fields as [string, keyof Item][]).map(([label, field]) => <div key={field}><dt className="text-[10px] font-semibold uppercase text-muted-foreground">{label}</dt><dd className="text-sm font-medium tabular-nums">{number(item[field] as number | null | undefined, digits as number)}{item[field] != null && title === "Quantity" && item.unit ? <span className="ml-1 text-[10px] text-muted-foreground">{item.unit}</span> : null}</dd></div>)}</dl></section>)}<p className="text-xs"><strong>Status:</strong> {currentStatus}</p>{children}</article>; }


/** Body columns: 4 identity + 7 quantity + 7 CIF + Status + Marking. */
const BODY_COLUMNS = 4 + quantityFields.length + cifFields.length + 2;

interface RowControlsProps {
    licenseId: string | number;
    item: Item;
    canEdit: boolean;
    normClass?: string | null;
    expanded: boolean;
    onToggle: () => void;
}

function UsageToggle({ item, expanded, onToggle, controlsId }: Pick<RowControlsProps, "item" | "expanded" | "onToggle"> & { controlsId: string }) {
    return (
        <Button
            variant="ghost"
            size="icon"
            className="size-6"
            aria-expanded={expanded}
            aria-controls={controlsId}
            aria-label={`${expanded ? "Hide" : "Show"} usage for SR ${item.serial_number ?? item.id}`}
            onClick={onToggle}
        >
            {expanded ? <ChevronDown className="size-3.5" aria-hidden="true" /> : <ChevronRight className="size-3.5" aria-hidden="true" />}
        </Button>
    );
}

/** Mobile-card variant of the ported modal controls (tags, marking, usage drill). */
function CardControls({ licenseId, item, canEdit, normClass, expanded, onToggle }: RowControlsProps) {
    return (
        <div className="space-y-2 border-t pt-2 text-xs">
            {canEdit && <ItemTagsEditor licenseId={licenseId} itemId={item.id} tags={item.items_detail ?? []} normClass={normClass} />}
            <div className="flex items-center gap-2"><strong>License Marking:</strong> <LicenceMarkingControl licenseId={licenseId} itemId={item.id} value={item.condition_type} canEdit={canEdit} label={`License marking for SR ${item.serial_number ?? item.id}`} /></div>
            <div className="flex items-center gap-1"><UsageToggle item={item} expanded={expanded} onToggle={onToggle} controlsId={`item-usage-card-${item.id}`} /> Usage</div>
            {expanded && <div id={`item-usage-card-${item.id}`}><ItemUsageDrill licenseId={licenseId} itemId={item.id} type="import" /></div>}
        </div>
    );
}

type Detail = { import_license?: Item[]; get_norm_class?: string | null };
const selectDetail = (data: Record<string, unknown>) => data as Detail;

/** One source-row-authoritative matrix. It never groups or recalculates item values. */
export default function CustomsLedgerSection({ licenseId }: { licenseId: string | number }) {
    const canEdit = useCanEditLicence();
    const [expandedId, setExpandedId] = useState<number | null>(null);
    const query = useLicenseDetail(licenseId, selectDetail);
    const normClass = query.data?.get_norm_class ?? null;
    const items = useMemo(
        () => (query.data?.import_license ?? []).map((item) => ({
            ...item,
            actual_available_quantity: actualAvailableQuantity(item),
        })),
        [query.data],
    );
    const toggle = (id: number) => setExpandedId((prev) => (prev === id ? null : id));
    if (query.isLoading) return <div className="flex items-center gap-2 py-5 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Loading import-item utilization…</div>;
    if (query.isError) return <p className="flex gap-2 py-4 text-sm text-destructive"><AlertTriangle className="size-4" /> Failed to load import-item utilization.</p>;
    return <section aria-labelledby="import-items-utilization-heading" className="space-y-3"><div className="flex flex-wrap items-start justify-between gap-2"><div><h3 id="import-items-utilization-heading" className="text-sm font-semibold">Import Items &amp; Utilization</h3><p className="mt-0.5 text-xs text-muted-foreground">One server-authoritative source row per SR number. No product rows are aggregated in the browser.</p></div><Badge variant="outline">{items.length} {items.length === 1 ? "source row" : "source rows"}</Badge></div>{items.length === 0 ? <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">No import items on this licence.</p> : <><div className="grid gap-3 md:hidden">{items.map((item) => <Card key={item.id} item={item}><CardControls licenseId={licenseId} item={item} canEdit={canEdit} normClass={normClass} expanded={expandedId === item.id} onToggle={() => toggle(item.id)} /></Card>)}</div><div className="hidden overflow-x-auto rounded-lg border border-border/70 md:block" tabIndex={0} aria-label="Import Items and Utilization matrix; scroll horizontally to view all metrics"><table className="w-full min-w-[1900px] text-[13px]"><thead className="bg-muted/95 text-[10px] uppercase tracking-wide text-muted-foreground"><tr><th colSpan={4} className="sticky left-0 z-[2] bg-muted/95 px-3 py-2 text-left">Identity</th><th colSpan={7} className="border-l px-3 py-2 text-center">Quantity</th><th colSpan={7} className="border-l px-3 py-2 text-center">CIF (FC)</th><th className="border-l px-3 py-2">Status</th><th className="border-l px-3 py-2">Marking</th></tr><tr className="border-t"><th className="sticky left-0 z-[2] bg-muted/95 px-3 py-2 text-left">SR No.</th><th className="sticky left-[72px] z-[2] bg-muted/95 px-3 py-2 text-left">Product / SION</th><th className="sticky left-[300px] z-[2] bg-muted/95 px-3 py-2 text-left">Description / HSN</th><th className="sticky left-[510px] z-[2] bg-muted/95 px-3 py-2 text-left">Unit</th>{[...quantityFields, ...cifFields].map(([label], index) => <th key={`${label}-${index}`} className="px-3 py-2 text-right">{label}</th>)}<th className="border-l px-3 py-2">Status</th><th className="border-l px-3 py-2">License Marking</th></tr></thead><tbody>{items.map((item) => { const expanded = expandedId === item.id; return <Fragment key={item.id}><tr className="border-t bg-card hover:bg-muted/20"><td className="sticky left-0 z-[1] bg-card px-3 py-2 tabular-nums"><span className="inline-flex items-center gap-1"><UsageToggle item={item} expanded={expanded} onToggle={() => toggle(item.id)} controlsId={`item-usage-${item.id}`} />{item.serial_number ?? "—"}</span></td><td className="sticky left-[72px] z-[1] min-w-[228px] bg-card px-3 py-2"><Identity item={item}/>{canEdit && <ItemTagsEditor licenseId={licenseId} itemId={item.id} tags={item.items_detail ?? []} normClass={normClass} />}</td><td className="sticky left-[300px] z-[1] min-w-[210px] bg-card px-3 py-2">{item.description ?? "—"}<p className="text-xs text-muted-foreground">HSN {item.hs_code_label ?? "—"}</p></td><td className="sticky left-[510px] z-[1] bg-card px-3 py-2">{item.unit ?? "—"}</td>{quantityFields.map(([, field]) => <td key={field} className="px-3 py-2 text-right tabular-nums">{number(item[field] as number | null | undefined, 3)}</td>)}{cifFields.map(([, field]) => <td key={field} className="px-3 py-2 text-right tabular-nums">{number(item[field] as number | null | undefined, 2)}</td>)}<td className="border-l px-3 py-2"><Badge variant={status(item) === "Exhausted" ? "destructive" : "outline"}>{status(item)}</Badge></td><td className="border-l px-3 py-2"><LicenceMarkingControl licenseId={licenseId} itemId={item.id} value={item.condition_type} canEdit={canEdit} label={`License marking for SR ${item.serial_number ?? item.id}`} /></td></tr>{expanded && <tr id={`item-usage-${item.id}`} className="border-t bg-muted/20"><td colSpan={BODY_COLUMNS} className="px-3 py-3"><div className="sticky left-3 max-w-[900px]"><ItemUsageDrill licenseId={licenseId} itemId={item.id} type="import" /></div></td></tr>}</Fragment>; })}</tbody></table></div></>}<p className="text-[11px] text-muted-foreground">— means the canonical licence-detail response did not provide a value; numeric zero remains visible as zero.</p></section>;
}
