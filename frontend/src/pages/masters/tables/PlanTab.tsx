/**
 * PlanTab — embedded planning tab (no Dialog wrapper).
 *
 * Reuses the same APIs and business logic as LicensePlanningPanel:
 *   fetchLicense / fetchItemPlans / bulkUpsertItemPlans / fetchNormPrefill
 *
 * Improvements over the original:
 *   1. VIEW mode by default when saved plans exist; edit requires "Edit Planning".
 *   2. Remaining Qty = Available − Σ(all split quantities), not per-row.
 *   3. Split-aware auto-calc: qty cap uses remaining for the current row only.
 *   4. Planning summary card at the top.
 *   5. Per-group save (bulkUpsert for that group's item), not global.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
    BookOpen,
    Loader2,
    Pencil,
    Plus,
    Save,
    Target,
    Trash2,
    Wand2,
    X,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
    bulkUpsertItemPlans,
    fetchItemPlans,
    fetchLicense,
    fetchNormPrefill,
} from "../../../services/api/licenseApi";

// ─────────────────────────────────────────────────────────────────────────────
// Pure helpers (same as LicensePlanningPanel)
// ─────────────────────────────────────────────────────────────────────────────

let _sk = 0;
const nextKey = () => `s${++_sk}`;
const num = (v: string | number | undefined | null) => parseFloat(String(v ?? 0)) || 0;
const round2 = (x: number) => Math.round((x + Number.EPSILON) * 100) / 100;
const fmt2 = (x: number) => (x ? String(round2(x)) : "");
const fmt3 = (x: number) => (x ? String(Math.round((x + Number.EPSILON) * 1000) / 1000) : "");

const emptySplit = (): Split => ({
    key: nextKey(), id: null,
    item_name: "", planned_quantity: "", unit_price: "", planned_cif_fc: "",
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
    /** Local UI key — stable across renders. */
    key: string;
    /** Server-side plan line id (null = new, unsaved). */
    id: number | null;
    item_name: string;
    planned_quantity: string;
    unit_price: string;
    planned_cif_fc: string;
}

interface Group {
    id: number;          // representative import-item id
    description: string;
    serials: number[];
    hsCodes?: string[];
    memberIds: number[];
    total_quantity: number;
    available_quantity: number;
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
// PlanTab
// ─────────────────────────────────────────────────────────────────────────────

export default function PlanTab({
    licenseId, licenseNumber, balanceCif = 0, canWrite,
}: PlanTabProps) {
    const [loading, setLoading] = useState(false);
    const [prefilling, setPrefilling] = useState(false);

    /** Live groups (mutated as user edits). */
    const [groups, setGroups] = useState<Group[]>([]);
    /** Snapshot of groups as last saved — used for "Cancel". */
    const [savedGroups, setSavedGroups] = useState<Group[]>([]);
    /** Groups currently in edit mode. */
    const [editingIds, setEditingIds] = useState<Set<number>>(new Set());
    /** Groups currently being saved. */
    const [savingIds, setSavingIds] = useState<Set<number>>(new Set());

    const [poolBalance, setPoolBalance] = useState(Number(balanceCif) || 0);

    // ── Initial load ──────────────────────────────────────────────────────────

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
            }[] = Array.isArray(rawPlans)
                ? rawPlans
                : (rawPlans as { results?: unknown[] })?.results ?? [];

            // Index plan lines by import_item id
            const splitsByItem: Record<number, Split[]> = {};
            planList.forEach((p) => {
                const arr = (splitsByItem[p.import_item] ||= []);
                arr.push({
                    key: nextKey(),
                    id: p.id,
                    item_name: p.item_name != null ? String(p.item_name) : "",
                    planned_quantity: p.planned_quantity != null ? String(p.planned_quantity) : "",
                    unit_price: p.unit_price != null ? String(p.unit_price) : "",
                    planned_cif_fc: p.planned_cif_fc != null ? String(p.planned_cif_fc) : "",
                });
            });

            const importItems: {
                id: number;
                serial_number: number;
                product_description?: string;
                description?: string;
                quantity?: number;
                available_quantity?: number;
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
                        itemNames: [],
                        // If saved plans exist → view mode (no empty row added).
                        // If no saved plans → one empty split so user can type.
                        splits: splitsByItem[it.id] ?? [emptySplit()],
                    };
                }
                const g = groupMap[key];
                g.serials.push(it.serial_number);
                if (it.hs_code_label && !g.hsCodes!.includes(it.hs_code_label))
                    g.hsCodes!.push(it.hs_code_label);
                g.memberIds.push(it.id);
                g.total_quantity += Number(it.quantity ?? 0);
                g.available_quantity += Number(it.available_quantity ?? 0);
                itemNames.forEach((n) => { if (!g.itemNames.find((x) => x.id === n.id)) g.itemNames.push(n); });
            }

            const built = Object.values(groupMap);
            setGroups(built);
            setSavedGroups(structuredClone ? structuredClone(built) : JSON.parse(JSON.stringify(built)));
            setPoolBalance(Number(license?.balance_cif ?? balanceCif) || 0);

            // Groups with NO saved plans open in edit mode so user can start planning.
            // Groups WITH saved plans open in view mode.
            const newEditingIds = new Set<number>();
            built.forEach((g) => {
                const hasSavedPlan = g.splits.some((s) => s.id !== null);
                if (!hasSavedPlan) newEditingIds.add(g.id);
            });
            setEditingIds(newEditingIds);
        } catch {
            toast.error("Failed to load plan data");
        } finally {
            setLoading(false);
        }
    }, [licenseId, balanceCif]);

    useEffect(() => { load(); }, [load]);

    // ── Edit / cancel helpers ─────────────────────────────────────────────────

    const enterEdit = useCallback((gId: number) => {
        setEditingIds((prev) => new Set([...prev, gId]));
    }, []);

    const cancelEdit = useCallback((gId: number) => {
        // Revert splits to last saved state
        const saved = savedGroups.find((g) => g.id === gId);
        if (saved) {
            setGroups((prev) => prev.map((g) => g.id === gId
                ? { ...g, splits: JSON.parse(JSON.stringify(saved.splits)) }
                : g
            ));
        }
        setEditingIds((prev) => { const n = new Set(prev); n.delete(gId); return n; });
    }, [savedGroups]);

    // ── 3-way auto-calc ───────────────────────────────────────────────────────
    // Remaining for this specific split = available − sum_of_other_splits.
    // This fixes the bug where capping used g.available_quantity instead of
    // the remaining quantity after accounting for other splits.

    const changeSplit = useCallback((gId: number, key: string, field: string, value: string) => {
        setGroups((prev) => prev.map((g) => {
            if (g.id !== gId) return g;
            const newSplits = g.splits.map((sp) => {
                if (sp.key !== key) return sp;
                const updated = { ...sp, [field]: value };
                const q = num(updated.planned_quantity);
                const p = num(updated.unit_price);
                const c = num(updated.planned_cif_fc);
                // Max qty for this split = available − sum of all OTHER splits
                const otherQty = g.splits
                    .filter((s) => s.key !== key)
                    .reduce((s, s2) => s + num(s2.planned_quantity), 0);
                const maxForThisRow = Math.max(0, g.available_quantity - otherQty);

                if (field === "planned_quantity" || field === "unit_price") {
                    if (q > 0 && p > 0) updated.planned_cif_fc = fmt2(q * p);
                } else if (field === "planned_cif_fc") {
                    if (p > 0 && c > 0)
                        updated.planned_quantity = fmt3(Math.min(c / p, maxForThisRow));
                    else if (q > 0 && c > 0)
                        updated.unit_price = fmt2(c / q);
                }
                return updated;
            });
            return { ...g, splits: newSplits };
        }));
    }, []);

    const addSplit = useCallback((gId: number) => {
        setGroups((prev) => prev.map((g) =>
            g.id === gId ? { ...g, splits: [...g.splits, emptySplit()] } : g
        ));
    }, []);

    const removeSplit = useCallback((gId: number, key: string) => {
        setGroups((prev) => prev.map((g) =>
            g.id === gId && g.splits.length > 1
                ? { ...g, splits: g.splits.filter((s) => s.key !== key) }
                : g
        ));
    }, []);

    // ── Save (per group) ──────────────────────────────────────────────────────

    const handleSave = useCallback(async (g: Group) => {
        // Validation: total planned qty for this group vs available
        const totalQty = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
        if (totalQty > g.available_quantity + 1e-6) {
            toast.error(`${g.description}: total planned qty (${totalQty.toFixed(3)}) exceeds available (${g.available_quantity.toFixed(3)})`);
            return;
        }

        const lines = g.splits
            .filter((sp) => num(sp.planned_quantity) > 0 || num(sp.planned_cif_fc) > 0)
            .map((sp) => ({
                import_item: g.id,
                item_name: sp.item_name ? Number(sp.item_name) : null,
                planned_quantity: num(sp.planned_quantity),
                unit_price: num(sp.unit_price),
                planned_cif_fc: num(sp.planned_cif_fc),
            }));

        setSavingIds((prev) => new Set([...prev, g.id]));
        try {
            await bulkUpsertItemPlans(licenseId, lines);
            toast.success(`Plan saved for ${g.description}`);
            // Snapshot updated splits as new saved state
            setSavedGroups((prev) => prev.map((sg) =>
                sg.id === g.id ? { ...sg, splits: JSON.parse(JSON.stringify(g.splits)) } : sg
            ));
            // Exit edit mode
            setEditingIds((prev) => { const n = new Set(prev); n.delete(g.id); return n; });
            // Refresh plan ids from server
            await load();
        } catch (err: unknown) {
            const data = (err as { response?: { data?: { error?: string; errors?: unknown } } })?.response?.data;
            toast.error(data?.error || (data?.errors ? JSON.stringify(data.errors) : null) || "Failed to save plan");
        } finally {
            setSavingIds((prev) => { const n = new Set(prev); n.delete(g.id); return n; });
        }
    }, [licenseId, load]);

    // ── Prefill (global) ──────────────────────────────────────────────────────

    const handlePrefill = async () => {
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
                    return { ...g, splits: [{ key: nextKey(), id: null, item_name: "", planned_quantity: q ? fmt3(q) : "", unit_price: q ? String(round2(c / q)) : "", planned_cif_fc: c ? fmt2(c) : "" }] };
                }
                return g;
            }));
            // Switch all groups to edit mode after prefill
            setEditingIds(new Set(groups.map((g) => g.id)));
            toast.success(`Prefilled ${filled} product(s) from ${norm} — review and Save`);
        } catch { toast.error("Failed to compute norm plan"); }
        finally { setPrefilling(false); }
    };

    // ── Derived totals for summary card ───────────────────────────────────────

    const summaryTotals = useMemo(() => {
        let totalAvail = 0, totalPlanned = 0, totalEntries = 0;
        groups.forEach((g) => {
            totalAvail += g.available_quantity;
            const qtySum = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
            totalPlanned += qtySum;
            totalEntries += g.splits.filter((sp) => num(sp.planned_quantity) > 0 || num(sp.planned_cif_fc) > 0).length;
        });
        return { totalAvail, totalPlanned, remaining: totalAvail - totalPlanned, totalEntries };
    }, [groups]);

    const plannedCifTotal = useMemo(() =>
        groups.reduce((s, g) => s + g.splits.reduce((ss, sp) => ss + num(sp.planned_cif_fc), 0), 0),
        [groups]
    );
    const cifRemaining = Number(poolBalance) - plannedCifTotal;
    const cifOver = cifRemaining < 0;

    // ── Render ────────────────────────────────────────────────────────────────

    if (loading) {
        return (
            <div className="space-y-3 py-4">
                <Skeleton className="h-20 w-full rounded-xl" />
                <Skeleton className="h-32 w-full rounded-xl" />
                <Skeleton className="h-32 w-full rounded-xl" />
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
            {/* ── Header ─────────────────────────────────────────── */}
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Target className="size-4 text-primary" aria-hidden="true" />
                    Plan utilization — {licenseNumber}
                </div>
                <Button variant="outline" size="sm" onClick={handlePrefill}
                    disabled={loading || prefilling} className="h-7 gap-1.5 text-xs">
                    {prefilling ? <Loader2 className="size-3.5 animate-spin" /> : <Wand2 className="size-3.5" />}
                    Prefill from norm
                </Button>
            </div>

            {/* ── Planning Summary card ───────────────────────────── */}
            {groups.length > 0 && (
                <div className="mb-4 grid grid-cols-2 gap-3 rounded-xl border border-border bg-card px-4 py-3 sm:grid-cols-4">
                    <div>
                        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Available Qty</div>
                        <div className="text-base font-bold tabular-nums text-foreground">{summaryTotals.totalAvail.toFixed(3)}</div>
                    </div>
                    <div>
                        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Total Planned</div>
                        <div className="text-base font-bold tabular-nums text-foreground">{summaryTotals.totalPlanned.toFixed(3)}</div>
                    </div>
                    <div>
                        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Remaining Qty</div>
                        <div className={cn("text-base font-bold tabular-nums",
                            summaryTotals.remaining < -1e-6 ? "text-destructive" :
                            summaryTotals.remaining < 1e-6 ? "text-muted-foreground" : "text-emerald-700")}>
                            {summaryTotals.remaining.toFixed(3)}
                        </div>
                    </div>
                    <div>
                        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Plan Entries</div>
                        <div className="text-base font-bold tabular-nums text-foreground">{summaryTotals.totalEntries}</div>
                    </div>
                </div>
            )}

            {/* CIF balance bar */}
            <div className={cn(
                "mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm",
                cifOver ? "border-destructive/40 bg-destructive/5" : "border-border bg-muted/40"
            )}>
                <span>Balance CIF: <b className="tabular-nums">{Number(poolBalance).toFixed(2)}</b></span>
                <span>Planned CIF: <b className="tabular-nums">{plannedCifTotal.toFixed(2)}</b></span>
                <span className={cn("font-semibold tabular-nums", cifOver ? "text-destructive" : "text-emerald-700")}>
                    {cifOver ? "Over by " : "Remaining CIF "}{Math.abs(cifRemaining).toFixed(2)}
                </span>
            </div>

            {/* ── Groups ─────────────────────────────────────────── */}
            <div className="space-y-3">
                {groups.map((g) => {
                    const isEditing = editingIds.has(g.id);
                    const isSaving = savingIds.has(g.id);
                    const qtySum = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
                    const remainingQty = g.available_quantity - qtySum;
                    const qtyOver = qtySum > g.available_quantity + 1e-6;
                    const hasSavedPlan = g.splits.some((s) => s.id !== null);

                    return (
                        <div key={g.id} className={cn(
                            "overflow-hidden rounded-xl border bg-card",
                            qtyOver ? "border-destructive/40" : "border-border"
                        )}>
                            {/* Group header */}
                            <div className={cn(
                                "flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2.5",
                                isEditing ? "border-border bg-muted/30" : "border-border/50 bg-muted/10"
                            )}>
                                <div>
                                    <div className="text-sm font-semibold text-foreground">
                                        {g.description}
                                        <span className="ml-2 text-xs font-normal text-muted-foreground">S.No {g.serials.join(", ")}</span>
                                        {g.hsCodes && g.hsCodes.length > 0 && (
                                            <span className="ml-2 text-xs font-normal text-muted-foreground">HSN {g.hsCodes.join(", ")}</span>
                                        )}
                                    </div>
                                    <div className="mt-0.5 flex flex-wrap gap-3 text-xs">
                                        <span className="text-muted-foreground">Available: <b>{g.available_quantity.toFixed(3)}</b></span>
                                        <span className="text-muted-foreground">Planned: <b className={qtyOver ? "text-destructive" : "text-foreground"}>{qtySum.toFixed(3)}</b></span>
                                        <span className={cn("font-semibold", remainingQty < -1e-6 ? "text-destructive" : remainingQty < 1e-6 ? "text-muted-foreground" : "text-emerald-700")}>
                                            Remaining: {remainingQty.toFixed(3)}
                                        </span>
                                    </div>
                                </div>
                                {/* Mode controls */}
                                {!isEditing && (
                                    <Button variant="outline" size="sm" onClick={() => enterEdit(g.id)}
                                        className="h-7 gap-1.5 text-xs">
                                        <Pencil className="size-3.5" />
                                        {hasSavedPlan ? "Edit Planning" : "Add Planning"}
                                    </Button>
                                )}
                            </div>

                            {/* ── VIEW mode ─────────────────────────────────── */}
                            {!isEditing && (
                                <div className="px-4 py-3">
                                    {g.splits.some((s) => num(s.planned_quantity) > 0 || num(s.planned_cif_fc) > 0) ? (
                                        <table className="w-full text-sm">
                                            <thead>
                                                <tr className="text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground border-b border-border/50">
                                                    <th scope="col" className="pb-1.5 pr-3">Item Name</th>
                                                    <th scope="col" className="pb-1.5 pr-3 text-right">Planned Qty</th>
                                                    <th scope="col" className="pb-1.5 pr-3 text-right">Unit Price</th>
                                                    <th scope="col" className="pb-1.5 text-right">CIF ($)</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-border/30">
                                                {g.splits.map((sp) => {
                                                    const itemLabel = sp.item_name
                                                        ? (g.itemNames.find((n) => n.id === Number(sp.item_name))?.name ?? `#${sp.item_name}`)
                                                        : "—";
                                                    return (
                                                        <tr key={sp.key} className="py-1.5">
                                                            <td className="py-1.5 pr-3 text-sm text-foreground">{itemLabel}</td>
                                                            <td className="py-1.5 pr-3 text-right tabular-nums">{num(sp.planned_quantity).toFixed(3)}</td>
                                                            <td className="py-1.5 pr-3 text-right tabular-nums">{num(sp.unit_price) ? num(sp.unit_price).toFixed(2) : "—"}</td>
                                                            <td className="py-1.5 text-right tabular-nums font-medium">{num(sp.planned_cif_fc) ? `$${num(sp.planned_cif_fc).toFixed(2)}` : "—"}</td>
                                                        </tr>
                                                    );
                                                })}
                                            </tbody>
                                            {g.splits.length > 1 && (
                                                <tfoot className="border-t border-border/50 font-semibold">
                                                    <tr>
                                                        <td className="pt-1.5 pr-3 text-[10.5px] uppercase tracking-wider text-muted-foreground text-right">Total</td>
                                                        <td className="pt-1.5 pr-3 text-right tabular-nums">{qtySum.toFixed(3)}</td>
                                                        <td />
                                                        <td className="pt-1.5 text-right tabular-nums">
                                                            ${g.splits.reduce((s, sp) => s + num(sp.planned_cif_fc), 0).toFixed(2)}
                                                        </td>
                                                    </tr>
                                                </tfoot>
                                            )}
                                        </table>
                                    ) : (
                                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                            <BookOpen className="size-4" />
                                            No planning recorded — click "Add Planning" to begin.
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* ── EDIT mode ─────────────────────────────────── */}
                            {isEditing && (
                                <div className="px-4 py-3">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-left text-xs text-muted-foreground">
                                                <th scope="col" className="pb-1 pr-2 font-medium">Item name</th>
                                                <th scope="col" className="pb-1 pr-2 font-medium text-right">Qty</th>
                                                <th scope="col" className="pb-1 pr-2 font-medium text-right">Unit price</th>
                                                <th scope="col" className="pb-1 pr-2 font-medium text-right">CIF ($)</th>
                                                <th scope="col" className="pb-1 w-7" />
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {g.splits.map((sp) => {
                                                const otherQty = g.splits.filter((s) => s.key !== sp.key).reduce((s, s2) => s + num(s2.planned_quantity), 0);
                                                const maxForThisRow = Math.max(0, g.available_quantity - otherQty);
                                                return (
                                                    <tr key={sp.key}>
                                                        <td className="py-1 pr-2">
                                                            <select
                                                                value={sp.item_name}
                                                                onChange={(e) => changeSplit(g.id, sp.key, "item_name", e.target.value)}
                                                                className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
                                                                aria-label="Item name"
                                                            >
                                                                <option value="">—</option>
                                                                {g.itemNames.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
                                                            </select>
                                                        </td>
                                                        <td className="py-1 pr-2">
                                                            <Input
                                                                type="number" min="0" step="0.001" max={maxForThisRow}
                                                                value={sp.planned_quantity}
                                                                onChange={(e) => changeSplit(g.id, sp.key, "planned_quantity", e.target.value)}
                                                                className={cn("h-8 w-24 text-right",
                                                                    num(sp.planned_quantity) > maxForThisRow + 1e-6 && "border-destructive")}
                                                                aria-label="Planned quantity"
                                                                title={`Max for this row: ${maxForThisRow.toFixed(3)}`}
                                                            />
                                                        </td>
                                                        <td className="py-1 pr-2">
                                                            <Input type="number" min="0" step="0.01" value={sp.unit_price}
                                                                onChange={(e) => changeSplit(g.id, sp.key, "unit_price", e.target.value)}
                                                                className="h-8 w-24 text-right" aria-label="Unit price" />
                                                        </td>
                                                        <td className="py-1 pr-2">
                                                            <Input type="number" min="0" step="0.01" value={sp.planned_cif_fc}
                                                                onChange={(e) => changeSplit(g.id, sp.key, "planned_cif_fc", e.target.value)}
                                                                className="h-8 w-28 text-right" aria-label="Planned CIF" />
                                                        </td>
                                                        <td className="py-1 text-center">
                                                            <button type="button"
                                                                onClick={() => removeSplit(g.id, sp.key)}
                                                                disabled={g.splits.length <= 1}
                                                                className="text-muted-foreground hover:text-destructive disabled:opacity-30 cursor-pointer"
                                                                title="Remove split" aria-label="Remove split">
                                                                <Trash2 className="size-4" />
                                                            </button>
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>

                                    {/* Add split */}
                                    <button type="button" onClick={() => addSplit(g.id)}
                                        className="mt-2 flex cursor-pointer items-center gap-1 text-xs font-medium text-primary hover:underline">
                                        <Plus className="size-3.5" />Add split
                                    </button>

                                    {/* Per-group Save / Cancel */}
                                    <div className="mt-3 flex items-center gap-2">
                                        <Button size="sm" onClick={() => handleSave(g)}
                                            disabled={isSaving || qtyOver} className="h-7 gap-1.5 text-xs">
                                            {isSaving ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
                                            Save
                                        </Button>
                                        <Button variant="outline" size="sm" onClick={() => cancelEdit(g.id)}
                                            disabled={isSaving} className="h-7 gap-1.5 text-xs">
                                            <X className="size-3.5" />Cancel
                                        </Button>
                                        {qtyOver && (
                                            <span className="text-xs text-destructive">
                                                Planned ({qtySum.toFixed(3)}) exceeds available ({g.available_quantity.toFixed(3)})
                                            </span>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
                {groups.length === 0 && (
                    <div className="py-6 text-center text-sm text-muted-foreground">
                        No import items found for this license.
                    </div>
                )}
            </div>
        </div>
    );
}
