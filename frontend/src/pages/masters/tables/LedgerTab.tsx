/**
 * LedgerTab — comprehensive financial & utilization summary for a single license.
 *
 * Sections (top → bottom):
 *   1. License Summary card — key financial metrics at a glance
 *   2. Import Items table — every import line with allotment + BOE utilization
 *      (each row is expandable; expansion lazy-fetches item-usage data)
 *   3. Balance Summary — visual breakdown of opening vs. utilized vs. remaining
 *
 * All data comes from:
 *   • `detail.import_license[]` — already fetched on first accordion expand
 *   • `GET licenses/{id}/item-usage/?item_id=X&type=import` — lazy per row
 */

import { useState, useCallback } from "react";
import {
    ChevronRight,
    FileText,
    Package,
    Receipt,
    TrendingDown,
    TrendingUp,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import api from "../../../api/axios";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface ImportItem {
    id: number;
    serial_number: number;
    description: string;
    hs_code_label?: string;
    quantity: number;
    unit: string;
    cif_fc: number;
    cif_inr?: number;
    allotted_quantity?: number;
    allotted_value?: number;
    debited_quantity?: number;
    debited_value?: number;
    balance_cif_fc?: number;
    available_quantity?: number;
    available_value?: number;
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
    exporter_name: string | null;
    port_name: string | null;
    get_norm_class: string | null;
    license_date: string | null;
    license_expiry_date: string | null;
    [key: string]: unknown;
}

interface LedgerTabProps {
    item: ListItem;
    detail: LicenseDetail | null;
    loading: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function fmtUsd(v: number | undefined | null, dp = 2): string {
    if (v === null || v === undefined) return "—";
    const n = Number(v);
    if (isNaN(n)) return "—";
    return `$${n.toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
}

function fmtInr(v: number | undefined | null): string {
    if (v === null || v === undefined) return "—";
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
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function SummaryMetric({
    label,
    value,
    sub,
    variant = "default",
}: {
    label: string;
    value: string;
    sub?: string;
    variant?: "default" | "primary" | "success" | "danger" | "muted";
}) {
    const valueClasses = {
        default: "text-foreground",
        primary: "text-primary",
        success: "text-emerald-700",
        danger: "text-destructive",
        muted: "text-muted-foreground",
    }[variant];

    return (
        <div>
            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                {label}
            </div>
            <div className={cn("mt-0.5 text-base font-bold tabular-nums", valueClasses)}>
                {value}
            </div>
            {sub && <div className="text-[10.5px] text-muted-foreground">{sub}</div>}
        </div>
    );
}

function UsageDetail({
    usage,
    loading,
}: {
    usage: ItemUsage | undefined;
    loading: boolean | undefined;
}) {
    if (loading) {
        return (
            <div className="space-y-2 p-3">
                <Skeleton className="h-3 w-1/2" />
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="h-3 w-2/3" />
            </div>
        );
    }

    const boes = usage?.boes ?? [];
    const allotments = usage?.allotments ?? [];

    if (boes.length === 0 && allotments.length === 0) {
        return (
            <div className="px-4 py-3 text-sm text-muted-foreground">
                No BOE or allotment usage recorded for this item.
            </div>
        );
    }

    return (
        <div className="grid gap-4 px-4 py-3 lg:grid-cols-2">
            {/* BOE usage */}
            {boes.length > 0 && (
                <div>
                    <div className="mb-1.5 flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        <Receipt className="size-3.5" aria-hidden="true" />
                        BOE Utilization
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
                            {boes.map((b) => (
                                <tr key={b.id} className="hover:bg-muted/20">
                                    <td className="py-1 pr-3 font-mono text-[10.5px]">
                                        {b.bill_of_entry_number || "—"}
                                        {b.date && (
                                            <div className="text-muted-foreground">{String(b.date)}</div>
                                        )}
                                    </td>
                                    <td className="py-1 pr-3 text-[10.5px]">{b.company || "—"}</td>
                                    <td className="py-1 pr-3 text-right tabular-nums">{fmtQty(b.quantity)}</td>
                                    <td className="py-1 text-right tabular-nums text-amber-700">{fmtUsd(b.cif_fc)}</td>
                                </tr>
                            ))}
                        </tbody>
                        <tfoot>
                            <tr className="border-t border-border font-semibold">
                                <td colSpan={3} className="pr-3 pt-1 text-right text-[10.5px] text-muted-foreground">Total BOE</td>
                                <td className="pt-1 text-right tabular-nums text-[10.5px] text-amber-700">
                                    {fmtUsd(boes.reduce((s, b) => s + (Number(b.cif_fc) || 0), 0))}
                                </td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            )}

            {/* Allotment usage */}
            {allotments.length > 0 && (
                <div>
                    <div className="mb-1.5 flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        <Package className="size-3.5" aria-hidden="true" />
                        Allotment Usage
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
                            {allotments.map((a) => (
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
                                <td className="pt-1 text-right tabular-nums text-[10.5px] text-violet-700">
                                    {fmtUsd(allotments.reduce((s, a) => s + (Number(a.cif_fc) || 0), 0))}
                                </td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            )}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main LedgerTab component
// ─────────────────────────────────────────────────────────────────────────────

export default function LedgerTab({ item, detail, loading }: LedgerTabProps) {
    const [expandedItemId, setExpandedItemId] = useState<number | null>(null);
    const [itemUsage, setItemUsage] = useState<Record<number, ItemUsage>>({});
    const [itemUsageLoading, setItemUsageLoading] = useState<Record<number, boolean>>({});

    const importItems = detail?.import_license ?? [];

    // Aggregate totals from import_license data
    const totalCifFc = importItems.reduce((s, r) => s + (Number(r.cif_fc) || 0), 0);
    const totalAllotted = importItems.reduce((s, r) => s + (Number(r.allotted_value) || 0), 0);
    const totalDebited = importItems.reduce((s, r) => s + (Number(r.debited_value) || 0), 0);
    const totalBalance = importItems.reduce((s, r) => s + (Number(r.balance_cif_fc) || 0), 0);

    const handleRowClick = useCallback(async (importItem: ImportItem) => {
        const id = importItem.id;
        setExpandedItemId((prev) => (prev === id ? null : id));
        // Lazy-fetch usage data on first expand
        if (!itemUsage[id] && !itemUsageLoading[id]) {
            setItemUsageLoading((prev) => ({ ...prev, [id]: true }));
            try {
                const { data } = await api.get(`licenses/${item.id}/item-usage/`, {
                    params: { item_id: id, type: "import" },
                });
                setItemUsage((prev) => ({ ...prev, [id]: data }));
            } catch {
                toast.error("Failed to load item usage details");
            } finally {
                setItemUsageLoading((prev) => ({ ...prev, [id]: false }));
            }
        }
    }, [item.id, itemUsage, itemUsageLoading]);

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

    const balancePct = totalCifFc > 0 ? (totalBalance / totalCifFc) * 100 : 0;

    return (
        <div className="space-y-4 py-3">
            {/* ── 1. License Summary ───────────────────────────────── */}
            <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
                <div className="border-b border-border/50 px-4 py-2.5">
                    <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        License Summary
                    </div>
                </div>
                <div className="grid grid-cols-2 gap-x-6 gap-y-3 px-4 py-3 sm:grid-cols-3 lg:grid-cols-6">
                    <SummaryMetric label="License No." value={item.license_number || "—"} />
                    <SummaryMetric label="License Value" value={fmtUsd(totalCifFc)} />
                    <SummaryMetric label="Balance CIF" value={fmtUsd(totalBalance)} variant="primary" />
                    <SummaryMetric label="BOE Utilized" value={fmtUsd(totalDebited)} variant="danger" />
                    <SummaryMetric label="Allotted" value={fmtUsd(totalAllotted)} variant="muted" />
                    <SummaryMetric label="Ledger Date" value={item.ledger_date || "—"} variant="success" />
                </div>
                {/* Utilization progress bar */}
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
                                aria-label={`${(100 - balancePct).toFixed(1)}% utilized`}
                            />
                        </div>
                    </div>
                )}
            </div>

            {/* ── 2. Import Items Table ─────────────────────────────── */}
            <div className="overflow-hidden rounded-xl border border-border/60">
                <div className="border-b border-border/50 bg-muted/30 px-4 py-2.5">
                    <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Import Items — click a row to see BOE &amp; Allotment details
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
                                <th scope="col" className="px-3 py-2.5 text-right">Balance ($)</th>
                                <th scope="col" className="px-3 py-2.5 w-6" aria-label="Expand" />
                            </tr>
                        </thead>
                        <tbody>
                            {importItems.map((r) => {
                                const isExpanded = expandedItemId === r.id;
                                const balCif = Number(r.balance_cif_fc || 0);
                                const origCif = Number(r.cif_fc || 0);
                                const balPct = origCif > 0 ? (balCif / origCif) * 100 : 0;

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
                                            <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                                                {r.serial_number}
                                            </td>
                                            <td className="px-3 py-2">
                                                <div className="max-w-[180px] truncate text-sm font-medium" title={r.description}>
                                                    {r.description || "—"}
                                                </div>
                                                <div className="mt-0.5 text-[10px] text-muted-foreground">{r.unit}</div>
                                            </td>
                                            <td className="hidden px-3 py-2 font-mono text-xs text-muted-foreground sm:table-cell">
                                                {r.hs_code_label || "—"}
                                            </td>
                                            <td className="px-3 py-2 text-right tabular-nums text-xs">
                                                {fmtQty(r.quantity)}
                                            </td>
                                            <td className="px-3 py-2 text-right tabular-nums text-xs">
                                                {fmtUsd(r.cif_fc)}
                                            </td>
                                            <td className="px-3 py-2 text-right tabular-nums text-xs">
                                                {r.debited_value != null && Number(r.debited_value) > 0 ? (
                                                    <span className="text-amber-700">
                                                        {fmtUsd(r.debited_value)}
                                                    </span>
                                                ) : (
                                                    <span className="text-muted-foreground/40">—</span>
                                                )}
                                            </td>
                                            <td className="px-3 py-2 text-right tabular-nums text-xs">
                                                {r.allotted_value != null && Number(r.allotted_value) > 0 ? (
                                                    <span className="text-violet-700">
                                                        {fmtUsd(r.allotted_value)}
                                                    </span>
                                                ) : (
                                                    <span className="text-muted-foreground/40">—</span>
                                                )}
                                            </td>
                                            <td className="px-3 py-2 text-right tabular-nums text-xs">
                                                <span className={cn(
                                                    "font-semibold",
                                                    balPct > 50 ? "text-emerald-700" : balPct > 20 ? "text-amber-700" : "text-destructive"
                                                )}>
                                                    {fmtUsd(balCif)}
                                                </span>
                                            </td>
                                            <td className="px-3 py-2 text-center">
                                                <ChevronRight
                                                    className={cn(
                                                        "size-3.5 text-muted-foreground/50 transition-transform",
                                                        isExpanded && "rotate-90"
                                                    )}
                                                    aria-hidden="true"
                                                />
                                            </td>
                                        </tr>
                                        {isExpanded && (
                                            <tr key={`${r.id}-usage`} className="border-b border-border/40 bg-muted/10">
                                                <td colSpan={9} className="px-0 py-0">
                                                    <UsageDetail
                                                        usage={itemUsage[r.id]}
                                                        loading={itemUsageLoading[r.id]}
                                                    />
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
                                <td colSpan={4} className="px-3 py-2.5 text-right text-xs text-muted-foreground uppercase tracking-wider">
                                    Totals
                                </td>
                                <td className="px-3 py-2.5 text-right tabular-nums text-xs">{fmtUsd(totalCifFc)}</td>
                                <td className="px-3 py-2.5 text-right tabular-nums text-xs text-amber-700">{fmtUsd(totalDebited)}</td>
                                <td className="px-3 py-2.5 text-right tabular-nums text-xs text-violet-700">{fmtUsd(totalAllotted)}</td>
                                <td className="px-3 py-2.5 text-right tabular-nums text-xs text-primary">{fmtUsd(totalBalance)}</td>
                                <td />
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>

            {/* ── 3. Balance Summary ───────────────────────────────── */}
            <div className="overflow-hidden rounded-xl border border-primary/20 bg-primary/5">
                <div className="border-b border-primary/20 px-4 py-2.5">
                    <div className="text-[10.5px] font-semibold uppercase tracking-wider text-primary">
                        Balance Summary
                    </div>
                </div>
                <div className="grid grid-cols-2 gap-4 px-4 py-3 sm:grid-cols-4">
                    <div className="flex items-center gap-2.5">
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                            <FileText className="size-4 text-primary" aria-hidden="true" />
                        </div>
                        <div>
                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                Opening CIF
                            </div>
                            <div className="text-sm font-bold tabular-nums text-foreground">
                                {fmtUsd(totalCifFc)}
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2.5">
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-amber-50">
                            <TrendingDown className="size-4 text-amber-700" aria-hidden="true" />
                        </div>
                        <div>
                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                BOE Utilized
                            </div>
                            <div className="text-sm font-bold tabular-nums text-amber-700">
                                {fmtUsd(totalDebited)}
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2.5">
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-violet-50">
                            <Package className="size-4 text-violet-700" aria-hidden="true" />
                        </div>
                        <div>
                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                Allotted
                            </div>
                            <div className="text-sm font-bold tabular-nums text-violet-700">
                                {fmtUsd(totalAllotted)}
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2.5">
                        <div className={cn(
                            "flex size-8 shrink-0 items-center justify-center rounded-lg",
                            totalBalance > 0 ? "bg-emerald-50" : "bg-muted"
                        )}>
                            <TrendingUp className={cn(
                                "size-4",
                                totalBalance > 0 ? "text-emerald-700" : "text-muted-foreground"
                            )} aria-hidden="true" />
                        </div>
                        <div>
                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                Remaining Balance
                            </div>
                            <div className={cn(
                                "text-lg font-bold tabular-nums",
                                totalBalance > 0 ? "text-emerald-700" : "text-muted-foreground"
                            )}>
                                {fmtUsd(totalBalance)}
                            </div>
                            <div className="text-[10px] text-muted-foreground">
                                also {fmtInr(Number(item.get_balance_cif))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
