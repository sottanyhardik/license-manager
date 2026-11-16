import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight, FileText, Loader2, Package, PenSquare, Pencil, Save, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import OverUtilisedBadge from "@/components/OverUtilisedBadge";

import { fmtNum } from "./licenseOverviewHelpers";
import ItemUsageDrill from "./ItemUsageDrill";
import { useLicenseDetail } from "./useLicenseDetail";
import { useCanEditLicence, useLicenceModalEdits, type LicenceTextField } from "./useLicenceModalParity";

type ExportRow = { id: number; description?: string | null; norm_class_label?: string | null; cif_fc?: number | string | null; fob_fc?: number | string | null };
type LicenceFields = {
    condition_sheet?: string | null;
    balance_report_notes?: string | null;
    balance_cif?: number | string | null;
    is_over_utilised?: boolean | null;
    export_license?: ExportRow[];
};

const selectFields = (data: Record<string, unknown>): LicenceFields => data as LicenceFields;
const money = (value: number | string | null | undefined) => (value == null || value === "" ? "—" : fmtNum(Number(value), 2));

interface InlineTextProps {
    licenseId: string | number;
    field: LicenceTextField;
    label: string;
    icon: typeof FileText;
    text: string;
    canEdit: boolean;
}

/** Port of the modal's `InlineEditableText` (`LicenseBalanceModal.tsx:31, :539-565`). */
function InlineTextBlock({ licenseId, field, label, icon: Icon, text, canEdit }: InlineTextProps) {
    const { saveLicenceText } = useLicenceModalEdits(licenseId);
    const [draft, setDraft] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const editing = draft !== null;
    const inputId = `licence-${field}`;

    const handleSave = async () => {
        if (draft === null) return;
        setSaving(true);
        const ok = await saveLicenceText(field, draft, label);
        setSaving(false);
        if (ok) setDraft(null);
    };

    return (
        <section aria-labelledby={`${inputId}-heading`} className="min-w-0 space-y-2">
            <div className="flex items-center justify-between gap-2">
                <h3 id={`${inputId}-heading`} className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-widest text-muted-foreground">
                    <Icon className="size-3.5" aria-hidden="true" /> {label}
                </h3>
                {canEdit && !editing && (
                    <Button variant="ghost" size="sm" onClick={() => setDraft(text)} aria-label={`Edit ${label.toLowerCase()}`}>
                        <Pencil className="size-3.5" aria-hidden="true" /> Edit
                    </Button>
                )}
            </div>
            {editing ? (
                <div className="space-y-2">
                    <label htmlFor={inputId} className="sr-only">{label}</label>
                    <Textarea
                        id={inputId}
                        rows={4}
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        placeholder={`Enter ${label.toLowerCase()} here...`}
                        disabled={saving}
                    />
                    <div className="flex gap-2">
                        <Button size="sm" onClick={() => void handleSave()} disabled={saving}>
                            {saving ? <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> : <Save className="size-3.5" aria-hidden="true" />}
                            {saving ? "Saving..." : "Save"}
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setDraft(null)} disabled={saving}>
                            <X className="size-3.5" aria-hidden="true" /> Cancel
                        </Button>
                    </div>
                </div>
            ) : (
                <p className="min-h-12 whitespace-pre-wrap rounded-md border border-border/70 bg-muted/30 px-3 py-2 text-sm">
                    {text || <span className="italic text-muted-foreground">No {label.toLowerCase()}.</span>}
                </p>
            )}
        </section>
    );
}

/** Port of the modal's Export Items table (`LicenseBalanceModal.tsx:574-711`) with its usage drill. */
function ExportItemsTable({ licenseId, rows, balanceCif, isOverUtilised }: { licenseId: string | number; rows: ExportRow[]; balanceCif: LicenceFields["balance_cif"]; isOverUtilised: LicenceFields["is_over_utilised"] }) {
    const [expandedId, setExpandedId] = useState<number | null>(null);
    return (
        <section aria-labelledby="licence-export-items-heading" className="space-y-2">
            <h3 id="licence-export-items-heading" className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-widest text-muted-foreground">
                <Package className="size-3.5" aria-hidden="true" /> Export Items
            </h3>
            <div className="overflow-x-auto rounded-lg border border-border/70">
                <table className="w-full text-[13px]">
                    <thead className="bg-muted/95 text-[10px] uppercase tracking-wide text-muted-foreground">
                        <tr>
                            <th scope="col" className="w-10 px-3 py-2"><span className="sr-only">Usage</span></th>
                            <th scope="col" className="px-3 py-2 text-left">Item</th>
                            <th scope="col" className="px-3 py-2 text-right">Total CIF</th>
                            <th scope="col" className="px-3 py-2 text-right">Balance CIF</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row) => {
                            const expanded = expandedId === row.id;
                            const name = row.description || row.norm_class_label || "None";
                            return (
                                <Fragment key={row.id}>
                                    <tr className="border-t bg-card">
                                        <td className="px-3 py-2">
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="size-7"
                                                aria-expanded={expanded}
                                                aria-controls={`export-usage-${row.id}`}
                                                aria-label={`${expanded ? "Hide" : "Show"} usage for ${name}`}
                                                onClick={() => setExpandedId(expanded ? null : row.id)}
                                            >
                                                {expanded ? <ChevronDown className="size-4" aria-hidden="true" /> : <ChevronRight className="size-4" aria-hidden="true" />}
                                            </Button>
                                        </td>
                                        <td className="px-3 py-2">{name}</td>
                                        <td className="px-3 py-2 text-right tabular-nums">{money(row.cif_fc ?? row.fob_fc)}</td>
                                        <td className="px-3 py-2 text-right tabular-nums">
                                            {money(balanceCif)}
                                            <OverUtilisedBadge balance={balanceCif} isOverUtilised={isOverUtilised} />
                                        </td>
                                    </tr>
                                    {expanded && (
                                        <tr id={`export-usage-${row.id}`} className="bg-muted/20">
                                            <td colSpan={4} className="px-3 py-3"><ItemUsageDrill licenseId={licenseId} itemId={row.id} type="export" /></td>
                                        </tr>
                                    )}
                                </Fragment>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </section>
    );
}

/**
 * Licence-level features ported from `LicenseBalanceModal` (doc 06 D3 (c)):
 * condition sheet, notes and the Export Items table. Reads the shared
 * `licenses/:id/` cache entry, so it adds no request.
 */
export default function LicenceModalSections({ licenseId }: { licenseId: string | number }) {
    const canEdit = useCanEditLicence();
    const { data } = useLicenseDetail(licenseId, selectFields);
    if (!data) return null;
    const exportRows = data.export_license ?? [];

    return (
        <Card className="border-border/70 shadow-sm">
            <CardContent className="space-y-4 px-4 py-3">
                <div className="grid gap-4 md:grid-cols-2">
                    <InlineTextBlock licenseId={licenseId} field="condition_sheet" label="Condition Sheet" icon={FileText} text={data.condition_sheet ?? ""} canEdit={canEdit} />
                    <InlineTextBlock licenseId={licenseId} field="balance_report_notes" label="Notes" icon={PenSquare} text={data.balance_report_notes ?? ""} canEdit={canEdit} />
                </div>
                {exportRows.length > 0 && (
                    <ExportItemsTable licenseId={licenseId} rows={exportRows} balanceCif={data.balance_cif} isOverUtilised={data.is_over_utilised} />
                )}
            </CardContent>
        </Card>
    );
}
