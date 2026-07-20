/**
 * LedgerTab (displayed as "Balance" tab) — comprehensive financial &
 * utilization summary for a single license.
 *
 * Business logic, APIs and validations are UNCHANGED.
 * This revision is a pure UX modernisation:
 *
 *   Collapsed row  — # | Description | HS Code | Qty | CIF | BOE Used |
 *                    Allotted | [Balance] | ▶
 *   (Item Names and Marking moved into the expanded detail panel.)
 *
 *   Expanded panel — four logical sections:
 *     1. Item Summary   — key metrics at a glance
 *     2. Usage          — BOE cards (≤10) or compact table (>10) +
 *                         Allotment cards / table, with running balance
 *     3. Item Management — Item Names + Marking in 2-col responsive grid
 *     4. Balance Calc   — visual waterfall (Opening → BOE → Allotted → Remaining)
 *
 * APIs (identical to LicenseBalanceModal):
 *   GET  licenses/{id}/item-usage/?item_id=X&type=import
 *   PATCH license-items/{id}/   { items: [...ids] }        ← item-name tags
 *   PATCH license-items/{id}/   { condition_type: "AU"|… } ← marking
 */

import { useState, useCallback } from "react";
import AsyncSelect from "react-select/async";
import Select from "react-select";
import {
    ChevronDown,
    ChevronRight,
    ClipboardCopy,
    FileText,
    Loader2,
    Package,
    Pencil,
    Plus,
    Receipt,
    Tag,
    TrendingDown,
    TrendingUp,
    X,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import ConditionBadge from "../../../components/ConditionBadge";
import api from "../../../api/axios";

// ─────────────────────────────────────────────────────────────────────────────
// Types (unchanged from previous version)
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

interface ItemUsage { boes: BoeEntry[]; allotments: AllotmentEntry[]; }

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
// Business logic (UNCHANGED)
// ─────────────────────────────────────────────────────────────────────────────

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
    label, value, sub, variant = "default", size = "sm",
}: {
    label: string; value: string; sub?: string;
    variant?: "default" | "primary" | "success" | "danger" | "muted";
    size?: "sm" | "lg";
}) {
    const cls = { default: "text-foreground", primary: "text-primary", success: "text-emerald-700", danger: "text-destructive", muted: "text-muted-foreground" }[variant];
    return (
        <div>
            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
            <div className={cn("mt-0.5 tabular-nums font-bold", cls, size === "lg" ? "text-2xl" : "text-sm")}>{value}</div>
            {sub && <div className="text-[10.5px] text-muted-foreground">{sub}</div>}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Copy-to-clipboard
// ─────────────────────────────────────────────────────────────────────────────

async function copyToClipboard(text: string) {
    try { await navigator.clipboard.writeText(text); toast.success("Copied"); }
    catch { toast.error("Failed to copy"); }
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 2 — Usage (BOE + Allotment)
// ─────────────────────────────────────────────────────────────────────────────

const CARD_THRESHOLD = 10; // cards when ≤ this count, table otherwise

function BoeSection({ boes, openingCif }: { boes: BoeEntry[]; openingCif: number }) {
    if (boes.length === 0) return null;

    // Sort by date for running-balance calculation
    const sorted = [...boes].sort((a, b) => {
        if (!a.date && !b.date) return 0;
        if (!a.date) return 1;
        if (!b.date) return -1;
        return String(a.date).localeCompare(String(b.date));
    });

    let running = openingCif;
    const withBalance = sorted.map((b) => {
        running -= Number(b.cif_fc || 0);
        return { ...b, running_balance: Math.max(0, running) };
    });

    const totalCif = boes.reduce((s, b) => s + (Number(b.cif_fc) || 0), 0);
    const totalQty = boes.reduce((s, b) => s + (Number(b.quantity) || 0), 0);

    return (
        <div>
            <div className="mb-3 flex items-center gap-2">
                <div className="flex size-6 shrink-0 items-center justify-center rounded-md bg-amber-100">
                    <Receipt className="size-3.5 text-amber-700" aria-hidden="true" />
                </div>
                <span className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">BOE Utilization</span>
                <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10.5px] font-semibold text-amber-700 ring-1 ring-amber-200">
                    {boes.length} {boes.length === 1 ? "entry" : "entries"}
                </span>
            </div>

            {boes.length <= CARD_THRESHOLD ? (
                /* Cards layout */
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3">
                    {withBalance.map((b) => {
                        const rate = b.quantity > 0 ? Number(b.cif_fc) / b.quantity : 0;
                        return (
                            <div key={b.id} className="group rounded-xl border border-border/60 bg-card p-3 transition-shadow hover:shadow-sm">
                                {/* Reference + copy */}
                                <div className="mb-2 flex items-start justify-between gap-2">
                                    <div className="flex items-center gap-1.5">
                                        <span className="font-mono text-sm font-semibold text-foreground">
                                            {b.bill_of_entry_number || "—"}
                                        </span>
                                        {b.bill_of_entry_number && (
                                            <button type="button" onClick={() => copyToClipboard(b.bill_of_entry_number)}
                                                className="text-muted-foreground/50 hover:text-muted-foreground cursor-pointer opacity-0 transition-opacity group-hover:opacity-100"
                                                title="Copy BOE number" aria-label="Copy BOE number">
                                                <ClipboardCopy className="size-3" />
                                            </button>
                                        )}
                                    </div>
                                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 ring-1 ring-amber-200/60">
                                        BOE
                                    </span>
                                </div>
                                {/* Company */}
                                <div className="mb-1.5 truncate text-xs text-muted-foreground" title={b.company || ""}>{b.company || "—"}</div>
                                {/* Date + port */}
                                {(b.date || b.port) && (
                                    <div className="mb-2 text-[10.5px] text-muted-foreground/70">
                                        {b.date && String(b.date)}
                                        {b.date && b.port && " · "}
                                        {b.port}
                                    </div>
                                )}
                                {/* Metrics */}
                                <div className="grid grid-cols-3 gap-2 border-t border-border/40 pt-2">
                                    <div>
                                        <div className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">Qty</div>
                                        <div className="tabular-nums text-[11.5px] font-semibold text-foreground">{fmtQty(b.quantity)}</div>
                                    </div>
                                    <div>
                                        <div className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">Rate</div>
                                        <div className="tabular-nums text-[11.5px] font-semibold text-foreground">{rate > 0 ? fmtUsd(rate) : "—"}</div>
                                    </div>
                                    <div>
                                        <div className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">CIF</div>
                                        <div className="tabular-nums text-[11.5px] font-semibold text-amber-700">{fmtUsd(b.cif_fc)}</div>
                                    </div>
                                </div>
                                {/* Running balance */}
                                <div className="mt-2 flex items-center justify-between rounded-lg bg-muted/40 px-2 py-1">
                                    <span className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">Balance after</span>
                                    <span className="tabular-nums text-[11.5px] font-bold text-emerald-700">{fmtUsd(b.running_balance)}</span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            ) : (
                /* Compact table for >10 rows */
                <div className="overflow-x-auto rounded-xl border border-border/50">
                    <table className="w-full text-xs">
                        <thead className="bg-muted/50">
                            <tr className="text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                                <th scope="col" className="px-3 py-2">BOE No.</th>
                                <th scope="col" className="px-3 py-2">Company</th>
                                <th scope="col" className="px-3 py-2">Date</th>
                                <th scope="col" className="px-3 py-2 text-right">Qty</th>
                                <th scope="col" className="px-3 py-2 text-right">CIF ($)</th>
                                <th scope="col" className="px-3 py-2 text-right">Balance</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border/30">
                            {withBalance.map((b) => (
                                <tr key={b.id} className="hover:bg-muted/20">
                                    <td className="px-3 py-1.5">
                                        <div className="flex items-center gap-1">
                                            <span className="font-mono text-[10.5px]">{b.bill_of_entry_number || "—"}</span>
                                            {b.bill_of_entry_number && (
                                                <button type="button" onClick={() => copyToClipboard(b.bill_of_entry_number)}
                                                    className="text-muted-foreground/50 hover:text-muted-foreground cursor-pointer" title="Copy">
                                                    <ClipboardCopy className="size-3" />
                                                </button>
                                            )}
                                        </div>
                                    </td>
                                    <td className="px-3 py-1.5 text-[10.5px]">{b.company || "—"}</td>
                                    <td className="px-3 py-1.5 text-[10.5px] text-muted-foreground">{b.date ? String(b.date) : "—"}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums">{fmtQty(b.quantity)}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums text-amber-700">{fmtUsd(b.cif_fc)}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums text-emerald-700">{fmtUsd(b.running_balance)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Section total */}
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-amber-50/60 px-4 py-2.5 ring-1 ring-amber-200/60">
                <span className="text-[10.5px] font-bold uppercase tracking-widest text-amber-700">Total BOE Utilized</span>
                <div className="flex items-center gap-4">
                    <span className="text-[11px] text-amber-700">Qty: <b>{fmtQty(totalQty)}</b></span>
                    <span className="text-base font-bold tabular-nums text-amber-700">{fmtUsd(totalCif)}</span>
                </div>
            </div>
        </div>
    );
}

function AllotmentSection({ allotments }: { allotments: AllotmentEntry[] }) {
    if (allotments.length === 0) return null;

    const totalCif = allotments.reduce((s, a) => s + (Number(a.cif_fc) || 0), 0);
    const totalQty = allotments.reduce((s, a) => s + (Number(a.quantity) || 0), 0);

    return (
        <div>
            <div className="mb-3 flex items-center gap-2">
                <div className="flex size-6 shrink-0 items-center justify-center rounded-md bg-violet-100">
                    <Package className="size-3.5 text-violet-700" aria-hidden="true" />
                </div>
                <span className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">Allotment Usage</span>
                <span className="rounded-full bg-violet-50 px-2 py-0.5 text-[10.5px] font-semibold text-violet-700 ring-1 ring-violet-200">
                    {allotments.length} {allotments.length === 1 ? "entry" : "entries"}
                </span>
            </div>

            {allotments.length <= CARD_THRESHOLD ? (
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                    {allotments.map((a) => {
                        const rate = a.quantity > 0 ? Number(a.cif_fc) / a.quantity : 0;
                        return (
                            <div key={a.id} className="group rounded-xl border border-border/60 bg-card p-3 transition-shadow hover:shadow-sm">
                                <div className="mb-2 flex items-start justify-between gap-2">
                                    <div className="flex items-center gap-1.5">
                                        <span className="font-mono text-sm font-semibold text-foreground">
                                            {a.allotment_number || "—"}
                                        </span>
                                        {a.allotment_number && (
                                            <button type="button" onClick={() => copyToClipboard(a.allotment_number)}
                                                className="text-muted-foreground/50 hover:text-muted-foreground cursor-pointer opacity-0 transition-opacity group-hover:opacity-100"
                                                title="Copy allotment number">
                                                <ClipboardCopy className="size-3" />
                                            </button>
                                        )}
                                    </div>
                                    <span className="rounded-full bg-violet-50 px-2 py-0.5 text-[10px] font-semibold text-violet-700 ring-1 ring-violet-200/60">
                                        Allotment
                                    </span>
                                </div>
                                <div className="mb-2 truncate text-xs text-muted-foreground">{a.company || "—"}</div>
                                <div className="grid grid-cols-3 gap-2 border-t border-border/40 pt-2">
                                    <div>
                                        <div className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">Qty</div>
                                        <div className="tabular-nums text-[11.5px] font-semibold text-foreground">{fmtQty(a.quantity)}</div>
                                    </div>
                                    <div>
                                        <div className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">Rate</div>
                                        <div className="tabular-nums text-[11.5px] font-semibold text-foreground">{rate > 0 ? fmtUsd(rate) : "—"}</div>
                                    </div>
                                    <div>
                                        <div className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">CIF</div>
                                        <div className="tabular-nums text-[11.5px] font-semibold text-violet-700">{fmtUsd(a.cif_fc)}</div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            ) : (
                <div className="overflow-x-auto rounded-xl border border-border/50">
                    <table className="w-full text-xs">
                        <thead className="bg-muted/50">
                            <tr className="text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                                <th scope="col" className="px-3 py-2">Allotment</th>
                                <th scope="col" className="px-3 py-2">Company</th>
                                <th scope="col" className="px-3 py-2 text-right">Qty</th>
                                <th scope="col" className="px-3 py-2 text-right">CIF ($)</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border/30">
                            {allotments.map((a) => (
                                <tr key={a.id} className="hover:bg-muted/20">
                                    <td className="px-3 py-1.5">
                                        <div className="flex items-center gap-1">
                                            <span className="font-mono text-[10.5px]">{a.allotment_number || "—"}</span>
                                            {a.allotment_number && (
                                                <button type="button" onClick={() => copyToClipboard(a.allotment_number)}
                                                    className="text-muted-foreground/50 hover:text-muted-foreground cursor-pointer" title="Copy">
                                                    <ClipboardCopy className="size-3" />
                                                </button>
                                            )}
                                        </div>
                                    </td>
                                    <td className="px-3 py-1.5 text-[10.5px]">{a.company || "—"}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums">{fmtQty(a.quantity)}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums text-violet-700">{fmtUsd(a.cif_fc)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-violet-50/60 px-4 py-2.5 ring-1 ring-violet-200/60">
                <span className="text-[10.5px] font-bold uppercase tracking-widest text-violet-700">Total Allotted</span>
                <div className="flex items-center gap-4">
                    <span className="text-[11px] text-violet-700">Qty: <b>{fmtQty(totalQty)}</b></span>
                    <span className="text-base font-bold tabular-nums text-violet-700">{fmtUsd(totalCif)}</span>
                </div>
            </div>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main LedgerTab
// ─────────────────────────────────────────────────────────────────────────────

export default function LedgerTab({ item, detail, loading }: LedgerTabProps) {
    const [expandedItemId, setExpandedItemId] = useState<number | null>(null);
    const [itemUsage, setItemUsage] = useState<Record<number, ItemUsage>>({});
    const [itemUsageLoading, setItemUsageLoading] = useState<Record<number, boolean>>({});

    // ── Item-tag state (business logic UNCHANGED) ──────────────────────────
    const [localItems, setLocalItems] = useState<ImportItem[]>([]);
    const [addingItemId, setAddingItemId] = useState<number | null>(null);
    const [tagSaving, setTagSaving] = useState<Record<number, boolean>>({});
    const [editingItemId, setEditingItemId] = useState<number | null>(null);
    const [editingTags, setEditingTags] = useState<{ value: number; label: string }[]>([]);
    const [editSaving, setEditSaving] = useState(false);

    // ── Marking state ──────────────────────────────────────────────────────
    const [markingOverrides, setMarkingOverrides] = useState<Record<number, string>>({});
    /** Which row's marking is in edit mode (dropdown visible). */
    const [markingEditingId, setMarkingEditingId] = useState<number | null>(null);

    const detailItems = (detail?.import_license ?? []) as ImportItem[];
    const importItems: ImportItem[] = detailItems.map((r) => ({
        ...r,
        items_detail: localItems.find((l) => l.id === r.id)?.items_detail ?? r.items_detail ?? [],
        condition_type: markingOverrides[r.id] !== undefined ? markingOverrides[r.id] : (r.condition_type ?? ""),
    }));

    const commonBalance = isCommonCifBalance(importItems);

    const totalCifFc   = importItems.reduce((s, r) => s + (Number(r.cif_fc)         || 0), 0);
    const totalAllotted = importItems.reduce((s, r) => s + (Number(r.allotted_value) || 0), 0);
    const totalDebited  = importItems.reduce((s, r) => s + (Number(r.debited_value)  || 0), 0);
    const totalBalance  = importItems.reduce((s, r) => s + (Number(r.balance_cif_fc) || 0), 0);
    const displayBalance = commonBalance ? Number(item.get_balance_cif ?? 0) : totalBalance;

    // "License Value" = sum of import items' cif_fc when items carry individual CIF.
    // Many DFIA/multi-item licenses store cif_fc = 0 on every import item and instead
    // track the total on the export license (e.g. license 0310736639: export cif_fc =
    // $334,909.19 while all import cif_fc = $0.00).  Fall back to the export total so
    // "License Value" never shows $0.00 for a valid license.
    const exportItems  = ((detail as Record<string, unknown>)?.export_license ?? []) as Array<{ cif_fc?: number | string | null; fob_fc?: number | string | null }>;
    const exportCifFc  = exportItems.reduce((s, e) => s + (Number(e.cif_fc ?? e.fob_fc) || 0), 0);
    const licenseValue = totalCifFc > 0 ? totalCifFc : exportCifFc;

    // ── Usage fetch (UNCHANGED) ────────────────────────────────────────────
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
            } catch { toast.error("Failed to load item usage details"); }
            finally { setItemUsageLoading((prev) => ({ ...prev, [id]: false })); }
        }
    }, [item.id, itemUsage, itemUsageLoading]);

    // ── Item-tag helpers (UNCHANGED) ───────────────────────────────────────
    const loadItemOptions = useCallback(async (input: string) => {
        if (input.length < 2) return [];
        try {
            const { data } = await api.get("masters/item-names/", { params: { search: input } });
            const results = Array.isArray(data.results) ? data.results : [];
            return results.map((i: { id: number; name: string }) => ({ value: i.id, label: i.name }));
        } catch { return []; }
    }, []);

    const patchItemTags = useCallback(async (rowId: number, newDetails: ItemDetail[]) => {
        const itemIds = newDetails.map((d) => d.id);
        setLocalItems((prev) => {
            const existing = prev.find((p) => p.id === rowId);
            if (existing) return prev.map((p) => p.id === rowId ? { ...p, items_detail: newDetails } : p);
            return [...prev, { ...detailItems.find((r) => r.id === rowId)!, items_detail: newDetails }];
        });
        setTagSaving((s) => ({ ...s, [rowId]: true }));
        try {
            await api.patch(`license-items/${rowId}/`, { items: itemIds });
        } catch (err: unknown) {
            const d = (err as { response?: { data?: { detail?: string; error?: string } } })?.response?.data;
            toast.error(d?.detail || d?.error || "Failed to update items");
            setLocalItems((prev) => prev.filter((p) => p.id !== rowId));
        } finally { setTagSaving((s) => ({ ...s, [rowId]: false })); }
    }, [detailItems]);

    const handleAddItemTag = useCallback((rowId: number, option: { value: number; label: string } | null) => {
        setAddingItemId(null);
        if (!option) return;
        const current = importItems.find((r) => r.id === rowId)?.items_detail ?? [];
        if (current.some((d) => d.id === option.value)) return;
        patchItemTags(rowId, [...current, { id: option.value, name: option.label }]);
    }, [importItems, patchItemTags]);

    const handleRemoveItemTag = useCallback((rowId: number, tagId: number) => {
        const current = importItems.find((r) => r.id === rowId)?.items_detail ?? [];
        patchItemTags(rowId, current.filter((d) => d.id !== tagId));
    }, [importItems, patchItemTags]);

    const handleSaveEditTags = useCallback(async (rowId: number) => {
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
            toast.success("Items updated");
            setEditingItemId(null);
        } catch (err: unknown) {
            const d = (err as { response?: { data?: { detail?: string; error?: string } } })?.response?.data;
            toast.error(d?.detail || d?.error || "Failed to update items");
        } finally { setEditSaving(false); }
    }, [editingTags, detailItems]);

    // ── Marking handler (UNCHANGED) ────────────────────────────────────────
    const handleConditionTypeChange = useCallback(async (rowId: number, newValue: string) => {
        const previous = markingOverrides[rowId] !== undefined
            ? markingOverrides[rowId]
            : (detailItems.find((r) => r.id === rowId)?.condition_type ?? "");
        if (previous === newValue) return;
        setMarkingOverrides((prev) => ({ ...prev, [rowId]: newValue }));
        setMarkingEditingId(null);
        try {
            await api.patch(`license-items/${rowId}/`, { condition_type: newValue || null });
            toast.success("License marking updated");
        } catch (err: unknown) {
            setMarkingOverrides((prev) => ({ ...prev, [rowId]: previous }));
            const d = (err as { response?: { data?: { detail?: string; condition_type?: string[] } } })?.response?.data;
            toast.error(d?.detail || d?.condition_type?.[0] || "Failed to update marking");
        }
    }, [markingOverrides, detailItems]);

    // ── Column counts ──────────────────────────────────────────────────────
    // Collapsed: # | Desc | HS | Qty | CIF | BOE | Allotted | [Balance] | ▶
    const collapsedColCount = commonBalance ? 8 : 9;

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
                    <FileText className="size-5 text-muted-foreground/60" />
                </div>
                <div className="text-sm font-medium text-muted-foreground">No import items</div>
                <div className="mt-1 text-xs text-muted-foreground/70">No import line items are linked to this license.</div>
            </div>
        );
    }

    const balancePct = licenseValue > 0 ? (displayBalance / licenseValue) * 100 : 0;

    return (
        <div className="space-y-4 py-3">
            {/* ── License Summary ──────────────────────────────────── */}
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
                    <SummaryMetric label="License Value" value={fmtUsd(licenseValue)} />
                    <SummaryMetric label="Balance CIF" value={fmtUsd(displayBalance)} variant="primary"
                        sub={commonBalance ? "shared across items" : undefined} />
                    <SummaryMetric label="BOE Utilized" value={fmtUsd(totalDebited)} variant="danger" />
                    <SummaryMetric label="Allotted" value={fmtUsd(totalAllotted)} variant="muted" />
                    <SummaryMetric label="Ledger Date" value={String(item.ledger_date ?? "—")} variant="success" />
                </div>
                {licenseValue > 0 && (
                    <div className="border-t border-border/30 px-4 pb-3 pt-2">
                        <div className="mb-1 flex justify-between text-[10px] text-muted-foreground">
                            <span>Utilization</span>
                            <span>{(100 - balancePct).toFixed(1)}% used · {balancePct.toFixed(1)}% remaining</span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                            <div className="h-full rounded-full bg-primary transition-[width] duration-500"
                                style={{ width: `${Math.min(100 - balancePct, 100)}%` }} />
                        </div>
                    </div>
                )}
            </div>

            {/* ── Import Items table ────────────────────────────────── */}
            <div className="overflow-hidden rounded-xl border border-border/60">
                <div className="border-b border-border/50 bg-muted/30 px-4 py-2.5">
                    <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Import Items — click a row to expand full details
                    </div>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur-sm">
                            <tr className="border-b border-border text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                <th scope="col" className="w-8 px-3 py-2.5">#</th>
                                <th scope="col" className="px-3 py-2.5">Description</th>
                                <th scope="col" className="hidden px-3 py-2.5 sm:table-cell">HS Code</th>
                                <th scope="col" className="px-3 py-2.5 text-right">Qty</th>
                                <th scope="col" className="px-3 py-2.5 text-right">CIF ($)</th>
                                <th scope="col" className="px-3 py-2.5 text-right">BOE Used</th>
                                <th scope="col" className="px-3 py-2.5 text-right">Allotted</th>
                                {!commonBalance && <th scope="col" className="px-3 py-2.5 text-right">Balance ($)</th>}
                                <th scope="col" className="w-7 px-3 py-2.5" aria-label="Expand" />
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
                                const usage = itemUsage[r.id];
                                const usageLoading = itemUsageLoading[r.id];

                                return (
                                    <>
                                        {/* ── Collapsed row ─────────────────────────────────── */}
                                        <tr key={r.id}
                                            onClick={() => handleRowClick(r)}
                                            className={cn(
                                                "cursor-pointer border-b border-border/40 transition-colors",
                                                isExpanded ? "bg-primary/5" : "hover:bg-muted/30"
                                            )}
                                            aria-expanded={isExpanded}
                                        >
                                            <td className="px-3 py-2.5 font-mono text-xs text-muted-foreground">{r.serial_number}</td>
                                            <td className="px-3 py-2.5">
                                                <div className="max-w-[200px] truncate text-sm font-medium" title={r.description}>{r.description || "—"}</div>
                                                <div className="mt-0.5 text-[10px] text-muted-foreground">{r.unit}</div>
                                            </td>
                                            <td className="hidden px-3 py-2.5 font-mono text-xs text-muted-foreground sm:table-cell">{r.hs_code_label || "—"}</td>
                                            <td className="px-3 py-2.5 text-right tabular-nums text-xs">{fmtQty(r.quantity)}</td>
                                            <td className="px-3 py-2.5 text-right tabular-nums text-xs">{fmtUsd(r.cif_fc)}</td>
                                            <td className="px-3 py-2.5 text-right tabular-nums text-xs">
                                                {r.debited_value != null && Number(r.debited_value) > 0
                                                    ? <span className="text-amber-700">{fmtUsd(r.debited_value)}</span>
                                                    : <span className="text-muted-foreground/40">—</span>}
                                            </td>
                                            <td className="px-3 py-2.5 text-right tabular-nums text-xs">
                                                {r.allotted_value != null && Number(r.allotted_value) > 0
                                                    ? <span className="text-violet-700">{fmtUsd(r.allotted_value)}</span>
                                                    : <span className="text-muted-foreground/40">—</span>}
                                            </td>
                                            {!commonBalance && (
                                                <td className="px-3 py-2.5 text-right tabular-nums text-xs">
                                                    <span className={cn("font-semibold",
                                                        balPct > 50 ? "text-emerald-700" : balPct > 20 ? "text-amber-700" : "text-destructive"
                                                    )}>{fmtUsd(balCif)}</span>
                                                </td>
                                            )}
                                            <td className="px-3 py-2.5 text-center">
                                                <ChevronRight className={cn(
                                                    "size-3.5 text-muted-foreground/50 transition-transform duration-200",
                                                    isExpanded && "rotate-90"
                                                )} aria-hidden="true" />
                                            </td>
                                        </tr>

                                        {/* ── Expanded detail panel ─────────────────────────── */}
                                        {isExpanded && (
                                            <tr key={`${r.id}-detail`} className="border-b border-border/40">
                                                <td colSpan={collapsedColCount} className="px-0 py-0">
                                                    <div className="bg-muted/10 px-4 pb-5 pt-4">
                                                        {usageLoading ? (
                                                            <div className="space-y-3">
                                                                <Skeleton className="h-24 w-full rounded-xl" />
                                                                <Skeleton className="h-32 w-full rounded-xl" />
                                                            </div>
                                                        ) : (
                                                            <div className="space-y-4">
                                                                {/* ══ Section 1: Item Summary ════════════════════════ */}
                                                                <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
                                                                    <div className="border-b border-border/50 bg-muted/20 px-4 py-2">
                                                                        <div className="text-[10.5px] font-bold uppercase tracking-widest text-muted-foreground">
                                                                            Item Summary
                                                                        </div>
                                                                    </div>
                                                                    <div className="grid grid-cols-2 gap-x-6 gap-y-3 px-4 py-3 sm:grid-cols-3 lg:grid-cols-4">
                                                                        <div className="lg:col-span-1">
                                                                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Item</div>
                                                                            <div className="mt-0.5 text-sm font-semibold text-foreground">{r.description || "—"}</div>
                                                                            {r.hs_code_label && <div className="text-[10.5px] font-mono text-muted-foreground">{r.hs_code_label}</div>}
                                                                        </div>
                                                                        <SummaryMetric label="Available Qty" value={fmtQty(r.available_quantity)} />
                                                                        <SummaryMetric label="Opening CIF" value={fmtUsd(r.cif_fc)} />
                                                                        <SummaryMetric label="Current Balance CIF" value={fmtUsd(r.balance_cif_fc)} variant={balPct > 50 ? "success" : balPct > 20 ? "default" : "danger"} />
                                                                        <SummaryMetric label="BOE Used" value={fmtUsd(r.debited_value)} variant="danger"
                                                                            sub={r.debited_quantity != null ? `${fmtQty(r.debited_quantity)} ${r.unit}` : undefined} />
                                                                        <SummaryMetric label="Allotted" value={fmtUsd(r.allotted_value)} variant="muted"
                                                                            sub={r.allotted_quantity != null ? `${fmtQty(r.allotted_quantity)} ${r.unit}` : undefined} />
                                                                        <div>
                                                                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Remaining Balance</div>
                                                                            <div className={cn("mt-0.5 text-xl font-bold tabular-nums",
                                                                                balCif > 0 ? "text-emerald-700" : "text-muted-foreground")}>
                                                                                {fmtUsd(balCif)}
                                                                            </div>
                                                                            <div className="text-[10.5px] text-muted-foreground">{fmtInr(r.balance_cif_fc)}</div>
                                                                        </div>
                                                                    </div>
                                                                </div>

                                                                {/* ══ Section 2: Usage ════════════════════════════════ */}
                                                                {(usage?.boes?.length || usage?.allotments?.length) ? (
                                                                    <div className="rounded-xl border border-border/60 bg-card p-4 space-y-5">
                                                                        <div className="text-[10.5px] font-bold uppercase tracking-widest text-muted-foreground">Usage</div>
                                                                        <BoeSection boes={usage?.boes ?? []} openingCif={Number(r.cif_fc || 0)} />
                                                                        {(usage?.boes?.length > 0 && usage?.allotments?.length > 0) && (
                                                                            <div className="border-t border-border/40" />
                                                                        )}
                                                                        <AllotmentSection allotments={usage?.allotments ?? []} />
                                                                    </div>
                                                                ) : usage && (
                                                                    <div className="rounded-xl border border-border/60 bg-card px-4 py-5 text-center text-sm text-muted-foreground">
                                                                        No BOE or allotment usage recorded for this item.
                                                                    </div>
                                                                )}

                                                                {/* ══ Section 3: Item Management ══════════════════════ */}
                                                                <div className="grid gap-3 lg:grid-cols-2">
                                                                    {/* Item Names card */}
                                                                    <div className="rounded-xl border border-border/60 bg-card p-4">
                                                                        <div className="mb-3 flex items-center gap-2">
                                                                            <div className="flex size-6 shrink-0 items-center justify-center rounded-md bg-primary/10">
                                                                                <Tag className="size-3.5 text-primary" />
                                                                            </div>
                                                                            <span className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">Item Names</span>
                                                                            {tags.length > 0 && (
                                                                                <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">
                                                                                    {tags.length}
                                                                                </span>
                                                                            )}
                                                                        </div>

                                                                        {editingItemId === r.id ? (
                                                                            <div className="space-y-2">
                                                                                <AsyncSelect isMulti cacheOptions
                                                                                    loadOptions={loadItemOptions}
                                                                                    value={editingTags}
                                                                                    onChange={(v) => setEditingTags(v as typeof editingTags)}
                                                                                    placeholder="Search item names…"
                                                                                    menuPortalTarget={document.body}
                                                                                    menuPosition="fixed"
                                                                                    styles={{
                                                                                        control: (b) => ({ ...b, minHeight: 36, fontSize: 13, borderRadius: 8 }),
                                                                                        menuPortal: (b) => ({ ...b, zIndex: 9999 }),
                                                                                        menu: (b) => ({ ...b, minWidth: 240 }),
                                                                                    }}
                                                                                />
                                                                                <div className="flex gap-2">
                                                                                    <Button size="sm" onClick={() => handleSaveEditTags(r.id)}
                                                                                        disabled={editSaving} className="h-7 text-xs gap-1.5">
                                                                                        {editSaving ? <Loader2 className="size-3.5 animate-spin" /> : null}Save
                                                                                    </Button>
                                                                                    <Button variant="outline" size="sm" onClick={() => setEditingItemId(null)}
                                                                                        disabled={editSaving} className="h-7 text-xs">Cancel</Button>
                                                                                </div>
                                                                            </div>
                                                                        ) : (
                                                                            <div>
                                                                                {/* Tag chips */}
                                                                                <div className="flex flex-wrap gap-1.5">
                                                                                    {tags.map((d) => (
                                                                                        <span key={d.id} className="inline-flex items-center gap-1 rounded-full bg-primary/5 px-2.5 py-1 text-[11.5px] font-medium text-foreground ring-1 ring-primary/20">
                                                                                            {d.name}
                                                                                            <button type="button"
                                                                                                onClick={() => handleRemoveItemTag(r.id, d.id)}
                                                                                                disabled={tagSaving[r.id]}
                                                                                                className="ml-0.5 text-muted-foreground/50 hover:text-destructive cursor-pointer"
                                                                                                aria-label={`Remove ${d.name}`}>
                                                                                                <X className="size-3" />
                                                                                            </button>
                                                                                        </span>
                                                                                    ))}
                                                                                    {tags.length === 0 && addingItemId !== r.id && (
                                                                                        <span className="text-sm text-muted-foreground/60 italic">No item names assigned</span>
                                                                                    )}
                                                                                </div>

                                                                                {/* Add / Edit controls */}
                                                                                <div className="mt-3 flex items-center gap-2">
                                                                                    {addingItemId === r.id ? (
                                                                                        <div className="w-full min-w-[200px]">
                                                                                            <AsyncSelect autoFocus cacheOptions defaultOptions
                                                                                                loadOptions={loadItemOptions}
                                                                                                onChange={(opt) => handleAddItemTag(r.id, opt as { value: number; label: string } | null)}
                                                                                                onBlur={() => setAddingItemId(null)}
                                                                                                placeholder="Search to add item…"
                                                                                                menuPortalTarget={document.body}
                                                                                                menuPosition="fixed"
                                                                                                styles={{
                                                                                                    control: (b) => ({ ...b, minHeight: 34, fontSize: 13, borderRadius: 8 }),
                                                                                                    menuPortal: (b) => ({ ...b, zIndex: 9999 }),
                                                                                                    menu: (b) => ({ ...b, minWidth: 240 }),
                                                                                                }}
                                                                                            />
                                                                                        </div>
                                                                                    ) : (
                                                                                        <>
                                                                                            <Button variant="outline" size="sm"
                                                                                                onClick={() => setAddingItemId(r.id)}
                                                                                                disabled={tagSaving[r.id]}
                                                                                                className="h-7 gap-1.5 text-xs">
                                                                                                <Plus className="size-3.5" />Add Item Name
                                                                                            </Button>
                                                                                            {tags.length > 0 && (
                                                                                                <Button variant="ghost" size="sm"
                                                                                                    onClick={() => {
                                                                                                        setEditingItemId(r.id);
                                                                                                        setEditingTags(tags.map((d) => ({ value: d.id, label: d.name })));
                                                                                                    }}
                                                                                                    className="h-7 gap-1.5 text-xs text-muted-foreground">
                                                                                                    <Pencil className="size-3.5" />Edit All
                                                                                                </Button>
                                                                                            )}
                                                                                            {tagSaving[r.id] && <Loader2 className="size-4 animate-spin text-muted-foreground" />}
                                                                                        </>
                                                                                    )}
                                                                                </div>
                                                                            </div>
                                                                        )}
                                                                    </div>

                                                                    {/* Marking card */}
                                                                    <div className="rounded-xl border border-border/60 bg-card p-4">
                                                                        <div className="mb-3 flex items-center gap-2">
                                                                            <div className="flex size-6 shrink-0 items-center justify-center rounded-md bg-muted">
                                                                                <FileText className="size-3.5 text-muted-foreground" />
                                                                            </div>
                                                                            <span className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">Marking</span>
                                                                        </div>

                                                                        {markingEditingId === r.id ? (
                                                                            <div className="space-y-2">
                                                                                <Select
                                                                                    options={MARKING_OPTIONS}
                                                                                    value={MARKING_OPTIONS.find((o) => o.value === currentMarking) ?? MARKING_OPTIONS[0]}
                                                                                    onChange={(sel) => handleConditionTypeChange(r.id, sel?.value ?? "")}
                                                                                    isSearchable={false}
                                                                                    menuPortalTarget={document.body}
                                                                                    menuPosition="fixed"
                                                                                    styles={{
                                                                                        control: (b) => ({ ...b, minHeight: 36, fontSize: 13.5, borderRadius: 8 }),
                                                                                        menuPortal: (b) => ({ ...b, zIndex: 9999 }),
                                                                                    }}
                                                                                />
                                                                                <Button variant="outline" size="sm" onClick={() => setMarkingEditingId(null)}
                                                                                    className="h-7 text-xs gap-1.5">
                                                                                    <X className="size-3.5" />Cancel
                                                                                </Button>
                                                                            </div>
                                                                        ) : (
                                                                            <div>
                                                                                {/* Current marking display */}
                                                                                {currentMarking ? (
                                                                                    <div className="mb-3">
                                                                                        <div className="text-[10.5px] text-muted-foreground mb-1">Current Marking</div>
                                                                                        <div className="flex items-center gap-2">
                                                                                            <ConditionBadge type={currentMarking} size="sm" />
                                                                                            <span className="text-xl font-bold text-foreground">{currentMarking}</span>
                                                                                        </div>
                                                                                    </div>
                                                                                ) : (
                                                                                    <div className="mb-3 text-sm text-muted-foreground italic">No marking assigned</div>
                                                                                )}
                                                                                <Button variant="outline" size="sm"
                                                                                    onClick={() => setMarkingEditingId(r.id)}
                                                                                    className="h-7 gap-1.5 text-xs">
                                                                                    <Pencil className="size-3.5" />Edit Marking
                                                                                </Button>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                </div>

                                                                {/* ══ Section 4: Balance Calculation ══════════════════ */}
                                                                <div className="overflow-hidden rounded-xl border border-primary/20 bg-primary/5">
                                                                    <div className="border-b border-primary/20 px-4 py-2">
                                                                        <div className="text-[10.5px] font-bold uppercase tracking-widest text-primary">Balance Calculation</div>
                                                                    </div>
                                                                    <div className="px-6 py-4">
                                                                        {/* Waterfall */}
                                                                        <div className="flex flex-col gap-0">
                                                                            {/* Opening */}
                                                                            <div className="flex items-center justify-between">
                                                                                <span className="text-sm text-muted-foreground">Opening Balance</span>
                                                                                <span className="font-mono text-sm font-semibold text-foreground">{fmtUsd(r.cif_fc)}</span>
                                                                            </div>
                                                                            {/* BOE */}
                                                                            <div className="my-1.5 flex items-center gap-2 text-muted-foreground/40">
                                                                                <div className="flex-1 border-t border-dashed border-border/50" />
                                                                                <ChevronDown className="size-3.5" />
                                                                                <div className="flex-1 border-t border-dashed border-border/50" />
                                                                            </div>
                                                                            <div className="flex items-center justify-between">
                                                                                <span className="flex items-center gap-1.5 text-sm text-amber-700">
                                                                                    <span className="text-muted-foreground">−</span> BOE Utilized
                                                                                </span>
                                                                                <span className="font-mono text-sm font-semibold text-amber-700">{fmtUsd(r.debited_value)}</span>
                                                                            </div>
                                                                            {/* Allotted */}
                                                                            <div className="my-1.5 flex items-center gap-2 text-muted-foreground/40">
                                                                                <div className="flex-1 border-t border-dashed border-border/50" />
                                                                                <ChevronDown className="size-3.5" />
                                                                                <div className="flex-1 border-t border-dashed border-border/50" />
                                                                            </div>
                                                                            <div className="flex items-center justify-between">
                                                                                <span className="flex items-center gap-1.5 text-sm text-violet-700">
                                                                                    <span className="text-muted-foreground">−</span> Allotted
                                                                                </span>
                                                                                <span className="font-mono text-sm font-semibold text-violet-700">{fmtUsd(r.allotted_value)}</span>
                                                                            </div>
                                                                            {/* Remaining */}
                                                                            <div className="mt-3 flex items-center justify-between rounded-xl bg-card px-4 py-3">
                                                                                <div className="flex items-center gap-2">
                                                                                    <TrendingUp className={cn("size-5", balCif > 0 ? "text-emerald-700" : "text-muted-foreground")} />
                                                                                    <div>
                                                                                        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Remaining Balance</div>
                                                                                        <div className="text-[10.5px] text-muted-foreground">{fmtInr(r.balance_cif_fc)}</div>
                                                                                    </div>
                                                                                </div>
                                                                                <div className={cn("text-2xl font-extrabold tabular-nums",
                                                                                    balCif > 0 ? "text-emerald-700" : "text-muted-foreground")}>
                                                                                    {fmtUsd(balCif)}
                                                                                </div>
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </>
                                );
                            })}
                        </tbody>

                        {/* Totals footer */}
                        <tfoot className="border-t-2 border-border bg-muted/40 text-sm font-semibold">
                            <tr>
                                <td colSpan={4} className="px-3 py-2.5 text-right text-xs uppercase tracking-wider text-muted-foreground">Totals</td>
                                <td className="px-3 py-2.5 text-right tabular-nums text-xs">{fmtUsd(licenseValue)}</td>
                                <td className="px-3 py-2.5 text-right tabular-nums text-xs text-amber-700">{fmtUsd(totalDebited)}</td>
                                <td className="px-3 py-2.5 text-right tabular-nums text-xs text-violet-700">{fmtUsd(totalAllotted)}</td>
                                {!commonBalance && <td className="px-3 py-2.5 text-right tabular-nums text-xs text-primary">{fmtUsd(totalBalance)}</td>}
                                <td />
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>

            {/* ── Balance Summary ────────────────────────────────────── */}
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
                            <div className="text-sm font-bold tabular-nums text-foreground">{fmtUsd(licenseValue)}</div>
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
