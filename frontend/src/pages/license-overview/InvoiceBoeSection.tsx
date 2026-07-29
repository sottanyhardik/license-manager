import { Fragment, useContext, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ChevronDown, ChevronRight, Search } from "lucide-react";
import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useConfirmDialog } from "@/hooks/useConfirmDialog";
import BoeAllocationDrawer, {
    type AllocationCandidate,
    type AllocationSelection,
} from "@/components/BoeAllocationDrawer";
import { licenseBalanceKeys } from "@/pages/license-balance/useLicenseBalanceLedger";
import { extractApiError, fmtDate, fmtNum, invoiceBoeStatusVariant } from "@/pages/license-balance/licenseBalanceHelpers";
import type { BoeInvoiceCandidate, InvoiceBoeEntry } from "@/pages/license-balance/types";

interface InvoiceBoeSectionProps {
    licenseId: string | number;
    invoices: InvoiceBoeEntry[];
    /** The correct candidate source for "Find BOE" / "Mark External Invoice" — INVOICE-side remaining capacity per BOE. */
    boeInvoiceCandidates: BoeInvoiceCandidate[];
}

/**
 * Maps `boe_invoice_candidates` (server-computed via
 * `remaining_for_row_details_invoice_side`, see
 * `LicenseBalanceLedgerBuilder.build_boe_invoice_candidates`) to the
 * drawer's generic candidate shape.
 *
 * This REPLACES the previous client-side derivation from `boe_allotment`
 * (the ALLOTMENT-side remaining), which was the root cause of a false
 * "Selected total exceeds the remaining amount available to allocate"
 * error: a BOE's allotment-side remaining and invoice-side remaining are
 * two independent consumption tracks that only coincidentally match when
 * neither has any allocations yet.
 */
function toAllocationCandidates(candidates: BoeInvoiceCandidate[]): AllocationCandidate[] {
    return candidates.map((c) => ({
        id: c.row_details_id,
        number: c.bill_of_entry_number,
        date: c.bill_of_entry_date,
        counterparty: c.company,
        itemName: c.item_name,
        totalQty: c.boe_qty,
        totalCif: c.boe_cif,
        remainingQty: c.remaining_qty,
        remainingCif: c.remaining_cif,
    }));
}

const EMPTY_EXTERNAL_FORM = { rowDetailsId: "", invoiceNumber: "", qty: "", cifFc: "", cifInr: "" };

/**
 * Overview tab's Invoice ↔ BOE Reconciliation section. One expandable row
 * per `invoice_boe` entry (expand pattern mirrors `AccordionTable.tsx`'s
 * sibling-`<tr>`-with-`colSpan`), plus the "Find BOE" allocation drawer and
 * the "Mark External Invoice" flow.
 *
 * Relocated (unchanged) from `pages/license-balance/` — still backed by
 * `useLicenseBalanceLedger`; this is the allocation-editing entry point kept
 * alongside the Warnings panel in this feature's v1.
 */
export default function InvoiceBoeSection({ licenseId, invoices, boeInvoiceCandidates }: InvoiceBoeSectionProps) {
    const { hasRole } = useContext(AuthContext);
    const queryClient = useQueryClient();
    const { confirmDangerousAction, confirmDialog } = useConfirmDialog();

    // Only invoices with no BOE attached at all belong in this reconciliation
    // panel — once one or more BOEs are linked, there's nothing left to
    // reconcile for that invoice.
    const unmatchedInvoices = useMemo(() => invoices.filter((invoice) => invoice.linked_boes.length === 0), [invoices]);

    const [expanded, setExpanded] = useState<Set<string>>(new Set());
    const [drawerInvoice, setDrawerInvoice] = useState<InvoiceBoeEntry | null>(null);
    const [markExternalOpen, setMarkExternalOpen] = useState(false);
    const [markExternalForm, setMarkExternalForm] = useState(EMPTY_EXTERNAL_FORM);
    const [markExternalSubmitting, setMarkExternalSubmitting] = useState(false);

    // Per `LicenseBalanceLedgerPermission.write_action_roles`: invoice<->BOE
    // allocation requires TRADE_MANAGER AND BOE_MANAGER; marking an external
    // invoice only touches the BOE side, so BOE_MANAGER alone.
    const canAllocate = hasRole("TRADE_MANAGER") && hasRole("BOE_MANAGER");
    const canMarkExternal = hasRole("BOE_MANAGER");

    const boeCandidates = useMemo(() => toAllocationCandidates(boeInvoiceCandidates), [boeInvoiceCandidates]);
    // The "Mark External Invoice" picker only makes sense for BOEs that still have invoice-side capacity left.
    const markExternalBoeOptions = useMemo(
        () => boeCandidates.filter((c) => c.remainingCif > 0 || c.remainingQty > 0),
        [boeCandidates]
    );

    const invalidate = () => queryClient.invalidateQueries({ queryKey: licenseBalanceKeys.ledger(licenseId) });

    const toggleExpanded = (key: string) => {
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });
    };

    const rowKey = (invoice: InvoiceBoeEntry) =>
        invoice.kind === "system" ? `t-${invoice.trade_line_id}` : `e-${invoice.invoice_number}`;

    const handleAllocateConfirm = async (selections: AllocationSelection[]) => {
        if (!drawerInvoice || drawerInvoice.kind !== "system") return;
        try {
            await api.post(`licenses/${licenseId}/allocate-invoice-boe/`, {
                trade_line_id: drawerInvoice.trade_line_id,
                allocations: selections.map((s) => ({
                    row_details_id: s.id,
                    qty: s.qty,
                    cif_fc: s.cifFc,
                    cif_inr: s.cifInr,
                    notes: s.notes || undefined,
                })),
            });
            toast.success("Invoice allocated to BOE(s).");
            invalidate();
            setDrawerInvoice(null);
        } catch (err) {
            toast.error(extractApiError(err, "Failed to allocate invoice to BOE."));
            throw err;
        }
    };

    const handleMarkExternalSubmit = async () => {
        if (!markExternalForm.rowDetailsId || !markExternalForm.invoiceNumber.trim()) {
            toast.error("Select a BOE and enter an invoice number.");
            return;
        }
        const confirmed = await confirmDangerousAction(
            "Mark External Invoice",
            "This action will mark this BOE as belonging to an external or unavailable invoice. Continue?"
        );
        if (!confirmed) return;

        setMarkExternalSubmitting(true);
        try {
            await api.post(`licenses/${licenseId}/mark-external-invoice/`, {
                row_details_id: Number(markExternalForm.rowDetailsId),
                invoice_number: markExternalForm.invoiceNumber.trim(),
                qty: parseFloat(markExternalForm.qty) || 0,
                cif_fc: parseFloat(markExternalForm.cifFc) || 0,
                cif_inr: parseFloat(markExternalForm.cifInr) || 0,
            });
            toast.success("BOE marked as external invoice.");
            invalidate();
            setMarkExternalOpen(false);
            setMarkExternalForm(EMPTY_EXTERNAL_FORM);
        } catch (err) {
            toast.error(extractApiError(err, "Failed to mark external invoice."));
        } finally {
            setMarkExternalSubmitting(false);
        }
    };

    return (
        <div>
            <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-foreground">Invoice ↔ BOE Reconciliation</h3>
                {canMarkExternal && (
                    <Button size="sm" variant="outline" onClick={() => setMarkExternalOpen(true)}>
                        Mark External Invoice
                    </Button>
                )}
            </div>

            <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-sm">
                    <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                        <tr>
                            <th scope="col" className="w-8 px-3 py-2" />
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Invoice #</th>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Supplier</th>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Purchase Date</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Invoice Qty</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Invoice CIF</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Matched Qty</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Matched CIF</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Remaining Qty</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Remaining CIF</th>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Status</th>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {unmatchedInvoices.length === 0 && (
                            <tr>
                                <td colSpan={12} className="px-3 py-6 text-center text-muted-foreground">
                                    No unmatched invoices on this licence.
                                </td>
                            </tr>
                        )}
                        {unmatchedInvoices.map((invoice) => {
                            const key = rowKey(invoice);
                            const isOpen = expanded.has(key);
                            const canFindBoe =
                                canAllocate &&
                                invoice.kind === "system" &&
                                (invoice.remaining_cif > 0 || invoice.remaining_qty > 0);
                            return (
                                <Fragment key={key}>
                                    <tr className="border-t border-border/60">
                                        <td className="px-3 py-2">
                                            <button
                                                type="button"
                                                onClick={() => toggleExpanded(key)}
                                                className="cursor-pointer text-muted-foreground hover:text-foreground"
                                                aria-label={isOpen ? "Collapse" : "Expand"}
                                            >
                                                {isOpen ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                                            </button>
                                        </td>
                                        <td className="px-3 py-2 font-medium">{invoice.invoice_number}</td>
                                        <td className="px-3 py-2">{invoice.supplier ?? "—"}</td>
                                        <td className="whitespace-nowrap px-3 py-2">{fmtDate(invoice.purchase_date)}</td>
                                        <td className="px-3 py-2 text-right">{fmtNum(invoice.invoice_qty)}</td>
                                        <td className="px-3 py-2 text-right">{fmtNum(invoice.invoice_cif)}</td>
                                        <td className="px-3 py-2 text-right">{fmtNum(invoice.matched_qty)}</td>
                                        <td className="px-3 py-2 text-right">{fmtNum(invoice.matched_cif)}</td>
                                        <td className="px-3 py-2 text-right">{fmtNum(invoice.remaining_qty)}</td>
                                        <td className="px-3 py-2 text-right">{fmtNum(invoice.remaining_cif)}</td>
                                        <td className="px-3 py-2">
                                            <Badge variant={invoiceBoeStatusVariant(invoice.status)}>
                                                {invoice.status.replace(/_/g, " ")}
                                            </Badge>
                                        </td>
                                        <td className="px-3 py-2">
                                            {canFindBoe && (
                                                <Button size="sm" variant="outline" onClick={() => setDrawerInvoice(invoice)}>
                                                    <Search className="size-3.5" /> Find BOE
                                                </Button>
                                            )}
                                        </td>
                                    </tr>
                                    {isOpen && (
                                        <tr>
                                            <td colSpan={12} className="border-t border-border/60 bg-muted/30 p-3">
                                                {invoice.linked_boes.length === 0 ? (
                                                    <p className="text-xs text-muted-foreground">No BOEs linked yet.</p>
                                                ) : (
                                                    <table className="w-full text-xs">
                                                        <thead className="text-muted-foreground">
                                                            <tr>
                                                                <th scope="col" className="px-2 py-1 text-left">BOE Number</th>
                                                                <th scope="col" className="px-2 py-1 text-right">Allocated Qty</th>
                                                                <th scope="col" className="px-2 py-1 text-right">Allocated CIF</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {invoice.linked_boes.map((boe) => (
                                                                <tr key={boe.allocation_id ?? boe.link_id}>
                                                                    <td className="px-2 py-1">{boe.bill_of_entry_number}</td>
                                                                    <td className="px-2 py-1 text-right">{fmtNum(boe.allocated_qty)}</td>
                                                                    <td className="px-2 py-1 text-right">{fmtNum(boe.allocated_cif_fc)}</td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                )}
                                            </td>
                                        </tr>
                                    )}
                                </Fragment>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {drawerInvoice && (
                <BoeAllocationDrawer
                    open={drawerInvoice !== null}
                    onClose={() => setDrawerInvoice(null)}
                    title={`Allocate Invoice ${drawerInvoice.invoice_number} to BOE(s)`}
                    description="Select one or more BOEs to allocate this invoice against."
                    qtyLabel="Qty"
                    numberLabel="BOE Number"
                    dateLabel="BOE Date"
                    candidates={boeCandidates}
                    summary={{
                        label: "Invoice",
                        number: drawerInvoice.invoice_number,
                        counterparty: drawerInvoice.supplier,
                        totalQty: drawerInvoice.invoice_qty,
                        totalCif: drawerInvoice.invoice_cif,
                        allocatedQty: drawerInvoice.matched_qty,
                        allocatedCif: drawerInvoice.matched_cif,
                        remainingQty: drawerInvoice.remaining_qty,
                        remainingCif: drawerInvoice.remaining_cif,
                    }}
                    confirmLabel="Allocate"
                    onConfirm={handleAllocateConfirm}
                />
            )}

            <Dialog open={markExternalOpen} onOpenChange={(o) => !markExternalSubmitting && setMarkExternalOpen(o)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Mark External Invoice</DialogTitle>
                        <DialogDescription>
                            Mark a BOE on this licence as belonging to an external or out-of-system invoice.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-3">
                        <div>
                            <label className="mb-1 block text-xs font-medium text-muted-foreground">BOE</label>
                            <select
                                className="flex h-9 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                value={markExternalForm.rowDetailsId}
                                onChange={(e) => setMarkExternalForm((f) => ({ ...f, rowDetailsId: e.target.value }))}
                            >
                                <option value="">Select a BOE…</option>
                                {markExternalBoeOptions.map((c) => {
                                    const sublabel = [fmtDate(c.date), c.counterparty].filter(Boolean).join(" · ");
                                    return (
                                        <option key={c.id} value={c.id}>
                                            {c.number}
                                            {sublabel ? ` (${sublabel})` : ""}
                                        </option>
                                    );
                                })}
                            </select>
                        </div>
                        <div>
                            <label className="mb-1 block text-xs font-medium text-muted-foreground">Invoice Number</label>
                            <input
                                type="text"
                                className="flex h-9 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                value={markExternalForm.invoiceNumber}
                                onChange={(e) => setMarkExternalForm((f) => ({ ...f, invoiceNumber: e.target.value }))}
                                placeholder="e.g. OTH-001245"
                            />
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                            <div>
                                <label className="mb-1 block text-xs font-medium text-muted-foreground">Qty</label>
                                <input
                                    type="number"
                                    min={0}
                                    step="any"
                                    className="flex h-9 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                    value={markExternalForm.qty}
                                    onChange={(e) => setMarkExternalForm((f) => ({ ...f, qty: e.target.value }))}
                                />
                            </div>
                            <div>
                                <label className="mb-1 block text-xs font-medium text-muted-foreground">CIF (FC)</label>
                                <input
                                    type="number"
                                    min={0}
                                    step="any"
                                    className="flex h-9 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                    value={markExternalForm.cifFc}
                                    onChange={(e) => setMarkExternalForm((f) => ({ ...f, cifFc: e.target.value }))}
                                />
                            </div>
                            <div>
                                <label className="mb-1 block text-xs font-medium text-muted-foreground">CIF (INR)</label>
                                <input
                                    type="number"
                                    min={0}
                                    step="any"
                                    className="flex h-9 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                    value={markExternalForm.cifInr}
                                    onChange={(e) => setMarkExternalForm((f) => ({ ...f, cifInr: e.target.value }))}
                                />
                            </div>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setMarkExternalOpen(false)} disabled={markExternalSubmitting}>
                            Cancel
                        </Button>
                        <Button onClick={handleMarkExternalSubmit} disabled={markExternalSubmitting}>
                            {markExternalSubmitting ? "Saving…" : "Mark External"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {confirmDialog}
        </div>
    );
}
