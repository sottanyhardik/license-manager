import { useMemo, useRef, useState } from "react";
import { Loader2, X, CheckCheck, Eraser, Wand2 } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import DebouncedSearchInput from "@/components/DebouncedSearchInput";
import { fmtDate, fmtNum } from "@/pages/license-balance/licenseBalanceHelpers";
import {
    ALLOCATION_EPS as EPS,
    distributeAllocation,
    validateAllocationTotals,
    validateRowWithinCapacity,
} from "@/pages/license-balance/allocationMath";

/**
 * One selectable candidate in the allocation drawer — a BOE (sourced from
 * `boe_invoice_candidates`, when allocating an invoice) or an allotment
 * (sourced from `allotment_candidates`, when allocating a BOE). Both are
 * real server-computed "remaining capacity on the correct consumption
 * track" lists — see `InvoiceBoeSection.tsx` / `BoeAllotmentSection.tsx`
 * for the mapping from the ledger payload shape to this generic shape.
 */
export interface AllocationCandidate {
    id: number | string;
    /** BOE number / Allotment number. */
    number: string;
    date: string | null;
    counterparty: string | null;
    itemName?: string | null;
    /** Candidate's own total qty/CIF (boe_qty/boe_cif or allotment_qty/allotment_cif). */
    totalQty: number;
    totalCif: number;
    /** Candidate's own remaining capacity on the track relevant to this drawer. */
    remainingQty: number;
    remainingCif: number;
}

/** Whichever side is being allocated FROM — the invoice when finding BOEs, the BOE when finding allotments. */
export interface AllocationSummary {
    /** e.g. "Invoice" / "BOE" */
    label: string;
    number: string;
    counterparty: string | null;
    totalQty: number;
    totalCif: number;
    allocatedQty: number;
    allocatedCif: number;
    remainingQty: number;
    remainingCif: number;
}

export interface AllocationSelection {
    id: number | string;
    qty: number;
    cifFc: number;
    cifInr: number;
    notes: string;
}

interface RowState {
    checked: boolean;
    qty: string;
    cifFc: string;
    cifInr: string;
    notes: string;
}

/**
 * A freshly-checked row starts BLANK, not pre-filled to the candidate's own
 * remaining capacity. Selecting a BOE/allotment only marks it as a
 * candidate — it does not mean "allocate everything it has." Auto-fill (via
 * the Auto Allocate toggle/button) is a distinct, explicit step; see
 * `distributeAllocation` in `allocationMath.ts`.
 */
function blankRowState(): RowState {
    return { checked: false, qty: "", cifFc: "", cifInr: "", notes: "" };
}

/** Monotonic thresholds shared by every progress bar in this drawer: green >=80%, amber 40-79%, red <40%. */
function progressTone(pct: number): "success" | "warning" | "destructive" {
    if (pct >= 80) return "success";
    if (pct >= 40) return "warning";
    return "destructive";
}

const TONE_BAR_CLASS: Record<"success" | "warning" | "destructive", string> = {
    success: "bg-success",
    warning: "bg-warning",
    destructive: "bg-destructive",
};

function ProgressBar({ pct, tone }: { pct: number; tone: "success" | "warning" | "destructive" }) {
    const clamped = Math.max(0, Math.min(100, pct));
    return (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div className={`h-full rounded-full ${TONE_BAR_CLASS[tone]}`} style={{ width: `${clamped}%` }} />
        </div>
    );
}

type SortOption = "newest" | "oldest" | "largest_cif" | "smallest_cif";

interface BoeAllocationDrawerProps {
    open: boolean;
    onClose: () => void;
    title: string;
    description?: string;
    /** e.g. "Qty (kg)" — candidate quantity unit label. */
    qtyLabel?: string;
    /** Column header for the candidate identifier, e.g. "BOE Number" / "Allotment Number". */
    numberLabel?: string;
    /** Column header for the candidate date, e.g. "BOE Date" / "Est. Arrival". */
    dateLabel?: string;
    /** Summary of the invoice/BOE being allocated FROM — drives the summary card and every validation rule. */
    summary: AllocationSummary;
    candidates: AllocationCandidate[];
    confirmLabel?: string;
    onConfirm: (selections: AllocationSelection[]) => Promise<void>;
    /** Optional banner shown above the toolbar (e.g. a data-gap notice). */
    notice?: string;
}

/**
 * Reusable side-drawer for bulk-allocating one invoice/BOE against multiple
 * BOEs/allotments in a single confirm — used for both "Find BOE" (Section 2)
 * and "Find Allotment" (Section 3) of the Licence Balance Workspace.
 *
 * Selection vs. allocation (fixes a reported bug — see `allocationMath.ts`):
 * checking a candidate ONLY marks it as a candidate. It does NOT mean
 * "allocate everything it has." With "Auto Allocate" ON (default), the
 * invoice/BOE's remaining Qty/CIF is distributed across the currently
 * checked candidates, IN SELECTION ORDER, capped at each candidate's own
 * capacity — recomputed every time the selection changes. With Auto
 * Allocate OFF, checking a candidate leaves its Qty/CIF fields blank for
 * fully manual entry.
 *
 * Validation:
 * 1. Aggregate — SUM(allocated CIF/Qty across selected rows) must not
 *    exceed `summary.remaining*` (the invoice's/BOE's own remaining) — NEVER
 *    compared against the selected candidates' combined capacity.
 * 2. Per-row, independently — each selected row's own allocated CIF/Qty
 *    must not exceed THAT row's own `remainingCif`/`remainingQty` (only
 *    reachable via manual override, since auto-distribute never violates
 *    this by construction).
 */
export default function BoeAllocationDrawer({
    open,
    onClose,
    title,
    description,
    qtyLabel = "Qty",
    numberLabel = "Number",
    dateLabel = "Date",
    summary,
    candidates,
    confirmLabel = "Confirm Allocation",
    onConfirm,
    notice,
}: BoeAllocationDrawerProps) {
    const [search, setSearch] = useState("");
    const [sortOption, setSortOption] = useState<SortOption>("newest");
    const [remainingOnly, setRemainingOnly] = useState(true);
    const [autoAllocate, setAutoAllocate] = useState(true);
    const [rows, setRows] = useState<Record<string, RowState>>({});
    const [submitting, setSubmitting] = useState(false);
    // Order candidates were checked in — auto-distribute fills in this
    // order (first-selected gets priority), not array/display order.
    const selectionOrderRef = useRef<(string | number)[]>([]);

    const filtered = useMemo(() => {
        const term = search.trim().toLowerCase();
        let list = candidates.filter(
            (c) =>
                !term ||
                c.number.toLowerCase().includes(term) ||
                (c.counterparty ?? "").toLowerCase().includes(term) ||
                (c.itemName ?? "").toLowerCase().includes(term)
        );
        if (remainingOnly) list = list.filter((c) => c.remainingCif > EPS || c.remainingQty > EPS);

        const sorted = [...list];
        switch (sortOption) {
            case "newest":
                sorted.sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));
                break;
            case "oldest":
                sorted.sort((a, b) => (a.date ?? "").localeCompare(b.date ?? ""));
                break;
            case "largest_cif":
                sorted.sort((a, b) => b.remainingCif - a.remainingCif);
                break;
            case "smallest_cif":
                sorted.sort((a, b) => a.remainingCif - b.remainingCif);
                break;
        }
        return sorted;
    }, [search, remainingOnly, sortOption, candidates]);

    const getRow = (candidate: AllocationCandidate): RowState => rows[String(candidate.id)] ?? blankRowState();

    const setRow = (id: string | number, patch: Partial<RowState>) => {
        setRows((prev) => {
            const key = String(id);
            const existing = prev[key] ?? blankRowState();
            return { ...prev, [key]: { ...existing, ...patch } };
        });
    };

    /** Recomputes and applies auto-distribution across `ids` (selection order), leaving unselected rows untouched. */
    const applyAutoDistribution = (ids: (string | number)[]) => {
        const orderedCandidates = ids
            .map((id) => candidates.find((c) => c.id === id))
            .filter((c): c is AllocationCandidate => c != null);
        const distribution = distributeAllocation(orderedCandidates, summary.remainingQty, summary.remainingCif);

        setRows((prev) => {
            const next = { ...prev };
            for (const { id, qty, cif } of distribution) {
                const key = String(id);
                next[key] = { ...(next[key] ?? blankRowState()), checked: true, qty: String(qty), cifFc: String(cif) };
            }
            return next;
        });
    };

    const toggleChecked = (candidate: AllocationCandidate, checked: boolean) => {
        const id = candidate.id;
        if (checked) {
            if (!selectionOrderRef.current.includes(id)) selectionOrderRef.current.push(id);
        } else {
            selectionOrderRef.current = selectionOrderRef.current.filter((x) => x !== id);
        }

        if (autoAllocate) {
            // Recompute the whole distribution from scratch across the
            // updated selection set — simplest way to guarantee it never
            // exceeds the invoice/BOE's remaining capacity regardless of
            // check/uncheck order.
            if (!checked) setRow(id, blankRowState());
            applyAutoDistribution(selectionOrderRef.current);
        } else {
            // Manual mode: checking a row leaves its Qty/CIF blank (never
            // auto-filled); unchecking clears whatever was manually typed.
            setRow(id, checked ? { ...blankRowState(), checked: true } : blankRowState());
        }
    };

    const checkedRows = candidates
        .map((c) => ({ candidate: c, row: getRow(c) }))
        .filter(({ row }) => row.checked);

    const totalQty = checkedRows.reduce((sum, { row }) => sum + (parseFloat(row.qty) || 0), 0);
    const totalCif = checkedRows.reduce((sum, { row }) => sum + (parseFloat(row.cifFc) || 0), 0);

    // Rule 1 — SUM(allocated) vs. the invoice/BOE's own remaining capacity.
    // NEVER compared against the candidates' combined capacity.
    const aggregateValidation = validateAllocationTotals({
        invoiceRemainingQty: summary.remainingQty,
        invoiceRemainingCif: summary.remainingCif,
        allocatedQty: totalQty,
        allocatedCif: totalCif,
    });
    const { overQty, overCif } = aggregateValidation;

    // Rule 2 — each selected row, independently, vs. that row's own remaining capacity.
    const rowViolations = checkedRows.filter(({ candidate, row }) => {
        const v = validateRowWithinCapacity({ qty: parseFloat(row.qty) || 0, cif: parseFloat(row.cifFc) || 0 }, candidate);
        return v.overQty || v.overCif;
    });

    const hasValidSelection =
        checkedRows.length > 0 &&
        checkedRows.every(({ row }) => (parseFloat(row.qty) || 0) > 0 && (parseFloat(row.cifFc) || 0) > 0);

    const canConfirm = hasValidSelection && aggregateValidation.valid && rowViolations.length === 0 && !submitting;

    const validationStatus: { label: string; variant: "success" | "destructive" | "secondary" } =
        checkedRows.length === 0
            ? { label: "No Selection", variant: "secondary" }
            : !aggregateValidation.valid || rowViolations.length > 0
            ? { label: "Over Allocation", variant: "destructive" }
            : { label: "Ready to Allocate", variant: "success" };

    const summaryAllocatedPct = summary.totalCif > 0 ? (summary.allocatedCif / summary.totalCif) * 100 : 0;

    const handleSelectAll = () => {
        for (const candidate of filtered) {
            if (!selectionOrderRef.current.includes(candidate.id)) selectionOrderRef.current.push(candidate.id);
        }
        if (autoAllocate) {
            applyAutoDistribution(selectionOrderRef.current);
        } else {
            setRows((prev) => {
                const next = { ...prev };
                for (const candidate of filtered) {
                    const key = String(candidate.id);
                    next[key] = { ...(next[key] ?? blankRowState()), checked: true };
                }
                return next;
            });
        }
    };

    const handleClearAll = () => {
        selectionOrderRef.current = [];
        setRows({});
    };

    /** Explicit "Auto Allocate" button — re-runs distribution across the currently checked candidates on demand. */
    const handleAutoDistribute = () => {
        const ids = selectionOrderRef.current.length > 0 ? selectionOrderRef.current : filtered.map((c) => c.id);
        selectionOrderRef.current = ids;
        applyAutoDistribution(ids);
    };

    const handleConfirm = async () => {
        if (!canConfirm) return;
        setSubmitting(true);
        try {
            await onConfirm(
                checkedRows.map(({ candidate, row }) => ({
                    id: candidate.id,
                    qty: parseFloat(row.qty) || 0,
                    cifFc: parseFloat(row.cifFc) || 0,
                    cifInr: parseFloat(row.cifInr) || 0,
                    notes: row.notes,
                }))
            );
            // Success — caller resolved without throwing. Reset and close.
            setRows({});
            setSearch("");
            onClose();
        } catch {
            // Caller is responsible for surfacing the error (toast); keep the
            // drawer open with the entered values so the user can retry.
        } finally {
            setSubmitting(false);
        }
    };

    const handleClose = () => {
        if (submitting) return;
        setRows({});
        setSearch("");
        onClose();
    };

    if (!open) return null;

    return (
        <>
            <div
                onClick={handleClose}
                style={{
                    position: "fixed",
                    inset: 0,
                    background: "var(--surface-overlay, rgba(0,0,0,0.45))",
                    backdropFilter: "blur(2px)",
                    WebkitBackdropFilter: "blur(2px)",
                    zIndex: 1050,
                }}
            />
            <aside
                role="dialog"
                aria-label={title}
                style={{
                    position: "fixed",
                    top: 0,
                    right: 0,
                    bottom: 0,
                    width: "min(920px, 100vw)",
                    background: "var(--surface-raised, var(--card))",
                    zIndex: 1060,
                    display: "flex",
                    flexDirection: "column",
                    boxShadow: "var(--elevation-overlay, -8px 0 24px rgba(0,0,0,0.15))",
                    borderLeft: "1px solid var(--border-subtle, var(--border))",
                }}
            >
                {/* Header */}
                <div className="flex items-start justify-between border-b border-border px-5 py-4">
                    <div className="min-w-0">
                        <div className="text-base font-semibold tracking-tight">{title}</div>
                        {description && <div className="mt-0.5 text-sm text-muted-foreground">{description}</div>}
                    </div>
                    <button
                        type="button"
                        onClick={handleClose}
                        aria-label="Close"
                        className="inline-flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-lg border border-border bg-muted text-muted-foreground hover:bg-muted/80"
                    >
                        <X className="size-4" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto px-5 py-4">
                    {notice && (
                        <div className="mb-4 rounded-md border border-warning/25 bg-warning/10 px-3 py-2.5 text-xs text-warning">
                            {notice}
                        </div>
                    )}

                    {/* 1. Summary card */}
                    <div className="mb-4 rounded-lg border border-border bg-muted/30 p-3.5">
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                            <div className="min-w-0">
                                <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                                    {summary.label}
                                </div>
                                <div className="truncate text-sm font-semibold text-foreground">{summary.number}</div>
                                {summary.counterparty && (
                                    <div className="text-xs text-muted-foreground">{summary.counterparty}</div>
                                )}
                            </div>
                            <Badge variant={progressTone(summaryAllocatedPct)}>
                                {fmtNum(summaryAllocatedPct, 1)}% allocated
                            </Badge>
                        </div>
                        <div className="mt-2">
                            <ProgressBar pct={summaryAllocatedPct} tone={progressTone(summaryAllocatedPct)} />
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-4">
                            {[
                                ["Total Qty", fmtNum(summary.totalQty)],
                                ["Total CIF", `$${fmtNum(summary.totalCif)}`],
                                ["Allocated Qty", fmtNum(summary.allocatedQty)],
                                ["Allocated CIF", `$${fmtNum(summary.allocatedCif)}`],
                                ["Remaining Qty", fmtNum(summary.remainingQty)],
                                ["Remaining CIF", `$${fmtNum(summary.remainingCif)}`],
                            ].map(([label, value]) => (
                                <div key={label}>
                                    <div className="text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground">
                                        {label}
                                    </div>
                                    <div className="text-sm font-semibold tabular-nums text-foreground">{value}</div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* 2. Live allocation summary */}
                    <div className="mb-4 rounded-lg border border-border p-3.5">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                Live Allocation Summary
                            </span>
                            <Badge variant={validationStatus.variant}>{validationStatus.label}</Badge>
                        </div>
                        <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-3">
                            {[
                                ["Selected BOEs", String(checkedRows.length)],
                                ["Allocated Qty", fmtNum(totalQty)],
                                ["Allocated CIF", `$${fmtNum(totalCif)}`],
                                ["Remaining Qty After Allocation", fmtNum(aggregateValidation.remainingQtyAfter), aggregateValidation.remainingQtyAfter < -EPS],
                                ["Remaining CIF After Allocation", `$${fmtNum(aggregateValidation.remainingCifAfter)}`, aggregateValidation.remainingCifAfter < -EPS],
                            ].map(([label, value, negative]) => (
                                <div key={label as string}>
                                    <div className="text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground">
                                        {label}
                                    </div>
                                    <div
                                        className={`text-sm font-semibold tabular-nums ${
                                            negative ? "text-destructive" : "text-foreground"
                                        }`}
                                    >
                                        {value}
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* 7. Itemized over-allocation errors — only the constraint(s) actually violated. */}
                        {(overCif || overQty) && (
                            <div className="mt-3 space-y-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                                {overCif && (
                                    <div>
                                        <p className="font-semibold">CIF over-allocation</p>
                                        <p>{summary.label} Remaining CIF: ${fmtNum(summary.remainingCif)}</p>
                                        <p>Selected CIF: ${fmtNum(totalCif)}</p>
                                        <p>Maximum Allowed: ${fmtNum(summary.remainingCif)}</p>
                                        <p>Reduce allocation by ${fmtNum(totalCif - summary.remainingCif)}</p>
                                    </div>
                                )}
                                {overQty && (
                                    <div className={overCif ? "border-t border-destructive/20 pt-2" : undefined}>
                                        <p className="font-semibold">Qty over-allocation</p>
                                        <p>{summary.label} Remaining Qty: {fmtNum(summary.remainingQty)} {qtyLabel}</p>
                                        <p>Selected Qty: {fmtNum(totalQty)} {qtyLabel}</p>
                                        <p>Maximum Allowed: {fmtNum(summary.remainingQty)} {qtyLabel}</p>
                                        <p>Reduce allocation by {fmtNum(totalQty - summary.remainingQty)} {qtyLabel}</p>
                                    </div>
                                )}
                            </div>
                        )}
                        {rowViolations.length > 0 && (
                            <p className="mt-2 text-xs font-medium text-destructive">
                                {rowViolations.length} selected row{rowViolations.length > 1 ? "s" : ""} exceed{rowViolations.length === 1 ? "s" : ""} their own remaining capacity — see highlighted fields below.
                            </p>
                        )}
                    </div>

                    {/* 3. Toolbar */}
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                        <div className="min-w-[220px] flex-1">
                            <DebouncedSearchInput value={search} onChange={setSearch} placeholder="Search candidates…" />
                        </div>
                        <Select value={sortOption} onValueChange={(v) => setSortOption(v as SortOption)}>
                            <SelectTrigger className="w-[160px]">
                                <SelectValue placeholder="Sort" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="newest">Newest</SelectItem>
                                <SelectItem value="oldest">Oldest</SelectItem>
                                <SelectItem value="largest_cif">Largest CIF</SelectItem>
                                <SelectItem value="smallest_cif">Smallest CIF</SelectItem>
                            </SelectContent>
                        </Select>
                        <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-muted-foreground">
                            <Switch checked={remainingOnly} onCheckedChange={setRemainingOnly} />
                            Remaining Only
                        </label>
                        <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-muted-foreground">
                            <Switch
                                checked={autoAllocate}
                                onCheckedChange={(checked) => {
                                    setAutoAllocate(checked);
                                    if (checked) applyAutoDistribution(selectionOrderRef.current);
                                }}
                            />
                            Auto Allocate
                        </label>
                    </div>

                    {/* 4. Quick actions + 6. Auto-distribute */}
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                        <Button size="sm" variant="outline" onClick={handleSelectAll} disabled={filtered.length === 0}>
                            <CheckCheck className="size-3.5" /> Select All
                        </Button>
                        <Button size="sm" variant="outline" onClick={handleClearAll} disabled={checkedRows.length === 0}>
                            <Eraser className="size-3.5" /> Clear
                        </Button>
                        {autoAllocate && (
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={handleAutoDistribute}
                                disabled={summary.remainingCif <= EPS && summary.remainingQty <= EPS}
                            >
                                <Wand2 className="size-3.5" /> Auto Allocate
                            </Button>
                        )}
                        {!autoAllocate && (
                            <span className="text-xs text-muted-foreground">
                                Manual mode — enter Qty/CIF for each selected row yourself.
                            </span>
                        )}
                    </div>

                    {/* 5. Candidate grid */}
                    <div className="overflow-x-auto rounded-lg border border-border">
                        <table className="w-full min-w-[920px] text-sm">
                            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                                <tr>
                                    <th scope="col" className="w-8 px-2 py-2" />
                                    <th scope="col" className="px-2 py-2 text-left font-semibold">{numberLabel}</th>
                                    <th scope="col" className="px-2 py-2 text-left font-semibold">{dateLabel}</th>
                                    <th scope="col" className="px-2 py-2 text-left font-semibold">Company</th>
                                    <th scope="col" className="px-2 py-2 text-left font-semibold">Item</th>
                                    <th scope="col" className="px-2 py-2 text-right font-semibold">Rem. {qtyLabel}</th>
                                    <th scope="col" className="px-2 py-2 text-right font-semibold">Rem. CIF</th>
                                    <th scope="col" className="px-2 py-2 text-right font-semibold">Alloc. {qtyLabel}</th>
                                    <th scope="col" className="px-2 py-2 text-right font-semibold">Alloc. CIF</th>
                                    <th scope="col" className="px-2 py-2 text-right font-semibold">Alloc. INR</th>
                                    <th scope="col" className="px-2 py-2 text-right font-semibold">Rem. After</th>
                                    <th scope="col" className="px-2 py-2 text-left font-semibold">Status</th>
                                    <th scope="col" className="px-2 py-2 text-left font-semibold">Notes</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.length === 0 && (
                                    <tr>
                                        <td colSpan={13} className="px-3 py-6 text-center text-muted-foreground">
                                            No candidates found.
                                        </td>
                                    </tr>
                                )}
                                {filtered.map((candidate) => {
                                    const row = getRow(candidate);
                                    const rowCheck = validateRowWithinCapacity(
                                        { qty: parseFloat(row.qty) || 0, cif: parseFloat(row.cifFc) || 0 },
                                        candidate
                                    );
                                    const qtyBad = row.checked && rowCheck.overQty;
                                    const cifBad = row.checked && rowCheck.overCif;
                                    const utilisationPct =
                                        candidate.totalCif > 0
                                            ? ((candidate.totalCif - candidate.remainingCif) / candidate.totalCif) * 100
                                            : 0;
                                    const remainingAfterQty = candidate.remainingQty - (parseFloat(row.qty) || 0);
                                    const remainingAfterCif = candidate.remainingCif - (parseFloat(row.cifFc) || 0);
                                    return (
                                        <tr key={candidate.id} className="border-t border-border/60 align-top">
                                            <td className="px-2 py-2">
                                                <Checkbox
                                                    checked={row.checked}
                                                    onCheckedChange={(checked) => toggleChecked(candidate, checked === true)}
                                                />
                                            </td>
                                            <td className="px-2 py-2 font-medium text-foreground">{candidate.number}</td>
                                            <td className="whitespace-nowrap px-2 py-2 text-muted-foreground">{fmtDate(candidate.date)}</td>
                                            <td className="px-2 py-2 text-muted-foreground">{candidate.counterparty ?? "—"}</td>
                                            <td className="px-2 py-2 text-muted-foreground">{candidate.itemName ?? "—"}</td>
                                            <td className="px-2 py-2 text-right tabular-nums">{fmtNum(candidate.remainingQty)}</td>
                                            <td className="px-2 py-2 text-right tabular-nums">${fmtNum(candidate.remainingCif)}</td>
                                            <td className="px-2 py-2 text-right">
                                                {row.checked ? (
                                                    <>
                                                        <input
                                                            type="number"
                                                            className={`h-8 w-24 rounded-md border bg-card px-2 py-1 text-right text-sm outline-none focus-visible:border-ring ${
                                                                qtyBad ? "border-destructive" : "border-input"
                                                            }`}
                                                            value={row.qty}
                                                            min={0}
                                                            step="any"
                                                            onChange={(e) => setRow(candidate.id, { qty: e.target.value })}
                                                        />
                                                        {qtyBad && (
                                                            <div className="mt-0.5 text-[10.5px] text-destructive">
                                                                Max {fmtNum(candidate.remainingQty)}
                                                            </div>
                                                        )}
                                                    </>
                                                ) : (
                                                    <span className="text-muted-foreground">—</span>
                                                )}
                                            </td>
                                            <td className="px-2 py-2 text-right">
                                                {row.checked ? (
                                                    <>
                                                        <input
                                                            type="number"
                                                            className={`h-8 w-24 rounded-md border bg-card px-2 py-1 text-right text-sm outline-none focus-visible:border-ring ${
                                                                cifBad ? "border-destructive" : "border-input"
                                                            }`}
                                                            value={row.cifFc}
                                                            min={0}
                                                            step="any"
                                                            onChange={(e) => setRow(candidate.id, { cifFc: e.target.value })}
                                                        />
                                                        {cifBad && (
                                                            <div className="mt-0.5 text-[10.5px] text-destructive">
                                                                Max ${fmtNum(candidate.remainingCif)}
                                                            </div>
                                                        )}
                                                    </>
                                                ) : (
                                                    <span className="text-muted-foreground">—</span>
                                                )}
                                            </td>
                                            <td className="px-2 py-2 text-right">
                                                {row.checked ? (
                                                    <input
                                                        type="number"
                                                        className="h-8 w-24 rounded-md border border-input bg-card px-2 py-1 text-right text-sm outline-none focus-visible:border-ring"
                                                        value={row.cifInr}
                                                        min={0}
                                                        step="any"
                                                        onChange={(e) => setRow(candidate.id, { cifInr: e.target.value })}
                                                    />
                                                ) : (
                                                    <span className="text-muted-foreground">—</span>
                                                )}
                                            </td>
                                            <td className="px-2 py-2 text-right tabular-nums">
                                                {row.checked ? (
                                                    <>
                                                        <div>{fmtNum(remainingAfterQty)} {qtyLabel}</div>
                                                        <div className="text-muted-foreground">${fmtNum(remainingAfterCif)}</div>
                                                    </>
                                                ) : (
                                                    <span className="text-muted-foreground">—</span>
                                                )}
                                            </td>
                                            <td className="w-24 px-2 py-2">
                                                <div className="text-[10.5px] tabular-nums text-muted-foreground">
                                                    {fmtNum(utilisationPct, 0)}% used
                                                </div>
                                                <ProgressBar pct={utilisationPct} tone={progressTone(utilisationPct)} />
                                            </td>
                                            <td className="px-2 py-2">
                                                {row.checked ? (
                                                    <input
                                                        type="text"
                                                        className="h-8 w-32 rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                        value={row.notes}
                                                        onChange={(e) => setRow(candidate.id, { notes: e.target.value })}
                                                    />
                                                ) : (
                                                    <span className="text-muted-foreground">—</span>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Footer */}
                <div className="border-t border-border bg-muted/40 px-5 py-3.5">
                    <div className="flex justify-end gap-2">
                        <Button variant="outline" onClick={handleClose} disabled={submitting}>
                            Cancel
                        </Button>
                        <Button onClick={handleConfirm} disabled={!canConfirm}>
                            {submitting && <Loader2 className="size-4 animate-spin" />}
                            {confirmLabel}
                        </Button>
                    </div>
                </div>
            </aside>
        </>
    );
}
