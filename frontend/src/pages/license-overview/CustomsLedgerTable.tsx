import { useMemo, useState } from "react";
import { ArrowRight, EyeOff, RotateCcw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/api/axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { CustomsLedgerRow, CustomsLedgerSummary } from "@/pages/license-balance/types";
import { customsLedgerRowClass, customsStatusVariant, extractApiError, fmtDate, fmtNum } from "@/pages/license-balance/licenseBalanceHelpers";
import { licenseBalanceKeys } from "@/pages/license-balance/useLicenseBalanceLedger";
import { licenseOverviewKeys } from "./useLicenseOverviewSummary";
import SummaryCard from "./SummaryCard";

interface CustomsLedgerTableProps {
    rows: CustomsLedgerRow[];
    summary: CustomsLedgerSummary;
    licenseId: string | number | undefined;
    showHidden: boolean;
    onShowHiddenChange: (next: boolean) => void;
}

const HEADERS = [
    "Sr", "Date", "Type", "Doc Number", "BOE Number", "BOE Date", "Company", "Item",
    "Qty", "CIF USD", "Credit", "Debit", "Running Balance", "Status", "Remarks", "Actions",
];

/** One step of the Available Balance flow — a compact value chip, optionally
 * preceded by an inline operator ("−" for a deduction, "=" for a resulting
 * total). Laid out horizontally (wrapping on narrow screens) rather than as
 * a tall vertical stack, so the whole flow fits in one shallow strip. */
function FlowStep({
    label,
    value,
    operator,
    emphasize,
}: {
    label: string;
    value: string;
    operator?: "−" | "=";
    emphasize?: boolean;
}) {
    return (
        <div className="flex items-center gap-2">
            {operator && (
                <div className="flex items-center gap-1 text-xs font-semibold text-muted-foreground">
                    <ArrowRight className="size-3.5 shrink-0" />
                    <span>{operator}</span>
                </div>
            )}
            <div
                className={cn(
                    "flex items-baseline gap-1.5 whitespace-nowrap rounded-md border px-2.5 py-1",
                    emphasize ? "border-primary/40 bg-primary/5" : "border-border/70 bg-card"
                )}
            >
                <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
                <span className={cn("text-sm font-bold tabular-nums", emphasize ? "text-primary" : "text-foreground")}>
                    {value}
                </span>
            </div>
        </div>
    );
}

/**
 * Overview tab's "Customs Ledger — Running Balance": the SEPARATE
 * running-CUSTOMS-utilisation statement from `data.customs_ledger` (every
 * BOE debits at its FULL raw CIF, unconditionally — see the backend
 * builder's docstring). This is intentionally distinct from
 * `CustomsLedgerSection.tsx`'s per-item "Customs Ledger — Item Detail" table
 * (HSN/available-qty breakdown) — the two answer different questions and
 * are never conflated.
 *
 * Mirrors the PDF's "Customs Summary" card + "Customs Ledger" table
 * (`_build_customs_ledger_elements`) so PDF/Excel/UI share one information
 * architecture.
 *
 * Relocated (unchanged) from `pages/license-balance/` — still backed by
 * `useLicenseBalanceLedger`.
 *
 * Hidden-BOE (previous-owner) support: `showHidden` drives the `?show_hidden`
 * param on `useLicenseBalanceLedger` (lifted to `OverviewTab` since that's
 * where the hook lives); when on, `rows` includes `is_hidden` BOE debits with
 * `hidden_reason` set, rendered muted/struck-through with a "Hidden" badge.
 * The per-row Hide/Restore action posts to `licenses/<id>/hide-boe/` /
 * `restore-boe/` (plain `api.post`, then a manual `queryClient.
 * invalidateQueries` — no `useMutation`, matching this workspace's
 * established convention per `useLicenseBalanceLedger.ts`'s own docstring).
 * Gated on `row.bill_of_entry_id`.
 *
 * Hide is a 3-case dispatch on the BOE's CURRENT `boe_invoice_no` (mirrors
 * the backend `hide_boe` service's own 3 cases exactly): blank/null or
 * already `"OTH"` hides instantly with no confirmation; any other real
 * value opens the confirmation `Dialog` below first (hiding will
 * temporarily overwrite that invoice number — restored automatically on
 * unhide, per the backend's preserve-on-hide/restore-on-unhide contract).
 */
/** Sentinel `invoice_no` marking a BOE as previous-owner utilisation — see
 * `apps.bill_of_entry.models.OTH_INVOICE_MARKER` (backend source of truth;
 * duplicated here as a literal since the frontend has no shared constants
 * module for backend enum values). */
const OTH_INVOICE_MARKER = "OTH";

/** True for a row that could ever carry a Hide/Restore action or a bulk
 * select checkbox — a real `customs_boe` row with a resolvable BOE id. */
function isBoeRow(row: CustomsLedgerRow): boolean {
    return row.row_kind === "customs_boe" && Boolean(row.bill_of_entry_id);
}

export default function CustomsLedgerTable({ rows, summary, licenseId, showHidden, onShowHiddenChange }: CustomsLedgerTableProps) {
    const queryClient = useQueryClient();
    // Rows pending confirmation before a Hide (single- or bulk-length) —
    // null means no dialog is open. Populated only when at least one row
    // in the batch is Case 3 (see `handleHide`/`handleBulkHide`'s 3-case
    // dispatch); Case 1/2 rows never reach this state.
    const [pendingHideRows, setPendingHideRows] = useState<CustomsLedgerRow[] | null>(null);
    // Bulk multi-select — keyed by `bill_of_entry_id` (the id the hide/
    // restore endpoints actually operate on), not `row.sr`/`row_details_id`,
    // so two rows debiting the same BOE (different licence items) select
    // as one unit and de-duplicate naturally when building `boe_ids`.
    const [selected, setSelected] = useState<Set<number>>(new Set());
    const [bulkBusy, setBulkBusy] = useState(false);

    const invalidate = () => {
        if (licenseId === undefined || licenseId === null || licenseId === "") return;
        // Both the ledger (this table + Financial Ledger) AND the Overview
        // summary cards (Total/Debited/Balance CIF etc.) change when a BOE
        // is hidden/restored — refresh both, nothing else (see `OverviewTab`
        // .tsx's `!data` loading guards for why this never causes a full
        // page/scroll reset).
        queryClient.invalidateQueries({ queryKey: licenseBalanceKeys.ledger(licenseId) });
        queryClient.invalidateQueries({ queryKey: licenseOverviewKeys.summary(licenseId) });
    };

    const boeRows = useMemo(() => rows.filter(isBoeRow), [rows]);
    const hideableRows = useMemo(() => boeRows.filter((r) => !r.is_hidden), [boeRows]);
    // Restore checkboxes only make sense while hidden rows are actually
    // visible (`showHidden`) — matches the existing single-row Restore
    // button's own `showHidden` gate.
    const restorableRows = useMemo(
        () => (showHidden ? boeRows.filter((r) => r.is_hidden) : []),
        [boeRows, showHidden]
    );
    const selectableRows = useMemo(() => [...hideableRows, ...restorableRows], [hideableRows, restorableRows]);
    const selectedHideRows = useMemo(
        () => hideableRows.filter((r) => r.bill_of_entry_id !== undefined && selected.has(r.bill_of_entry_id)),
        [hideableRows, selected]
    );
    const selectedRestoreRows = useMemo(
        () => restorableRows.filter((r) => r.bill_of_entry_id !== undefined && selected.has(r.bill_of_entry_id)),
        [restorableRows, selected]
    );
    const allSelectableSelected = selectableRows.length > 0 && selectableRows.every(
        (r) => r.bill_of_entry_id !== undefined && selected.has(r.bill_of_entry_id)
    );

    const toggleRow = (boeId: number) => {
        setSelected((prev) => {
            const next = new Set(prev);
            if (next.has(boeId)) next.delete(boeId);
            else next.add(boeId);
            return next;
        });
    };

    const toggleSelectAll = () => {
        setSelected((prev) => {
            if (allSelectableSelected) return new Set();
            const next = new Set(prev);
            for (const r of selectableRows) {
                if (r.bill_of_entry_id !== undefined) next.add(r.bill_of_entry_id);
            }
            return next;
        });
    };

    const uniqueBoeIds = (rowsIn: CustomsLedgerRow[]): number[] =>
        Array.from(new Set(rowsIn.map((r) => r.bill_of_entry_id).filter((id): id is number => id !== undefined)));

    const doHide = async (rowsToHide: CustomsLedgerRow[]) => {
        if (!licenseId) return;
        const boeIds = uniqueBoeIds(rowsToHide);
        if (boeIds.length === 0) return;
        setBulkBusy(true);
        try {
            if (boeIds.length === 1) {
                await api.post(`licenses/${licenseId}/hide-boe/`, { boe_id: boeIds[0] });
                toast.success("BOE hidden.");
            } else {
                const { data } = await api.post(`licenses/${licenseId}/hide-boe-bulk/`, { boe_ids: boeIds });
                const hiddenCount = data?.hidden?.length ?? 0;
                const failedCount = data?.failed?.length ?? 0;
                if (failedCount > 0) {
                    toast.warning(`Hid ${hiddenCount} BOE(s); ${failedCount} could not be hidden.`);
                } else {
                    toast.success(`Hid ${hiddenCount} BOE(s).`);
                }
            }
            setSelected(new Set());
            invalidate();
        } catch (err) {
            toast.error(extractApiError(err, "Failed to hide BOE(s)."));
        } finally {
            setBulkBusy(false);
        }
    };

    /**
     * 3-case dispatch by each row's CURRENT `boe_invoice_no` (see the
     * backend `hide_boe`/`hide_boes_bulk` service docstrings for the same
     * 3 cases, generalized from one row to a batch):
     *   1. every selected BOE blank/null or already "OTH" -> hide
     *      immediately, no confirmation (single-click, per spec).
     *   2. one or more hold a real invoice number -> ONE confirmation
     *      dialog for the whole batch (never one per row).
     */
    const dispatchHide = (rowsToHide: CustomsLedgerRow[]) => {
        const needsConfirm = rowsToHide.some(
            (r) => r.boe_invoice_no && r.boe_invoice_no !== OTH_INVOICE_MARKER
        );
        if (!needsConfirm) {
            void doHide(rowsToHide);
            return;
        }
        setPendingHideRows(rowsToHide);
    };

    const handleHide = (row: CustomsLedgerRow) => dispatchHide([row]);
    const handleBulkHide = () => dispatchHide(selectedHideRows);

    const doRestore = async (rowsToRestore: CustomsLedgerRow[]) => {
        if (!licenseId) return;
        const boeIds = uniqueBoeIds(rowsToRestore);
        if (boeIds.length === 0) return;
        setBulkBusy(true);
        try {
            if (boeIds.length === 1) {
                await api.post(`licenses/${licenseId}/restore-boe/`, { boe_id: boeIds[0] });
                toast.success("BOE restored.");
            } else {
                const { data } = await api.post(`licenses/${licenseId}/restore-boe-bulk/`, { boe_ids: boeIds });
                const restoredCount = data?.restored?.length ?? 0;
                const failedCount = data?.failed?.length ?? 0;
                if (failedCount > 0) {
                    toast.warning(`Restored ${restoredCount} BOE(s); ${failedCount} could not be restored.`);
                } else {
                    toast.success(`Restored ${restoredCount} BOE(s).`);
                }
            }
            setSelected(new Set());
            invalidate();
        } catch (err) {
            toast.error(extractApiError(err, "Failed to restore BOE(s)."));
        } finally {
            setBulkBusy(false);
        }
    };

    const handleRestore = (row: CustomsLedgerRow) => void doRestore([row]);
    const handleBulkRestore = () => void doRestore(selectedRestoreRows);

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-end gap-2">
                <Label htmlFor="customs-ledger-show-hidden" className="text-xs font-medium text-muted-foreground">
                    Show Hidden BOEs
                </Label>
                <Switch
                    id="customs-ledger-show-hidden"
                    aria-label="Show hidden BOEs"
                    checked={showHidden}
                    onCheckedChange={onShowHiddenChange}
                />
            </div>

            {/* Bulk action toolbar — appears only while >=1 row is selected,
                in the table's own flow (never fixed/sticky), so it never
                affects scroll position on its own. */}
            {selected.size > 0 && (
                <div className="flex flex-wrap items-center gap-3 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2">
                    <span className="text-sm font-medium text-foreground">
                        Selected: {selected.size} BOE{selected.size === 1 ? "" : "s"}
                    </span>
                    {selectedHideRows.length > 0 && (
                        <Button size="sm" variant="destructive" onClick={handleBulkHide} disabled={bulkBusy}>
                            <EyeOff className="size-3.5" aria-hidden="true" />
                            Hide Selected ({selectedHideRows.length})
                        </Button>
                    )}
                    {selectedRestoreRows.length > 0 && (
                        <Button size="sm" variant="outline" onClick={handleBulkRestore} disabled={bulkBusy}>
                            <RotateCcw className="size-3.5" aria-hidden="true" />
                            Restore Selected ({selectedRestoreRows.length})
                        </Button>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())} disabled={bulkBusy}>
                        Clear selection
                    </Button>
                </div>
            )}

            {/* Available Balance flow: Original CIF -> (-) Total BOE CIF ->
                Remaining After BOE -> (-) Pending/Unlinked Allotted CIF ->
                Available Balance. Horizontal + wrapping, so it's one shallow
                strip instead of a tall column. Every value is read straight
                off `summary` (computed server-side) — nothing is re-derived
                here. The card grid below only repeats the figures NOT
                already visible in this flow (Balance Engine/Difference/
                Status), to avoid showing the same number twice. */}
            <div className="rounded-lg border border-border/70 bg-muted/10 px-3 py-2.5">
                <div className="flex flex-wrap items-center gap-2">
                    <FlowStep label="Original Licence CIF" value={fmtNum(summary.opening_balance)} />
                    <FlowStep label="Total BOE CIF" value={fmtNum(summary.total_boe_cif)} operator="−" />
                    <FlowStep label="Remaining After BOE" value={fmtNum(summary.remaining_after_boe)} operator="=" />
                    <FlowStep label="Pending / Unlinked Allotted CIF" value={fmtNum(summary.total_pending_allotment_cif)} operator="−" />
                    <FlowStep label="Available Balance" value={fmtNum(summary.computed_balance)} operator="=" emphasize />
                </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <SummaryCard label="Available Balance" value={fmtNum(summary.computed_balance)} variant="primary" size="lg" />
                <SummaryCard label="Balance Engine" value={fmtNum(summary.engine_balance)} size="lg" />
                <SummaryCard
                    label="Difference"
                    value={fmtNum(summary.difference)}
                    variant={summary.mismatched ? "danger" : "success"}
                />
                <div className="rounded-lg border border-border/70 bg-card px-3 py-2.5">
                    <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Status</div>
                    <div className="mt-1">
                        <Badge variant={summary.mismatched ? "destructive" : "success"}>
                            {summary.mismatched ? "Reconciliation Failed" : "Reconciled"}
                        </Badge>
                    </div>
                </div>
            </div>

            <div className="overflow-x-auto rounded-lg border border-border" tabIndex={0} aria-label="Customs ledger table; scroll horizontally to view all columns">
                <table className="w-full text-sm">
                    <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                        <tr>
                            <th scope="col" className="w-8 px-3 py-2">
                                {selectableRows.length > 0 && (
                                    <Checkbox
                                        checked={allSelectableSelected}
                                        onCheckedChange={toggleSelectAll}
                                        aria-label="Select all BOEs"
                                    />
                                )}
                            </th>
                            {HEADERS.map((h) => (
                                <th key={h} scope="col" className="whitespace-nowrap px-3 py-2 text-left font-semibold">
                                    {h}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.length === 0 && (
                            <tr>
                                <td colSpan={HEADERS.length + 1} className="px-3 py-6 text-center text-muted-foreground">
                                    No customs ledger rows.
                                </td>
                            </tr>
                        )}
                        {rows.map((row) => {
                            const isHideable = row.row_kind === "customs_boe" && Boolean(row.bill_of_entry_id);
                            const isSelectable = row.bill_of_entry_id !== undefined
                                && (row.is_hidden ? showHidden : isHideable);
                            return (
                                <tr
                                    key={row.sr}
                                    className={cn(
                                        "border-t border-border/60",
                                        row.is_hidden
                                            ? "bg-muted/30 text-muted-foreground [&_td]:text-muted-foreground [&_td]:line-through"
                                            : customsLedgerRowClass(row.row_kind, row.mismatched)
                                    )}
                                >
                                    <td className="px-3 py-2 align-top">
                                        {isSelectable && (
                                            <Checkbox
                                                checked={row.bill_of_entry_id !== undefined && selected.has(row.bill_of_entry_id)}
                                                onCheckedChange={() => row.bill_of_entry_id !== undefined && toggleRow(row.bill_of_entry_id)}
                                                aria-label={`Select BOE ${row.boe_number ?? row.bill_of_entry_id}`}
                                            />
                                        )}
                                    </td>
                                    <td className="px-3 py-2">{row.sr}</td>
                                    <td className="whitespace-nowrap px-3 py-2">{fmtDate(row.date)}</td>
                                    <td className="whitespace-nowrap px-3 py-2 font-medium">
                                        {row.type}
                                        {row.is_hidden && (
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Badge variant="secondary" className="ml-2 gap-1 align-middle no-underline cursor-default">
                                                        <EyeOff className="size-3" aria-hidden="true" />
                                                        Hidden
                                                    </Badge>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                    {row.hidden_reason || "Hidden as a previous owner's utilisation."}
                                                </TooltipContent>
                                            </Tooltip>
                                        )}
                                    </td>
                                    <td className="px-3 py-2">{row.document_number ?? "—"}</td>
                                    <td className="px-3 py-2">{row.boe_number ?? "—"}</td>
                                    <td className="whitespace-nowrap px-3 py-2">{fmtDate(row.boe_date)}</td>
                                    <td className="px-3 py-2">{row.company ?? "—"}</td>
                                    <td className="px-3 py-2">{row.item_name ?? "—"}</td>
                                    <td className="px-3 py-2 text-right">{fmtNum(row.qty)}</td>
                                    <td className="px-3 py-2 text-right">{fmtNum(row.cif_usd)}</td>
                                    <td className="px-3 py-2 text-right">{fmtNum(row.credit)}</td>
                                    <td className="px-3 py-2 text-right">{fmtNum(row.debit)}</td>
                                    <td className="px-3 py-2 text-right font-medium">{fmtNum(row.running_balance)}</td>
                                    <td className="px-3 py-2">
                                        <Badge variant={customsStatusVariant(row.status)}>{row.status}</Badge>
                                    </td>
                                    <td className="px-3 py-2">{row.remarks ?? "—"}</td>
                                    <td className="px-3 py-2">
                                        {isHideable && !row.is_hidden && (
                                            <Button
                                                size="icon"
                                                variant="outline"
                                                className="size-7"
                                                onClick={() => handleHide(row)}
                                                title="Hide as Previous Owner"
                                                aria-label="Hide as Previous Owner"
                                            >
                                                <EyeOff className="size-3.5" aria-hidden="true" />
                                            </Button>
                                        )}
                                        {isHideable && row.is_hidden && showHidden && (
                                            <Button
                                                size="icon"
                                                variant="outline"
                                                className="size-7"
                                                onClick={() => handleRestore(row)}
                                                title="Restore"
                                                aria-label="Restore"
                                            >
                                                <RotateCcw className="size-3.5" aria-hidden="true" />
                                            </Button>
                                        )}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {/* Single confirmation dialog, generalized over 1..N rows —
                never one dialog per row, even for a bulk hide (per spec:
                "Only one confirmation should be shown"). Radix `Dialog` is
                position:fixed + viewport-centered already (not scrolled to
                via a trigger ref), and this state is set from a plain
                onClick, not `DialogTrigger` — opening/closing it never
                touches the page's own scroll position. */}
            <Dialog open={pendingHideRows !== null} onOpenChange={(open) => !open && setPendingHideRows(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{pendingHideRows && pendingHideRows.length > 1 ? `Hide ${pendingHideRows.length} BOEs?` : "Hide BOE"}</DialogTitle>
                        <DialogDescription>
                            {pendingHideRows && pendingHideRows.length > 1 ? (
                                (() => {
                                    const blankCount = pendingHideRows.filter((r) => !r.boe_invoice_no).length;
                                    const realCount = pendingHideRows.length - blankCount;
                                    const multiLicenceCount = pendingHideRows.filter((r) => (r.licenses_count ?? 1) > 1).length;
                                    return (
                                        <>
                                            {blankCount > 0 && <>{blankCount} BOE{blankCount === 1 ? "" : "s"} have no invoice.<br /></>}
                                            {realCount} BOE{realCount === 1 ? "" : "s"} have existing invoice numbers that will be
                                            temporarily replaced with "OTH".
                                            <br />
                                            All affected licences will be recalculated.
                                            {multiLicenceCount > 0 && (
                                                <>
                                                    <br />
                                                    {multiLicenceCount} of the selected BOE{multiLicenceCount === 1 ? "" : "s"} {multiLicenceCount === 1 ? "is" : "are"} linked
                                                    to more than one licence — continuing will update all affected licences.
                                                </>
                                            )}
                                        </>
                                    );
                                })()
                            ) : (
                                <>
                                    This BOE is currently linked to Invoice "{pendingHideRows?.[0]?.boe_invoice_no}". Hiding this
                                    BOE will temporarily replace the invoice number with "OTH" and remove it from invoice matching
                                    and pending invoice workflows. The original invoice number will be restored automatically when
                                    the BOE is unhidden.
                                    {(pendingHideRows?.[0]?.licenses_count ?? 1) > 1 && (
                                        <>
                                            {" "}This BOE is linked to {pendingHideRows?.[0]?.licenses_count} licences. Continuing will
                                            update all affected licences.
                                        </>
                                    )}
                                    {" "}Do you want to continue?
                                </>
                            )}
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setPendingHideRows(null)} disabled={bulkBusy}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            disabled={bulkBusy}
                            onClick={() => {
                                const rowsToHide = pendingHideRows;
                                setPendingHideRows(null);
                                if (rowsToHide) void doHide(rowsToHide);
                            }}
                        >
                            {pendingHideRows && pendingHideRows.length > 1 ? "Hide Selected" : "Hide BOE"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
