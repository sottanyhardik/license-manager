import { Fragment, useContext, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ChevronDown, ChevronRight, Search } from "lucide-react";
import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import BoeAllocationDrawer, { type AllocationCandidate, type AllocationSelection } from "@/components/BoeAllocationDrawer";
import { licenseBalanceKeys } from "./useLicenseBalanceLedger";
import { boeAllotmentStatusVariant, extractApiError, fmtDate, fmtNum } from "./licenseBalanceHelpers";
import type { AllotmentCandidate, BoeAllotmentEntry } from "./types";

interface BoeAllotmentSectionProps {
    licenseId: string | number;
    boeAllotment: BoeAllotmentEntry[];
    /** The correct candidate source for "Find Allotment" — real remaining-capacity-to-be-sourced per allotment item. */
    allotmentCandidates: AllotmentCandidate[];
}

/**
 * Maps `allotment_candidates` (server-computed via
 * `remaining_for_allotment_item`, see
 * `LicenseBalanceLedgerBuilder.build_allotment_candidates`) to the drawer's
 * generic candidate shape.
 *
 * This REPLACES the previous client-side derivation from
 * `boe_allotment[].linked_allotments` (which only ever listed allotments
 * ALREADY allocated to some BOE, with no real remaining-capacity figure —
 * `remainingQty`/`remainingCif` were hardcoded to `null`). The new list has
 * real, server-computed remaining capacity for every allotment item with
 * some left, whether or not it has been touched yet.
 */
function toAllocationCandidates(candidates: AllotmentCandidate[]): AllocationCandidate[] {
    return candidates.map((c) => ({
        id: c.allotment_item_id,
        number: c.allotment_number,
        date: c.estimated_arrival_date,
        counterparty: c.company,
        itemName: c.item_name,
        totalQty: c.allotment_qty,
        totalCif: c.allotment_cif,
        remainingQty: c.remaining_qty,
        remainingCif: c.remaining_cif,
    }));
}

/**
 * Section 3 — BOE ↔ Allotment Reconciliation. Mirrors `InvoiceBoeSection.tsx`
 * one-for-one: expandable rows, a "Find Allotment" allocation drawer.
 */
export default function BoeAllotmentSection({ licenseId, boeAllotment, allotmentCandidates }: BoeAllotmentSectionProps) {
    const { hasRole } = useContext(AuthContext);
    const queryClient = useQueryClient();

    const [expanded, setExpanded] = useState<Set<number>>(new Set());
    const [drawerBoe, setDrawerBoe] = useState<BoeAllotmentEntry | null>(null);

    // Per `LicenseBalanceLedgerPermission.write_action_roles`: BOE<->allotment
    // allocation requires BOE_MANAGER AND ALLOTMENT_MANAGER.
    const canAllocate = hasRole("BOE_MANAGER") && hasRole("ALLOTMENT_MANAGER");

    const allotmentDrawerCandidates = useMemo(() => toAllocationCandidates(allotmentCandidates), [allotmentCandidates]);

    const invalidate = () => queryClient.invalidateQueries({ queryKey: licenseBalanceKeys.ledger(licenseId) });

    const toggleExpanded = (id: number) => {
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const handleAllocateConfirm = async (selections: AllocationSelection[]) => {
        if (!drawerBoe) return;
        try {
            await api.post(`licenses/${licenseId}/allocate-boe-allotment/`, {
                row_details_id: drawerBoe.row_details_id,
                allocations: selections.map((s) => ({
                    allotment_item_id: s.id,
                    qty: s.qty,
                    cif_fc: s.cifFc,
                    cif_inr: s.cifInr,
                    notes: s.notes || undefined,
                })),
            });
            toast.success("BOE allocated to allotment(s).");
            invalidate();
            setDrawerBoe(null);
        } catch (err) {
            toast.error(extractApiError(err, "Failed to allocate BOE to allotment."));
            throw err;
        }
    };

    return (
        <div>
            <h3 className="mb-3 text-sm font-semibold text-foreground">BOE ↔ Allotment Reconciliation</h3>

            <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-sm">
                    <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                        <tr>
                            <th scope="col" className="w-8 px-3 py-2" />
                            <th scope="col" className="px-3 py-2 text-left font-semibold">BOE Number</th>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Date</th>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Company</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">BOE Qty</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">BOE CIF</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Matched Qty</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Matched CIF</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Remaining Qty</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Remaining CIF</th>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Status</th>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {boeAllotment.length === 0 && (
                            <tr>
                                <td colSpan={12} className="px-3 py-6 text-center text-muted-foreground">
                                    No BOE debit rows on this licence.
                                </td>
                            </tr>
                        )}
                        {boeAllotment.map((boe) => {
                            const isOpen = expanded.has(boe.row_details_id);
                            const canFindAllotment = canAllocate && (boe.remaining_cif > 0 || boe.remaining_qty > 0);
                            return (
                                <Fragment key={boe.row_details_id}>
                                    <tr className="border-t border-border/60">
                                        <td className="px-3 py-2">
                                            <button
                                                type="button"
                                                onClick={() => toggleExpanded(boe.row_details_id)}
                                                className="cursor-pointer text-muted-foreground hover:text-foreground"
                                                aria-label={isOpen ? "Collapse" : "Expand"}
                                            >
                                                {isOpen ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                                            </button>
                                        </td>
                                        <td className="px-3 py-2 font-medium">{boe.bill_of_entry_number}</td>
                                        <td className="whitespace-nowrap px-3 py-2">{fmtDate(boe.bill_of_entry_date)}</td>
                                        <td className="px-3 py-2">{boe.company ?? "—"}</td>
                                        <td className="px-3 py-2 text-right">{fmtNum(boe.boe_qty)}</td>
                                        <td className="px-3 py-2 text-right">{fmtNum(boe.boe_cif)}</td>
                                        <td className="px-3 py-2 text-right">{fmtNum(boe.matched_qty)}</td>
                                        <td className="px-3 py-2 text-right">{fmtNum(boe.matched_cif)}</td>
                                        <td className="px-3 py-2 text-right">{fmtNum(boe.remaining_qty)}</td>
                                        <td className="px-3 py-2 text-right">{fmtNum(boe.remaining_cif)}</td>
                                        <td className="px-3 py-2">
                                            <Badge variant={boeAllotmentStatusVariant(boe.status)}>
                                                {boe.status.replace(/_/g, " ")}
                                            </Badge>
                                        </td>
                                        <td className="px-3 py-2">
                                            {canFindAllotment && (
                                                <Button size="sm" variant="outline" onClick={() => setDrawerBoe(boe)}>
                                                    <Search className="size-3.5" /> Find Allotment
                                                </Button>
                                            )}
                                        </td>
                                    </tr>
                                    {isOpen && (
                                        <tr>
                                            <td colSpan={12} className="border-t border-border/60 bg-muted/30 p-3">
                                                {boe.linked_allotments.length === 0 ? (
                                                    <p className="text-xs text-muted-foreground">No allotments linked yet.</p>
                                                ) : (
                                                    <table className="w-full text-xs">
                                                        <thead className="text-muted-foreground">
                                                            <tr>
                                                                <th scope="col" className="px-2 py-1 text-left">Allotment</th>
                                                                <th scope="col" className="px-2 py-1 text-right">Allocated Qty</th>
                                                                <th scope="col" className="px-2 py-1 text-right">Allocated CIF</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {boe.linked_allotments.map((allotment) => (
                                                                <tr key={allotment.allocation_id}>
                                                                    <td className="px-2 py-1">{allotment.allotment_number}</td>
                                                                    <td className="px-2 py-1 text-right">{fmtNum(allotment.allocated_qty)}</td>
                                                                    <td className="px-2 py-1 text-right">{fmtNum(allotment.allocated_cif_fc)}</td>
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

            {drawerBoe && (
                <BoeAllocationDrawer
                    open={drawerBoe !== null}
                    onClose={() => setDrawerBoe(null)}
                    title={`Allocate BOE ${drawerBoe.bill_of_entry_number} to Allotment(s)`}
                    description="Select one or more allotments to source this BOE from."
                    qtyLabel="Qty"
                    numberLabel="Allotment Number"
                    dateLabel="Est. Arrival"
                    candidates={allotmentDrawerCandidates}
                    summary={{
                        label: "BOE",
                        number: drawerBoe.bill_of_entry_number,
                        counterparty: drawerBoe.company,
                        totalQty: drawerBoe.boe_qty,
                        totalCif: drawerBoe.boe_cif,
                        allocatedQty: drawerBoe.matched_qty,
                        allocatedCif: drawerBoe.matched_cif,
                        remainingQty: drawerBoe.remaining_qty,
                        remainingCif: drawerBoe.remaining_cif,
                    }}
                    confirmLabel="Allocate"
                    onConfirm={handleAllocateConfirm}
                />
            )}
        </div>
    );
}
