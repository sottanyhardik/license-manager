/**
 * BalanceTab — inline balance view embedded in the license accordion.
 *
 * Mirrors the LicenseBalanceModal exactly — same API calls, same data,
 * same business logic — but rendered inside the tab panel instead of
 * a Dialog.
 *
 * APIs used (identical to LicenseBalanceModal):
 *   GET  licenses/{id}/          — detail with import_license, export_license
 *   GET  licenses/{id}/balance-pdf/   → PDF blob
 *   GET  licenses/{id}/balance-excel/ → Excel blob
 *   PATCH licenses/{id}/              → condition_sheet / balance_report_notes
 *   PATCH license-items/{id}/         → condition_type (license marking)
 *
 * Data comes from the `detail` prop already fetched by LicenseRow on expand.
 * No duplicate fetch. Download buttons call the same endpoints as the modal.
 */

import { useCallback, useEffect, useState } from "react";
import {
    CheckCircle,
    FileSpreadsheet,
    FileText,
    Loader2,
    Pencil,
    X,
} from "lucide-react";
import { toast } from "sonner";
import Select from "react-select";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import api from "../../../api/axios";
import ConditionBadge from "../../../components/ConditionBadge";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function fmtDec(v: unknown, dp = 2): string {
    const n = Number(v);
    return Number.isFinite(n) ? n.toFixed(dp) : "0.00";
}

const LICENSE_MARKING_OPTIONS = [
    { value: "", label: "None" },
    { value: "AU", label: "AU" },
    { value: "10%", label: "10%" },
    { value: "5%", label: "5%" },
    { value: "3%", label: "3%" },
    { value: "2%", label: "2%" },
];

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface ImportItemRow {
    id: number;
    serial_number: number;
    description: string;
    hs_code_label?: string;
    quantity?: number;
    unit?: string;
    cif_fc?: number;
    allotted_quantity?: number;
    debited_quantity?: number;
    available_quantity?: number;
    balance_cif_fc?: number;
    condition_type?: string;
    [key: string]: unknown;
}

interface ExportItemRow {
    id: number;
    description?: string;
    norm_class_label?: string;
    cif_fc?: number;
    fob_fc?: number;
    [key: string]: unknown;
}

interface LicenseDetail {
    id: number;
    license_number?: string;
    license_date?: string;
    license_expiry_date?: string;
    exporter_name?: string;
    port_name?: string;
    balance_cif?: number | string;
    purchase_status_label?: string;
    latest_transfer?: string;
    condition_sheet?: string | null;
    balance_report_notes?: string | null;
    import_license?: ImportItemRow[];
    export_license?: ExportItemRow[];
    has_tl?: boolean;
    has_copy?: boolean;
    [key: string]: unknown;
}

interface BalanceTabProps {
    licenseId: number;
    detail: LicenseDetail | null;
    detailLoading: boolean;
    onDetailUpdate: (patch: Partial<LicenseDetail>) => void;
    onDownloadPdf: () => void;
    onDownloadExcel: () => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Inline editable note — identical logic to LicenseBalanceModal.InlineEditableText
// ─────────────────────────────────────────────────────────────────────────────

function EditableNote({
    licenseId,
    value,
    fieldName,
    label,
    onUpdate,
}: {
    licenseId: number;
    value: string | null;
    fieldName: string;
    label: string;
    onUpdate: (v: string) => void;
}) {
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState(value ?? "");
    const [saving, setSaving] = useState(false);

    useEffect(() => { setDraft(value ?? ""); }, [value]);

    const handleSave = async () => {
        setSaving(true);
        try {
            await api.patch(`licenses/${licenseId}/`, { [fieldName]: draft });
            onUpdate(draft);
            setEditing(false);
            toast.success(`${label} saved`);
        } catch {
            toast.error(`Failed to save ${label}`);
        } finally {
            setSaving(false);
        }
    };

    if (editing) {
        return (
            <div className="space-y-2">
                <textarea
                    className="flex w-full rounded-md border border-ring bg-card px-3 py-2 text-sm outline-none focus-visible:border-ring"
                    rows={4}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    placeholder={`Enter ${label.toLowerCase()}…`}
                    autoFocus
                />
                <div className="flex gap-2">
                    <button
                        type="button"
                        onClick={handleSave}
                        disabled={saving}
                        className="flex items-center gap-1.5 rounded bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 cursor-pointer"
                    >
                        <CheckCircle className="size-3.5" aria-hidden="true" />
                        {saving ? "Saving…" : "Save"}
                    </button>
                    <button
                        type="button"
                        onClick={() => { setDraft(value ?? ""); setEditing(false); }}
                        disabled={saving}
                        className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1 text-xs font-medium text-muted-foreground hover:bg-muted cursor-pointer"
                    >
                        <X className="size-3.5" aria-hidden="true" />Cancel
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div
            role="button"
            tabIndex={0}
            onClick={() => setEditing(true)}
            onKeyDown={(e) => e.key === "Enter" && setEditing(true)}
            aria-label={`Edit ${label}`}
            className={cn(
                "min-h-[60px] cursor-pointer rounded-md border px-3 py-2.5 text-sm transition-colors",
                "hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                draft ? "border-border bg-card/80 text-foreground" : "border-dashed border-border/60 bg-muted/20 text-muted-foreground"
            )}
        >
            {draft ? (
                <span className="whitespace-pre-wrap">{draft}</span>
            ) : (
                <span className="italic">Click to add {label.toLowerCase()}…</span>
            )}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// License marking row — same PATCH logic as LicenseBalanceModal
// ─────────────────────────────────────────────────────────────────────────────

function MarkingRow({
    row,
    appliedMarking,
    onMarked,
}: {
    row: ImportItemRow;
    appliedMarking: string;
    onMarked: (id: number, marking: string) => void;
}) {
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);

    const saveMarking = async (marking: string) => {
        setSaving(true);
        try {
            await api.patch(`license-items/${row.id}/`, { condition_type: marking || null });
            onMarked(row.id, marking);
            setEditing(false);
            toast.success("License marking updated");
        } catch {
            toast.error("Failed to update marking");
        } finally {
            setSaving(false);
        }
    };

    if (!editing) {
        return (
            <div className="flex flex-wrap items-center gap-2">
                <ConditionBadge type={appliedMarking} size="sm" />
                <button
                    type="button"
                    onClick={() => setEditing(true)}
                    className="flex items-center gap-1 rounded border border-border/60 bg-muted/40 px-1.5 py-0.5 text-[10.5px] text-muted-foreground hover:bg-muted cursor-pointer"
                >
                    <Pencil className="size-3" aria-hidden="true" />Edit
                </button>
            </div>
        );
    }

    return (
        <div className="flex flex-wrap items-center gap-2">
            <Select
                options={LICENSE_MARKING_OPTIONS}
                value={LICENSE_MARKING_OPTIONS.find((o) => o.value === appliedMarking) ?? LICENSE_MARKING_OPTIONS[0]}
                onChange={(opt) => { if (opt) saveMarking(opt.value); }}
                isDisabled={saving}
                menuPortalTarget={document.body}
                menuPosition="fixed"
                className="text-xs w-28"
                classNamePrefix="marking-select"
            />
            {saving && <Loader2 className="size-3.5 animate-spin text-muted-foreground" aria-hidden="true" />}
            <button
                type="button"
                onClick={() => setEditing(false)}
                className="text-xs text-muted-foreground hover:text-foreground cursor-pointer"
            >
                Cancel
            </button>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main BalanceTab
// ─────────────────────────────────────────────────────────────────────────────

export default function BalanceTab({
    licenseId,
    detail,
    detailLoading,
    onDetailUpdate,
    onDownloadPdf,
    onDownloadExcel,
}: BalanceTabProps) {
    const [conditionSheet, setConditionSheet] = useState(detail?.condition_sheet ?? "");
    const [notes, setNotes] = useState(detail?.balance_report_notes ?? "");
    // Per-row marking override (same as LicenseBalanceModal marking state)
    const [markings, setMarkings] = useState<Record<number, string>>({});

    // Sync note fields when detail prop updates
    useEffect(() => {
        setConditionSheet(detail?.condition_sheet ?? "");
        setNotes(detail?.balance_report_notes ?? "");
    }, [detail?.condition_sheet, detail?.balance_report_notes]);

    const handleMarkingUpdate = useCallback((id: number, marking: string) => {
        setMarkings((prev) => ({ ...prev, [id]: marking }));
    }, []);

    // ── Loading / null guard ─────────────────────────────────────────────────

    if (detailLoading || !detail) {
        return (
            <div className="space-y-3 py-4">
                <Skeleton className="h-24 w-full rounded-xl" />
                <Skeleton className="h-48 w-full rounded-xl" />
                <Skeleton className="h-24 w-full rounded-xl" />
            </div>
        );
    }

    const importItems = (detail.import_license ?? []) as ImportItemRow[];
    const exportItems = (detail.export_license ?? []) as ExportItemRow[];

    const totalImportBalance = importItems.reduce(
        (s, r) => s + (Number(r.balance_cif_fc) || 0),
        0
    );

    // ── Render ───────────────────────────────────────────────────────────────

    return (
        <div className="space-y-4 py-3">
            {/* ── 1. Financial header + downloads ─────────────────── */}
            <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
                {/* Header table — matches modal's License Header section */}
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-primary text-white">
                            <tr>
                                <th scope="col" className="px-4 py-2.5 text-left text-xs font-semibold">License Number</th>
                                <th scope="col" className="px-4 py-2.5 text-left text-xs font-semibold">License Date</th>
                                <th scope="col" className="px-4 py-2.5 text-left text-xs font-semibold">Expiry Date</th>
                                <th scope="col" className="px-4 py-2.5 text-left text-xs font-semibold">Exporter</th>
                                <th scope="col" className="px-4 py-2.5 text-left text-xs font-semibold">Port</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr className="bg-muted/40">
                                <td className="px-4 py-2.5 text-sm font-semibold text-foreground border-b border-border/50">{detail.license_number || "—"}</td>
                                <td className="px-4 py-2.5 text-sm text-foreground border-b border-border/50">{detail.license_date || "—"}</td>
                                <td className="px-4 py-2.5 text-sm text-foreground border-b border-border/50">{detail.license_expiry_date || "—"}</td>
                                <td className="px-4 py-2.5 text-sm text-foreground border-b border-border/50">{detail.exporter_name || "—"}</td>
                                <td className="px-4 py-2.5 text-sm text-foreground border-b border-border/50">{detail.port_name || "—"}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                {/* Purchase status / balance row — matches second table in modal */}
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-primary text-white">
                            <tr>
                                <th scope="col" className="px-4 py-2.5 text-left text-xs font-semibold">Purchase Status</th>
                                <th scope="col" className="px-4 py-2.5 text-left text-xs font-semibold">Balance CIF</th>
                                <th scope="col" className="px-4 py-2.5 text-left text-xs font-semibold">Latest Transfer</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr className="bg-muted/40">
                                <td className="px-4 py-2.5 text-sm text-foreground border-b border-border/50">{detail.purchase_status_label || "—"}</td>
                                <td className="px-4 py-2.5 text-sm font-bold tabular-nums text-primary border-b border-border/50">
                                    {fmtDec(detail.balance_cif)}
                                </td>
                                <td className="px-4 py-2.5 text-sm text-foreground border-b border-border/50">{detail.latest_transfer || "—"}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                {/* Download buttons */}
                <div className="flex items-center justify-end gap-2 px-4 py-2.5 bg-muted/20">
                    <Button variant="outline" size="sm" onClick={onDownloadPdf} className="h-7 gap-1.5 text-xs">
                        <FileText className="size-3.5" aria-hidden="true" />Download PDF
                    </Button>
                    <Button variant="outline" size="sm" onClick={onDownloadExcel} className="h-7 gap-1.5 text-xs">
                        <FileSpreadsheet className="size-3.5" aria-hidden="true" />Download Excel
                    </Button>
                </div>
            </div>

            {/* ── 2. Condition Sheet ───────────────────────────────── */}
            <div className="rounded-xl border border-border/60 bg-card px-4 py-3">
                <div className="mb-2.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Condition Sheet
                </div>
                <EditableNote
                    licenseId={licenseId}
                    value={conditionSheet}
                    fieldName="condition_sheet"
                    label="Condition Sheet"
                    onUpdate={(v) => { setConditionSheet(v); onDetailUpdate({ condition_sheet: v }); }}
                />
            </div>

            {/* ── 3. Notes ─────────────────────────────────────────── */}
            <div className="rounded-xl border border-border/60 bg-card px-4 py-3">
                <div className="mb-2.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Balance Report Notes
                </div>
                <EditableNote
                    licenseId={licenseId}
                    value={notes}
                    fieldName="balance_report_notes"
                    label="Notes"
                    onUpdate={(v) => { setNotes(v); onDetailUpdate({ balance_report_notes: v }); }}
                />
            </div>

            {/* ── 4. Export Items — matches modal's Export Items section ── */}
            {exportItems.length > 0 && (
                <div className="overflow-hidden rounded-xl border border-border/60">
                    <div className="border-b border-border/50 bg-muted/30 px-4 py-2.5">
                        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                            Export Items
                        </div>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="bg-primary text-white">
                                <tr>
                                    <th scope="col" className="px-3 py-2.5 text-left text-xs font-semibold">Description / Norm Class</th>
                                    <th scope="col" className="px-3 py-2.5 text-right text-xs font-semibold">CIF FC</th>
                                    <th scope="col" className="px-3 py-2.5 text-right text-xs font-semibold">Balance CIF</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border/40">
                                {exportItems.map((ex) => (
                                    <tr key={ex.id} className="hover:bg-muted/20 transition-colors">
                                        <td className="px-3 py-2.5 text-sm text-foreground">
                                            {ex.description || ex.norm_class_label || "—"}
                                        </td>
                                        <td className="px-3 py-2.5 text-right tabular-nums text-sm">
                                            {fmtDec(ex.cif_fc ?? ex.fob_fc)}
                                        </td>
                                        <td className="px-3 py-2.5 text-right tabular-nums text-sm font-semibold text-primary">
                                            {fmtDec(detail.balance_cif)}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* ── 5. Import Items with License Marking ─────────────── */}
            {importItems.length > 0 && (
                <div className="overflow-hidden rounded-xl border border-border/60">
                    <div className="border-b border-border/50 bg-muted/30 px-4 py-2.5">
                        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                            Import Items — Balance &amp; License Marking
                        </div>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="bg-primary/90 text-white">
                                <tr>
                                    <th scope="col" className="px-3 py-2.5 text-left text-xs font-semibold min-w-[50px]">Sr#</th>
                                    <th scope="col" className="px-3 py-2.5 text-left text-xs font-semibold min-w-[100px]">HS Code</th>
                                    <th scope="col" className="px-3 py-2.5 text-left text-xs font-semibold min-w-[200px]">Description</th>
                                    <th scope="col" className="px-3 py-2.5 text-right text-xs font-semibold min-w-[90px]">Total Qty</th>
                                    <th scope="col" className="px-3 py-2.5 text-right text-xs font-semibold min-w-[90px]">Allotted Qty</th>
                                    <th scope="col" className="px-3 py-2.5 text-right text-xs font-semibold min-w-[90px]">Debited Qty</th>
                                    <th scope="col" className="px-3 py-2.5 text-right text-xs font-semibold min-w-[90px]">Available Qty</th>
                                    <th scope="col" className="px-3 py-2.5 text-right text-xs font-semibold min-w-[90px]">CIF FC</th>
                                    <th scope="col" className="px-3 py-2.5 text-right text-xs font-semibold min-w-[100px]">Balance CIF</th>
                                    <th scope="col" className="px-3 py-2.5 text-left text-xs font-semibold min-w-[130px]">Marking</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border/40">
                                {importItems.map((row) => {
                                    const appliedMarking =
                                        markings[row.id] !== undefined
                                            ? markings[row.id]
                                            : (row.condition_type || "");
                                    const balCif = Number(row.balance_cif_fc || 0);
                                    return (
                                        <tr key={row.id} className="transition-colors hover:bg-muted/20">
                                            <td className="px-3 py-2.5 font-mono text-xs text-muted-foreground">{row.serial_number}</td>
                                            <td className="px-3 py-2.5 font-mono text-xs text-muted-foreground">{row.hs_code_label || "—"}</td>
                                            <td className="px-3 py-2.5">
                                                <div className="max-w-[200px] truncate text-xs" title={row.description}>{row.description || "—"}</div>
                                                {row.unit && <div className="text-[10px] text-muted-foreground">{row.unit}</div>}
                                            </td>
                                            <td className="px-3 py-2.5 text-right tabular-nums text-xs">{fmtDec(row.quantity, 3)}</td>
                                            <td className="px-3 py-2.5 text-right tabular-nums text-xs text-violet-700">{fmtDec(row.allotted_quantity, 3)}</td>
                                            <td className="px-3 py-2.5 text-right tabular-nums text-xs text-amber-700">{fmtDec(row.debited_quantity, 3)}</td>
                                            <td className="px-3 py-2.5 text-right tabular-nums text-xs">{fmtDec(row.available_quantity, 3)}</td>
                                            <td className="px-3 py-2.5 text-right tabular-nums text-xs">{fmtDec(row.cif_fc)}</td>
                                            <td className="px-3 py-2.5 text-right tabular-nums text-xs">
                                                <span className={cn("font-semibold", balCif > 0 ? "text-emerald-700" : "text-muted-foreground")}>
                                                    {fmtDec(balCif)}
                                                </span>
                                            </td>
                                            <td className="px-3 py-2.5">
                                                <MarkingRow
                                                    row={row}
                                                    appliedMarking={appliedMarking}
                                                    onMarked={handleMarkingUpdate}
                                                />
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                            <tfoot className="border-t-2 border-border bg-muted/40 font-semibold">
                                <tr>
                                    <td colSpan={8} className="px-3 py-2.5 text-right text-xs uppercase tracking-wider text-muted-foreground">
                                        Total Balance CIF FC
                                    </td>
                                    <td className="px-3 py-2.5 text-right tabular-nums text-xs text-primary">{fmtDec(totalImportBalance)}</td>
                                    <td />
                                </tr>
                            </tfoot>
                        </table>
                    </div>
                </div>
            )}

            {/* Empty state when no items at all */}
            {importItems.length === 0 && exportItems.length === 0 && (
                <div className="rounded-xl border border-border/50 bg-muted/20 py-8 text-center text-sm text-muted-foreground">
                    No import or export items linked to this license.
                </div>
            )}
        </div>
    );
}
