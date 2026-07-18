/**
 * LedgerTab (displayed as "Balance" tab) — comprehensive financial &
 * utilization summary for a single license, with legacy Balance-modal
 * features: item-name tag editing + license marking.
 *
 * Sections:
 *   1. License Summary card
 *   2. Import Items table  — expandable rows showing BOE & Allotment usage;
 *                             inline Item-Name tags and Marking edits
 *   3. Balance Summary card
 *
 * Business rule — Common vs Individual CIF balance:
 *   COMMON  : first item has non-zero cif_fc; ALL remaining items are null /
 *             blank / 0.  In this case the per-row "Balance ($)" column is
 *             hidden because it is meaningless; only the license-level balance
 *             (get_balance_cif) is relevant.
 *   INDIVIDUAL: every item carries its own cif_fc → show per-row balance.
 *
 * APIs (identical to LicenseBalanceModal — no new endpoints):
 *   GET  licenses/{id}/item-usage/?item_id=X&type=import
 *   PATCH license-items/{id}/   { items: [...ids] }        ← item-name tags
 *   PATCH license-items/{id}/   { condition_type: "AU"|… } ← marking
 */

import { useState, useCallback } from "react";
import AsyncSelect from "react-select/async";
import Select from "react-select";
import {
    ChevronRight,
    FileText,
    Loader2,
    Package,
    Receipt,
    TrendingDown,
    TrendingUp,
    X,
    Plus,
    Pencil,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import ConditionBadge from "../../../components/ConditionBadge";
import api from "../../../api/axios";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface ItemDetail { id: number; name: string; }

interface ImportItem {
    id: number;
    serial_number: number;
    description: string;
    hs_code_label?: string;
    quantity: number;
    unit: string;
    cif_fc: number | null;
    cif_inr?: number;
    allotted_quantity?: number;
    allotted_value?: number;
    debited_quantity?: number;
    debited_value?: number;
    balance_cif_fc?: number | null;
    available_quantity?: number;
    available_value?: number;
    condition_type?: string | null;
    items_detail?: ItemDetail[];
}

interface BoeEntry {
    id: number;
    bill_of_entry_number: string;
    date: string | null;
    port: string | null;
    company: string | null;
    quantity: number;
    cif_fc: number;
    cif_inr: number;
}

interface AllotmentEntry {
    id: number;
    allotment_number: string;
    company: string | null;
    quantity: number;
    cif_fc: number;
    cif_inr: number;
}

interface ItemUsage {
    boes: BoeEntry[];
    allotments: AllotmentEntry[];
}

interface LicenseDetail {
    import_license?: ImportItem[];
    [key: string]: unknown;
}

interface ListItem {
    id: number;
    license_number: string;
    get_balance_cif: number | string | null;
    ledger_date: string | null;
    [key: string]: unknown;
}

interface LedgerTabProps {
    item: ListItem;
    detail: LicenseDetail | null;
    loading: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Business logic helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Returns true when the license uses a single shared CIF FC balance
 * (first item non-zero, all remaining items are null / blank / 0).
 * In this mode the per-row "Balance ($)" column is meaningless and must
 * be hidden.  Mirrors the legacy Balance-modal business rule.
 */
function isCommonCifBalance(items: ImportItem[]): boolean {
    if (items.length < 2) return false;
    const firstCif = Number(items[0]?.cif_fc ?? 0);
    if (firstCif === 0) return false;
    return items.slice(1).every((r) => {
        const v = r.cif_fc;
        return v === null || v === undefined || (v as unknown as string) === "" || Number(v) === 0;
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// Format helpers
// ─────────────────────────────────────────────────────────────────────────────

function fmtUsd(v: number | string | undefined | null, dp = 2): string {
    if (v === null || v === undefined || v === "") return "—";
    const n = Number(v);
    if (isNaN(n)) return "—";
    return `$${n.toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
}

function fmtInr(v: number | string | undefined | null): string {
    if (v === null || v === undefined || v === "") return "—";
    const n = Number(v);
    if (isNaN(n)) return "—";
    return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function fmtQty(v: number | undefined | null, dp = 3): string {
    if (v === null || v === undefined) return "—";
    const n = Number(v);
    if (isNaN(n)) return "—";
    return n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: dp });
}

// ─────────────────────────────────────────────────────────────────────────────
// Marking options (same set as LicenseBalanceModal)
// ─────────────────────────────────────────────────────────────────────────────

const MARKING_OPTIONS = [
    { value: "", label: "None" },
    { value: "AU", label: "AU" },
    { value: "10%", label: "10%" },
    { value: "5%", label: "5%" },
    { value: "3%", label: "3%" },
    { value: "2%", label: "2%" },
];

// ─────────────────────────────────────────────────────────────────────────────
// SummaryMetric
// ─────────────────────────────────────────────────────────────────────────────

function SummaryMetric({
    label, value, sub,
    variant = "default",
}: {
    label: string; value: string; sub?: string;
    variant?: "default" | "primary" | "success" | "danger" | "muted";
}) {
    const cls = {
        default: "text-foreground", primary: "text-primary",
        success: "text-emerald-700", danger: "text-destructive",
        muted: "text-muted-foreground",
    }[variant];
    return (
        <div>
            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
            <div className={cn("mt-0.5 text-base font-bold tabular-nums", cls)}>{value}</div>
            {sub && <div className="text-[10.5px] text-muted-foreground">{sub}</div>}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// UsageDetail (expandable BOE + Allotment sub-tables)
// ─────────────────────────────────────────────────────────────────────────────

function UsageDetail({ usage, loading }: { usage: ItemUsage | undefined; loading: boolean | undefined }) {
    if (loading) return (
        <div className="space-y-2 p-3">
            <Skeleton className="h-3 w-1/2" /><Skeleton className="h-3 w-3/4" />
        </div>
    );
    const boes = usage?.boes ?? [];
    const allotments = usage?.allotments ?? [];
    if (boes.length === 0 && allotments.length === 0) {
        return <div className="px-4 py-3 text-sm text-muted-foreground">No BOE or allotment usage recorded for this item.</div>;
    }
    return (
        <div className="grid gap-4 px-4 py-3 lg:grid-cols-2">
            {boes.length > 0 && (
                <div>
                    <div className="mb-1.5 flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        <Receipt className="size-3.5" />BOE Utilization
                    </div>
                    <table className="w-full text-xs">
                        <thead>
                            <tr className="text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                                <th scope="col" className="pb-1 pr-3">BOE No.</th>
                                <th scope="col" className="pb-1 pr-3">Company</th>
                                <th scope="col" className="pb-1 pr-3 text-right">Qty</th>
                                <th scope="col" className="pb-1 text-right">CIF ($)</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border/30">
                            {boes.map(b => (
                                <tr key={b.id} className="hover:bg-muted/20">
                                    <td className="py-1 pr-3 font-mono text-[10.5px]">{b.bill_of_entry_number || "—"}{b.date && <div className="text-muted-foreground">{String(b.date)}</div>}</td>
                                    <td className="py-1 pr-3 text-[10.5px]">{b.company || "—"}</td>
                                    <td className="py-1 pr-3 text-right tabular-nums">{fmtQty(b.quantity)}</td>
                                    <td className="py-1 text-right tabular-nums text-amber-700">{fmtUsd(b.cif_fc)}</td>
                                </tr>
                            ))}
                        </tbody>
                        <tfoot>
                            <tr className="border-t border-border font-semibold">
                                <td colSpan={3} className="pr-3 pt-1 text-right text-[10.5px] text-muted-foreground">Total BOE</td>
                                <td className="pt-1 text-right tabular-nums text-[10.5px] text-amber-700">{fmtUsd(boes.reduce((s, b) => s + (Number(b.cif_fc) || 0), 0))}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            )}
            {allotments.length > 0 && (
                <div>
                    <div className="mb-1.5 flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        <Package className="size-3.5" />Allotment Usage
                    </div>
                    <table className="w-full text-xs">
                        <thead>
                            <tr className="text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                                <th scope="col" className="pb-1 pr-3">Allotment</th>
                                <th scope="col" className="pb-1 pr-3">Company</th>
                                <th scope="col" className="pb-1 pr-3 text-right">Qty</th>
                                <th scope="col" className="pb-1 text-right">CIF ($)</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border/30">
                            {allotments.map(a => (
                                <tr key={a.id} className="hover:bg-muted/20">
                                    <td className="py-1 pr-3 font-mono text-[10.5px]">{a.allotment_number || "—"}</td>
                                    <td className="py-1 pr-3 text-[10.5px]">{a.company || "—"}</td>
                                    <td className="py-1 pr-3 text-right tabular-nums">{fmtQty(a.quantity)}</td>
                                    <td className="py-1 text-right tabular-nums text-violet-700">{fmtUsd(a.cif_fc)}</td>
                                </tr>
                            ))}
                        </tbody>
                        <tfoot>
                            <tr className="border-t border-border font-semibold">
                                <td colSpan={3} className="pr-3 pt-1 text-right text-[10.5px] text-muted-foreground">Total Allotted</td>
                                <td className="pt-1 text-right tabular-nums text-[10.5px] text-violet-700">{fmtUsd(allotments.reduce((s, a) => s + (Number(a.cif_fc) || 0), 0))}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            )}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main LedgerTab
// ─────────────────────────────────────────────────────────────────────────────

export default function LedgerTab({ item, detail, loading }: LedgerTabProps) {
    // ── Expand / usage state ───────────────────────────────────────────────
    const [expandedItemId, setExpandedItemId] = useState<number | null>(null);
    const [itemUsage, setItemUsage] = useState<Record<number, ItemUsage>>({});
    const [itemUsageLoading, setItemUsageLoading] = useState<Record<number, boolean>>({});

    // ── Item-tag state (same as LicenseBalanceModal) ───────────────────────
    const [localItems, setLocalItems] = useState<ImportItem[]>([]);
    const [addingItemId, setAddingItemId] = useState<number | null>(null);
    const [tagSaving, setTagSaving] = useState<Record<number, boolean>>({});
    const [editingItemId, setEditingItemId] = useState<number | null>(null);
    const [editingTags, setEditingTags] = useState<{ value: number; label: string }[]>([]);
    const [editSaving, setEditSaving] = useState(false);

    // ── Marking state ──────────────────────────────────────────────────────
    const [markingOverrides, setMarkingOverrides] = useState<Record<number, string>>({});

    // Initialise localItems from detail (keeps local edits alive across re-renders)
    const detailItems = (detail?.import_license ?? []) as ImportItem[];
    // Merge server data with local mutations so item_detail/condition_type stay fresh
    const importItems: ImportItem[] = detailItems.map((r) => ({
        ...r,
        items_detail: localItems.find((l) => l.id === r.id)?.items_detail ?? r.items_detail ?? [],
        condition_type: markingOverrides[r.id] !== undefined ? markingOverrides[r.id] : (r.condition_type ?? ""),
    }));

    // ── Common CIF detection ───────────────────────────────────────────────
    const commonBalance = isCommonCifBalance(importItems);

    // ── Aggregate totals ───────────────────────────────────────────────────
    const totalCifFc = importItems.reduce((s, r) => s + (Number(r.cif_fc) || 0), 0);
    const totalAllotted = importItems.reduce((s, r) => s + (Number(r.allotted_value) || 0), 0);
    const totalDebited = importItems.reduce((s, r) => s + (Number(r.debited_value) || 0), 0);
    const totalBalance = importItems.reduce((s, r) => s + (Number(r.balance_cif_fc) || 0), 0);
    // For common-balance licenses use the authoritative license-level balance
    const displayBalance = commonBalance ? Number(item.get_balance_cif ?? 0) : totalBalance;

    // ── BOE / Allotment usage fetch ────────────────────────────────────────
    const handleRowClick = useCallback(async (importItem: ImportItem) => {
        const id = importItem.id;
        setExpandedItemId((prev) => (prev === id ? null : id));
        if (!itemUsage[id] && !itemUsageLoading[id]) {
            setItemUsageLoading((prev) => ({ ...prev, [id]: true }));
            try {
                const { data } = await api.get(`licenses/${item.id}/item-usage/`, {
                    params: { item_id: id, type: "import" },
                });
                setItemUsage((prev) => ({ ...prev, [id]: data as ItemUsage }));
            } catch {
                toast.error("Failed to load item usage details");
            } finally {
                setItemUsageLoading((prev) => ({ ...prev, [id]: false }));
            }
        }
    }, [item.id, itemUsage, itemUsageLoading]);

    // ── Item-name tag helpers (same logic as LicenseBalanceModal) ──────────
    const loadItemOptions = useCallback(async (input: string) => {
        if (input.length < 2) return [];
        try {
            const { data } = await api.get("masters/item-names/", { params: { search: input } });
            const results = Array.isArray(data.results) ? data.results : [];
            return results.map((i: { id: number; name: string }) => ({ value: i.id, label: i.name }));
        } catch {
            return [];
        }
    }, []);

    const patchItemTags = useCallback(async (rowId: number, newDetails: ItemDetail[]) => {
        const itemIds = newDetails.map((d) => d.id);
        // Optimistic update
        setLocalItems((prev) => {
            const existing = prev.find((p) => p.id === rowId);
            if (existing) {
                return prev.map((p) => p.id === rowId ? { ...p, items_detail: newDetails } : p);
            }
            return [...prev, { ...detailItems.find((r) => r.id === rowId)!, items_detail: newDetails }];
        });
        setTagSaving((s) => ({ ...s, [rowId]: true }));
        try {
            await api.patch(`license-items/${rowId}/`, { items: itemIds });
        } catch (err: unknown) {
            // Revert on failure
            const d = (err as { response?: { data?: { detail?: string; error?: string } } })?.response?.data;
            toast.error(d?.detail || d?.error || "Failed to update items");
            setLocalItems((prev) => prev.filter((p) => p.id !== rowId)); // drop local override → revert to server state
        } finally {
            setTagSaving((s) => ({ ...s, [rowId]: false }));
        }
    }, [detailItems]);

    const handleAddItemTag = useCallback((rowId: number, option: { value: number; label: string } | null) => {
        setAddingItemId(null);
        if (!option) return;
        const current = importItems.find((r) => r.id === rowId)?.items_detail ?? [];
        if (current.some((d) => d.id === option.value)) return; // already present
        patchItemTags(rowId, [...current, { id: option.value, name: option.label }]);
    }, [importItems, patchItemTags]);

    const handleRemoveItemTag = useCallback((e: React.MouseEvent, rowId: number, tagId: number) => {
        e.stopPropagation();
        const current = importItems.find((r) => r.id === rowId)?.items_detail ?? [];
        patchItemTags(rowId, current.filter((d) => d.id !== tagId));
    }, [importItems, patchItemTags]);

    const handleEditClick = useCallback((e: React.MouseEvent, row: ImportItem) => {
        e.stopPropagation();
        setEditingItemId(row.id);
        setEditingTags((row.items_detail ?? []).map((d) => ({ value: d.id, label: d.name })));
    }, []);

    const handleSaveEditTags = useCallback(async (e: React.MouseEvent, rowId: number) => {
        e.stopPropagation();
        setEditSaving(true);
        try {
            const itemIds = editingTags.map((t) => t.value);
            const newDetails = editingTags.map((t) => ({ id: t.value, name: t.label }));
            await api.patch(`license-items/${rowId}/`, { items: itemIds });
            setLocalItems((prev) => {
                const existing = prev.find((p) => p.id === rowId);
                if (existing) return prev.map((p) => p.id === rowId ? { ...p, items_detail: newDetails } : p);
                return [...prev, { ...detailItems.find((r) => r.id === rowId)!, items_detail: newDetails }];
            });
            toast.success("Items updated successfully");
            setEditingItemId(null);
        } catch (err: unknown) {
            const d = (err as { response?: { data?: { detail?: string; error?: string } } })?.response?.data;
            toast.error(d?.detail || d?.error || "Failed to update items");
        } finally {
            setEditSaving(false);
        }
    }, [editingTags, detailItems]);

    // ── Marking handler (same logic as LicenseBalanceModal) ───────────────
    const handleConditionTypeChange = useCallback(async (rowId: number, newValue: string) => {
        const previous = markingOverrides[rowId] !== undefined
            ? markingOverrides[rowId]
            : (detailItems.find((r) => r.id === rowId)?.condition_type ?? "");
        if (previous === newValue) return;
        setMarkingOverrides((prev) => ({ ...prev, [rowId]: newValue })); // optimistic
        try {
            await api.patch(`license-items/${rowId}/`, { condition_type: newValue || null });
            toast.success("License marking updated");
        } catch (err: unknown) {
            setMarkingOverrides((prev) => ({ ...prev, [rowId]: previous })); // revert
            const d = (err as { response?: { data?: { detail?: string; condition_type?: string[] } } })?.response?.data;
            toast.error(d?.detail || d?.condition_type?.[0] || "Failed to update marking");
        }
    }, [markingOverrides, detailItems]);

    // ── Total column count (varies on whether Balance ($) column is shown) ─
    const colCount = commonBalance ? 8 : 9; // # + Desc + HS + Qty + CIF + BOE + Allotted + [Balance] + Item + Marking + ▶ = 11 or 10
    // Actually: # Desc HS Qty CIF BOE Allotted [Balance?] ItemNames Marking ▶
    const totalCols = commonBalance ? 10 : 11;

    // ── Render ─────────────────────────────────────────────────────────────

    if (loading) {
        return (
            <div className="space-y-3 py-4">
                <Skeleton className="h-24 w-full rounded-xl" />
                <Skeleton className="h-48 w-full rounded-xl" />
                <Skeleton className="h-20 w-full rounded-xl" />
            </div>
        );
    }

    if (importItems.length === 0) {
        return (
            <div className="flex flex-col items-center py-10 text-center">
                <div className="mb-3 flex size-10 items-center justify-center rounded-full bg-muted">
                    <FileText className="size-5 text-muted-foreground/60" aria-hidden="true" />
                </div>
                <div className="text-sm font-medium text-muted-foreground">No import items</div>
                <div className="mt-1 text-xs text-muted-foreground/70">No import line items are linked to this license.</div>
            </div>
        );
    }

    const balancePct = totalCifFc > 0 ? (displayBalance / totalCifFc) * 100 : 0;

    return (
        <div className="space-y-4 py-3">
            {/* ── 1. License Summary ──────────────────────────────────── */}
            <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
                <div className="border-b border-border/50 px-4 py-2.5">
                    <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        License Summary
                        {commonBalance && (
                            <span className="ml-2 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700 ring-1 ring-blue-200">
                                Common CIF Balance
                            </span>
                        )}
                    </div>
                </div>
                <div className="grid grid-cols-2 gap-x-6 gap-y-3 px-4 py-3 sm:grid-cols-3 lg:grid-cols-6">
                    <SummaryMetric label="License No." value={item.license_number || "—"} />
                    <SummaryMetric label="License Value" value={fmtUsd(totalCifFc)} />
                    <SummaryMetric label="Balance CIF" value={fmtUsd(displayBalance)} variant="primary"
                        sub={commonBalance ? "shared across items" : undefined} />
                    <SummaryMetric label="BOE Utilized" value={fmtUsd(totalDebited)} variant="danger" />
                    <SummaryMetric label="Allotted" value={fmtUsd(totalAllotted)} variant="muted" />
                    <SummaryMetric label="Ledger Date" value={String(item.ledger_date ?? "—")} variant="success" />
                </div>
                {totalCifFc > 0 && (
                    <div className="border-t border-border/30 px-4 pb-3 pt-2">
                        <div className="mb-1 flex justify-between text-[10px] text-muted-foreground">
                            <span>Utilization</span>
                            <span>{(100 - balancePct).toFixed(1)}% used · {balancePct.toFixed(1)}% remaining</span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                            <div
                                className="h-full rounded-full bg-primary transition-[width] duration-500"
                                style={{ width: `${Math.min(100 - balancePct, 100)}%` }}
                            />
                        </div>
                    </div>
                )}
            </div>

            {/* ── 2. Import Items Table ───────────────────────────────── */}
            <div className="overflow-hidden rounded-xl border border-border/60">
                <div className="border-b border-border/50 bg-muted/30 px-4 py-2.5">
                    <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Import Items — click row to expand BOE &amp; Allotment details
                    </div>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur-sm">
                            <tr className="border-b border-border text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                <th scope="col" className="px-3 py-2.5 w-8">#</th>
                                <th scope="col" className="px-3 py-2.5">Description</th>
                                <th scope="col" className="px-3 py-2.5 hidden sm:table-cell">HS Code</th>
                                <th scope="col" className="px-3 py-2.5 text-right">Qty</th>
                                <th scope="col" className="px-3 py-2.5 text-right">CIF ($)</th>
                                <th scope="col" className="px-3 py-2.5 text-right">BOE Used</th>
                                <th scope="col" className="px-3 py-2.5 text-right">Allotted</th>
                                {/* Balance column only for individual-CIF licenses */}
                                {!commonBalance && (
                                    <th scope="col" className="px-3 py-2.5 text-right">Balance ($)</th>
                                )}
                                <th scope="col" className="px-3 py-2.5 min-w-[160px]">Item Names</th>
                                <th scope="col" className="px-3 py-2.5 min-w-[120px]">Marking</th>
                                <th scope="col" className="px-3 py-2.5 w-6" aria-label="Expand" />
                            </tr>
                        </thead>
                        <tbody>
                            {importItems.map((r) => {
                                const isExpanded = expandedItemId === r.id;
                                const balCif = Number(r.balance_cif_fc || 0);
                                const origCif = Number(r.cif_fc || 0);
                                const balPct = origCif > 0 ? (balCif / origCif) * 100 : 0;
                                const currentMarking = r.condition_type ?? "";
                                const tags = r.items_detail ?? [];
                                const isEditingTags = editingItemId === r.id;

                                return (
                                    <>
                                        <tr
                                            key={r.id}
                                            onClick={() => handleRowClick(r)}
                                            className={cn(
                                                "cursor-pointer border-b border-border/40 transition-colors",
                                                isExpanded ? "bg-primary/5" : "hover:bg-muted/30"
                                            )}
                                            aria-expanded={isExpanded}
                                        >
                                            {/* Sl# */}
                                            <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{r.serial_number}</td>
                                            {/* Description */}
                                            <td className="px-3 py-2">
                                                <div className="max-w-[160px] truncate text-sm font-medium" title={r.description}>{r.description || "—"}</div>
                                                <div className="mt-0.5 text-[10px] text-muted-foreground">{r.unit}</div>
                                            </td>
                                            {/* HS Code */}
                                            <td className="hidden px-3 py-2 font-mono text-xs text-muted-foreground sm:table-cell">{r.hs_code_label || "—"}</td>
                                            {/* Qty */}
                                            <td className="px-3 py-2 text-right tabular-nums text-xs">{fmtQty(r.quantity)}</td>
                                            {/* CIF ($) */}
                                            <td className="px-3 py-2 text-right tabular-nums text-xs">{fmtUsd(r.cif_fc)}</td>
                                            {/* BOE Used */}
                                            <td className="px-3 py-2 text-right tabular-nums text-xs">
                                                {r.debited_value != null && Number(r.debited_value) > 0
                                                    ? <span className="text-amber-700">{fmtUsd(r.debited_value)}</span>
                                                    : <span className="text-muted-foreground/40">—</span>}
                                            </td>
                                            {/* Allotted */}
                                            <td className="px-3 py-2 text-right tabular-nums text-xs">
                                                {r.allotted_value != null && Number(r.allotted_value) > 0
                                                    ? <span className="text-violet-700">{fmtUsd(r.allotted_value)}</span>
                                                    : <span className="text-muted-foreground/40">—</span>}
                                            </td>
                                            {/* Balance ($) — only for individual-CIF licenses */}
                                            {!commonBalance && (
                                                <td className="px-3 py-2 text-right tabular-nums text-xs">
                                                    <span className={cn("font-semibold",
                                                        balPct > 50 ? "text-emerald-700" : balPct > 20 ? "text-amber-700" : "text-destructive"
                                                    )}>
                                                        {fmtUsd(balCif)}
                                                    </span>
                                                </td>
                                            )}

                                            {/* ── Item Names ───────────────────────────────────── */}
                                            <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                                                {isEditingTags ? (
                                                    <div className="flex flex-wrap items-center gap-1 min-w-[200px]" onClick={(e) => e.stopPropagation()}>
                                                        <AsyncSelect
                                                            isMulti
                                                            cacheOptions
                                                            loadOptions={loadItemOptions}
                                                            value={editingTags}
                                                            onChange={(v) => setEditingTags(v as typeof editingTags)}
                                                            placeholder="Search items…"
                                                            menuPortalTarget={document.body}
                                                            menuPosition="fixed"
                                                            styles={{
                                                                control: (b) => ({ ...b, minHeight: 32, fontSize: 12.5, minWidth: 180 }),
                                                                menuPortal: (b) => ({ ...b, zIndex: 9999 }),
                                                                menu: (b) => ({ ...b, minWidth: 220, width: "max-content" }),
                                                                option: (b) => ({ ...b, whiteSpace: "nowrap" }),
                                                            }}
                                                        />
                                                        <button type="button"
                                                            onClick={(e) => handleSaveEditTags(e, r.id)}
                                                            disabled={editSaving}
                                                            className="rounded bg-primary px-2 py-1 text-[10.5px] font-medium text-white hover:bg-primary/90 disabled:opacity-50 cursor-pointer">
                                                            {editSaving ? <Loader2 className="size-3.5 animate-spin" /> : "Save"}
                                                        </button>
                                                        <button type="button"
                                                            onClick={(e) => { e.stopPropagation(); setEditingItemId(null); }}
                                                            className="text-xs text-muted-foreground hover:text-foreground cursor-pointer">
                                                            Cancel
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <div className="flex flex-wrap items-center gap-1 min-w-[140px]">
                                                        {tags.map((d) => (
                                                            <span key={d.id} className="chip chip-neutral inline-flex items-center gap-1 pr-1">
                                                                {d.name}
                                                                <button type="button"
                                                                    onClick={(e) => handleRemoveItemTag(e, r.id, d.id)}
                                                                    disabled={tagSaving[r.id]}
                                                                    className="hover:text-destructive cursor-pointer"
                                                                    title={`Remove ${d.name}`}>
                                                                    <X className="size-3" />
                                                                </button>
                                                            </span>
                                                        ))}
                                                        {tags.length === 0 && addingItemId !== r.id && (
                                                            <span className="text-[10.5px] text-muted-foreground/60">—</span>
                                                        )}
                                                        {addingItemId === r.id ? (
                                                            <div className="min-w-[200px]" onClick={(e) => e.stopPropagation()}>
                                                                <AsyncSelect
                                                                    autoFocus
                                                                    cacheOptions
                                                                    defaultOptions
                                                                    loadOptions={loadItemOptions}
                                                                    onChange={(opt) => handleAddItemTag(r.id, opt as { value: number; label: string } | null)}
                                                                    onBlur={() => setAddingItemId(null)}
                                                                    placeholder="Add item…"
                                                                    menuPortalTarget={document.body}
                                                                    menuPosition="fixed"
                                                                    styles={{
                                                                        control: (b) => ({ ...b, minHeight: 32, fontSize: 12.5, minWidth: 200 }),
                                                                        menuPortal: (b) => ({ ...b, zIndex: 9999 }),
                                                                        menu: (b) => ({ ...b, minWidth: 240, width: "max-content" }),
                                                                        option: (b) => ({ ...b, whiteSpace: "nowrap" }),
                                                                    }}
                                                                />
                                                            </div>
                                                        ) : (
                                                            <div className="flex items-center gap-0.5">
                                                                <button type="button"
                                                                    onClick={(e) => { e.stopPropagation(); setAddingItemId(r.id); }}
                                                                    disabled={tagSaving[r.id]}
                                                                    className="chip chip-primary inline-flex items-center gap-1 cursor-pointer border-0"
                                                                    title="Add item">
                                                                    <Plus className="size-3" />Add
                                                                </button>
                                                                {tags.length > 0 && (
                                                                    <button type="button"
                                                                        onClick={(e) => handleEditClick(e, r)}
                                                                        className="ml-0.5 text-muted-foreground hover:text-foreground cursor-pointer"
                                                                        title="Edit all item tags">
                                                                        <Pencil className="size-3.5" />
                                                                    </button>
                                                                )}
                                                            </div>
                                                        )}
                                                        {tagSaving[r.id] && <Loader2 className="size-3.5 animate-spin text-muted-foreground" />}
                                                    </div>
                                                )}
                                            </td>

                                            {/* ── Marking ──────────────────────────────────────── */}
                                            <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                                                <Select
                                                    options={MARKING_OPTIONS}
                                                    value={MARKING_OPTIONS.find((o) => o.value === currentMarking) ?? MARKING_OPTIONS[0]}
                                                    onChange={(sel) => handleConditionTypeChange(r.id, sel?.value ?? "")}
                                                    isSearchable={false}
                                                    menuPortalTarget={document.body}
                                                    menuPosition="fixed"
                                                    styles={{
                                                        control: (b) => ({ ...b, minHeight: 32, fontSize: 12.5, minWidth: 100 }),
                                                        valueContainer: (b) => ({ ...b, padding: "0 6px" }),
                                                        indicatorsContainer: (b) => ({ ...b, height: 30 }),
                                                        menuPortal: (b) => ({ ...b, zIndex: 9999 }),
                                                        menu: (b) => ({ ...b, fontSize: 12.5 }),
                                                    }}
                                                />
                                                {currentMarking && (
                                                    <div className="mt-0.5">
                                                        <ConditionBadge type={currentMarking} size="xs" />
                                                    </div>
                                                )}
                                            </td>

                                            {/* Expand chevron */}
                                            <td className="px-3 py-2 text-center">
                                                <ChevronRight className={cn(
                                                    "size-3.5 text-muted-foreground/50 transition-transform",
                                                    isExpanded && "rotate-90"
                                                )} aria-hidden="true" />
                                            </td>
                                        </tr>

                                        {/* Expanded BOE / Allotment sub-rows */}
                                        {isExpanded && (
                                            <tr key={`${r.id}-usage`} className="border-b border-border/40 bg-muted/10">
                                                <td colSpan={totalCols} className="px-0 py-0">
                                                    <UsageDetail usage={itemUsage[r.id]} loading={itemUsageLoading[r.id]} />
                                                </td>
                                            </tr>
                                        )}
                                    </>
                                );
                            })}
                        </tbody>

                        {/* Totals row */}
                        <tfoot className="border-t-2 border-border bg-muted/40 text-sm font-semibold">
                            <tr>
                                <td colSpan={4} className="px-3 py-2.5 text-right text-xs text-muted-foreground uppercase tracking-wider">Totals</td>
                                <td className="px-3 py-2.5 text-right tabular-nums text-xs">{fmtUsd(totalCifFc)}</td>
                                <td className="px-3 py-2.5 text-right tabular-nums text-xs text-amber-700">{fmtUsd(totalDebited)}</td>
                                <td className="px-3 py-2.5 text-right tabular-nums text-xs text-violet-700">{fmtUsd(totalAllotted)}</td>
                                {!commonBalance && (
                                    <td className="px-3 py-2.5 text-right tabular-nums text-xs text-primary">{fmtUsd(totalBalance)}</td>
                                )}
                                {/* Item Names + Marking + expand — no totals */}
                                <td /><td /><td />
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>

            {/* ── 3. Balance Summary ──────────────────────────────────── */}
            <div className="overflow-hidden rounded-xl border border-primary/20 bg-primary/5">
                <div className="border-b border-primary/20 px-4 py-2.5">
                    <div className="text-[10.5px] font-semibold uppercase tracking-wider text-primary">Balance Summary</div>
                </div>
                <div className="grid grid-cols-2 gap-4 px-4 py-3 sm:grid-cols-4">
                    <div className="flex items-center gap-2.5">
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                            <FileText className="size-4 text-primary" />
                        </div>
                        <div>
                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Opening CIF</div>
                            <div className="text-sm font-bold tabular-nums text-foreground">{fmtUsd(totalCifFc)}</div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2.5">
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-amber-50">
                            <TrendingDown className="size-4 text-amber-700" />
                        </div>
                        <div>
                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">BOE Utilized</div>
                            <div className="text-sm font-bold tabular-nums text-amber-700">{fmtUsd(totalDebited)}</div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2.5">
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-violet-50">
                            <Package className="size-4 text-violet-700" />
                        </div>
                        <div>
                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Allotted</div>
                            <div className="text-sm font-bold tabular-nums text-violet-700">{fmtUsd(totalAllotted)}</div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2.5">
                        <div className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg", displayBalance > 0 ? "bg-emerald-50" : "bg-muted")}>
                            <TrendingUp className={cn("size-4", displayBalance > 0 ? "text-emerald-700" : "text-muted-foreground")} />
                        </div>
                        <div>
                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Remaining Balance</div>
                            <div className={cn("text-lg font-bold tabular-nums", displayBalance > 0 ? "text-emerald-700" : "text-muted-foreground")}>
                                {fmtUsd(displayBalance)}
                            </div>
                            <div className="text-[10px] text-muted-foreground">also {fmtInr(item.get_balance_cif)}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
