/**
 * BalanceTab — inline balance view embedded in the license accordion.
 *
 * Reuses the same APIs and data as LicenseBalanceModal:
 *   - `detail` (licenses/{id}/) already fetched on accordion expand
 *   - GET licenses/{id}/balance-pdf/  → PDF download
 *   - GET licenses/{id}/balance-excel/ → Excel download
 *   - PATCH licenses/{id}/             → condition_sheet / balance_report_notes edits
 *   - PATCH license-items/{id}/        → condition_type (license marking) edits
 *
 * Differences vs modal: renders inline (no Dialog), no fixed height, no
 * gradient header chrome.  All business logic, validations and API calls
 * are identical.
 */

import { useState, useEffect, useCallback } from "react";
import {
    Check,
    CheckCircle,
    FileSpreadsheet,
    FileText,
    Loader2,
    Package,
    Pencil,
    Plus,
    X,
} from "lucide-react";
import { toast } from "sonner";
import AsyncSelect from "react-select/async";
import Select from "react-select";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import api from "../../../api/axios";
import ConditionBadge from "../../../components/ConditionBadge";
import { openPdfPreview } from "../../../utils/pdfPreview";
import { formatDate } from "../../../utils/dateFormatter";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers (same as LicenseBalanceModal)
// ─────────────────────────────────────────────────────────────────────────────

function fmtDecimal(v: unknown, dp = 2): string {
    const n = Number(v);
    return Number.isFinite(n) ? n.toFixed(dp) : Number(0).toFixed(dp);
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
// Inline editable text (same logic as LicenseBalanceModal.InlineEditableText)
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
    items_detail?: { id: number; name: string }[];
}

interface LicenseDetail {
    id: number;
    license_number: string;
    license_date?: string;
    license_expiry_date?: string;
    exporter_name?: string;
    port_name?: string;
    balance_cif?: number;
    purchase_status_label?: string;
    condition_sheet?: string;
    balance_report_notes?: string;
    import_license?: ImportItemRow[];
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
// Marking row (condition_type inline edit — same as LicenseBalanceModal)
// ─────────────────────────────────────────────────────────────────────────────

function MarkingRow({
    row,
    licenseId,
    onMarked,
}: {
    row: ImportItemRow;
    licenseId: number;
    onMarked: (id: number, marking: string) => void;
}) {
    const [editing, setEditing] = useState(false);
    const [editItems, setEditItems] = useState<{ value: number; label: string }[]>([]);
    const [saving, setSaving] = useState(false);
    const [addingItem, setAddingItem] = useState(false);

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

    const loadItemOptions = async (input: string) => {
        if (input.length < 2) return [];
        try {
            const { data } = await api.get("masters/item-names/", { params: { search: input } });
            const items = Array.isArray(data.results) ? data.results : [];
            return items.map((i: { id: number; name: string }) => ({ value: i.id, label: i.name }));
        } catch {
            return [];
        }
    };

    const saveItemTags = async () => {
        setSaving(true);
        try {
            await api.patch(`license-items/${row.id}/`, {
                items: editItems.map((i) => i.value),
            });
            toast.success("Item tags saved");
            setAddingItem(false);
        } catch {
            toast.error("Failed to save item tags");
        } finally {
            setSaving(false);
        }
    };

    const currentMarking = row.condition_type || "";

    return (
        <div className="flex flex-wrap items-center gap-2">
            {!editing ? (
                <>
                    <ConditionBadge type={currentMarking} size="sm" />
                    <button
                        type="button"
                        onClick={() => setEditing(true)}
                        className="flex items-center gap-1 rounded border border-border/60 bg-muted/40 px-1.5 py-0.5 text-[10.5px] text-muted-foreground hover:bg-muted cursor-pointer"
                        title="Edit marking"
                    >
                        <Pencil className="size-3" aria-hidden="true" />Edit
                    </button>
                </>
            ) : (
                <div className="flex items-center gap-2 flex-wrap">
                    <Select
                        options={LICENSE_MARKING_OPTIONS}
                        value={LICENSE_MARKING_OPTIONS.find((o) => o.value === currentMarking) || LICENSE_MARKING_OPTIONS[0]}
                        onChange={(opt) => { if (opt) saveMarking(opt.value); }}
                        isDisabled={saving}
                        menuPortalTarget={document.body}
                        menuPosition="fixed"
                        className="text-xs w-28"
                        classNamePrefix="marking-select"
                    />
                    {saving && <Loader2 className="size-3.5 animate-spin text-muted-foreground" />}
                    <button
                        type="button"
                        onClick={() => setEditing(false)}
                        className="text-xs text-muted-foreground hover:text-foreground cursor-pointer"
                    >
                        Cancel
                    </button>
                </div>
            )}
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
    const [markings, setMarkings] = useState<Record<number, string>>({});

    // Sync local state when detail loads
    useEffect(() => {
        setConditionSheet(detail?.condition_sheet ?? "");
        setNotes(detail?.balance_report_notes ?? "");
    }, [detail?.condition_sheet, detail?.balance_report_notes]);

    const handleMarkingUpdate = useCallback((id: number, marking: string) => {
        setMarkings((prev) => ({ ...prev, [id]: marking }));
    }, []);

    if (detailLoading || !detail) {
        return (
            <div className="space-y-3 py-4">
                <Skeleton className="h-24 w-full rounded-xl" />
                <Skeleton className="h-40 w-full rounded-xl" />
                <Skeleton className="h-24 w-full rounded-xl" />
            </div>
        );
    }

    const importItems = detail.import_license ?? [];
    const totalBalance = importItems.reduce(
        (s, r) => s + (Number(r.balance_cif_fc) || 0),
        0
    );

    return (
        <div className="space-y-4 py-3">
            {/* ── Financial summary + downloads ─────────────────── */}
            <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-border/60 bg-card px-4 py-3">
                <div className="grid grid-cols-2 gap-x-8 gap-y-2 sm:grid-cols-4">
                    <div>
                        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">License</div>
                        <div className="font-mono text-sm font-semibold text-foreground">{detail.license_number}</div>
                    </div>
                    <div>
                        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Balance CIF</div>
                        <div className="text-sm font-bold tabular-nums text-primary">
                            ${fmtDecimal(detail.balance_cif)}
                        </div>
                    </div>
                    <div>
                        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Purchase Status</div>
                        <div className="text-sm font-medium text-foreground">{detail.purchase_status_label || "—"}</div>
                    </div>
                    <div>
                        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Exporter</div>
                        <div className="truncate text-sm font-medium text-foreground" title={detail.exporter_name || ""}>
                            {detail.exporter_name || "—"}
                        </div>
                    </div>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onDownloadPdf}
                        className="h-7 gap-1.5 text-xs"
                    >
                        <FileText className="size-3.5" aria-hidden="true" />PDF
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onDownloadExcel}
                        className="h-7 gap-1.5 text-xs"
                    >
                        <FileSpreadsheet className="size-3.5" aria-hidden="true" />Excel
                    </Button>
                </div>
            </div>

            {/* ── Condition Sheet ───────────────────────────────── */}
            <div className="rounded-xl border border-border/60 bg-card px-4 py-3">
                <div className="mb-2.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Condition Sheet
                </div>
                <EditableNote
                    licenseId={licenseId}
                    value={conditionSheet}
                    fieldName="condition_sheet"
                    label="Condition Sheet"
                    onUpdate={(v) => {
                        setConditionSheet(v);
                        onDetailUpdate({ condition_sheet: v });
                    }}
                />
            </div>

            {/* ── Notes ────────────────────────────────────────── */}
            <div className="rounded-xl border border-border/60 bg-card px-4 py-3">
                <div className="mb-2.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Balance Report Notes
                </div>
                <EditableNote
                    licenseId={licenseId}
                    value={notes}
                    fieldName="balance_report_notes"
                    label="Notes"
                    onUpdate={(v) => {
                        setNotes(v);
                        onDetailUpdate({ balance_report_notes: v });
                    }}
                />
            </div>

            {/* ── Import Items — License Marking ────────────────── */}
            {importItems.length > 0 && (
                <div className="overflow-hidden rounded-xl border border-border/60">
                    <div className="border-b border-border/50 bg-muted/30 px-4 py-2.5">
                        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                            Import Items — License Marking
                        </div>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="bg-primary text-white">
                                <tr>
                                    <th scope="col" className="p-3 text-left text-xs font-semibold">Sr No</th>
                                    <th scope="col" className="p-3 text-left text-xs font-semibold">HS Code</th>
                                    <th scope="col" className="p-3 text-left text-xs font-semibold">Description</th>
                                    <th scope="col" className="p-3 text-right text-xs font-semibold">Qty</th>
                                    <th scope="col" className="p-3 text-right text-xs font-semibold">Allotted</th>
                                    <th scope="col" className="p-3 text-right text-xs font-semibold">Debited</th>
                                    <th scope="col" className="p-3 text-right text-xs font-semibold">Available</th>
                                    <th scope="col" className="p-3 text-right text-xs font-semibold">CIF FC</th>
                                    <th scope="col" className="p-3 text-right text-xs font-semibold">Balance CIF</th>
                                    <th scope="col" className="p-3 text-left text-xs font-semibold">Marking</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border/40">
                                {importItems.map((row) => {
                                    const appliedMarking = markings[row.id] !== undefined
                                        ? markings[row.id]
                                        : (row.condition_type || "");
                                    const balCif = Number(row.balance_cif_fc || 0);
                                    return (
                                        <tr
                                            key={row.id}
                                            className="transition-colors hover:bg-muted/20"
                                        >
                                            <td className="p-3 font-mono text-xs text-muted-foreground">
                                                {row.serial_number}
                                            </td>
                                            <td className="p-3 font-mono text-xs text-muted-foreground">
                                                {row.hs_code_label || "—"}
                                            </td>
                                            <td className="max-w-[180px] p-3">
                                                <div className="truncate text-xs" title={row.description}>
                                                    {row.description || "—"}
                                                </div>
                                                <div className="text-[10px] text-muted-foreground">{row.unit}</div>
                                            </td>
                                            <td className="p-3 text-right tabular-nums text-xs">
                                                {fmtDecimal(row.quantity, 3)}
                                            </td>
                                            <td className="p-3 text-right tabular-nums text-xs text-violet-700">
                                                {fmtDecimal(row.allotted_quantity, 3)}
                                            </td>
                                            <td className="p-3 text-right tabular-nums text-xs text-amber-700">
                                                {fmtDecimal(row.debited_quantity, 3)}
                                            </td>
                                            <td className="p-3 text-right tabular-nums text-xs">
                                                {fmtDecimal(row.available_quantity, 3)}
                                            </td>
                                            <td className="p-3 text-right tabular-nums text-xs">
                                                {fmtDecimal(row.cif_fc)}
                                            </td>
                                            <td className="p-3 text-right tabular-nums text-xs">
                                                <span className={cn(
                                                    "font-semibold",
                                                    balCif > 0 ? "text-emerald-700" : "text-muted-foreground"
                                                )}>
                                                    {fmtDecimal(balCif)}
                                                </span>
                                            </td>
                                            <td className="p-3">
                                                <MarkingRow
                                                    row={{ ...row, condition_type: appliedMarking }}
                                                    licenseId={licenseId}
                                                    onMarked={handleMarkingUpdate}
                                                />
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                            <tfoot className="border-t-2 border-border bg-muted/40 font-semibold">
                                <tr>
                                    <td colSpan={7} className="p-3 text-right text-xs text-muted-foreground uppercase tracking-wider">
                                        Total Balance CIF FC
                                    </td>
                                    <td className="p-3" />
                                    <td className="p-3 text-right tabular-nums text-xs text-primary">
                                        {fmtDecimal(totalBalance)}
                                    </td>
                                    <td />
                                </tr>
                            </tfoot>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}
