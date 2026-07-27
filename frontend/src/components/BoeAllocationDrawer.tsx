import { useMemo, useState } from "react";
import { Loader2, X } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import DebouncedSearchInput from "@/components/DebouncedSearchInput";
import { fmtNum } from "@/pages/license-balance/licenseBalanceHelpers";

/**
 * One selectable candidate in the allocation drawer — a BOE (when allocating
 * an invoice) or an allotment (when allocating a BOE). Deliberately generic:
 * this is the ONE place a future real "available BOEs/allotments" search
 * endpoint plugs in (see the `fetchCandidates` isolation note in
 * `InvoiceBoeSection.tsx` / `BoeAllotmentSection.tsx`).
 */
export interface AllocationCandidate {
    id: number | string;
    label: string;
    sublabel?: string;
    remainingQty: number | null;
    remainingCif: number | null;
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

function defaultRowState(candidate: AllocationCandidate): RowState {
    return {
        checked: false,
        qty: candidate.remainingQty != null ? String(candidate.remainingQty) : "",
        cifFc: candidate.remainingCif != null ? String(candidate.remainingCif) : "",
        // No CIF-INR breakdown is available per-candidate in the ledger payload
        // (no FX rate carried on invoice_boe/boe_allotment entries) — left for
        // the user to fill in accurately rather than guessing an FX rate.
        cifInr: "",
        notes: "",
    };
}

interface BoeAllocationDrawerProps {
    open: boolean;
    onClose: () => void;
    title: string;
    description?: string;
    /** e.g. "Qty (kg)" — candidate quantity unit label. */
    qtyLabel?: string;
    candidates: AllocationCandidate[];
    /** The remaining amount on the *other* side (the invoice or the BOE being allocated) — used only for the footer's over-allocation warning. */
    targetRemainingQty?: number | null;
    targetRemainingCif?: number | null;
    confirmLabel?: string;
    onConfirm: (selections: AllocationSelection[]) => Promise<void>;
    /** Optional banner shown above the candidate list (e.g. the "no dedicated search endpoint yet" note). */
    notice?: string;
}

/**
 * Reusable side-drawer for bulk-allocating one invoice/BOE against multiple
 * BOEs/allotments in a single confirm — used for both "Find BOE" (Section 2)
 * and "Find Allotment" (Section 3) of the Licence Balance Workspace.
 * Positioning/overlay/z-index mirrors `TaskDrawer.tsx` to stay visually
 * consistent with the rest of the app.
 */
export default function BoeAllocationDrawer({
    open,
    onClose,
    title,
    description,
    qtyLabel = "Qty",
    candidates,
    targetRemainingQty,
    targetRemainingCif,
    confirmLabel = "Confirm Allocation",
    onConfirm,
    notice,
}: BoeAllocationDrawerProps) {
    const [search, setSearch] = useState("");
    const [rows, setRows] = useState<Record<string, RowState>>({});
    const [submitting, setSubmitting] = useState(false);

    const filtered = useMemo(() => {
        const term = search.trim().toLowerCase();
        if (!term) return candidates;
        return candidates.filter(
            (c) => c.label.toLowerCase().includes(term) || (c.sublabel ?? "").toLowerCase().includes(term)
        );
    }, [search, candidates]);

    const getRow = (candidate: AllocationCandidate): RowState => rows[String(candidate.id)] ?? defaultRowState(candidate);

    const setRow = (id: string | number, patch: Partial<RowState>) => {
        setRows((prev) => {
            const key = String(id);
            const existing = prev[key] ?? defaultRowState(candidates.find((c) => c.id === id) ?? { id, label: "", remainingQty: null, remainingCif: null });
            return { ...prev, [key]: { ...existing, ...patch } };
        });
    };

    const toggleChecked = (candidate: AllocationCandidate, checked: boolean) => {
        const base = getRow(candidate);
        setRow(candidate.id, { ...base, checked });
    };

    const checkedRows = candidates
        .map((c) => ({ candidate: c, row: getRow(c) }))
        .filter(({ row }) => row.checked);

    const totalQty = checkedRows.reduce((sum, { row }) => sum + (parseFloat(row.qty) || 0), 0);
    const totalCif = checkedRows.reduce((sum, { row }) => sum + (parseFloat(row.cifFc) || 0), 0);

    const overQty = targetRemainingQty != null && totalQty > targetRemainingQty + 0.005;
    const overCif = targetRemainingCif != null && totalCif > targetRemainingCif + 0.005;

    const hasValidSelection =
        checkedRows.length > 0 &&
        checkedRows.every(({ row }) => (parseFloat(row.qty) || 0) > 0 && (parseFloat(row.cifFc) || 0) > 0);

    const canConfirm = hasValidSelection && !overQty && !overCif && !submitting;

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
                    width: "min(680px, 100vw)",
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

                {notice && (
                    <div className="border-b border-warning/25 bg-warning/10 px-5 py-2.5 text-xs text-warning">
                        {notice}
                    </div>
                )}

                {/* Search */}
                <div className="border-b border-border px-5 py-3">
                    <DebouncedSearchInput value={search} onChange={setSearch} placeholder="Search candidates…" />
                </div>

                {/* Candidate list */}
                <div className="flex-1 overflow-y-auto px-5 py-3">
                    {filtered.length === 0 && (
                        <p className="py-6 text-center text-sm text-muted-foreground">No candidates found.</p>
                    )}
                    {filtered.map((candidate) => {
                        const row = getRow(candidate);
                        return (
                            <div
                                key={candidate.id}
                                className="mb-2 rounded-lg border border-border p-3 last:mb-0"
                            >
                                <label className="flex cursor-pointer items-start gap-2.5">
                                    <Checkbox
                                        checked={row.checked}
                                        onCheckedChange={(checked) => toggleChecked(candidate, checked === true)}
                                        className="mt-0.5"
                                    />
                                    <div className="min-w-0 flex-1">
                                        <div className="text-sm font-medium text-foreground">{candidate.label}</div>
                                        {candidate.sublabel && (
                                            <div className="text-xs text-muted-foreground">{candidate.sublabel}</div>
                                        )}
                                        <div className="mt-0.5 text-xs text-muted-foreground">
                                            Remaining: {fmtNum(candidate.remainingQty)} {qtyLabel} · ${fmtNum(candidate.remainingCif)} CIF
                                        </div>
                                    </div>
                                </label>

                                {row.checked && (
                                    <div className="mt-3 grid grid-cols-2 gap-2 pl-6 sm:grid-cols-4">
                                        <div>
                                            <label className="mb-1 block text-[11px] font-medium text-muted-foreground">{qtyLabel}</label>
                                            <input
                                                type="number"
                                                className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                value={row.qty}
                                                min={0}
                                                step="any"
                                                onChange={(e) => setRow(candidate.id, { qty: e.target.value })}
                                            />
                                        </div>
                                        <div>
                                            <label className="mb-1 block text-[11px] font-medium text-muted-foreground">CIF (FC)</label>
                                            <input
                                                type="number"
                                                className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                value={row.cifFc}
                                                min={0}
                                                step="any"
                                                onChange={(e) => setRow(candidate.id, { cifFc: e.target.value })}
                                            />
                                        </div>
                                        <div>
                                            <label className="mb-1 block text-[11px] font-medium text-muted-foreground">CIF (INR)</label>
                                            <input
                                                type="number"
                                                className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                value={row.cifInr}
                                                min={0}
                                                step="any"
                                                onChange={(e) => setRow(candidate.id, { cifInr: e.target.value })}
                                            />
                                        </div>
                                        <div>
                                            <label className="mb-1 block text-[11px] font-medium text-muted-foreground">Notes</label>
                                            <input
                                                type="text"
                                                className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                value={row.notes}
                                                onChange={(e) => setRow(candidate.id, { notes: e.target.value })}
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* Footer */}
                <div className="border-t border-border bg-muted/40 px-5 py-3.5">
                    <div className="mb-2 flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">
                            Selected: {checkedRows.length} · Total Qty: {fmtNum(totalQty)} · Total CIF: ${fmtNum(totalCif)}
                        </span>
                    </div>
                    {(overQty || overCif) && (
                        <p className="mb-2 text-xs font-medium text-destructive">
                            Selected total exceeds the remaining amount available to allocate.
                        </p>
                    )}
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
