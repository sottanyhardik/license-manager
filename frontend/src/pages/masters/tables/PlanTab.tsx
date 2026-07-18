/**
 * PlanTab — view-first, edit-second planning tab.
 *
 * VIEW mode (default when plans exist):
 *   • Planning Summary card — Planned CIF, Balance CIF, Available Qty,
 *     Planned Qty, Remaining Qty, Entries, Last Updated, Planned By
 *   • Planned Items table — one row per import-item group with
 *     Available / Planned / Remaining / Planned CIF / Balance CIF / Remarks
 *   • Single "Edit Planning" button at top-right
 *
 * EDIT mode (after clicking Edit Planning):
 *   • All groups editable simultaneously
 *   • Per-split item-name, qty, unit price, CIF, remarks
 *   • 3-way auto-calc: qty×price=cif, cif÷price=qty, cif÷qty=price
 *   • Remaining cap per-split = available − other splits' qty
 *   • Global Save / Cancel (Cancel reverts, no server call)
 *   • Prefill from norm
 *
 * APIs (unchanged):
 *   fetchLicense / fetchItemPlans / bulkUpsertItemPlans / fetchNormPrefill
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
    BookOpen,
    Calendar,
    ClipboardList,
    Loader2,
    Pencil,
    Plus,
    Save,
    Target,
    Trash2,
    User,
    Wand2,
    X,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
    bulkUpsertItemPlans,
    fetchItemPlans,
    fetchLicense,
    fetchNormPrefill,
} from "../../../services/api/licenseApi";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers (same as LicensePlanningPanel — no duplication risk, stable API)
// ─────────────────────────────────────────────────────────────────────────────

let _sk = 0;
const nextKey = () => `s${++_sk}`;
const num = (v: string | number | undefined | null) => parseFloat(String(v ?? 0)) || 0;
const round2 = (x: number) => Math.round((x + Number.EPSILON) * 100) / 100;
const fmt2 = (x: number) => (x ? String(round2(x)) : "");
const fmt3 = (x: number) => (x ? String(Math.round((x + Number.EPSILON) * 1000) / 1000) : "");
const fmtQty = (v: number) => v.toLocaleString("en-US", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
const fmtUsd = (v: number) => `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDate = (s: string | null | undefined) => {
    if (!s) return null;
    try { return new Date(s).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }); } catch { return s; }
};

const emptySplit = (): Split => ({
    key: nextKey(), id: null,
    item_name: "", planned_quantity: "", unit_price: "", planned_cif_fc: "", note: "",
});

const groupKeyOf = (desc: string | undefined | null, itemNames: { id: number; name: string }[]): string | null => {
    const d = (desc || "").trim();
    if (d) return d.toUpperCase();
    const names = itemNames.map((n) => n.name).sort().join(", ");
    if (names) return "N:" + names.toUpperCase();
    return null;
};

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface Split {
    key: string;
    id: number | null;
    item_name: string;
    planned_quantity: string;
    unit_price: string;
    planned_cif_fc: string;
    note: string;
    /** Metadata from server (read-only). */
    modified_on?: string | null;
    modified_by_username?: string | null;
}

interface Group {
    id: number;
    description: string;
    serials: number[];
    hsCodes?: string[];
    memberIds: number[];
    total_quantity: number;
    available_quantity: number;
    /** Current balance CIF for the import item (from LicenseImportItemSerializer). */
    balance_cif_fc: number;
    itemNames: { id: number; name: string }[];
    splits: Split[];
}

interface PlanTabProps {
    licenseId: number;
    licenseNumber: string;
    balanceCif?: number;
    canWrite: boolean;
}

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
// PlanTab
// ─────────────────────────────────────────────────────────────────────────────

export default function PlanTab({
    licenseId, licenseNumber, balanceCif = 0, canWrite,
}: PlanTabProps) {
    /** "view" = read-only; "edit" = form visible. */
    const [mode, setMode] = useState<"view" | "edit">("view");
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [prefilling, setPrefilling] = useState(false);

    const [groups, setGroups] = useState<Group[]>([]);
    /** Snapshot of groups at last successful load/save — used for Cancel. */
    const [savedGroups, setSavedGroups] = useState<Group[]>([]);
    const [poolBalance, setPoolBalance] = useState(Number(balanceCif) || 0);

    // ── Load ───────────────────────────────────────────────────────────────────

    const load = useCallback(async () => {
        if (!licenseId) return;
        setLoading(true);
        try {
            const [license, rawPlans] = await Promise.all([
                fetchLicense(licenseId),
                fetchItemPlans(licenseId),
            ]);

            const planList: {
                id: number;
                import_item: number;
                item_name?: number | null;
                planned_quantity?: number | null;
                unit_price?: number | null;
                planned_cif_fc?: number | null;
                note?: string | null;
                modified_on?: string | null;
                modified_by_username?: string | null;
            }[] = Array.isArray(rawPlans) ? rawPlans
                : (rawPlans as { results?: unknown[] })?.results ?? [];

            const splitsByItem: Record<number, Split[]> = {};
            planList.forEach((p) => {
                (splitsByItem[p.import_item] ||= []).push({
                    key: nextKey(), id: p.id,
                    item_name: p.item_name != null ? String(p.item_name) : "",
                    planned_quantity: p.planned_quantity != null ? String(p.planned_quantity) : "",
                    unit_price: p.unit_price != null ? String(p.unit_price) : "",
                    planned_cif_fc: p.planned_cif_fc != null ? String(p.planned_cif_fc) : "",
                    note: p.note ?? "",
                    modified_on: p.modified_on,
                    modified_by_username: p.modified_by_username,
                });
            });

            const importItems: {
                id: number;
                serial_number: number;
                product_description?: string;
                description?: string;
                quantity?: number;
                available_quantity?: number;
                balance_cif_fc?: number | null;
                hs_code_label?: string;
                items_detail?: { id: number; name: string }[];
            }[] = Array.isArray(license?.import_license) ? license.import_license : [];

            const groupMap: Record<string, Group> = {};
            for (const it of importItems) {
                const itemNames = (it.items_detail ?? []).map((i) => ({ id: i.id, name: i.name }));
                const key = groupKeyOf(it.product_description || it.description, itemNames) || `ID:${it.id}`;
                if (!groupMap[key]) {
                    groupMap[key] = {
                        id: it.id,
                        description: it.product_description || it.description || key,
                        serials: [], hsCodes: [], memberIds: [],
                        total_quantity: 0, available_quantity: 0,
                        balance_cif_fc: 0,
                        itemNames: [],
                        splits: splitsByItem[it.id] ?? [emptySplit()],
                    };
                }
                const g = groupMap[key];
                g.serials.push(it.serial_number);
                if (it.hs_code_label && !g.hsCodes!.includes(it.hs_code_label)) g.hsCodes!.push(it.hs_code_label);
                g.memberIds.push(it.id);
                g.total_quantity += Number(it.quantity ?? 0);
                g.available_quantity += Number(it.available_quantity ?? 0);
                g.balance_cif_fc += Number(it.balance_cif_fc ?? 0);
                itemNames.forEach((n) => { if (!g.itemNames.find((x) => x.id === n.id)) g.itemNames.push(n); });
            }

            const built = Object.values(groupMap);
            setGroups(built);
            setSavedGroups(JSON.parse(JSON.stringify(built)));
            setPoolBalance(Number(license?.balance_cif ?? balanceCif) || 0);

            // Default to VIEW mode when any plan exists; EDIT for fresh licenses
            const anyPlan = planList.length > 0;
            setMode(anyPlan ? "view" : "edit");
        } catch {
            toast.error("Failed to load plan data");
        } finally {
            setLoading(false);
        }
    }, [licenseId, balanceCif]);

    useEffect(() => { load(); }, [load]);

    // ── Edit / Cancel ──────────────────────────────────────────────────────────

    const enterEdit = useCallback(() => {
        // If no plans exist yet, ensure at least one empty split per group
        setGroups((prev) => prev.map((g) => ({
            ...g,
            splits: g.splits.length === 0 ? [emptySplit()] : g.splits,
        })));
        setMode("edit");
    }, []);

    const cancelEdit = useCallback(() => {
        setGroups(JSON.parse(JSON.stringify(savedGroups)));
        setMode(savedGroups.some((g) => g.splits.some((s) => s.id !== null)) ? "view" : "edit");
    }, [savedGroups]);

    // ── 3-way auto-calc ───────────────────────────────────────────────────────

    const changeSplit = useCallback((gId: number, key: string, field: string, value: string) => {
        setGroups((prev) => prev.map((g) => {
            if (g.id !== gId) return g;
            return {
                ...g,
                splits: g.splits.map((sp) => {
                    if (sp.key !== key) return sp;
                    const updated = { ...sp, [field]: value };
                    const q = num(updated.planned_quantity);
                    const p = num(updated.unit_price);
                    const c = num(updated.planned_cif_fc);
                    const otherQty = g.splits.filter((s) => s.key !== key).reduce((s, s2) => s + num(s2.planned_quantity), 0);
                    const maxForRow = Math.max(0, g.available_quantity - otherQty);
                    if (field === "planned_quantity" || field === "unit_price") {
                        if (q > 0 && p > 0) updated.planned_cif_fc = fmt2(q * p);
                    } else if (field === "planned_cif_fc") {
                        if (p > 0 && c > 0) updated.planned_quantity = fmt3(Math.min(c / p, maxForRow));
                        else if (q > 0 && c > 0) updated.unit_price = fmt2(c / q);
                    }
                    return updated;
                }),
            };
        }));
    }, []);

    const addSplit = useCallback((gId: number) => {
        setGroups((prev) => prev.map((g) => g.id === gId ? { ...g, splits: [...g.splits, emptySplit()] } : g));
    }, []);

    const removeSplit = useCallback((gId: number, key: string) => {
        setGroups((prev) => prev.map((g) =>
            g.id === gId && g.splits.length > 1
                ? { ...g, splits: g.splits.filter((s) => s.key !== key) }
                : g
        ));
    }, []);

    // ── Save (global) ─────────────────────────────────────────────────────────

    const handleSave = useCallback(async () => {
        // Validation
        for (const g of groups) {
            const totalQty = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
            if (totalQty > g.available_quantity + 1e-6) {
                toast.error(`${g.description}: planned qty (${totalQty.toFixed(3)}) exceeds available (${g.available_quantity.toFixed(3)})`);
                return;
            }
        }
        if (cifOver) {
            toast.error("Total planned CIF exceeds the license balance");
            return;
        }

        const lines = groups.flatMap((g) =>
            g.splits
                .filter((sp) => num(sp.planned_quantity) > 0 || num(sp.planned_cif_fc) > 0)
                .map((sp) => ({
                    import_item: g.id,
                    item_name: sp.item_name ? Number(sp.item_name) : null,
                    planned_quantity: num(sp.planned_quantity),
                    unit_price: num(sp.unit_price),
                    planned_cif_fc: num(sp.planned_cif_fc),
                    note: sp.note || "",
                }))
        );

        setSaving(true);
        try {
            await bulkUpsertItemPlans(licenseId, lines);
            toast.success("Plan saved");
            await load(); // Refresh from server (picks up server ids + metadata)
            setMode("view");
        } catch (err: unknown) {
            const data = (err as { response?: { data?: { error?: string; errors?: unknown } } })?.response?.data;
            toast.error(data?.error || (data?.errors ? JSON.stringify(data.errors) : null) || "Failed to save plan");
        } finally {
            setSaving(false);
        }
    }, [groups, licenseId, load]);

    // ── Prefill ────────────────────────────────────────────────────────────────

    const handlePrefill = useCallback(async () => {
        setPrefilling(true);
        try {
            const { norm, plan } = await fetchNormPrefill(licenseId);
            if (!norm) { toast.error("This license has no E1/E5/E132 norm to plan from"); return; }
            let filled = 0;
            setGroups((prev) => prev.map((g) => {
                let q = 0, c = 0;
                g.memberIds.forEach((mid) => {
                    const p = (plan as Record<string, { planned_quantity?: number; planned_cif?: number }>)?.[String(mid)];
                    if (p) { q += Number(p.planned_quantity || 0); c += Number(p.planned_cif || 0); }
                });
                if (q > 0 || c > 0) {
                    filled++;
                    return { ...g, splits: [{ key: nextKey(), id: null, item_name: "", planned_quantity: q ? fmt3(q) : "", unit_price: q ? String(round2(c / q)) : "", planned_cif_fc: c ? fmt2(c) : "", note: "" }] };
                }
                return g;
            }));
            setMode("edit");
            toast.success(`Prefilled ${filled} product(s) from ${norm} — review and Save`);
        } catch { toast.error("Failed to compute norm plan"); }
        finally { setPrefilling(false); }
    }, [licenseId]);

    // ── Derived totals ─────────────────────────────────────────────────────────

    const totals = useMemo(() => {
        let totalAvail = 0, totalPlanned = 0, totalCif = 0, totalEntries = 0;
        let lastUpdated: string | null = null;
        let plannedBy: string | null = null;

        groups.forEach((g) => {
            totalAvail += g.available_quantity;
            const qtySum = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
            const cifSum = g.splits.reduce((s, sp) => s + num(sp.planned_cif_fc), 0);
            totalPlanned += qtySum;
            totalCif += cifSum;
            totalEntries += g.splits.filter((sp) => num(sp.planned_quantity) > 0 || num(sp.planned_cif_fc) > 0).length;

            // Most recent metadata across all splits
            g.splits.forEach((sp) => {
                if (sp.modified_on && (!lastUpdated || sp.modified_on > lastUpdated)) {
                    lastUpdated = sp.modified_on;
                    plannedBy = sp.modified_by_username ?? null;
                }
            });
        });

        return {
            totalAvail,
            totalPlanned,
            remaining: totalAvail - totalPlanned,
            totalCif,
            cifRemaining: Number(poolBalance) - totalCif,
            totalEntries,
            lastUpdated,
            plannedBy,
        };
    }, [groups, poolBalance]);

    const cifOver = totals.cifRemaining < -1e-6;

    const anyPlanExists = groups.some((g) => g.splits.some((s) => s.id !== null));

    // ── Render ─────────────────────────────────────────────────────────────────

    if (loading) {
        return (
            <div className="space-y-3 py-4">
                <Skeleton className="h-28 w-full rounded-xl" />
                <Skeleton className="h-40 w-full rounded-xl" />
            </div>
        );
    }

    if (!canWrite) {
        return (
            <div className="py-8 text-center text-sm text-muted-foreground">
                You don't have permission to plan utilization for this license.
            </div>
        );
    }

    return (
        <div className="py-3">
            {/* ── Tab header ─────────────────────────────────────── */}
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Target className="size-4 text-primary" aria-hidden="true" />
                    Plan utilization — {licenseNumber}
                    {mode === "edit" && (
                        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10.5px] font-semibold text-amber-700 ring-1 ring-amber-200">
                            Editing
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    {mode === "view" && (
                        <>
                            <Button variant="outline" size="sm" onClick={handlePrefill}
                                disabled={prefilling} className="h-7 gap-1.5 text-xs">
                                {prefilling ? <Loader2 className="size-3.5 animate-spin" /> : <Wand2 className="size-3.5" />}
                                Prefill from norm
                            </Button>
                            <Button size="sm" onClick={enterEdit} className="h-7 gap-1.5 text-xs">
                                <Pencil className="size-3.5" />
                                Edit Planning
                            </Button>
                        </>
                    )}
                    {mode === "edit" && (
                        <>
                            <Button variant="outline" size="sm" onClick={handlePrefill}
                                disabled={prefilling || saving} className="h-7 gap-1.5 text-xs">
                                {prefilling ? <Loader2 className="size-3.5 animate-spin" /> : <Wand2 className="size-3.5" />}
                                Prefill from norm
                            </Button>
                            <Button variant="outline" size="sm" onClick={cancelEdit}
                                disabled={saving} className="h-7 gap-1.5 text-xs">
                                <X className="size-3.5" />Cancel
                            </Button>
                            <Button size="sm" onClick={handleSave}
                                disabled={saving || cifOver} className="h-7 gap-1.5 text-xs">
                                {saving ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
                                Save Plan
                            </Button>
                        </>
                    )}
                </div>
            </div>

            {/* ══════════════════════════════════════════════════════ */}
            {/* VIEW MODE                                             */}
            {/* ══════════════════════════════════════════════════════ */}
            {mode === "view" && (
                <div className="space-y-4">
                    {/* ── Planning Summary card ─────────────────────── */}
                    <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
                        <div className="border-b border-border/50 px-4 py-2.5">
                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                Planning Summary
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-x-6 gap-y-4 px-4 py-4 sm:grid-cols-3 lg:grid-cols-6">
                            <SummaryMetric label="Planned CIF"
                                value={fmtUsd(totals.totalCif)} variant="primary" />
                            <SummaryMetric label="Balance CIF"
                                value={fmtUsd(Math.max(0, totals.cifRemaining))}
                                variant={cifOver ? "danger" : "success"} />
                            <SummaryMetric label="Available Qty"
                                value={fmtQty(totals.totalAvail)} />
                            <SummaryMetric label="Total Planned Qty"
                                value={fmtQty(totals.totalPlanned)} />
                            <SummaryMetric label="Remaining Qty"
                                value={fmtQty(Math.max(0, totals.remaining))}
                                variant={totals.remaining < -1e-6 ? "danger" : totals.remaining < 1e-6 ? "muted" : "success"} />
                            <SummaryMetric label="Entries"
                                value={String(totals.totalEntries)} variant="muted" />
                        </div>
                        {/* Metadata row */}
                        {(totals.lastUpdated || totals.plannedBy) && (
                            <div className="flex flex-wrap gap-4 border-t border-border/40 px-4 py-2 text-[11px] text-muted-foreground">
                                {totals.lastUpdated && (
                                    <span className="flex items-center gap-1">
                                        <Calendar className="size-3.5" aria-hidden="true" />
                                        Last updated: {fmtDate(totals.lastUpdated)}
                                    </span>
                                )}
                                {totals.plannedBy && (
                                    <span className="flex items-center gap-1">
                                        <User className="size-3.5" aria-hidden="true" />
                                        Planned by: {totals.plannedBy}
                                    </span>
                                )}
                            </div>
                        )}
                    </div>

                    {/* ── Planned Items table ───────────────────────── */}
                    {anyPlanExists ? (
                        <div className="overflow-hidden rounded-xl border border-border/60">
                            <div className="border-b border-border/50 bg-muted/30 px-4 py-2.5">
                                <div className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                    <ClipboardList className="size-3.5" />Planned Items
                                </div>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead className="bg-muted/50">
                                        <tr className="text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground border-b border-border/50">
                                            <th scope="col" className="px-4 py-2.5">Item</th>
                                            <th scope="col" className="px-4 py-2.5 text-right">Available Qty</th>
                                            <th scope="col" className="px-4 py-2.5 text-right">Planned Qty</th>
                                            <th scope="col" className="px-4 py-2.5 text-right">Remaining Qty</th>
                                            <th scope="col" className="px-4 py-2.5 text-right">Planned CIF</th>
                                            <th scope="col" className="px-4 py-2.5 text-right">Balance CIF</th>
                                            <th scope="col" className="px-4 py-2.5">Item Names</th>
                                            <th scope="col" className="px-4 py-2.5">Remarks</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border/40">
                                        {groups.map((g) => {
                                            const plannedQty = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
                                            const plannedCif = g.splits.reduce((s, sp) => s + num(sp.planned_cif_fc), 0);
                                            const remainingQty = g.available_quantity - plannedQty;
                                            const hasPlan = g.splits.some((s) => num(s.planned_quantity) > 0 || num(s.planned_cif_fc) > 0);
                                            // Collect unique item names across all splits
                                            const usedItemNames = [...new Set(
                                                g.splits
                                                    .map((sp) => sp.item_name ? g.itemNames.find((n) => n.id === Number(sp.item_name))?.name : null)
                                                    .filter(Boolean)
                                            )];
                                            const remarks = g.splits.map((sp) => sp.note).filter(Boolean).join("; ");

                                            return (
                                                <tr key={g.id} className={cn(
                                                    "transition-colors hover:bg-muted/20",
                                                    !hasPlan && "opacity-50"
                                                )}>
                                                    <td className="px-4 py-3">
                                                        <div className="font-medium text-foreground">{g.description}</div>
                                                        <div className="text-[10.5px] text-muted-foreground">
                                                            S.No {g.serials.join(", ")}
                                                            {g.hsCodes && g.hsCodes.length > 0 && ` · HSN ${g.hsCodes.join(", ")}`}
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-3 text-right tabular-nums text-sm">{fmtQty(g.available_quantity)}</td>
                                                    <td className="px-4 py-3 text-right tabular-nums text-sm font-semibold">
                                                        {hasPlan ? fmtQty(plannedQty) : <span className="font-normal text-muted-foreground">—</span>}
                                                    </td>
                                                    <td className="px-4 py-3 text-right tabular-nums text-sm">
                                                        <span className={cn("font-semibold",
                                                            remainingQty < -1e-6 ? "text-destructive" :
                                                            remainingQty < 1e-6 ? "text-muted-foreground" : "text-emerald-700"
                                                        )}>
                                                            {hasPlan ? fmtQty(remainingQty) : fmtQty(g.available_quantity)}
                                                        </span>
                                                    </td>
                                                    <td className="px-4 py-3 text-right tabular-nums text-sm">
                                                        {hasPlan ? <span className="text-primary">{fmtUsd(plannedCif)}</span> : <span className="text-muted-foreground">—</span>}
                                                    </td>
                                                    <td className="px-4 py-3 text-right tabular-nums text-sm text-muted-foreground">
                                                        {fmtUsd(g.balance_cif_fc)}
                                                    </td>
                                                    <td className="px-4 py-3 text-sm">
                                                        {usedItemNames.length > 0
                                                            ? usedItemNames.map((n, i) => (
                                                                <span key={i} className="mr-1 inline-block rounded-full bg-muted px-2 py-0.5 text-[10.5px] font-medium text-foreground">{n}</span>
                                                            ))
                                                            : <span className="text-muted-foreground">—</span>}
                                                    </td>
                                                    <td className="px-4 py-3 text-sm text-muted-foreground">
                                                        {remarks || <span className="text-muted-foreground/50">—</span>}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                    {/* Totals footer */}
                                    <tfoot className="border-t-2 border-border bg-muted/40 font-semibold text-sm">
                                        <tr>
                                            <td className="px-4 py-2 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Totals</td>
                                            <td className="px-4 py-2 text-right tabular-nums">{fmtQty(totals.totalAvail)}</td>
                                            <td className="px-4 py-2 text-right tabular-nums">{fmtQty(totals.totalPlanned)}</td>
                                            <td className="px-4 py-2 text-right tabular-nums">
                                                <span className={cn(totals.remaining < -1e-6 ? "text-destructive" : "text-emerald-700")}>{fmtQty(totals.remaining)}</span>
                                            </td>
                                            <td className="px-4 py-2 text-right tabular-nums text-primary">{fmtUsd(totals.totalCif)}</td>
                                            <td colSpan={3} />
                                        </tr>
                                    </tfoot>
                                </table>
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center py-12 text-center">
                            <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-muted">
                                <BookOpen className="size-6 text-muted-foreground/50" aria-hidden="true" />
                            </div>
                            <div className="text-sm font-medium text-muted-foreground">No planning recorded</div>
                            <div className="mt-1 text-xs text-muted-foreground/70">Click "Edit Planning" to add utilization planning for this license.</div>
                        </div>
                    )}
                </div>
            )}

            {/* ══════════════════════════════════════════════════════ */}
            {/* EDIT MODE                                             */}
            {/* ══════════════════════════════════════════════════════ */}
            {mode === "edit" && (
                <div className="space-y-3">
                    {/* CIF balance bar */}
                    <div className={cn(
                        "flex flex-wrap items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm",
                        cifOver ? "border-destructive/40 bg-destructive/5" : "border-border bg-muted/40"
                    )}>
                        <span>Balance CIF: <b className="tabular-nums">{Number(poolBalance).toFixed(2)}</b></span>
                        <span>Planned CIF: <b className="tabular-nums">{totals.totalCif.toFixed(2)}</b></span>
                        <span className={cn("font-semibold tabular-nums", cifOver ? "text-destructive" : "text-emerald-700")}>
                            {cifOver ? "Over by " : "Remaining CIF "}{Math.abs(totals.cifRemaining).toFixed(2)}
                        </span>
                        <Separator orientation="vertical" className="h-4" />
                        <span>Available Qty: <b>{fmtQty(totals.totalAvail)}</b></span>
                        <span>Planned Qty: <b className={totals.remaining < -1e-6 ? "text-destructive" : ""}>{fmtQty(totals.totalPlanned)}</b></span>
                        <span className={cn("font-semibold", totals.remaining < -1e-6 ? "text-destructive" : "text-emerald-700")}>
                            Remaining {fmtQty(totals.remaining)}
                        </span>
                    </div>

                    {/* Group edit cards */}
                    {groups.map((g) => {
                        const qtySum = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
                        const remainingQty = g.available_quantity - qtySum;
                        const qtyOver = qtySum > g.available_quantity + 1e-6;

                        return (
                            <div key={g.id} className={cn(
                                "overflow-hidden rounded-xl border bg-card",
                                qtyOver ? "border-destructive/40" : "border-border"
                            )}>
                                {/* Group header */}
                                <div className="border-b border-border bg-muted/20 px-4 py-2.5">
                                    <div className="text-sm font-semibold text-foreground">
                                        {g.description}
                                        <span className="ml-2 text-xs font-normal text-muted-foreground">S.No {g.serials.join(", ")}</span>
                                        {g.hsCodes && g.hsCodes.length > 0 && (
                                            <span className="ml-2 text-xs font-normal text-muted-foreground">HSN {g.hsCodes.join(", ")}</span>
                                        )}
                                    </div>
                                    <div className="mt-0.5 flex flex-wrap gap-3 text-xs">
                                        <span className="text-muted-foreground">Avail: <b>{fmtQty(g.available_quantity)}</b></span>
                                        <span className="text-muted-foreground">Planned: <b className={qtyOver ? "text-destructive" : ""}>{fmtQty(qtySum)}</b></span>
                                        <span className={cn("font-semibold", remainingQty < -1e-6 ? "text-destructive" : remainingQty < 1e-6 ? "text-muted-foreground" : "text-emerald-700")}>
                                            Remaining: {fmtQty(remainingQty)}
                                        </span>
                                    </div>
                                </div>

                                {/* Splits table */}
                                <div className="px-4 py-3">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-left text-xs text-muted-foreground border-b border-border/40">
                                                <th scope="col" className="pb-1.5 pr-2 font-medium">Item name</th>
                                                <th scope="col" className="pb-1.5 pr-2 font-medium text-right">Qty</th>
                                                <th scope="col" className="pb-1.5 pr-2 font-medium text-right">Unit price</th>
                                                <th scope="col" className="pb-1.5 pr-2 font-medium text-right">CIF ($)</th>
                                                <th scope="col" className="pb-1.5 pr-2 font-medium">Remarks</th>
                                                <th scope="col" className="pb-1.5 w-7" />
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {g.splits.map((sp) => {
                                                const otherQty = g.splits.filter((s) => s.key !== sp.key).reduce((s, s2) => s + num(s2.planned_quantity), 0);
                                                const maxForRow = Math.max(0, g.available_quantity - otherQty);
                                                const rowOver = num(sp.planned_quantity) > maxForRow + 1e-6;
                                                return (
                                                    <tr key={sp.key} className="border-b border-border/20 last:border-0">
                                                        <td className="py-1.5 pr-2">
                                                            <select value={sp.item_name}
                                                                onChange={(e) => changeSplit(g.id, sp.key, "item_name", e.target.value)}
                                                                className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
                                                                aria-label="Item name">
                                                                <option value="">—</option>
                                                                {g.itemNames.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
                                                            </select>
                                                        </td>
                                                        <td className="py-1.5 pr-2">
                                                            <Input type="number" min="0" step="0.001" max={maxForRow}
                                                                value={sp.planned_quantity}
                                                                onChange={(e) => changeSplit(g.id, sp.key, "planned_quantity", e.target.value)}
                                                                className={cn("h-8 w-24 text-right", rowOver && "border-destructive")}
                                                                aria-label={`Qty (max ${maxForRow.toFixed(3)})`}
                                                                title={`Max for this row: ${maxForRow.toFixed(3)}`} />
                                                        </td>
                                                        <td className="py-1.5 pr-2">
                                                            <Input type="number" min="0" step="0.01" value={sp.unit_price}
                                                                onChange={(e) => changeSplit(g.id, sp.key, "unit_price", e.target.value)}
                                                                className="h-8 w-24 text-right" aria-label="Unit price" />
                                                        </td>
                                                        <td className="py-1.5 pr-2">
                                                            <Input type="number" min="0" step="0.01" value={sp.planned_cif_fc}
                                                                onChange={(e) => changeSplit(g.id, sp.key, "planned_cif_fc", e.target.value)}
                                                                className="h-8 w-28 text-right" aria-label="Planned CIF" />
                                                        </td>
                                                        <td className="py-1.5 pr-2">
                                                            <Input value={sp.note}
                                                                onChange={(e) => changeSplit(g.id, sp.key, "note", e.target.value)}
                                                                className="h-8 w-32" placeholder="Remarks…" aria-label="Remarks" />
                                                        </td>
                                                        <td className="py-1.5 text-center">
                                                            <button type="button"
                                                                onClick={() => removeSplit(g.id, sp.key)}
                                                                disabled={g.splits.length <= 1}
                                                                className="text-muted-foreground hover:text-destructive disabled:opacity-30 cursor-pointer"
                                                                title="Remove row" aria-label="Remove row">
                                                                <Trash2 className="size-4" />
                                                            </button>
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                        {g.splits.length > 1 && (
                                            <tfoot className="border-t border-border/50">
                                                <tr>
                                                    <td className="pt-1 pr-2 text-[10.5px] text-muted-foreground text-right uppercase tracking-wider">Total</td>
                                                    <td className="pt-1 pr-2 text-right tabular-nums text-xs font-semibold">{fmtQty(qtySum)}</td>
                                                    <td />
                                                    <td className="pt-1 pr-2 text-right tabular-nums text-xs font-semibold">
                                                        {fmtUsd(g.splits.reduce((s, sp) => s + num(sp.planned_cif_fc), 0))}
                                                    </td>
                                                    <td colSpan={2} />
                                                </tr>
                                            </tfoot>
                                        )}
                                    </table>

                                    <button type="button" onClick={() => addSplit(g.id)}
                                        className="mt-2 flex cursor-pointer items-center gap-1 text-xs font-medium text-primary hover:underline">
                                        <Plus className="size-3.5" />Add split
                                    </button>

                                    {qtyOver && (
                                        <div className="mt-1.5 text-xs text-destructive">
                                            ⚠ Planned ({fmtQty(qtySum)}) exceeds available ({fmtQty(g.available_quantity)})
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}

                    {groups.length === 0 && (
                        <div className="py-6 text-center text-sm text-muted-foreground">No import items found.</div>
                    )}

                    {/* Bottom save/cancel bar */}
                    {groups.length > 0 && (
                        <div className="sticky bottom-0 flex items-center justify-end gap-2 rounded-xl border border-border bg-card/95 px-4 py-3 shadow-sm backdrop-blur-sm">
                            {cifOver && (
                                <span className="mr-2 text-xs text-destructive">Planned CIF exceeds license balance</span>
                            )}
                            <Button variant="outline" size="sm" onClick={cancelEdit}
                                disabled={saving} className="gap-1.5">
                                <X className="size-4" />Cancel
                            </Button>
                            <Button size="sm" onClick={handleSave}
                                disabled={saving || cifOver} className="gap-1.5">
                                {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
                                Save Plan
                            </Button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
