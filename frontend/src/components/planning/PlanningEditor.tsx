/**
 * PlanningEditor — shared planning core used by both PlanTab and
 * LicensePlanningPanel (modal).
 *
 * Behaviour (Notion / Airtable / GitHub Projects pattern):
 *   • Always in view mode — a clean read-only table.
 *   • Clicking Edit on a row expands an inline editor BELOW that row only.
 *   • All other rows remain read-only.
 *   • Only one row is editable at a time.
 *   • Save / Cancel operate on that single row.
 *   • Summary cards update immediately after each Save.
 *   • onSaved() fires after every successful row-level save so the caller
 *     (report, list, modal) can refresh its own data.
 *
 * No global "Edit Planning" mode. No full-page toggle. No modals inside.
 *
 * Business logic — identical in tab and modal:
 *   fetchLicense / fetchItemPlans / bulkUpsertItemPlans / fetchNormPrefill
 *   3-way auto-calc  ·  remaining cap per split  ·  bulkUpsert on save
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
    AlertTriangle,
    BookOpen,
    Calendar,
    CheckCircle2,
    Circle,
    ClipboardList,
    Loader2,
    MinusCircle,
    Pencil,
    Plus,
    Save,
    Target,
    Trash2,
    User,
    Wand2,
    X,
    XCircle,
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
} from "../../services/api/licenseApi";

// ─────────────────────────────────────────────────────────────────────────────
// Pure helpers
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
    try { return new Date(s).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }); }
    catch { return s; }
};

const emptySplit = (): Split => ({
    key: nextKey(), id: null,
    item_name: "", planned_quantity: "", unit_price: "", planned_cif_fc: "", note: "",
});

const groupKeyOf = (desc: string | undefined | null, names: { id: number; name: string }[]): string | null => {
    const d = (desc || "").trim();
    if (d) return d.toUpperCase();
    const ns = names.map((n) => n.name).sort().join(", ");
    return ns ? "N:" + ns.toUpperCase() : null;
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
    balance_cif_fc: number;
    itemNames: { id: number; name: string }[];
    splits: Split[];
}

type PlanStatus = "not_planned" | "partial" | "completed" | "over";

export interface PlanningEditorProps {
    licenseId: number;
    licenseNumber: string;
    balanceCif?: number;
    canWrite: boolean;
    /** Called after every successful per-row save so the parent can refresh its data. */
    onSaved?: () => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Status helpers
// ─────────────────────────────────────────────────────────────────────────────

function groupStatus(g: Group): PlanStatus {
    const planned = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
    if (planned <= 0) return "not_planned";
    if (planned > g.available_quantity + 1e-6) return "over";
    if (planned >= g.available_quantity - 1e-6) return "completed";
    return "partial";
}

const STATUS_CFG: Record<PlanStatus, { label: string; Icon: React.ElementType; badge: string }> = {
    not_planned: { label: "Not Planned",       Icon: Circle,       badge: "bg-muted text-muted-foreground ring-1 ring-border" },
    partial:     { label: "Partially Planned", Icon: MinusCircle,  badge: "bg-amber-50 text-amber-700 ring-1 ring-amber-200" },
    completed:   { label: "Planned",           Icon: CheckCircle2, badge: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200" },
    over:        { label: "Over Planned",      Icon: XCircle,      badge: "bg-destructive/10 text-destructive ring-1 ring-destructive/30" },
};

function StatusBadge({ status }: { status: PlanStatus }) {
    const { label, Icon, badge } = STATUS_CFG[status];
    return (
        <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-semibold", badge)}>
            <Icon className="size-3" aria-hidden="true" />
            {label}
        </span>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// SummaryCard
// ─────────────────────────────────────────────────────────────────────────────

function SummaryCard({ label, value, variant = "default" }: {
    label: string; value: string;
    variant?: "default" | "primary" | "success" | "danger" | "muted";
}) {
    const cls = { default: "text-foreground", primary: "text-primary", success: "text-emerald-700", danger: "text-destructive", muted: "text-muted-foreground" }[variant];
    const bg  = { default: "bg-card", primary: "bg-primary/5", success: "bg-emerald-50/50", danger: "bg-destructive/5", muted: "bg-muted/40" }[variant];
    return (
        <div className={cn("flex flex-col rounded-xl border border-border/60 px-3.5 py-3", bg)}>
            <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</div>
            <div className={cn("mt-0.5 text-base font-bold tabular-nums leading-tight", cls)}>{value}</div>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// SplitCard — compact editable card for a single planning entry
// ─────────────────────────────────────────────────────────────────────────────

function SplitCard({
    split, index, group, canRemove,
    onChange, onRemove,
}: {
    split: Split; index: number; group: Group; canRemove: boolean;
    onChange: (key: string, field: string, value: string) => void;
    onRemove: (key: string) => void;
}) {
    const otherQty  = group.splits.filter((s) => s.key !== split.key).reduce((s, s2) => s + num(s2.planned_quantity), 0);
    const maxForRow = Math.max(0, group.available_quantity - otherQty);
    const rowOver   = num(split.planned_quantity) > maxForRow + 1e-6;

    return (
        <div className={cn(
            "rounded-xl border bg-card/80 p-4",
            rowOver ? "border-destructive/40 bg-destructive/[0.02]" : "border-border/60",
        )}>
            <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="flex size-5 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">{index + 1}</span>
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Planning Entry {index + 1}</span>
                    {rowOver && (
                        <span className="rounded-full bg-destructive/10 px-1.5 py-0.5 text-[10px] font-semibold text-destructive">Over</span>
                    )}
                </div>
                {canRemove && (
                    <button type="button" onClick={() => onRemove(split.key)}
                        className="flex size-6 cursor-pointer items-center justify-center rounded-md text-muted-foreground/50 hover:bg-destructive/10 hover:text-destructive transition-colors"
                        aria-label="Remove entry">
                        <Trash2 className="size-3.5" />
                    </button>
                )}
            </div>

            <div className="grid gap-2.5 sm:grid-cols-2">
                <div className="sm:col-span-2">
                    <label className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Item Name</label>
                    <select value={split.item_name} onChange={(e) => onChange(split.key, "item_name", e.target.value)}
                        className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        aria-label="Item name">
                        <option value="">— None —</option>
                        {group.itemNames.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
                    </select>
                </div>

                <div>
                    <label className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Qty <span className="font-normal normal-case opacity-60">max {fmtQty(maxForRow)}</span>
                    </label>
                    <Input type="number" min="0" step="0.001" max={maxForRow}
                        value={split.planned_quantity}
                        onChange={(e) => onChange(split.key, "planned_quantity", e.target.value)}
                        className={cn("h-8 text-right tabular-nums", rowOver && "border-destructive")}
                        placeholder="0.000" aria-label="Planned quantity" />
                </div>

                <div>
                    <label className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Unit Price ($)</label>
                    <Input type="number" min="0" step="0.01" value={split.unit_price}
                        onChange={(e) => onChange(split.key, "unit_price", e.target.value)}
                        className="h-8 text-right tabular-nums" placeholder="0.00" aria-label="Unit price" />
                </div>

                <div>
                    <label className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">CIF ($)</label>
                    <Input type="number" min="0" step="0.01" value={split.planned_cif_fc}
                        onChange={(e) => onChange(split.key, "planned_cif_fc", e.target.value)}
                        className="h-8 text-right tabular-nums" placeholder="0.00" aria-label="Planned CIF" />
                </div>

                <div>
                    <label className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Remarks</label>
                    <Input value={split.note} onChange={(e) => onChange(split.key, "note", e.target.value)}
                        className="h-8" placeholder="Optional notes…" aria-label="Remarks" />
                </div>
            </div>

            {/* Computed preview */}
            {num(split.planned_quantity) > 0 && num(split.unit_price) > 0 && (
                <div className="mt-2.5 flex items-center justify-between rounded-lg bg-muted/40 px-2.5 py-1.5 text-[11px]">
                    <span className="text-muted-foreground">{fmtQty(num(split.planned_quantity))} × ${num(split.unit_price).toFixed(2)}</span>
                    <span className="font-semibold tabular-nums text-primary">= {fmtUsd(num(split.planned_quantity) * num(split.unit_price))}</span>
                </div>
            )}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// InlineEditor — the expanded panel that appears below the row being edited
// ─────────────────────────────────────────────────────────────────────────────

function InlineEditor({
    group, poolBalance, allGroups, saving, prefilling,
    onChange, onAddSplit, onRemoveSplit,
    onSave, onCancel, onPrefill,
}: {
    group: Group;
    poolBalance: number;
    allGroups: Group[];
    saving: boolean;
    prefilling: boolean;
    onChange: (key: string, field: string, value: string) => void;
    onAddSplit: () => void;
    onRemoveSplit: (key: string) => void;
    onSave: () => void;
    onCancel: () => void;
    onPrefill: () => void;
}) {
    const planned    = group.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
    const plannedCif = group.splits.reduce((s, sp) => s + num(sp.planned_cif_fc), 0);
    const remaining  = group.available_quantity - planned;
    const qtyOver    = planned > group.available_quantity + 1e-6;

    // Total CIF across ALL groups after this group's draft
    const totalCif     = allGroups.reduce((s, g) => s + g.splits.reduce((ss, sp) => ss + num(sp.planned_cif_fc), 0), 0);
    const cifRemaining = poolBalance - totalCif;
    const cifOver      = cifRemaining < -1e-6;

    const hasErrors = qtyOver;

    return (
        <div className="border-t border-border/50 bg-muted/5 px-4 pb-4 pt-3">
            {/* Per-item mini summary */}
            <div className="mb-3 grid grid-cols-3 gap-2 sm:grid-cols-5">
                <SummaryCard label="Available Qty"  value={fmtQty(group.available_quantity)} />
                <SummaryCard label="Planned Qty"    value={planned > 0 ? fmtQty(planned) : "—"}
                    variant={qtyOver ? "danger" : planned > 0 ? "default" : "muted"} />
                <SummaryCard label="Remaining Qty"  value={fmtQty(remaining)}
                    variant={remaining < -1e-6 ? "danger" : remaining < 1e-6 && planned > 0 ? "success" : "muted"} />
                <SummaryCard label="Balance CIF"    value={fmtUsd(group.balance_cif_fc)} variant="muted" />
                <SummaryCard label="Remaining CIF"  value={fmtUsd(Math.max(0, cifRemaining))}
                    variant={cifOver ? "danger" : "success"} />
            </div>

            {/* Over-planned warning */}
            {qtyOver && (
                <div className="mb-3 flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
                    <div>
                        <div className="text-sm font-semibold text-destructive">Over Planned</div>
                        <div className="mt-1 flex flex-wrap gap-4 text-xs">
                            <span className="text-muted-foreground">Available <b className="text-foreground">{fmtQty(group.available_quantity)}</b></span>
                            <span className="text-muted-foreground">Planned <b className="text-destructive">{fmtQty(planned)}</b></span>
                            <span className="text-muted-foreground">Over by <b className="text-destructive">{fmtQty(planned - group.available_quantity)}</b></span>
                        </div>
                        <p className="mt-1.5 text-[10.5px] text-muted-foreground">Reduce planned quantity to save this item.</p>
                    </div>
                </div>
            )}

            {/* Split cards */}
            <div className="space-y-2.5">
                {group.splits.map((sp, idx) => (
                    <SplitCard
                        key={sp.key}
                        split={sp} index={idx} group={group}
                        canRemove={group.splits.length > 1}
                        onChange={onChange}
                        onRemove={onRemoveSplit}
                    />
                ))}
            </div>

            {/* Add split */}
            <button type="button" onClick={onAddSplit}
                className="mt-2.5 flex w-full cursor-pointer items-center justify-center gap-1.5 rounded-xl border border-dashed border-border py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:border-primary hover:bg-primary/5 hover:text-primary">
                <Plus className="size-3.5" />Add Split
            </button>

            {/* Action bar */}
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                <Button variant="ghost" size="sm" onClick={onPrefill}
                    disabled={saving || prefilling} className="h-7 gap-1.5 text-xs text-muted-foreground">
                    {prefilling ? <Loader2 className="size-3.5 animate-spin" /> : <Wand2 className="size-3.5" />}
                    Prefill from norm
                </Button>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={onCancel}
                        disabled={saving} className="h-7 gap-1.5 text-xs">
                        <X className="size-3.5" />Cancel
                    </Button>
                    <Button size="sm" onClick={onSave}
                        disabled={saving || hasErrors} className="h-7 gap-1.5 text-xs">
                        {saving ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
                        Save Changes
                    </Button>
                </div>
            </div>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// PlanningEditor root
// ─────────────────────────────────────────────────────────────────────────────

export default function PlanningEditor({
    licenseId, licenseNumber, balanceCif = 0, canWrite, onSaved,
}: PlanningEditorProps) {
    const [loading, setLoading]       = useState(false);
    const [prefilling, setPrefilling] = useState(false);

    const [groups, setGroups]             = useState<Group[]>([]);
    const [savedGroups, setSavedGroups]   = useState<Group[]>([]);
    const [poolBalance, setPoolBalance]   = useState(Number(balanceCif) || 0);

    const [editingGroupId, setEditingGroupId]   = useState<number | null>(null);
    const [savingGroupId, setSavingGroupId]     = useState<number | null>(null);

    // ── Load ─────────────────────────────────────────────────────────────────

    const load = useCallback(async () => {
        if (!licenseId) return;
        setLoading(true);
        try {
            const [license, rawPlans] = await Promise.all([
                fetchLicense(licenseId),
                fetchItemPlans(licenseId),
            ]);
            const planList: {
                id: number; import_item: number; item_name?: number | null;
                planned_quantity?: number | null; unit_price?: number | null;
                planned_cif_fc?: number | null; note?: string | null;
                modified_on?: string | null; modified_by_username?: string | null;
            }[] = Array.isArray(rawPlans) ? rawPlans : (rawPlans as { results?: unknown[] })?.results ?? [];

            const splitsByItem: Record<number, Split[]> = {};
            planList.forEach((p) => {
                (splitsByItem[p.import_item] ||= []).push({
                    key: nextKey(), id: p.id,
                    item_name:        p.item_name != null ? String(p.item_name) : "",
                    planned_quantity: p.planned_quantity != null ? String(p.planned_quantity) : "",
                    unit_price:       p.unit_price != null ? String(p.unit_price) : "",
                    planned_cif_fc:   p.planned_cif_fc != null ? String(p.planned_cif_fc) : "",
                    note:             p.note ?? "",
                    modified_on:           p.modified_on,
                    modified_by_username:  p.modified_by_username,
                });
            });

            const importItems: {
                id: number; serial_number: number;
                product_description?: string; description?: string;
                quantity?: number; available_quantity?: number;
                balance_cif_fc?: number | null; hs_code_label?: string;
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
                        total_quantity: 0, available_quantity: 0, balance_cif_fc: 0,
                        itemNames: [],
                        splits: splitsByItem[it.id] ?? [emptySplit()],
                    };
                }
                const g = groupMap[key];
                g.serials.push(it.serial_number);
                if (it.hs_code_label && !g.hsCodes!.includes(it.hs_code_label)) g.hsCodes!.push(it.hs_code_label);
                g.memberIds.push(it.id);
                g.total_quantity      += Number(it.quantity ?? 0);
                g.available_quantity  += Number(it.available_quantity ?? 0);
                g.balance_cif_fc      += Number(it.balance_cif_fc ?? 0);
                itemNames.forEach((n) => { if (!g.itemNames.find((x) => x.id === n.id)) g.itemNames.push(n); });
            }

            const built = Object.values(groupMap);
            setGroups(built);
            setSavedGroups(JSON.parse(JSON.stringify(built)));
            setPoolBalance(Number(license?.balance_cif ?? balanceCif) || 0);
            setEditingGroupId(null);
        } catch { toast.error("Failed to load plan data"); }
        finally { setLoading(false); }
    }, [licenseId, balanceCif]);

    useEffect(() => { load(); }, [load]);

    // ── Edit / Cancel ─────────────────────────────────────────────────────────

    const openEditor = useCallback((gId: number) => {
        setGroups((prev) => prev.map((g) => {
            if (g.id === editingGroupId) {
                const saved = savedGroups.find((s) => s.id === editingGroupId);
                return saved ? { ...g, splits: JSON.parse(JSON.stringify(saved.splits)) } : g;
            }
            return g;
        }));
        setEditingGroupId(gId);
    }, [editingGroupId, savedGroups]);

    const cancelEditor = useCallback(() => {
        if (editingGroupId === null) return;
        const saved = savedGroups.find((s) => s.id === editingGroupId);
        setGroups((prev) => prev.map((g) =>
            g.id === editingGroupId && saved ? { ...g, splits: JSON.parse(JSON.stringify(saved.splits)) } : g,
        ));
        setEditingGroupId(null);
    }, [editingGroupId, savedGroups]);

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
                    const otherQty   = g.splits.filter((s) => s.key !== key).reduce((s, s2) => s + num(s2.planned_quantity), 0);
                    const maxForRow  = Math.max(0, g.available_quantity - otherQty);
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
                : g,
        ));
    }, []);

    // ── Save (per-row) ────────────────────────────────────────────────────────

    const saveGroup = useCallback(async (gId: number) => {
        const g = groups.find((gr) => gr.id === gId);
        if (!g) return;

        const totalQty = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
        if (totalQty > g.available_quantity + 1e-6) {
            toast.error(`Planned qty (${totalQty.toFixed(3)}) exceeds available (${g.available_quantity.toFixed(3)})`);
            return;
        }

        const lines = groups.flatMap((grp) =>
            grp.splits
                .filter((sp) => num(sp.planned_quantity) > 0 || num(sp.planned_cif_fc) > 0)
                .map((sp) => ({
                    import_item:      grp.id,
                    item_name:        sp.item_name ? Number(sp.item_name) : null,
                    planned_quantity: num(sp.planned_quantity),
                    unit_price:       num(sp.unit_price),
                    planned_cif_fc:   num(sp.planned_cif_fc),
                    note:             sp.note || "",
                }))
        );

        setSavingGroupId(gId);
        try {
            await bulkUpsertItemPlans(licenseId, lines);
            toast.success(`Saved — ${g.description}`);
            setSavedGroups((prev) => prev.map((sg) =>
                sg.id === gId ? { ...sg, splits: JSON.parse(JSON.stringify(g.splits)) } : sg,
            ));
            setEditingGroupId(null);
            await load();
            onSaved?.();
        } catch (err: unknown) {
            const data = (err as { response?: { data?: { error?: string; errors?: unknown } } })?.response?.data;
            toast.error(data?.error || (data?.errors ? JSON.stringify(data.errors) : null) || "Failed to save");
        } finally {
            setSavingGroupId(null);
        }
    }, [groups, licenseId, load, onSaved]);

    // ── Prefill (scoped to the open editor) ───────────────────────────────────

    const handlePrefill = useCallback(async () => {
        setPrefilling(true);
        try {
            const { norm, plan } = await fetchNormPrefill(licenseId);
            if (!norm) { toast.error("No E1/E5/E132 norm found for this license"); return; }
            let filled = 0;
            setGroups((prev) => prev.map((g) => {
                if (g.id !== editingGroupId) return g;
                let q = 0, c = 0;
                g.memberIds.forEach((mid) => {
                    const p = (plan as Record<string, { planned_quantity?: number; planned_cif?: number }>)?.[String(mid)];
                    if (p) { q += Number(p.planned_quantity || 0); c += Number(p.planned_cif || 0); }
                });
                if (q > 0 || c > 0) {
                    filled++;
                    return {
                        ...g,
                        splits: [{
                            key: nextKey(), id: null,
                            item_name: "", planned_quantity: q ? fmt3(q) : "",
                            unit_price: q ? String(round2(c / q)) : "",
                            planned_cif_fc: c ? fmt2(c) : "", note: "",
                        }],
                    };
                }
                return g;
            }));
            if (filled > 0) toast.success(`Prefilled from ${norm} — review and Save`);
            else toast.info("No norm data available for this item");
        } catch { toast.error("Failed to compute norm plan"); }
        finally { setPrefilling(false); }
    }, [licenseId, editingGroupId]);

    // ── Derived totals ─────────────────────────────────────────────────────────

    const totals = useMemo(() => {
        let totalAvail = 0, totalPlanned = 0, totalCif = 0, totalEntries = 0;
        let lastUpdated: string | null = null, plannedBy: string | null = null;
        groups.forEach((g) => {
            totalAvail  += g.available_quantity;
            const qs = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
            const cs = g.splits.reduce((s, sp) => s + num(sp.planned_cif_fc), 0);
            totalPlanned += qs; totalCif += cs;
            totalEntries += g.splits.filter((sp) => num(sp.planned_quantity) > 0 || num(sp.planned_cif_fc) > 0).length;
            g.splits.forEach((sp) => {
                if (sp.modified_on && (!lastUpdated || sp.modified_on > lastUpdated)) {
                    lastUpdated = sp.modified_on;
                    plannedBy   = sp.modified_by_username ?? null;
                }
            });
        });
        return {
            totalAvail, totalPlanned,
            remaining: totalAvail - totalPlanned,
            totalCif, cifRemaining: poolBalance - totalCif,
            totalEntries, lastUpdated, plannedBy,
        };
    }, [groups, poolBalance]);

    const anyPlanExists = groups.some((g) => g.splits.some((s) => s.id !== null));

    // ── Render ─────────────────────────────────────────────────────────────────

    if (loading) {
        return (
            <div className="space-y-3 py-4">
                <Skeleton className="h-20 w-full rounded-xl" />
                <Skeleton className="h-48 w-full rounded-xl" />
            </div>
        );
    }

    if (!canWrite) {
        return <div className="py-8 text-center text-sm text-muted-foreground">You don't have permission to plan utilization for this license.</div>;
    }

    return (
        <div className="py-3 space-y-4">
            {/* ── Header ───────────────────────────────────────────── */}
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Target className="size-4 text-primary" aria-hidden="true" />
                    Plan utilization — {licenseNumber}
                </div>
                {(totals.lastUpdated || totals.plannedBy) && (
                    <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
                        {totals.lastUpdated && (
                            <span className="flex items-center gap-1"><Calendar className="size-3.5" />Last saved: {fmtDate(totals.lastUpdated)}</span>
                        )}
                        {totals.plannedBy && (
                            <span className="flex items-center gap-1"><User className="size-3.5" />By: {totals.plannedBy}</span>
                        )}
                    </div>
                )}
            </div>

            {/* ── Summary cards ─────────────────────────────────────── */}
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
                <SummaryCard label="Balance CIF"    value={fmtUsd(poolBalance)} variant="muted" />
                <SummaryCard label="Planned CIF"    value={fmtUsd(totals.totalCif)} variant={totals.totalCif > 0 ? "primary" : "muted"} />
                <SummaryCard label="Remaining CIF"
                    value={fmtUsd(Math.max(0, totals.cifRemaining))}
                    variant={totals.cifRemaining < -1e-6 ? "danger" : totals.totalCif > 0 ? "success" : "muted"} />
                <SummaryCard label="Available Qty"  value={fmtQty(totals.totalAvail)} />
                <SummaryCard label="Planned Qty"    value={fmtQty(totals.totalPlanned)} variant={totals.totalPlanned > 0 ? "default" : "muted"} />
                <SummaryCard label="Remaining Qty"
                    value={fmtQty(totals.remaining)}
                    variant={totals.remaining < -1e-6 ? "danger" : totals.remaining < 1e-6 && totals.totalPlanned > 0 ? "success" : "muted"} />
            </div>

            {/* ── Planned Items table ──────────────────────────────── */}
            <div className="overflow-hidden rounded-xl border border-border/60">
                <div className="flex items-center justify-between border-b border-border/50 bg-muted/30 px-4 py-2.5">
                    <div className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        <ClipboardList className="size-3.5" />Planned Items
                        <span className="ml-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground">
                            {groups.length}
                        </span>
                    </div>
                    {editingGroupId !== null && (
                        <span className="text-[10.5px] font-medium text-amber-700">
                            1 item open for editing
                        </span>
                    )}
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-muted/50">
                            <tr className="border-b border-border/50 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                <th scope="col" className="px-4 py-2.5">Item</th>
                                <th scope="col" className="px-4 py-2.5">Status</th>
                                <th scope="col" className="px-4 py-2.5 text-right">Available Qty</th>
                                <th scope="col" className="px-4 py-2.5 text-right">Planned Qty</th>
                                <th scope="col" className="px-4 py-2.5 text-right">Remaining Qty</th>
                                <th scope="col" className="px-4 py-2.5 text-right">Planned CIF</th>
                                <th scope="col" className="px-4 py-2.5 text-center">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {groups.map((g) => {
                                const status     = groupStatus(g);
                                const planned    = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
                                const plannedCif = g.splits.reduce((s, sp) => s + num(sp.planned_cif_fc), 0);
                                const rem        = g.available_quantity - planned;
                                const isEditing  = editingGroupId === g.id;
                                const isSaving   = savingGroupId === g.id;

                                return (
                                    <>
                                        <tr
                                            key={g.id}
                                            className={cn(
                                                "border-b border-border/40 transition-colors",
                                                isEditing ? "bg-primary/5 border-primary/20" : "hover:bg-muted/20",
                                            )}
                                        >
                                            <td className="px-4 py-3">
                                                <div className="font-medium text-foreground">{g.description}</div>
                                                <div className="mt-0.5 text-[10.5px] text-muted-foreground">
                                                    S.No {g.serials.join(", ")}
                                                    {g.hsCodes?.length ? ` · HSN ${g.hsCodes.join(", ")}` : ""}
                                                </div>
                                            </td>
                                            <td className="px-4 py-3">
                                                <StatusBadge status={status} />
                                            </td>
                                            <td className="px-4 py-3 text-right tabular-nums">{fmtQty(g.available_quantity)}</td>
                                            <td className="px-4 py-3 text-right tabular-nums font-semibold">
                                                {planned > 0 ? fmtQty(planned) : <span className="font-normal text-muted-foreground">—</span>}
                                            </td>
                                            <td className="px-4 py-3 text-right tabular-nums">
                                                <span className={cn("font-semibold",
                                                    rem < -1e-6 ? "text-destructive" :
                                                    rem < 1e-6 && planned > 0 ? "text-emerald-700" : "text-muted-foreground",
                                                )}>{fmtQty(rem)}</span>
                                            </td>
                                            <td className="px-4 py-3 text-right tabular-nums">
                                                {plannedCif > 0
                                                    ? <span className="text-primary">{fmtUsd(plannedCif)}</span>
                                                    : <span className="text-muted-foreground">—</span>}
                                            </td>
                                            <td className="px-4 py-3 text-center">
                                                {isEditing ? (
                                                    <span className="text-[10.5px] font-medium text-primary">Editing ↓</span>
                                                ) : (
                                                    <Button
                                                        variant="ghost" size="sm"
                                                        onClick={() => openEditor(g.id)}
                                                        disabled={savingGroupId !== null}
                                                        className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                                                        aria-label={`Edit planning for ${g.description}`}
                                                    >
                                                        <Pencil className="size-3.5" />Edit
                                                    </Button>
                                                )}
                                            </td>
                                        </tr>

                                        {isEditing && (
                                            <tr key={`${g.id}-editor`} className="border-b border-primary/20 bg-primary/[0.02]">
                                                <td colSpan={7} className="p-0">
                                                    <InlineEditor
                                                        group={g}
                                                        poolBalance={poolBalance}
                                                        allGroups={groups}
                                                        saving={isSaving}
                                                        prefilling={prefilling}
                                                        onChange={(key, field, value) => changeSplit(g.id, key, field, value)}
                                                        onAddSplit={() => addSplit(g.id)}
                                                        onRemoveSplit={(key) => removeSplit(g.id, key)}
                                                        onSave={() => saveGroup(g.id)}
                                                        onCancel={cancelEditor}
                                                        onPrefill={handlePrefill}
                                                    />
                                                </td>
                                            </tr>
                                        )}
                                    </>
                                );
                            })}

                            {/* Totals row */}
                            {anyPlanExists && (
                                <tr className="border-t-2 border-border bg-muted/40 font-semibold text-sm">
                                    <td className="px-4 py-2 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Totals</td>
                                    <td />
                                    <td className="px-4 py-2 text-right tabular-nums">{fmtQty(totals.totalAvail)}</td>
                                    <td className="px-4 py-2 text-right tabular-nums">{fmtQty(totals.totalPlanned)}</td>
                                    <td className="px-4 py-2 text-right tabular-nums">
                                        <span className={cn(totals.remaining < -1e-6 ? "text-destructive" : "text-emerald-700")}>{fmtQty(totals.remaining)}</span>
                                    </td>
                                    <td className="px-4 py-2 text-right tabular-nums text-primary">{fmtUsd(totals.totalCif)}</td>
                                    <td />
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Empty state */}
                {groups.length === 0 && (
                    <div className="flex flex-col items-center py-12 text-center">
                        <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-muted">
                            <BookOpen className="size-6 text-muted-foreground/50" />
                        </div>
                        <div className="text-sm font-medium text-muted-foreground">No import items found</div>
                        <div className="mt-1 text-xs text-muted-foreground/70">This license has no import items to plan.</div>
                    </div>
                )}
            </div>
        </div>
    );
}
