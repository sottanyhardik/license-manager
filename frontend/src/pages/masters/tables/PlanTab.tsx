/**
 * PlanTab — embedded version of LicensePlanningPanel without the Dialog wrapper.
 *
 * Reuses the same APIs, state, business logic, and validations as the modal:
 *   - fetchLicense(licenseId)          → license detail
 *   - fetchItemPlans(licenseId)        → existing plan lines
 *   - bulkUpsertItemPlans(id, lines)   → save plan
 *   - fetchNormPrefill(licenseId)      → auto-fill from norm
 *
 * Groups import items by description (same groupKeyOf logic as the modal).
 * 3-way auto-calc: qty×price=cif, cif÷price=qty, cif÷qty=price.
 *
 * The only UX change vs the modal: this renders inline in a tab,
 * so there is no Cancel/Close button.
 */

import { useEffect, useMemo, useState, useCallback } from "react";
import { Loader2, Plus, Save, Target, Trash2, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
    fetchLicense,
    fetchItemPlans,
    bulkUpsertItemPlans,
    fetchNormPrefill,
} from "../../../services/api/licenseApi";

// ─────────────────────────────────────────────────────────────────────────────
// Same helpers as LicensePlanningPanel (copied verbatim to avoid coupling)
// ─────────────────────────────────────────────────────────────────────────────

let _sk = 0;
const nextKey = () => `s${++_sk}`;
const num = (v: string | number | undefined) => parseFloat(String(v ?? 0)) || 0;
const round2 = (x: number) => Math.round((x + Number.EPSILON) * 100) / 100;
const fmt2 = (x: number) => (x ? String(round2(x)) : "");
const fmt3 = (x: number) =>
    x ? String(Math.round((x + Number.EPSILON) * 1000) / 1000) : "";

const emptySplit = () => ({
    key: nextKey(),
    item_name: "",
    planned_quantity: "",
    unit_price: "",
    planned_cif_fc: "",
});

const groupKeyOf = (
    desc: string | undefined | null,
    itemNames: { id: number; name: string }[]
): string | null => {
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
    item_name: string;
    planned_quantity: string;
    unit_price: string;
    planned_cif_fc: string;
}

interface Group {
    id: number;
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
// PlanTab component
// ─────────────────────────────────────────────────────────────────────────────

export default function PlanTab({
    licenseId,
    licenseNumber,
    balanceCif = 0,
    canWrite,
}: PlanTabProps) {
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [prefilling, setPrefilling] = useState(false);
    const [groups, setGroups] = useState<Group[]>([]);
    const [poolBalance, setPoolBalance] = useState(Number(balanceCif) || 0);

    // Load on mount
    useEffect(() => {
        if (!licenseId) return;
        let cancelled = false;
        (async () => {
            setLoading(true);
            try {
                const [license, plans] = await Promise.all([
                    fetchLicense(licenseId),
                    fetchItemPlans(licenseId),
                ]);
                if (cancelled) return;

                const planList = Array.isArray(plans)
                    ? plans
                    : (plans as { results?: unknown[] })?.results ?? [];

                const splitsByItem: Record<string, Split[]> = {};
                (planList as {
                    import_item: number;
                    item_name?: number | null;
                    planned_quantity?: number | null;
                    unit_price?: number | null;
                    planned_cif_fc?: number | null;
                }[]).forEach((p) => {
                    (splitsByItem[p.import_item] ||= []).push({
                        key: nextKey(),
                        item_name: p.item_name != null ? String(p.item_name) : "",
                        planned_quantity:
                            p.planned_quantity != null ? String(p.planned_quantity) : "",
                        unit_price: p.unit_price != null ? String(p.unit_price) : "",
                        planned_cif_fc:
                            p.planned_cif_fc != null ? String(p.planned_cif_fc) : "",
                    });
                });

                // Build groups (same logic as LicensePlanningPanel)
                const importItems: {
                    id: number;
                    serial_number: number;
                    product_description?: string;
                    description?: string;
                    quantity?: number;
                    available_quantity?: number;
                    hs_code_label?: string;
                    items_detail?: { id: number; name: string }[];
                }[] = Array.isArray(license?.import_license)
                    ? license.import_license
                    : [];

                const groupMap: Record<string, Group> = {};

                for (const it of importItems) {
                    const itemNames: { id: number; name: string }[] = (
                        it.items_detail ?? []
                    ).map((i) => ({ id: i.id, name: i.name }));
                    const key =
                        groupKeyOf(
                            it.product_description || it.description,
                            itemNames
                        ) || `ID:${it.id}`;

                    if (!groupMap[key]) {
                        groupMap[key] = {
                            id: it.id,
                            description:
                                it.product_description || it.description || key,
                            serials: [],
                            hsCodes: [],
                            memberIds: [],
                            total_quantity: 0,
                            available_quantity: 0,
                            itemNames: [],
                            splits: splitsByItem[it.id] ?? [emptySplit()],
                        };
                    }
                    const g = groupMap[key];
                    g.serials.push(it.serial_number);
                    if (
                        it.hs_code_label &&
                        !g.hsCodes!.includes(it.hs_code_label)
                    )
                        g.hsCodes!.push(it.hs_code_label);
                    g.memberIds.push(it.id);
                    g.total_quantity += Number(it.quantity ?? 0);
                    g.available_quantity += Number(it.available_quantity ?? 0);
                    itemNames.forEach((n) => {
                        if (!g.itemNames.find((x) => x.id === n.id))
                            g.itemNames.push(n);
                    });
                }

                setGroups(Object.values(groupMap));
                setPoolBalance(Number(license?.balance_cif ?? balanceCif) || 0);
            } catch (e) {
                console.error(e);
                toast.error("Failed to load plan data");
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [licenseId]);

    // 3-way auto-calc (same as LicensePlanningPanel)
    const changeSplit = useCallback(
        (repId: number, key: string, field: string, value: string) => {
            setGroups((prev) =>
                prev.map((g) => {
                    if (g.id !== repId) return g;
                    return {
                        ...g,
                        splits: g.splits.map((sp) => {
                            if (sp.key !== key) return sp;
                            const updated = { ...sp, [field]: value };
                            const q = num(updated.planned_quantity);
                            const p = num(updated.unit_price);
                            const c = num(updated.planned_cif_fc);
                            if (field === "planned_quantity" || field === "unit_price") {
                                if (q > 0 && p > 0) updated.planned_cif_fc = fmt2(q * p);
                            } else if (field === "planned_cif_fc") {
                                if (p > 0 && c > 0)
                                    updated.planned_quantity = fmt3(
                                        Math.min(c / p, g.available_quantity)
                                    );
                                else if (q > 0 && c > 0)
                                    updated.unit_price = fmt2(c / q);
                            }
                            return updated;
                        }),
                    };
                })
            );
        },
        []
    );

    const addSplit = useCallback((repId: number) => {
        setGroups((prev) =>
            prev.map((g) =>
                g.id === repId
                    ? { ...g, splits: [...g.splits, emptySplit()] }
                    : g
            )
        );
    }, []);

    const removeSplit = useCallback((repId: number, key: string) => {
        setGroups((prev) =>
            prev.map((g) =>
                g.id === repId && g.splits.length > 1
                    ? {
                          ...g,
                          splits: g.splits.filter((s) => s.key !== key),
                      }
                    : g
            )
        );
    }, []);

    const plannedCifTotal = useMemo(
        () => groups.reduce((s, g) => s + g.splits.reduce((ss, sp) => ss + num(sp.planned_cif_fc), 0), 0),
        [groups]
    );
    const cifRemaining = Number(poolBalance) - plannedCifTotal;
    const cifOver = cifRemaining < 0;
    const groupQtySum = (g: Group) =>
        g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);

    const handlePrefill = async () => {
        setPrefilling(true);
        try {
            const { norm, plan } = await fetchNormPrefill(licenseId);
            if (!norm) {
                toast.error("This license has no E1/E5/E132 norm to plan from");
                return;
            }
            let filled = 0;
            setGroups((prev) =>
                prev.map((g) => {
                    let q = 0,
                        c = 0;
                    g.memberIds.forEach((mid) => {
                        const p = (plan as Record<string, { planned_quantity?: number; planned_cif?: number }>)?.[String(mid)];
                        if (p) {
                            q += Number(p.planned_quantity || 0);
                            c += Number(p.planned_cif || 0);
                        }
                    });
                    if (q > 0 || c > 0) {
                        filled += 1;
                        return {
                            ...g,
                            splits: [
                                {
                                    key: nextKey(),
                                    item_name: "",
                                    planned_quantity: q ? fmt3(q) : "",
                                    unit_price: q ? String(round2(c / q)) : "",
                                    planned_cif_fc: c ? fmt2(c) : "",
                                },
                            ],
                        };
                    }
                    return g;
                })
            );
            toast.success(
                `Prefilled ${filled} product(s) from ${norm} plan — review and Save`
            );
        } catch {
            toast.error("Failed to compute norm plan");
        } finally {
            setPrefilling(false);
        }
    };

    const handleSave = async () => {
        const lines: {
            import_item: number;
            item_name: number | null;
            planned_quantity: number;
            unit_price: number;
            planned_cif_fc: number;
        }[] = [];
        for (const g of groups) {
            for (const sp of g.splits) {
                if (num(sp.planned_quantity) > 0 || num(sp.planned_cif_fc) > 0) {
                    lines.push({
                        import_item: g.id,
                        item_name: sp.item_name ? Number(sp.item_name) : null,
                        planned_quantity: num(sp.planned_quantity),
                        unit_price: num(sp.unit_price),
                        planned_cif_fc: num(sp.planned_cif_fc),
                    });
                }
            }
        }
        if (cifOver) {
            toast.error("Planned CIF total exceeds the license balance");
            return;
        }
        const bad = groups.find(
            (g) => groupQtySum(g) > g.available_quantity + 1e-6
        );
        if (bad) {
            toast.error(`${bad.description}: planned qty exceeds available`);
            return;
        }
        setSaving(true);
        try {
            await bulkUpsertItemPlans(licenseId, lines);
            toast.success("Plan saved");
        } catch (err: unknown) {
            const data = (err as { response?: { data?: { error?: string; errors?: unknown } } })?.response?.data;
            const msg =
                data?.error ||
                (data?.errors ? JSON.stringify(data.errors) : null) ||
                "Failed to save plan";
            toast.error(msg);
        } finally {
            setSaving(false);
        }
    };

    // ── Render ──────────────────────────────────────────────────────────────

    if (loading) {
        return (
            <div className="space-y-3 py-4">
                <Skeleton className="h-12 w-full rounded-lg" />
                <Skeleton className="h-32 w-full rounded-lg" />
                <Skeleton className="h-32 w-full rounded-lg" />
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
            {/* Header bar */}
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Target className="size-4 text-primary" aria-hidden="true" />
                    Plan utilization — {licenseNumber}
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePrefill}
                    disabled={loading || prefilling}
                    className="h-7 gap-1.5 text-xs"
                >
                    {prefilling ? (
                        <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                        <Wand2 className="size-3.5" />
                    )}
                    Prefill from norm
                </Button>
            </div>

            {/* Balance bar */}
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
                <span>
                    Balance CIF:{" "}
                    <b className="tabular-nums">{Number(poolBalance).toFixed(2)}</b>
                </span>
                <span>
                    Planned:{" "}
                    <b className="tabular-nums">{plannedCifTotal.toFixed(2)}</b>
                </span>
                <span
                    className={cn(
                        "font-semibold tabular-nums",
                        cifOver ? "text-destructive" : "text-emerald-700"
                    )}
                >
                    {cifOver ? "Over by " : "Remaining "}
                    {Math.abs(cifRemaining).toFixed(2)}
                </span>
            </div>

            {/* Groups */}
            <div className="space-y-3">
                {groups.map((g) => {
                    const qtySum = groupQtySum(g);
                    const qtyOver = qtySum > g.available_quantity + 1e-6;
                    return (
                        <div
                            key={g.id}
                            className="rounded-xl border border-border bg-card p-3"
                        >
                            <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
                                <div className="text-sm font-medium text-foreground">
                                    {g.description}
                                    <span className="ml-2 text-xs text-muted-foreground">
                                        S.No {g.serials.join(", ")}
                                    </span>
                                    {g.hsCodes && g.hsCodes.length > 0 && (
                                        <span className="ml-2 text-xs text-muted-foreground">
                                            HSN {g.hsCodes.join(", ")}
                                        </span>
                                    )}
                                </div>
                                <div className="text-xs text-muted-foreground">
                                    Total{" "}
                                    <b>{g.total_quantity.toFixed(3)}</b> · Avail{" "}
                                    <b>{g.available_quantity.toFixed(3)}</b> ·{" "}
                                    <span
                                        className={cn(
                                            "font-semibold",
                                            qtyOver ? "text-destructive" : "text-foreground"
                                        )}
                                    >
                                        Planned {qtySum.toFixed(3)}
                                    </span>
                                </div>
                            </div>

                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="text-left text-xs text-muted-foreground">
                                        <th scope="col" className="pb-1 pr-2 font-medium">Item name</th>
                                        <th scope="col" className="pb-1 pr-2 font-medium text-right">Qty</th>
                                        <th scope="col" className="pb-1 pr-2 font-medium text-right">Unit price</th>
                                        <th scope="col" className="pb-1 pr-2 font-medium text-right">CIF ($)</th>
                                        <th scope="col" className="pb-1 w-8" />
                                    </tr>
                                </thead>
                                <tbody>
                                    {g.splits.map((sp) => (
                                        <tr key={sp.key}>
                                            <td className="py-1 pr-2">
                                                <select
                                                    value={sp.item_name}
                                                    onChange={(e) =>
                                                        changeSplit(
                                                            g.id,
                                                            sp.key,
                                                            "item_name",
                                                            e.target.value
                                                        )
                                                    }
                                                    className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
                                                    aria-label="Item name"
                                                >
                                                    <option value="">—</option>
                                                    {g.itemNames.map((n) => (
                                                        <option key={n.id} value={n.id}>
                                                            {n.name}
                                                        </option>
                                                    ))}
                                                </select>
                                            </td>
                                            <td className="py-1 pr-2">
                                                <Input
                                                    type="number"
                                                    min="0"
                                                    step="0.001"
                                                    value={sp.planned_quantity}
                                                    onChange={(e) =>
                                                        changeSplit(
                                                            g.id,
                                                            sp.key,
                                                            "planned_quantity",
                                                            e.target.value
                                                        )
                                                    }
                                                    className="h-8 w-24 text-right"
                                                    aria-label="Planned quantity"
                                                />
                                            </td>
                                            <td className="py-1 pr-2">
                                                <Input
                                                    type="number"
                                                    min="0"
                                                    step="0.01"
                                                    value={sp.unit_price}
                                                    onChange={(e) =>
                                                        changeSplit(
                                                            g.id,
                                                            sp.key,
                                                            "unit_price",
                                                            e.target.value
                                                        )
                                                    }
                                                    className="h-8 w-24 text-right"
                                                    aria-label="Unit price"
                                                />
                                            </td>
                                            <td className="py-1 pr-2">
                                                <Input
                                                    type="number"
                                                    min="0"
                                                    step="0.01"
                                                    value={sp.planned_cif_fc}
                                                    onChange={(e) =>
                                                        changeSplit(
                                                            g.id,
                                                            sp.key,
                                                            "planned_cif_fc",
                                                            e.target.value
                                                        )
                                                    }
                                                    className="h-8 w-28 text-right"
                                                    aria-label="Planned CIF"
                                                />
                                            </td>
                                            <td className="py-1 text-center">
                                                <button
                                                    type="button"
                                                    onClick={() => removeSplit(g.id, sp.key)}
                                                    disabled={g.splits.length <= 1}
                                                    className="text-muted-foreground hover:text-destructive disabled:opacity-30 cursor-pointer"
                                                    title="Remove split"
                                                    aria-label="Remove split"
                                                >
                                                    <Trash2 className="size-4" aria-hidden="true" />
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>

                            <button
                                type="button"
                                onClick={() => addSplit(g.id)}
                                className="mt-2 flex cursor-pointer items-center gap-1 text-xs font-medium text-primary hover:underline"
                            >
                                <Plus className="size-3.5" aria-hidden="true" />
                                Add split
                            </button>
                        </div>
                    );
                })}
                {groups.length === 0 && (
                    <div className="py-6 text-center text-sm text-muted-foreground">
                        No import items found for this license.
                    </div>
                )}
            </div>

            {/* Save */}
            {groups.length > 0 && (
                <div className="mt-4 flex justify-end gap-2">
                    <Button
                        onClick={handleSave}
                        disabled={saving || loading || cifOver}
                        size="sm"
                        className="gap-1.5"
                    >
                        {saving ? (
                            <Loader2 className="size-4 animate-spin" />
                        ) : (
                            <Save className="size-4" />
                        )}
                        Save plan
                    </Button>
                </div>
            )}
        </div>
    );
}
