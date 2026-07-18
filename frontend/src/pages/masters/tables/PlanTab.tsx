/**
 * PlanTab — modern enterprise planning workspace.
 *
 * VIEW mode  — sticky summary cards + collapsible item overview table.
 *              Single "Edit Planning" button.
 *
 * EDIT mode  — sticky 6-metric summary bar that updates live.
 *              Per-item collapsible cards (collapsed = read-only, expand = edit).
 *              Split cards (not a horizontal table) for each planning row.
 *              Bulk actions: Expand All · Collapse All · status filter.
 *              Inline validation cards on over-planned items.
 *              Sticky footer: Save Planning · Cancel · Reset Changes.
 *
 * Business logic — UNCHANGED:
 *   fetchLicense / fetchItemPlans / bulkUpsertItemPlans / fetchNormPrefill
 *   3-way auto-calc  · remaining cap per split · bulkUpsert on save
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
    AlertTriangle,
    BookOpen,
    Calendar,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Circle,
    ClipboardList,
    Loader2,
    MinusCircle,
    Pencil,
    Plus,
    RefreshCw,
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
} from "../../../services/api/licenseApi";

// ─────────────────────────────────────────────────────────────────────────────
// Pure helpers — identical to previous version (stable, no business change)
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
type StatusFilter = "all" | "not_planned" | "partial" | "completed" | "over";

interface PlanTabProps {
    licenseId: number;
    licenseNumber: string;
    balanceCif?: number;
    canWrite: boolean;
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

const STATUS_CONFIG: Record<PlanStatus, { label: string; icon: React.ElementType; cls: string; badge: string }> = {
    not_planned: { label: "Not Planned",       icon: Circle,        cls: "text-muted-foreground",  badge: "bg-muted text-muted-foreground ring-1 ring-border" },
    partial:     { label: "Partially Planned", icon: MinusCircle,   cls: "text-amber-700",         badge: "bg-amber-50 text-amber-700 ring-1 ring-amber-200" },
    completed:   { label: "Completed",         icon: CheckCircle2,  cls: "text-emerald-700",       badge: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200" },
    over:        { label: "Over Planned",      icon: XCircle,       cls: "text-destructive",       badge: "bg-destructive/10 text-destructive ring-1 ring-destructive/30" },
};

function StatusBadge({ status }: { status: PlanStatus }) {
    const cfg = STATUS_CONFIG[status];
    const Icon = cfg.icon;
    return (
        <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-semibold", cfg.badge)}>
            <Icon className="size-3" aria-hidden="true" />
            {cfg.label}
        </span>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// SummaryCard — one of the 6 sticky metrics
// ─────────────────────────────────────────────────────────────────────────────

function SummaryCard({
    label, value, variant = "default",
}: {
    label: string; value: string;
    variant?: "default" | "primary" | "success" | "danger" | "warning" | "muted";
}) {
    const cls = {
        default: "text-foreground",
        primary: "text-primary",
        success: "text-emerald-700",
        danger: "text-destructive",
        warning: "text-amber-700",
        muted: "text-muted-foreground",
    }[variant];
    const bg = {
        default: "bg-card",
        primary: "bg-primary/5",
        success: "bg-emerald-50/50",
        danger: "bg-destructive/5",
        warning: "bg-amber-50/50",
        muted: "bg-muted/40",
    }[variant];
    return (
        <div className={cn("flex flex-col rounded-xl border border-border/60 px-3.5 py-3", bg)}>
            <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</div>
            <div className={cn("mt-0.5 text-base font-bold tabular-nums leading-tight", cls)}>{value}</div>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// SplitCard — one planning row, shown as a card in edit mode
// ─────────────────────────────────────────────────────────────────────────────

function SplitCard({
    split, index, group, isLast, canRemove,
    onChangeSplit, onRemoveSplit,
}: {
    split: Split;
    index: number;
    group: Group;
    isLast: boolean;
    canRemove: boolean;
    onChangeSplit: (gId: number, key: string, field: string, value: string) => void;
    onRemoveSplit: (gId: number, key: string) => void;
}) {
    const otherQty = group.splits.filter((s) => s.key !== split.key).reduce((s, s2) => s + num(s2.planned_quantity), 0);
    const maxForRow = Math.max(0, group.available_quantity - otherQty);
    const rowQty = num(split.planned_quantity);
    const rowOver = rowQty > maxForRow + 1e-6;

    return (
        <div className={cn(
            "rounded-xl border bg-card p-4 transition-shadow hover:shadow-sm",
            rowOver ? "border-destructive/40" : "border-border/60"
        )}>
            {/* Card header */}
            <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10.5px] font-bold text-primary">
                        {index + 1}
                    </div>
                    <span className="text-sm font-semibold text-foreground">Planning #{index + 1}</span>
                    {rowOver && (
                        <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold text-destructive ring-1 ring-destructive/20">
                            Over
                        </span>
                    )}
                </div>
                {canRemove && (
                    <button type="button"
                        onClick={() => onRemoveSplit(group.id, split.key)}
                        className="flex size-7 cursor-pointer items-center justify-center rounded-lg text-muted-foreground/60 hover:bg-destructive/10 hover:text-destructive transition-colors"
                        title="Remove this planning row" aria-label="Remove this planning row">
                        <Trash2 className="size-4" />
                    </button>
                )}
            </div>

            {/* Fields — 2-col grid on sm+, 1-col on mobile */}
            <div className="grid gap-3 sm:grid-cols-2">
                {/* Item Name */}
                <div className="sm:col-span-2">
                    <label className="mb-1 block text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Item Name
                    </label>
                    <select
                        value={split.item_name}
                        onChange={(e) => onChangeSplit(group.id, split.key, "item_name", e.target.value)}
                        className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        aria-label="Item name"
                    >
                        <option value="">— None —</option>
                        {group.itemNames.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
                    </select>
                </div>

                {/* Qty */}
                <div>
                    <label className="mb-1 block text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Quantity
                        <span className="ml-1 font-normal normal-case text-muted-foreground/60">(max {fmtQty(maxForRow)})</span>
                    </label>
                    <Input
                        type="number" min="0" step="0.001" max={maxForRow}
                        value={split.planned_quantity}
                        onChange={(e) => onChangeSplit(group.id, split.key, "planned_quantity", e.target.value)}
                        className={cn("h-9 text-right tabular-nums font-medium",
                            rowOver && "border-destructive focus-visible:ring-destructive")}
                        placeholder="0.000"
                        aria-label={`Quantity, max ${maxForRow.toFixed(3)}`}
                    />
                    {rowOver && (
                        <p className="mt-1 text-[10.5px] text-destructive">
                            Exceeds remaining by {fmtQty(rowQty - maxForRow)}
                        </p>
                    )}
                </div>

                {/* Unit Price */}
                <div>
                    <label className="mb-1 block text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Unit Price ($)
                    </label>
                    <Input
                        type="number" min="0" step="0.01"
                        value={split.unit_price}
                        onChange={(e) => onChangeSplit(group.id, split.key, "unit_price", e.target.value)}
                        className="h-9 text-right tabular-nums font-medium"
                        placeholder="0.00"
                        aria-label="Unit price"
                    />
                </div>

                {/* CIF */}
                <div>
                    <label className="mb-1 block text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        CIF ($)
                    </label>
                    <Input
                        type="number" min="0" step="0.01"
                        value={split.planned_cif_fc}
                        onChange={(e) => onChangeSplit(group.id, split.key, "planned_cif_fc", e.target.value)}
                        className="h-9 text-right tabular-nums font-medium"
                        placeholder="0.00"
                        aria-label="Planned CIF"
                    />
                </div>

                {/* Remarks */}
                <div>
                    <label className="mb-1 block text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Remarks
                    </label>
                    <Input
                        value={split.note}
                        onChange={(e) => onChangeSplit(group.id, split.key, "note", e.target.value)}
                        className="h-9"
                        placeholder="Optional notes…"
                        aria-label="Remarks"
                    />
                </div>
            </div>

            {/* Computed CIF display when all three are filled */}
            {num(split.planned_quantity) > 0 && num(split.unit_price) > 0 && (
                <div className="mt-3 flex items-center justify-between rounded-lg bg-muted/40 px-3 py-1.5 text-[11px]">
                    <span className="text-muted-foreground">
                        {fmtQty(num(split.planned_quantity))} × ${num(split.unit_price).toFixed(2)}
                    </span>
                    <span className="font-semibold tabular-nums text-primary">
                        = {fmtUsd(num(split.planned_quantity) * num(split.unit_price))}
                    </span>
                </div>
            )}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// GroupCard — one import-item group in edit mode
// ─────────────────────────────────────────────────────────────────────────────

function GroupCard({
    group, isExpanded, onToggle,
    onChangeSplit, onAddSplit, onRemoveSplit,
}: {
    group: Group;
    isExpanded: boolean;
    onToggle: () => void;
    onChangeSplit: (gId: number, key: string, field: string, value: string) => void;
    onAddSplit: (gId: number) => void;
    onRemoveSplit: (gId: number, key: string) => void;
}) {
    const status = groupStatus(group);
    const cfg = STATUS_CONFIG[status];
    const planned = group.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
    const plannedCif = group.splits.reduce((s, sp) => s + num(sp.planned_cif_fc), 0);
    const remaining = group.available_quantity - planned;
    const qtyOver = planned > group.available_quantity + 1e-6;
    const activeSplits = group.splits.filter((sp) => num(sp.planned_quantity) > 0 || num(sp.planned_cif_fc) > 0);

    return (
        <div className={cn(
            "overflow-hidden rounded-2xl border shadow-sm transition-shadow",
            isExpanded ? "shadow-md" : "hover:shadow-md",
            qtyOver ? "border-destructive/30" : status === "completed" ? "border-emerald-200/70" : "border-border/70"
        )}>
            {/* ── Collapsed header ──────────────────────────────────── */}
            <button
                type="button"
                onClick={onToggle}
                aria-expanded={isExpanded}
                className="w-full cursor-pointer text-left"
            >
                <div className={cn(
                    "flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5 transition-colors",
                    isExpanded ? "bg-primary/5" : "bg-card hover:bg-muted/30"
                )}>
                    {/* Description block */}
                    <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-foreground">{group.description}</span>
                            <StatusBadge status={status} />
                        </div>
                        <div className="mt-0.5 text-[10.5px] text-muted-foreground">
                            S.No {group.serials.join(", ")}
                            {group.hsCodes && group.hsCodes.length > 0 && ` · HSN ${group.hsCodes.join(", ")}`}
                        </div>
                    </div>

                    {/* Metrics strip */}
                    <div className="flex flex-wrap items-center gap-4 text-[11px]">
                        <div className="text-center">
                            <div className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">Available</div>
                            <div className="font-semibold tabular-nums text-foreground">{fmtQty(group.available_quantity)}</div>
                        </div>
                        <div className="text-center">
                            <div className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">Planned</div>
                            <div className={cn("font-semibold tabular-nums", qtyOver ? "text-destructive" : planned > 0 ? "text-foreground" : "text-muted-foreground")}>
                                {planned > 0 ? fmtQty(planned) : "—"}
                            </div>
                        </div>
                        <div className="text-center">
                            <div className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">Remaining</div>
                            <div className={cn("font-semibold tabular-nums",
                                remaining < -1e-6 ? "text-destructive" : remaining < 1e-6 && planned > 0 ? "text-emerald-700" : "text-muted-foreground")}>
                                {fmtQty(remaining)}
                            </div>
                        </div>
                    </div>

                    {/* Expand indicator */}
                    <ChevronDown className={cn(
                        "size-4 shrink-0 text-muted-foreground/50 transition-transform duration-200",
                        isExpanded && "rotate-180"
                    )} aria-hidden="true" />
                </div>
            </button>

            {/* ── Expanded edit panel ───────────────────────────────── */}
            {isExpanded && (
                <div className="border-t border-border/50 bg-muted/10 px-5 pb-5 pt-4">
                    {/* Per-item planning summary */}
                    <div className="mb-4 grid grid-cols-3 gap-3 sm:grid-cols-6">
                        <SummaryCard label="Available Qty" value={fmtQty(group.available_quantity)} />
                        <SummaryCard label="Planned Qty" value={planned > 0 ? fmtQty(planned) : "—"}
                            variant={qtyOver ? "danger" : planned > 0 ? "default" : "muted"} />
                        <SummaryCard label="Remaining Qty" value={fmtQty(remaining)}
                            variant={remaining < -1e-6 ? "danger" : remaining < 1e-6 && planned > 0 ? "success" : "muted"} />
                        <SummaryCard label="Balance CIF" value={fmtUsd(group.balance_cif_fc)} variant="muted" />
                        <SummaryCard label="Planned CIF" value={plannedCif > 0 ? fmtUsd(plannedCif) : "—"}
                            variant={plannedCif > 0 ? "primary" : "muted"} />
                        <SummaryCard label="Entries" value={String(activeSplits.length)} variant="muted" />
                    </div>

                    {/* Over-planned warning card */}
                    {qtyOver && (
                        <div className="mb-4 overflow-hidden rounded-xl border border-destructive/30 bg-destructive/5">
                            <div className="flex items-start gap-3 px-4 py-3">
                                <AlertTriangle className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden="true" />
                                <div className="flex-1">
                                    <div className="text-sm font-semibold text-destructive">Over Planned</div>
                                    <div className="mt-1.5 grid grid-cols-3 gap-3 text-[11.5px]">
                                        <div>
                                            <span className="text-muted-foreground">Available</span>
                                            <div className="font-semibold tabular-nums text-foreground">{fmtQty(group.available_quantity)}</div>
                                        </div>
                                        <div>
                                            <span className="text-muted-foreground">Planned</span>
                                            <div className="font-semibold tabular-nums text-destructive">{fmtQty(planned)}</div>
                                        </div>
                                        <div>
                                            <span className="text-muted-foreground">Over by</span>
                                            <div className="font-semibold tabular-nums text-destructive">{fmtQty(planned - group.available_quantity)}</div>
                                        </div>
                                    </div>
                                    <p className="mt-2 text-[10.5px] text-muted-foreground">
                                        Reduce planned quantity or create a separate allocation for the excess.
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Split label */}
                    <div className="mb-2.5 flex items-center justify-between">
                        <span className="text-[10.5px] font-bold uppercase tracking-widest text-muted-foreground">
                            Planning Entries ({activeSplits.length})
                        </span>
                    </div>

                    {/* Split cards */}
                    <div className="space-y-3">
                        {group.splits.map((sp, idx) => (
                            <SplitCard
                                key={sp.key}
                                split={sp}
                                index={idx}
                                group={group}
                                isLast={idx === group.splits.length - 1}
                                canRemove={group.splits.length > 1}
                                onChangeSplit={onChangeSplit}
                                onRemoveSplit={onRemoveSplit}
                            />
                        ))}
                    </div>

                    {/* Add split */}
                    <button
                        type="button"
                        onClick={() => onAddSplit(group.id)}
                        className="mt-3 flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-border/70 py-3 text-sm font-medium text-muted-foreground transition-colors hover:border-primary hover:bg-primary/5 hover:text-primary"
                    >
                        <Plus className="size-4" aria-hidden="true" />
                        Add Split
                    </button>
                </div>
            )}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// PlanTab — root
// ─────────────────────────────────────────────────────────────────────────────

export default function PlanTab({
    licenseId, licenseNumber, balanceCif = 0, canWrite,
}: PlanTabProps) {
    const [mode, setMode] = useState<"view" | "edit">("view");
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [prefilling, setPrefilling] = useState(false);

    const [groups, setGroups] = useState<Group[]>([]);
    const [savedGroups, setSavedGroups] = useState<Group[]>([]);
    const [poolBalance, setPoolBalance] = useState(Number(balanceCif) || 0);

    /** Which group cards are expanded in edit mode. */
    const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
    /** Status filter for edit mode item list. */
    const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

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
                g.total_quantity += Number(it.quantity ?? 0);
                g.available_quantity += Number(it.available_quantity ?? 0);
                g.balance_cif_fc += Number(it.balance_cif_fc ?? 0);
                itemNames.forEach((n) => { if (!g.itemNames.find((x) => x.id === n.id)) g.itemNames.push(n); });
            }

            const built = Object.values(groupMap);
            setGroups(built);
            setSavedGroups(JSON.parse(JSON.stringify(built)));
            setPoolBalance(Number(license?.balance_cif ?? balanceCif) || 0);
            setMode(planList.length > 0 ? "view" : "edit");
            setExpandedIds(new Set());
        } catch { toast.error("Failed to load plan data"); }
        finally { setLoading(false); }
    }, [licenseId, balanceCif]);

    useEffect(() => { load(); }, [load]);

    // ── Edit / Cancel ─────────────────────────────────────────────────────────

    const enterEdit = useCallback(() => {
        setGroups((prev) => prev.map((g) => ({
            ...g, splits: g.splits.length === 0 ? [emptySplit()] : g.splits,
        })));
        setMode("edit");
        setExpandedIds(new Set()); // start all collapsed
    }, []);

    const cancelEdit = useCallback(() => {
        setGroups(JSON.parse(JSON.stringify(savedGroups)));
        setExpandedIds(new Set());
        setMode(savedGroups.some((g) => g.splits.some((s) => s.id !== null)) ? "view" : "edit");
    }, [savedGroups]);

    const resetChanges = useCallback(() => {
        setGroups(JSON.parse(JSON.stringify(savedGroups)));
        toast.info("Changes reset to last saved state");
    }, [savedGroups]);

    // ── 3-way auto-calc (UNCHANGED logic) ─────────────────────────────────────

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

    // ── Save (UNCHANGED logic) ─────────────────────────────────────────────────

    const handleSave = useCallback(async () => {
        for (const g of groups) {
            const totalQty = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
            if (totalQty > g.available_quantity + 1e-6) {
                toast.error(`${g.description}: planned qty (${totalQty.toFixed(3)}) exceeds available (${g.available_quantity.toFixed(3)})`);
                return;
            }
        }
        if (cifOver) { toast.error("Total planned CIF exceeds the license balance"); return; }

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
            await load();
            setMode("view");
        } catch (err: unknown) {
            const data = (err as { response?: { data?: { error?: string; errors?: unknown } } })?.response?.data;
            toast.error(data?.error || (data?.errors ? JSON.stringify(data.errors) : null) || "Failed to save plan");
        } finally { setSaving(false); }
    }, [groups, licenseId, load]);

    // ── Prefill (UNCHANGED logic) ──────────────────────────────────────────────

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

    // ── Derived totals (UNCHANGED logic) ──────────────────────────────────────

    const totals = useMemo(() => {
        let totalAvail = 0, totalPlanned = 0, totalCif = 0, totalEntries = 0;
        let lastUpdated: string | null = null, plannedBy: string | null = null;
        groups.forEach((g) => {
            totalAvail += g.available_quantity;
            const qtySum = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
            const cifSum = g.splits.reduce((s, sp) => s + num(sp.planned_cif_fc), 0);
            totalPlanned += qtySum;
            totalCif += cifSum;
            totalEntries += g.splits.filter((sp) => num(sp.planned_quantity) > 0 || num(sp.planned_cif_fc) > 0).length;
            g.splits.forEach((sp) => {
                if (sp.modified_on && (!lastUpdated || sp.modified_on > lastUpdated)) {
                    lastUpdated = sp.modified_on;
                    plannedBy = sp.modified_by_username ?? null;
                }
            });
        });
        return { totalAvail, totalPlanned, remaining: totalAvail - totalPlanned, totalCif, cifRemaining: Number(poolBalance) - totalCif, totalEntries, lastUpdated, plannedBy };
    }, [groups, poolBalance]);

    const cifOver = totals.cifRemaining < -1e-6;
    const anyPlanExists = groups.some((g) => g.splits.some((s) => s.id !== null));

    // ── Filtered groups (edit mode) ────────────────────────────────────────────

    const filteredGroups = useMemo(() => {
        if (statusFilter === "all") return groups;
        return groups.filter((g) => groupStatus(g) === statusFilter);
    }, [groups, statusFilter]);

    // ── Status counts for filter bar ──────────────────────────────────────────

    const statusCounts = useMemo(() => {
        const counts: Record<PlanStatus, number> = { not_planned: 0, partial: 0, completed: 0, over: 0 };
        groups.forEach((g) => { counts[groupStatus(g)]++; });
        return counts;
    }, [groups]);

    const hasValidationErrors = groups.some((g) => {
        const planned = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
        return planned > g.available_quantity + 1e-6;
    });

    // ── Render ─────────────────────────────────────────────────────────────────

    if (loading) {
        return (
            <div className="space-y-3 py-4">
                <Skeleton className="h-20 w-full rounded-xl" />
                <Skeleton className="h-24 w-full rounded-xl" />
                <Skeleton className="h-24 w-full rounded-xl" />
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

    // ─── 6-metric sticky summary (shared between view + edit) ─────────────────
    const StickyBar = (
        <div className="sticky top-0 z-20 -mx-1 mb-4 grid grid-cols-3 gap-2 rounded-2xl border border-border/60 bg-card/95 p-3 shadow-sm backdrop-blur-md sm:grid-cols-6">
            <SummaryCard label="Balance CIF" value={fmtUsd(poolBalance)} variant="muted" />
            <SummaryCard label="Planned CIF" value={fmtUsd(totals.totalCif)} variant={totals.totalCif > 0 ? "primary" : "muted"} />
            <SummaryCard label="Remaining CIF"
                value={fmtUsd(Math.abs(totals.cifRemaining))}
                variant={cifOver ? "danger" : totals.totalCif > 0 ? "success" : "muted"} />
            <SummaryCard label="Available Qty" value={fmtQty(totals.totalAvail)} />
            <SummaryCard label="Planned Qty"
                value={fmtQty(totals.totalPlanned)}
                variant={totals.totalPlanned > 0 ? "default" : "muted"} />
            <SummaryCard label="Remaining Qty"
                value={fmtQty(totals.remaining)}
                variant={totals.remaining < -1e-6 ? "danger" : totals.remaining < 1e-6 && totals.totalPlanned > 0 ? "success" : "muted"} />
        </div>
    );

    return (
        <div className="py-3">
            {/* ── Tab header ───────────────────────────────────────── */}
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
                    <Button variant="outline" size="sm" onClick={handlePrefill}
                        disabled={prefilling || saving} className="h-7 gap-1.5 text-xs">
                        {prefilling ? <Loader2 className="size-3.5 animate-spin" /> : <Wand2 className="size-3.5" />}
                        Prefill from norm
                    </Button>
                    {mode === "view" && (
                        <Button size="sm" onClick={enterEdit} className="h-7 gap-1.5 text-xs">
                            <Pencil className="size-3.5" />Edit Planning
                        </Button>
                    )}
                </div>
            </div>

            {/* ══════════════════════════════════════════════════════ */}
            {/* VIEW MODE                                             */}
            {/* ══════════════════════════════════════════════════════ */}
            {mode === "view" && (
                <div className="space-y-4">
                    {StickyBar}

                    {/* Metadata row */}
                    {(totals.lastUpdated || totals.plannedBy) && (
                        <div className="flex flex-wrap gap-4 text-[11px] text-muted-foreground">
                            {totals.lastUpdated && (
                                <span className="flex items-center gap-1">
                                    <Calendar className="size-3.5" />Last updated: {fmtDate(totals.lastUpdated)}
                                </span>
                            )}
                            {totals.plannedBy && (
                                <span className="flex items-center gap-1">
                                    <User className="size-3.5" />Planned by: {totals.plannedBy}
                                </span>
                            )}
                        </div>
                    )}

                    {anyPlanExists ? (
                        <div className="overflow-hidden rounded-xl border border-border/60">
                            <div className="flex items-center gap-1.5 border-b border-border/50 bg-muted/30 px-4 py-2.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                <ClipboardList className="size-3.5" />Planned Items
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead className="bg-muted/50">
                                        <tr className="border-b border-border/50 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                            <th scope="col" className="px-4 py-2.5">Item</th>
                                            <th scope="col" className="px-4 py-2.5">Status</th>
                                            <th scope="col" className="px-4 py-2.5 text-right">Available</th>
                                            <th scope="col" className="px-4 py-2.5 text-right">Planned</th>
                                            <th scope="col" className="px-4 py-2.5 text-right">Remaining</th>
                                            <th scope="col" className="px-4 py-2.5 text-right">Planned CIF</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border/40">
                                        {groups.map((g) => {
                                            const st = groupStatus(g);
                                            const planned = g.splits.reduce((s, sp) => s + num(sp.planned_quantity), 0);
                                            const plannedCif = g.splits.reduce((s, sp) => s + num(sp.planned_cif_fc), 0);
                                            const rem = g.available_quantity - planned;
                                            return (
                                                <tr key={g.id} className="transition-colors hover:bg-muted/20">
                                                    <td className="px-4 py-3">
                                                        <div className="font-medium text-foreground">{g.description}</div>
                                                        <div className="text-[10.5px] text-muted-foreground">
                                                            S.No {g.serials.join(", ")}
                                                            {g.hsCodes && g.hsCodes.length > 0 && ` · HSN ${g.hsCodes.join(", ")}`}
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-3"><StatusBadge status={st} /></td>
                                                    <td className="px-4 py-3 text-right tabular-nums">{fmtQty(g.available_quantity)}</td>
                                                    <td className="px-4 py-3 text-right tabular-nums font-semibold">
                                                        {planned > 0 ? fmtQty(planned) : <span className="font-normal text-muted-foreground">—</span>}
                                                    </td>
                                                    <td className="px-4 py-3 text-right tabular-nums">
                                                        <span className={cn("font-semibold", rem < -1e-6 ? "text-destructive" : rem < 1e-6 && planned > 0 ? "text-emerald-700" : "text-muted-foreground")}>
                                                            {fmtQty(rem)}
                                                        </span>
                                                    </td>
                                                    <td className="px-4 py-3 text-right tabular-nums">
                                                        {plannedCif > 0 ? <span className="text-primary">{fmtUsd(plannedCif)}</span> : <span className="text-muted-foreground">—</span>}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                    <tfoot className="border-t-2 border-border bg-muted/40 font-semibold text-sm">
                                        <tr>
                                            <td className="px-4 py-2 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Totals</td>
                                            <td />
                                            <td className="px-4 py-2 text-right tabular-nums">{fmtQty(totals.totalAvail)}</td>
                                            <td className="px-4 py-2 text-right tabular-nums">{fmtQty(totals.totalPlanned)}</td>
                                            <td className="px-4 py-2 text-right tabular-nums">
                                                <span className={cn(totals.remaining < -1e-6 ? "text-destructive" : "text-emerald-700")}>{fmtQty(totals.remaining)}</span>
                                            </td>
                                            <td className="px-4 py-2 text-right tabular-nums text-primary">{fmtUsd(totals.totalCif)}</td>
                                        </tr>
                                    </tfoot>
                                </table>
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center py-12 text-center">
                            <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-muted">
                                <BookOpen className="size-6 text-muted-foreground/50" />
                            </div>
                            <div className="text-sm font-medium text-muted-foreground">No planning recorded</div>
                            <div className="mt-1 text-xs text-muted-foreground/70">Click "Edit Planning" to begin utilization planning.</div>
                        </div>
                    )}
                </div>
            )}

            {/* ══════════════════════════════════════════════════════ */}
            {/* EDIT MODE                                             */}
            {/* ══════════════════════════════════════════════════════ */}
            {mode === "edit" && (
                <div className="space-y-3">
                    {StickyBar}

                    {/* Bulk action bar */}
                    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border/60 bg-card px-3 py-2.5">
                        {/* Expand / Collapse */}
                        <div className="flex items-center gap-1.5">
                            <button type="button"
                                onClick={() => setExpandedIds(new Set(groups.map((g) => g.id)))}
                                className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground hover:bg-muted cursor-pointer">
                                <ChevronDown className="size-3.5" />Expand All
                            </button>
                            <button type="button"
                                onClick={() => setExpandedIds(new Set())}
                                className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground hover:bg-muted cursor-pointer">
                                <ChevronRight className="size-3.5" />Collapse All
                            </button>
                        </div>

                        <div className="mx-2 h-4 w-px bg-border" aria-hidden="true" />

                        {/* Status filter pills */}
                        <div className="flex flex-wrap items-center gap-1">
                            {(["all", "not_planned", "partial", "completed", "over"] as StatusFilter[]).map((f) => {
                                const count = f === "all" ? groups.length : statusCounts[f as PlanStatus];
                                const labels: Record<StatusFilter, string> = {
                                    all: "All", not_planned: "Needs Planning",
                                    partial: "Partial", completed: "Completed", over: "Over Planned",
                                };
                                return (
                                    <button key={f} type="button"
                                        onClick={() => setStatusFilter(f)}
                                        className={cn(
                                            "flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium transition-colors cursor-pointer",
                                            statusFilter === f
                                                ? "bg-primary text-primary-foreground"
                                                : "bg-muted text-muted-foreground hover:text-foreground"
                                        )}>
                                        {labels[f]}
                                        {count > 0 && <span className={cn("rounded-full px-1 text-[9px]", statusFilter === f ? "bg-primary-foreground/20" : "bg-muted-foreground/20")}>{count}</span>}
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* Group cards */}
                    {filteredGroups.map((g) => (
                        <GroupCard
                            key={g.id}
                            group={g}
                            isExpanded={expandedIds.has(g.id)}
                            onToggle={() => setExpandedIds((prev) => {
                                const n = new Set(prev);
                                n.has(g.id) ? n.delete(g.id) : n.add(g.id);
                                return n;
                            })}
                            onChangeSplit={changeSplit}
                            onAddSplit={addSplit}
                            onRemoveSplit={removeSplit}
                        />
                    ))}

                    {filteredGroups.length === 0 && (
                        <div className="py-8 text-center text-sm text-muted-foreground">
                            {statusFilter === "all" ? "No import items found." : `No items match the "${statusFilter}" filter.`}
                        </div>
                    )}

                    {/* ── Sticky footer ────────────────────────────────── */}
                    {groups.length > 0 && (
                        <div className="sticky bottom-0 z-10 overflow-hidden rounded-2xl border border-border bg-card/95 shadow-lg backdrop-blur-md">
                            <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                                {/* Status indicators */}
                                <div className="flex flex-wrap items-center gap-3 text-xs">
                                    {hasValidationErrors && (
                                        <span className="flex items-center gap-1.5 text-destructive">
                                            <AlertTriangle className="size-3.5" />
                                            Validation errors
                                        </span>
                                    )}
                                    {cifOver && (
                                        <span className="flex items-center gap-1.5 text-destructive">
                                            <XCircle className="size-3.5" />
                                            CIF exceeds balance
                                        </span>
                                    )}
                                    {!hasValidationErrors && !cifOver && totals.totalPlanned > 0 && (
                                        <span className="flex items-center gap-1.5 text-muted-foreground">
                                            <CheckCircle2 className="size-3.5 text-emerald-700" />
                                            Ready to save
                                        </span>
                                    )}
                                </div>

                                {/* Action buttons */}
                                <div className="flex items-center gap-2">
                                    <Button variant="ghost" size="sm" onClick={resetChanges}
                                        disabled={saving} className="h-8 gap-1.5 text-xs text-muted-foreground">
                                        <RefreshCw className="size-3.5" />Reset Changes
                                    </Button>
                                    <Button variant="outline" size="sm" onClick={cancelEdit}
                                        disabled={saving} className="h-8 gap-1.5">
                                        <X className="size-4" />Cancel
                                    </Button>
                                    <Button size="sm" onClick={handleSave}
                                        disabled={saving || cifOver || hasValidationErrors}
                                        className="h-8 gap-1.5 px-4">
                                        {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
                                        Save Planning
                                    </Button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
