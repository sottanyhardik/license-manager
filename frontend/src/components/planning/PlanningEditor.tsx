/**
 * PlanningEditor — shared planning core used by both License Overview
 * and LicensePlanningPanel (modal).
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
 *   fetchLicense / fetchItemPlans / bulkUpsertItemPlans
 *   3-way auto-calc  ·  remaining cap per split  ·  bulkUpsert on save
 */

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import {
    AlertTriangle,
    BookOpen,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Circle,
    ClipboardList,
    Loader2,
    MinusCircle,
    Pencil,
    Plus,
    Save,
    Target,
    Trash2,
    X,
    XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
    bulkUpsertItemPlans,
    deleteItemPlan,
    fetchItemPlans,
    fetchLicense,
} from "@/services/api/licenseApi";
import { autoPlanLicense, planLicense } from "@/services/api/planningRuleApi";

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

const emptySplit = (): Split => ({
    key: nextKey(), id: null,
    item_name: "", planned_quantity: "", unit_price: "", planned_cif_fc: "", note: "",
});

const cloneSplits = (splits: Split[]): Split[] => splits.map((split) => ({ ...split }));
const cloneGroups = (groups: Group[]): Group[] => groups.map((group) => ({
    ...group,
    serials: [...group.serials],
    memberIds: [...group.memberIds],
    itemNames: group.itemNames.map((item) => ({ ...item })),
    splits: cloneSplits(group.splits),
}));

function apiErrorMessage(error: unknown, fallback: string): string {
    if (!error || typeof error !== "object" || !("response" in error)) return fallback;
    const response = (error as { response?: { data?: unknown } }).response;
    const data = response?.data;
    if (!data || typeof data !== "object") return fallback;
    for (const key of ["message", "error", "detail"] as const) {
        const value = (data as Record<string, unknown>)[key];
        if (typeof value === "string" && value.trim()) return value;
    }
    return fallback;
}

// A split "counts" for display once it carries a real quantity or CIF — mirrors
// the same filter the Download License Excel exporter uses (see
// license_balance_excel.py's split sub-row block) so both surfaces agree on
// what a "planning allocation" is.
const validSplitsOf = (g: Group): Split[] =>
    g.splits.filter((sp) => num(sp.planned_quantity) > 0 || num(sp.planned_cif_fc) > 0);

// Prefer the plan API's authoritative item-name label. The parent group's
// selectable names are only a compatibility fallback for older responses.
const splitLabel = (sp: Split, group: Group, index: number): string => {
    if (sp.planning_item_name) return sp.planning_item_name;
    const name = group.itemNames.find((n) => String(n.id) === sp.item_name)?.name;
    return name || `Planning item ${index + 1}`;
};

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface Split {
    key: string;
    id: number | null;
    item_name: string;
    planning_item_name?: string | null;
    planned_quantity: string;
    unit_price: string;
    planned_cif_fc: string;
    note: string;
    modified_on?: string | null;
    modified_by_username?: string | null;
    boe_used_quantity?: string;
    boe_used_cif?: string;
    unlinked_allotment_quantity?: string;
    unlinked_allotment_cif?: string;
    effective_used_quantity?: string;
    effective_used_cif?: string;
    remaining_quantity?: string;
    remaining_cif?: string;
    excess_quantity?: string;
    excess_cif?: string;
    reconciliation_status?: "NOT_USED" | "PARTIALLY_UTILIZED" | "FULLY_UTILIZED" | "MANUAL_PLANNING_REQUIRED";
    needs_rebuild?: boolean;
}

interface Group {
    id: number;
    description: string;
    serials: number[];
    hsCode?: string;
    memberIds: number[];
    total_quantity: number;
    available_quantity: number;
    effective_available_quantity: number;
    license_balance_cif: number;
    effective_license_balance_cif: number;
    balance_cif_fc: number;
    itemNames: { id: number; name: string }[];
    splits: Split[];
    // Utilization-plan status (Original/Used/Remaining), identical across
    // every member of the group — see plan_status_for on the backend. Used
    // only counts allotments made since this plan was last (re)saved, so
    // Remaining correctly resets to Original right after a re-plan instead
    // of going permanently negative from allotments made under an older,
    // since-replaced plan.
    has_plan?: boolean;
    original_planned_quantity?: number;
    used_planned_quantity?: number;
    remaining_planned_quantity?: number;
    original_planned_cif_fc?: number;
    used_planned_cif_fc?: number;
    remaining_planned_cif_fc?: number;
    has_reconciliation?: boolean;
    reconciliation_manual_required?: boolean;
    operational_status?: "PLANNED" | "MANUAL_PLANNING_REQUIRED" | "FEASIBLE" | "SHORT" | "UNPLANNED" | "BLOCKED_UNIT_MISMATCH";
    planning_status?: "FEASIBLE" | "SHORT" | "UNPLANNED" | "BLOCKED_UNIT_MISMATCH";
    shortage_qty?: number;
    feasible?: boolean;
}

type PlanStatus = "not_planned" | "partial" | "completed" | "over" | "blocked";

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
    if (g.effective_available_quantity < 0 || g.effective_license_balance_cif < 0) return "over";

    // Reconciled child rows are authoritative for the operational plan.  The
    // backend group status predates BOE/allotment reconciliation and compares
    // theoretical planning with availability, which can incorrectly report
    // "Over Planned" after legitimate utilization.
    if (g.has_reconciliation) {
        if (g.reconciliation_manual_required) return "over";
        if (g.operational_status === "MANUAL_PLANNING_REQUIRED") return "over";
        if (g.operational_status === "PLANNED") return "completed";
        // Operational completion uses backend-normalized live balances. Small
        // non-negative residuals are zeroed centrally by the backend; negative
        // balances remain visible as genuine excess/manual-review conditions.
        const theoreticalQty = g.original_planned_quantity ?? 0;
        const theoreticalCif = g.original_planned_cif_fc ?? 0;
        if (theoreticalQty <= 1e-6 && theoreticalCif <= 1e-6) return "not_planned";
        if (g.effective_license_balance_cif === 0) return "completed";
        if (g.effective_available_quantity === 0) return "completed";
        const remainingQty = g.remaining_planned_quantity ?? 0;
        const remainingCif = g.remaining_planned_cif_fc ?? 0;
        if (remainingQty <= 1e-6 && remainingCif <= 1e-6) return "completed";
        return "partial";
    }

    if (g.operational_status === "MANUAL_PLANNING_REQUIRED") return "over";
    if (g.operational_status === "PLANNED") return "completed";

    if (g.has_plan && (
        g.effective_license_balance_cif === 0 || g.effective_available_quantity === 0
    )) {
        return "completed";
    }

    // Persisted feasibility is canonical backend data. Local arithmetic below
    // is retained only as a fallback for a new, unsaved draft.
    if (g.planning_status === "BLOCKED_UNIT_MISMATCH") return "blocked";
    if (g.planning_status === "SHORT") return "over";
    if (g.planning_status === "FEASIBLE") {
        return (g.remaining_planned_quantity ?? 0) <= 1e-6 ? "completed" : "partial";
    }
    if (g.planning_status === "UNPLANNED") return "not_planned";

    const planned = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
    if (planned <= 0) return "not_planned";

    // Prefer the live Remaining Plan (Original minus usage since THIS plan
    // was last saved — see plan_status_for on the backend) over a static
    // "planned vs. currently-available" comparison. The old comparison trips
    // "Over Planned" every time a plan gets mostly/fully allotted — Available
    // Qty already nets out ALL-time consumption (including allotments made
    // under an earlier, since-replaced plan), so `planned > available` goes
    // "over" even when nothing is actually wrong. Remaining resets to
    // Original right after a re-plan and only goes negative when allotments
    // made AFTER that re-plan actually exceed it — a real problem worth
    // flagging.
    if (g.has_plan && g.remaining_planned_quantity != null) {
        const remaining = g.remaining_planned_quantity;
        if (remaining < -1e-6) return "over";
        if (remaining <= 1e-6) return "completed";
        return "partial";
    }

    if (planned > g.available_quantity + 1e-6) return "over";
    if (planned >= g.available_quantity - 1e-6) return "completed";
    return "partial";
}

const STATUS_CFG: Record<PlanStatus, { label: string; Icon: React.ElementType; badge: string }> = {
    not_planned: { label: "Not Planned",       Icon: Circle,       badge: "bg-muted text-muted-foreground ring-1 ring-border" },
    partial:     { label: "Partially Planned", Icon: MinusCircle,  badge: "bg-amber-50 text-amber-700 ring-1 ring-amber-200" },
    completed:   { label: "Planned",           Icon: CheckCircle2, badge: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200" },
    over:        { label: "Over Planned",      Icon: XCircle,      badge: "bg-destructive/10 text-destructive ring-1 ring-destructive/30" },
    blocked:     { label: "Blocked: Unit Mismatch", Icon: XCircle, badge: "bg-destructive/10 text-destructive ring-1 ring-destructive/30" },
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
    group, poolBalance, allGroups, saving,
    onChange, onAddSplit, onRemoveSplit,
    onSave, onCancel,
}: {
    group: Group;
    poolBalance: number;
    allGroups: Group[];
    saving: boolean;
    onChange: (key: string, field: string, value: string) => void;
    onAddSplit: () => void;
    onRemoveSplit: (key: string) => void;
    onSave: () => void;
    onCancel: () => void;
}) {
    const planned    = group.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
    const remaining  = group.available_quantity - planned;
    const qtyOver    = planned > group.available_quantity + 1e-6;

    // Total CIF across ALL groups after this group's draft
    const totalCif     = allGroups.reduce((s, g) => s + g.splits.reduce((ss, sp) => ss + num(sp.planned_cif_fc), 0), 0);
    const cifRemaining = poolBalance - totalCif;
    const cifOver      = cifRemaining < -1e-6;

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
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={onCancel}
                        disabled={saving} className="h-7 gap-1.5 text-xs">
                        <X className="size-3.5" />Cancel
                    </Button>
                    <Button size="sm" onClick={onSave}
                        disabled={saving || qtyOver} className="h-7 gap-1.5 text-xs">
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
    const [loading, setLoading]           = useState(false);
    const [isPlanning, setIsPlanning]     = useState(false);
    const [showForceConfirm, setShowForceConfirm] = useState(false);

    const [groups, setGroups]             = useState<Group[]>([]);
    const [savedGroups, setSavedGroups]   = useState<Group[]>([]);
    const [poolBalance, setPoolBalance]   = useState(Number(balanceCif) || 0);
    const [licenseTotalCif, setLicenseTotalCif] = useState(Number(balanceCif) || 0);

    const [editingGroupId, setEditingGroupId]   = useState<number | null>(null);
    const [savingGroupId, setSavingGroupId]     = useState<number | null>(null);
    const [deletingGroupId, setDeletingGroupId] = useState<number | null>(null);

    // Per-group split-breakdown disclosure. Defaults to expanded (every
    // planning allocation's item name/price/qty/CIF should be visible without
    // an extra click) — collapsing is an opt-in density choice, never a way
    // to hide required info.
    const [expandedIds, setExpandedIds]         = useState<Record<number, boolean>>({});
    const toggleExpand = useCallback((gId: number) => {
        setExpandedIds((prev) => ({ ...prev, [gId]: !(prev[gId] ?? true) }));
    }, []);

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
                planning_item_name?: string | null; item_name_label?: string | null;
                planned_quantity?: number | null; unit_price?: number | null;
                planned_cif_fc?: number | null; note?: string | null;
                modified_on?: string | null; modified_by_username?: string | null;
                boe_used_quantity?: string; boe_used_cif?: string;
                unlinked_allotment_quantity?: string; unlinked_allotment_cif?: string;
                effective_used_quantity?: string; effective_used_cif?: string;
                remaining_quantity?: string; remaining_cif?: string;
                excess_quantity?: string; excess_cif?: string;
                reconciliation_status?: Split["reconciliation_status"];
                needs_rebuild?: boolean;
            }[] = Array.isArray(rawPlans) ? rawPlans : (rawPlans as { results?: unknown[] })?.results ?? [];

            const splitsByItem: Record<number, Split[]> = {};
            planList.forEach((p) => {
                (splitsByItem[p.import_item] ||= []).push({
                    key: nextKey(), id: p.id,
                    item_name:        p.item_name != null ? String(p.item_name) : "",
                    planning_item_name: p.planning_item_name ?? p.item_name_label ?? null,
                    planned_quantity: p.planned_quantity != null ? String(p.planned_quantity) : "",
                    unit_price:       p.unit_price != null ? String(p.unit_price) : "",
                    planned_cif_fc:   p.planned_cif_fc != null ? String(p.planned_cif_fc) : "",
                    note:             p.note ?? "",
                    modified_on:           p.modified_on,
                    modified_by_username:  p.modified_by_username,
                    boe_used_quantity: p.boe_used_quantity,
                    boe_used_cif: p.boe_used_cif,
                    unlinked_allotment_quantity: p.unlinked_allotment_quantity,
                    unlinked_allotment_cif: p.unlinked_allotment_cif,
                    effective_used_quantity: p.effective_used_quantity,
                    effective_used_cif: p.effective_used_cif,
                    remaining_quantity: p.remaining_quantity,
                    remaining_cif: p.remaining_cif,
                    excess_quantity: p.excess_quantity,
                    excess_cif: p.excess_cif,
                    reconciliation_status: p.reconciliation_status,
                    needs_rebuild: p.needs_rebuild,
                });
            });

            // The backend's shared Plan Utilization service already merges
            // import items that share a planning group (same grouping
            // `plan_enforcement` uses for real allotment-cap math) into one
            // row per group — this component no longer re-derives groups
            // from the raw `import_license` list itself, so there is exactly
            // one place (the backend) that decides what counts as "the same
            // planning item". See `plan_utilization_rows` on the backend.
            const groupRows: {
                group_id: number; description?: string | null; hs_code?: string | null;
                serials?: number[]; member_ids?: number[];
                item_names?: { id: number; name: string }[];
                available_quantity?: string | number; total_quantity?: string | number;
                effective_available_quantity?: string | number;
                license_balance_cif?: string | number;
                effective_license_balance_cif?: string | number;
                balance_cif_fc?: string | number;
                has_plan?: boolean;
                original_quantity?: string | number; used_quantity?: string | number; remaining_quantity?: string | number;
                original_cif_fc?: string | number; used_cif_fc?: string | number; remaining_cif_fc?: string | number;
                shortage_qty?: string | number; feasible?: boolean;
                status?: "FEASIBLE" | "SHORT" | "UNPLANNED" | "BLOCKED_UNIT_MISMATCH";
                operational_status?: Group["operational_status"];
            }[] = Array.isArray(license?.plan_utilization) ? license.plan_utilization : [];

            const built: Group[] = groupRows.map((grp) => {
                const memberIds = grp.member_ids ?? [];
                // Union every merged member's plan lines — defensive, same as
                // the backend's own union across group_ids_of — rather than
                // assuming plans only ever live on the representative member.
                const splits = memberIds.flatMap((mid) => splitsByItem[mid] ?? []);
                const group: Group = {
                    id: grp.group_id,
                    description: grp.description || `ID:${grp.group_id}`,
                    serials: grp.serials ?? [],
                    hsCode: grp.hs_code || undefined,
                    memberIds,
                    total_quantity: Number(grp.total_quantity ?? 0),
                    available_quantity: Number(grp.available_quantity ?? 0),
                    effective_available_quantity: Number(grp.effective_available_quantity ?? grp.available_quantity ?? 0),
                    license_balance_cif: Number(grp.license_balance_cif ?? license?.get_balance_cif ?? 0),
                    effective_license_balance_cif: Number(
                        grp.effective_license_balance_cif ?? grp.license_balance_cif ?? license?.get_balance_cif ?? 0,
                    ),
                    balance_cif_fc: Number(grp.balance_cif_fc ?? 0),
                    itemNames: grp.item_names ?? [],
                    splits: splits.length ? splits : [emptySplit()],
                    operational_status: grp.operational_status,
                };
                const reconciledSplits = splits.filter((split) =>
                    split.remaining_quantity != null && split.remaining_cif != null,
                );
                if (reconciledSplits.length > 0) {
                    group.has_plan = true;
                    group.has_reconciliation = true;
                    group.original_planned_quantity = splits.reduce((sum, split) => sum + num(split.planned_quantity), 0);
                    group.original_planned_cif_fc = splits.reduce((sum, split) => sum + num(split.planned_cif_fc), 0);
                    group.used_planned_quantity = splits.reduce((sum, split) => sum + num(split.effective_used_quantity), 0);
                    group.used_planned_cif_fc = splits.reduce((sum, split) => sum + num(split.effective_used_cif), 0);
                    group.remaining_planned_quantity = splits.reduce(
                        (sum, split) => sum + num(split.remaining_quantity ?? split.planned_quantity), 0,
                    );
                    group.remaining_planned_cif_fc = splits.reduce(
                        (sum, split) => sum + num(split.remaining_cif ?? split.planned_cif_fc), 0,
                    );
                    group.reconciliation_manual_required = splits.some((split) =>
                        split.reconciliation_status === "MANUAL_PLANNING_REQUIRED"
                        || num(split.excess_quantity) > 1e-6
                        || num(split.excess_cif) > 1e-6,
                    );
                } else if (grp.has_plan) {
                    group.has_plan = true;
                    group.original_planned_quantity  = Number(grp.original_quantity ?? 0);
                    group.used_planned_quantity      = Number(grp.used_quantity ?? 0);
                    group.remaining_planned_quantity = Number(grp.remaining_quantity ?? 0);
                    group.original_planned_cif_fc    = Number(grp.original_cif_fc ?? 0);
                    group.used_planned_cif_fc        = Number(grp.used_cif_fc ?? 0);
                    group.remaining_planned_cif_fc    = Number(grp.remaining_cif_fc ?? 0);
                }
                // Retain the legacy status only for records that do not yet
                // have child-level reconciliation data.
                group.planning_status = group.has_reconciliation ? undefined : grp.status;
                group.shortage_qty = Number(grp.shortage_qty ?? 0);
                group.feasible = grp.feasible;
                return group;
            });

            setGroups(built);
            setSavedGroups(cloneGroups(built));
            setPoolBalance(Number(license?.balance_cif ?? balanceCif) || 0);
            const exportItems = Array.isArray(license?.export_license) ? license.export_license : [];
            const totalCif = exportItems.reduce(
                (sum: number, item: { cif_fc?: string | number | null }) => sum + Number(item.cif_fc ?? 0),
                0,
            );
            setLicenseTotalCif(totalCif || Number(license?.total_cif ?? balanceCif) || 0);
            setEditingGroupId(null);
        } catch { toast.error("Failed to load plan data"); }
        finally { setLoading(false); }
    }, [licenseId, balanceCif]);

    useEffect(() => { void load(); }, [load]);

    // ── Edit / Cancel ─────────────────────────────────────────────────────────

    const openEditor = useCallback((gId: number) => {
        setGroups((prev) => prev.map((g) => {
            if (g.id === editingGroupId) {
                const saved = savedGroups.find((s) => s.id === editingGroupId);
                return saved ? { ...g, splits: cloneSplits(saved.splits) } : g;
            }
            return g;
        }));
        setEditingGroupId(gId);
    }, [editingGroupId, savedGroups]);

    const cancelEditor = useCallback(() => {
        if (editingGroupId === null) return;
        const saved = savedGroups.find((s) => s.id === editingGroupId);
        setGroups((prev) => prev.map((g) =>
            g.id === editingGroupId && saved ? { ...g, splits: cloneSplits(saved.splits) } : g,
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
                sg.id === gId ? { ...sg, splits: cloneSplits(g.splits) } : sg,
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

    // ── Delete (per-row) ──────────────────────────────────────────────────────

    const deleteGroup = useCallback(async (gId: number) => {
        const g = groups.find((gr) => gr.id === gId);
        if (!g) return;

        const savedSplitIds = g.splits.map((sp) => sp.id).filter((id): id is number => id !== null);
        if (savedSplitIds.length === 0) return;

        const ok = window.confirm(`Delete the plan for "${g.description}"?\n\nThis removes every saved planning entry for this item and cannot be undone.`);
        if (!ok) return;

        setDeletingGroupId(gId);
        try {
            await Promise.all(savedSplitIds.map((id) => deleteItemPlan(id)));
            toast.success(`Plan deleted — ${g.description}`);
            if (editingGroupId === gId) setEditingGroupId(null);
            await load();
            onSaved?.();
        } catch {
            toast.error("Failed to delete plan");
        } finally {
            setDeletingGroupId(null);
        }
    }, [groups, editingGroupId, load, onSaved]);

    // ── Auto Plan ────────────────────────────────────────────────────────

    const handlePlan = useCallback(async (mode: "NEW" | "ALL") => {
        if (!licenseId || isPlanning) return;
        setIsPlanning(true);
        try {
            const result = await planLicense(Number(licenseId), mode);
            const siansExecuted = result?.total_results?.sions_executed || 0;
            const linesWritten = result?.total_results?.total_lines_written || 0;

            let message: string;
            if (linesWritten === 0) {
                message = "Planning already up to date. No new eligible items were found.";
            } else if (mode === "ALL") {
                message = `Force re-plan completed: ${siansExecuted} SION${siansExecuted !== 1 ? 's' : ''}, ${linesWritten} line${linesWritten !== 1 ? 's' : ''} processed`;
            } else {
                message = `Planning completed: ${siansExecuted} SION${siansExecuted !== 1 ? 's' : ''}, ${linesWritten} line${linesWritten !== 1 ? 's' : ''} planned`;
            }

            toast.success(message);
            await load();
            onSaved?.();
        } catch (error: unknown) {
            toast.error(apiErrorMessage(error, "Failed to plan license"));
        } finally {
            setIsPlanning(false);
            setShowForceConfirm(false);
        }
    }, [licenseId, isPlanning, load, onSaved]);

    const handleAutoPlan = useCallback(async () => {
        if (!licenseId || isPlanning) {
            return;
        }
        setIsPlanning(true);
        try {
            const result = await autoPlanLicense(Number(licenseId));
            const linesWritten = result?.total_lines_written || 0;
            const sionCode = result?.sion_code || 'Unknown';

            let message: string;
            if (linesWritten === 0) {
                // Check if there are diagnostics explaining why no items were planned
                const diagnostics = result.diagnostics;
                if (diagnostics?.skip_reasons?.length) {
                    const reasons = diagnostics.skip_reasons
                        .map((reason) => `${reason.item_key}: ${reason.reason}`)
                        .join('; ');
                    message = `Planning completed for ${sionCode}: No items planned. Reasons: ${reasons}`;
                } else {
                    message = `Planning completed for ${sionCode}: No new eligible items were found.`;
                }
            } else {
                message = `Auto-planning completed for ${sionCode}: ${linesWritten} line${linesWritten !== 1 ? 's' : ''} planned`;
            }

            toast.success(message);
            await load();
            onSaved?.();
        } catch (error: unknown) {
            toast.error(apiErrorMessage(error, "Failed to auto-plan license"));
        } finally {
            setIsPlanning(false);
        }
    }, [licenseId, isPlanning, load, onSaved]);

    const handleForceReplan = () => setShowForceConfirm(true);

    // ── Derived totals ─────────────────────────────────────────────────────────

    const totals = useMemo(() => {
        let totalAvail = 0, theoreticalPlanned = 0, theoreticalCif = 0;
        let effectivePlanned = 0, effectiveCif = 0, usedQuantity = 0, usedCif = 0;
        let lastUpdated: string | null = null;
        groups.forEach((g) => {
            totalAvail   += g.available_quantity;
            const groupTheoreticalQty = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
            const groupTheoreticalCif = g.splits.reduce((s, sp) => s + num(sp.planned_cif_fc), 0);
            theoreticalPlanned += groupTheoreticalQty;
            theoreticalCif += groupTheoreticalCif;
            effectivePlanned += g.has_reconciliation ? (g.remaining_planned_quantity ?? 0) : groupTheoreticalQty;
            effectiveCif += g.has_reconciliation ? (g.remaining_planned_cif_fc ?? 0) : groupTheoreticalCif;
            usedQuantity += g.has_reconciliation ? (g.used_planned_quantity ?? 0) : 0;
            usedCif += g.has_reconciliation ? (g.used_planned_cif_fc ?? 0) : 0;
            g.splits.forEach((sp) => {
                if (sp.modified_on) {
                    const d = new Date(sp.modified_on);
                    if (!isNaN(d.getTime()) && (!lastUpdated || sp.modified_on > lastUpdated)) {
                        lastUpdated = sp.modified_on;
                    }
                }
            });
        });
        const lastUpdatedLabel = lastUpdated
            ? new Date(lastUpdated).toLocaleDateString("en-IN", {
                  day: "numeric", month: "short", year: "numeric",
              })
            : null;
        return {
            totalAvail, theoreticalPlanned, theoreticalCif,
            effectivePlanned, effectiveCif, usedQuantity, usedCif,
            remaining: totalAvail - effectivePlanned,
            cifRemaining: licenseTotalCif - effectiveCif,
            lastUpdatedLabel,
        };
    }, [groups, licenseTotalCif]);

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
                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                        <Target className="size-4 text-primary" aria-hidden="true" />
                        Plan utilization
                    </div>
                    {totals.lastUpdatedLabel && (
                        <span className="text-[11px] text-muted-foreground">
                            · Last updated: {totals.lastUpdatedLabel}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        type="button"
                        onClick={handleAutoPlan}
                        disabled={isPlanning}
                        size="sm"
                        className="gap-2 bg-amber-50 text-amber-600 border border-amber-200 hover:bg-amber-100"
                    >
                        {isPlanning ? (
                            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                        ) : (
                            <Target className="size-3.5" aria-hidden="true" />
                        )}
                        {isPlanning ? "Planning..." : "Auto Plan"}
                    </Button>
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button
                                variant="outline"
                                size="sm"
                                className="px-2"
                                disabled={isPlanning}
                            >
                                <ChevronDown className="size-4" aria-hidden="true" />
                                <span className="sr-only">Planning options</span>
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-48">
                            <DropdownMenuItem asChild>
                                <button
                                    type="button"
                                    onClick={handleAutoPlan}
                                    disabled={isPlanning}
                                    className="w-full cursor-pointer"
                                >
                                    Auto Plan — New Only
                                </button>
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={handleForceReplan} disabled={isPlanning}>
                                Force Re-plan
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>

            <Dialog open={showForceConfirm} onOpenChange={setShowForceConfirm}>
                <DialogContent>
                    <DialogTitle>Re-plan this license?</DialogTitle>
                    <DialogDescription className="py-4">
                        Existing planning for license {licenseNumber} will be
                        recalculated using the current saved planning rules.
                    </DialogDescription>
                    <div className="flex gap-2 justify-end">
                        <Button variant="outline" onClick={() => setShowForceConfirm(false)}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={() => handlePlan("ALL")}
                        >
                            Force Re-plan
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>

            {/* ── Summary cards (CIF only) ──────────────────────────── */}
            <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
                <SummaryCard label="License Total CIF" value={fmtUsd(licenseTotalCif)} variant="muted" />
                <SummaryCard label="Theoretical Planned CIF" value={fmtUsd(totals.theoreticalCif)} variant={totals.theoreticalCif > 0 ? "primary" : "muted"} />
                <SummaryCard label="Effective Remaining CIF" value={fmtUsd(totals.effectiveCif)} variant={totals.effectiveCif > 0 ? "primary" : "muted"} />
                <SummaryCard
                    label={totals.cifRemaining < -1e-6 ? "Operational Excess CIF" : "Operational Available CIF"}
                    value={fmtUsd(Math.abs(totals.cifRemaining))}
                    variant={totals.cifRemaining < -1e-6 ? "danger" : totals.effectiveCif > 0 ? "success" : "muted"}
                />
            </div>
            {totals.cifRemaining < -1e-6 && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3">
                    <div className="font-semibold text-destructive">Manual Planning Required</div>
                    <div className="text-xs text-muted-foreground">
                        The effective remaining plan exceeds License Total CIF by {fmtUsd(Math.abs(totals.cifRemaining))}. Reason: TOTAL_CIF_EXCEEDED.
                    </div>
                </div>
            )}

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
                                <th scope="col" className="px-4 py-2.5">HS Code</th>
                                <th scope="col" className="px-4 py-2.5">S.No</th>
                                <th scope="col" className="px-4 py-2.5">Status</th>
                                <th scope="col" className="px-4 py-2.5 text-right">Available Qty</th>
                                <th scope="col" className="px-4 py-2.5 text-right">Planned Qty</th>
                                <th scope="col" className="px-4 py-2.5 text-right">Unit Price</th>
                                <th scope="col" className="px-4 py-2.5 text-right">Planned CIF</th>
                                <th scope="col" className="px-4 py-2.5 text-right">Used Qty</th>
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
                                const splitRows  = validSplitsOf(g);
                                const hasSplitRows = splitRows.length > 0;
                                const isExpanded   = hasSplitRows && (expandedIds[g.id] ?? true);
                                const splitRowsId  = `plan-splits-${g.id}`;

                                // "Planned Qty/CIF" show the live Remaining (Original minus
                                // usage since this plan was last saved) as the headline number
                                // when the group has a tracked plan — that's the actionable
                                // "how much can still be allotted" figure. The true Original
                                // (what was actually entered/auto-planned) stays visible as a
                                // "of X" sub-line so re-planning intent is never hidden, just
                                // no longer the number that drives the Over-Planned badge.
                                const showRemaining  = g.has_plan === true && g.remaining_planned_quantity != null;
                                const showRemainingCif = g.has_plan === true && g.remaining_planned_cif_fc != null;
                                const displayQty      = showRemaining ? g.remaining_planned_quantity ?? planned : planned;
                                const displayCif      = showRemainingCif ? g.remaining_planned_cif_fc ?? plannedCif : plannedCif;
                                const qtyDiffersFromOriginal = showRemaining && Math.abs((g.original_planned_quantity ?? 0) - displayQty) > 1e-6;

                                return (
                                    <Fragment key={g.id}>
                                        <tr
                                            key={g.id}
                                            className={cn(
                                                "border-b border-border/40 transition-colors",
                                                isEditing ? "bg-primary/5 border-primary/20" : "hover:bg-muted/20",
                                            )}
                                        >
                                            <td className="px-4 py-3">
                                                <div className="flex items-start gap-1.5">
                                                    {hasSplitRows ? (
                                                        <button
                                                            type="button"
                                                            onClick={() => toggleExpand(g.id)}
                                                            aria-expanded={isExpanded}
                                                            aria-controls={splitRowsId}
                                                            aria-label={`${isExpanded ? "Collapse" : "Expand"} ${splitRows.length} planning item${splitRows.length > 1 ? "s" : ""} for ${g.description}`}
                                                            className="mt-0.5 flex size-4 shrink-0 cursor-pointer items-center justify-center rounded text-muted-foreground/60 transition-colors hover:text-foreground"
                                                        >
                                                            {isExpanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
                                                        </button>
                                                    ) : (
                                                        <span className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                                                    )}
                                                    <div>
                                                        <div className="font-medium text-foreground">{g.description}</div>
                                                        {hasSplitRows && (
                                                            <span className="sr-only">
                                                                {splitRows.length} planning item{splitRows.length > 1 ? "s" : ""}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="px-4 py-3 text-muted-foreground">{g.hsCode || "—"}</td>
                                            <td className="px-4 py-3 text-muted-foreground">{g.serials.join(", ")}</td>
                                            <td className="px-4 py-3">
                                                <StatusBadge status={status} />
                                            </td>
                                            <td className="px-4 py-3 text-right tabular-nums">{fmtQty(g.available_quantity)}</td>
                                            <td className="px-4 py-3 text-right tabular-nums font-semibold">
                                                {planned > 0 ? (
                                                    <>
                                                        <span className={displayQty < -1e-6 ? "text-destructive" : undefined}>{fmtQty(displayQty)}</span>
                                                        {qtyDiffersFromOriginal && (
                                                            <div className="text-[10px] font-normal text-muted-foreground">of {fmtQty(g.original_planned_quantity)} planned</div>
                                                        )}
                                                    </>
                                                ) : <span className="font-normal text-muted-foreground">—</span>}
                                            </td>
                                            <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                                                {planned > 0 && plannedCif > 0
                                                    ? `$${round2(plannedCif / planned).toFixed(2)}`
                                                    : <span>—</span>}
                                            </td>
                                            <td className="px-4 py-3 text-right tabular-nums">
                                                {plannedCif > 0 ? (
                                                    <>
                                                        <span className={cn("font-semibold", displayCif < -1e-6 ? "text-destructive" : "text-primary")}>{fmtUsd(displayCif)}</span>
                                                        {qtyDiffersFromOriginal && (
                                                            <div className="text-[10px] font-normal text-muted-foreground">of {fmtUsd(g.original_planned_cif_fc)} planned</div>
                                                        )}
                                                    </>
                                                ) : <span className="text-muted-foreground">—</span>}
                                            </td>
                                            <td className="px-4 py-3 text-right tabular-nums">
                                                <span className={cn("font-semibold",
                                                    showRemaining ? "text-foreground" :
                                                    rem < -1e-6 ? "text-destructive" :
                                                    rem < 1e-6 && planned > 0 ? "text-emerald-700" : "text-muted-foreground",
                                                )}>{fmtQty(showRemaining ? g.used_planned_quantity ?? 0 : rem)}</span>
                                            </td>
                                            <td className="px-4 py-3 text-center">
                                                {isEditing ? (
                                                    <span className="text-[10.5px] font-medium text-primary">Editing ↓</span>
                                                ) : (
                                                    <div className="flex items-center justify-center gap-1">
                                                        <Button
                                                            variant="ghost" size="sm"
                                                            onClick={() => openEditor(g.id)}
                                                            disabled={savingGroupId !== null || deletingGroupId !== null}
                                                            className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                                                            aria-label={`Edit planning for ${g.description}`}
                                                        >
                                                            <Pencil className="size-3.5" />Edit
                                                        </Button>
                                                        {g.has_plan && (
                                                            <Button
                                                                variant="ghost" size="sm"
                                                                onClick={() => deleteGroup(g.id)}
                                                                disabled={savingGroupId !== null || deletingGroupId !== null}
                                                                className="h-7 gap-1.5 text-xs text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                                                                aria-label={`Delete plan for ${g.description}`}
                                                            >
                                                                {deletingGroupId === g.id
                                                                    ? <Loader2 className="size-3.5 animate-spin" />
                                                                    : <Trash2 className="size-3.5" />}
                                                                Delete
                                                            </Button>
                                                        )}
                                                    </div>
                                                )}
                                            </td>
                                        </tr>

                                        {isExpanded && splitRows.map((sp, si) => (
                                            <tr
                                                key={`${g.id}-split-${sp.key}`}
                                                id={si === 0 ? splitRowsId : undefined}
                                                className="border-b border-border/30 bg-primary/[0.02]"
                                            >
                                                <td colSpan={10} className="px-4 py-2 pl-11">
                                                    <div className="flex flex-wrap items-center gap-2 text-[12px]">
                                                        <span className="text-muted-foreground/50" aria-hidden="true">└</span>
                                                        <span className="text-muted-foreground">Planning Item:</span>
                                                        <span className="font-medium text-foreground">{splitLabel(sp, g, si)}</span>
                                                        <span className="rounded-full bg-muted px-1.5 py-0.5 text-[9.5px] font-semibold text-muted-foreground">
                                                            {(sp.reconciliation_status ?? "NOT_USED").replace(/_/g, " ")}
                                                        </span>
                                                        {sp.needs_rebuild && <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[9.5px] font-semibold text-amber-800">Needs Rebuild</span>}
                                                    </div>
                                                    <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] sm:grid-cols-5">
                                                        {[
                                                            ["Theoretical Qty", fmtQty(num(sp.planned_quantity))],
                                                            ["Theoretical CIF", fmtUsd(num(sp.planned_cif_fc))],
                                                            ["BOE Used Qty", fmtQty(num(sp.boe_used_quantity))],
                                                            ["BOE Used CIF", fmtUsd(num(sp.boe_used_cif))],
                                                            ["Unlinked Allotment Qty", fmtQty(num(sp.unlinked_allotment_quantity))],
                                                            ["Unlinked Allotment CIF", fmtUsd(num(sp.unlinked_allotment_cif))],
                                                            ["Remaining Qty", fmtQty(num(sp.remaining_quantity))],
                                                            ["Remaining CIF", fmtUsd(num(sp.remaining_cif))],
                                                            ["Excess Qty", fmtQty(num(sp.excess_quantity))],
                                                            ["Excess CIF", fmtUsd(num(sp.excess_cif))],
                                                        ].map(([label, value]) => <div key={label}><dt className="text-muted-foreground">{label}</dt><dd className="font-medium tabular-nums">{value}</dd></div>)}
                                                    </dl>
                                                </td>
                                            </tr>
                                        ))}

                                        {isEditing && (
                                            <tr key={`${g.id}-editor`} className="border-b border-primary/20 bg-primary/[0.02]">
                                                <td colSpan={10} className="p-0">
                                                    <InlineEditor
                                                        group={g}
                                                        poolBalance={poolBalance}
                                                        allGroups={groups}
                                                        saving={isSaving}
                                                        onChange={(key, field, value) => changeSplit(g.id, key, field, value)}
                                                        onAddSplit={() => addSplit(g.id)}
                                                        onRemoveSplit={(key) => removeSplit(g.id, key)}
                                                        onSave={() => saveGroup(g.id)}
                                                        onCancel={cancelEditor}
                                                    />
                                                </td>
                                            </tr>
                                        )}
                                    </Fragment>
                                );
                            })}

                            {/* Totals row — 10 columns: Item, HS Code, S.No, Status, Avail, Planned, UnitPrice, CIF, Remaining, Actions */}
                            {anyPlanExists && (
                                <tr className="border-t-2 border-border bg-muted/40 font-semibold text-sm">
                                    <td className="px-4 py-2 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Totals</td>
                                    <td />
                                    <td />
                                    <td />
                                    <td className="px-4 py-2 text-right tabular-nums">{fmtQty(totals.totalAvail)}</td>
                                    <td className="px-4 py-2 text-right tabular-nums">{fmtQty(totals.effectivePlanned)}</td>
                                    <td />{/* Unit Price — rate, not summed */}
                                    <td className="px-4 py-2 text-right tabular-nums text-primary">{fmtUsd(totals.effectiveCif)}</td>
                                    <td className="px-4 py-2 text-right tabular-nums">
                                        <span className="text-foreground">{fmtQty(totals.usedQuantity)}</span>
                                    </td>
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
