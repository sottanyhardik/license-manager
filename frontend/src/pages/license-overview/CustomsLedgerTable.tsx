import { useState } from "react";
import { ArrowRight, EyeOff, RotateCcw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/api/axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { CustomsLedgerRow, CustomsLedgerSummary } from "@/pages/license-balance/types";
import { customsLedgerRowClass, customsStatusVariant, extractApiError, fmtDate, fmtNum } from "@/pages/license-balance/licenseBalanceHelpers";
import { licenseBalanceKeys } from "@/pages/license-balance/useLicenseBalanceLedger";
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

export default function CustomsLedgerTable({ rows, summary, licenseId, showHidden, onShowHiddenChange }: CustomsLedgerTableProps) {
    const queryClient = useQueryClient();
    // Row pending confirmation for Case 3 (invoice_no holds a real value) —
    // null means no dialog is open. See `handleHide`'s 3-case dispatch.
    const [confirmRow, setConfirmRow] = useState<CustomsLedgerRow | null>(null);

    const invalidate = () => {
        if (licenseId === undefined || licenseId === null || licenseId === "") return;
        queryClient.invalidateQueries({ queryKey: licenseBalanceKeys.ledger(licenseId) });
    };

    const doHide = async (row: CustomsLedgerRow) => {
        if (!licenseId || !row.bill_of_entry_id) return;
        try {
            await api.post(`licenses/${licenseId}/hide-boe/`, { boe_id: row.bill_of_entry_id });
            toast.success("BOE hidden.");
            invalidate();
        } catch (err) {
            toast.error(extractApiError(err, "Failed to hide BOE."));
        }
    };

    /**
     * 3-case dispatch by the BOE's CURRENT `invoice_no` (see the backend
     * `hide_boe` service docstring for the same 3 cases):
     *   1. blank/null -> hide immediately, no confirmation.
     *   2. already "OTH" -> already hidden; idempotent, no confirmation.
     *   3. any other real value -> confirm first (hiding will temporarily
     *      overwrite it; the original is restored automatically on unhide).
     */
    const handleHide = (row: CustomsLedgerRow) => {
        const invoiceNo = row.boe_invoice_no;
        if (!invoiceNo || invoiceNo === OTH_INVOICE_MARKER) {
            void doHide(row);
            return;
        }
        setConfirmRow(row);
    };

    const handleRestore = async (row: CustomsLedgerRow) => {
        if (!licenseId || !row.bill_of_entry_id) return;
        try {
            await api.post(`licenses/${licenseId}/restore-boe/`, { boe_id: row.bill_of_entry_id });
            toast.success("BOE restored.");
            invalidate();
        } catch (err) {
            toast.error(extractApiError(err, "Failed to restore BOE."));
        }
    };

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-end gap-2">
                <Label htmlFor="customs-ledger-show-hidden" className="text-xs font-medium text-muted-foreground">
                    Show Hidden BOEs
                </Label>
                <Switch id="customs-ledger-show-hidden" checked={showHidden} onCheckedChange={onShowHiddenChange} />
            </div>

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

            <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-sm">
                    <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                        <tr>
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
                                <td colSpan={HEADERS.length} className="px-3 py-6 text-center text-muted-foreground">
                                    No customs ledger rows.
                                </td>
                            </tr>
                        )}
                        {rows.map((row) => {
                            const isHideable = row.row_kind === "customs_boe" && Boolean(row.bill_of_entry_id);
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

            <Dialog open={confirmRow !== null} onOpenChange={(open) => !open && setConfirmRow(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Hide BOE</DialogTitle>
                        <DialogDescription>
                            This BOE is currently linked to Invoice "{confirmRow?.boe_invoice_no}". Hiding this BOE
                            will temporarily replace the invoice number with "OTH" and remove it from invoice
                            matching and pending invoice workflows. The original invoice number will be restored
                            automatically when the BOE is unhidden. Do you want to continue?
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setConfirmRow(null)}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={() => {
                                const row = confirmRow;
                                setConfirmRow(null);
                                if (row) void doHide(row);
                            }}
                        >
                            Hide BOE
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
