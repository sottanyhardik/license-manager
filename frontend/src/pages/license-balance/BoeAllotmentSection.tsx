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
import type { BoeAllotmentEntry } from "./types";

interface BoeAllotmentSectionProps {
    licenseId: string | number;
    boeAllotment: BoeAllotmentEntry[];
}

/**
 * Derives the candidate allotment list for the "Find Allotment" drawer.
 *
 * BACKEND GAP (flagged in the final report, see also `InvoiceBoeSection.tsx`
 * for the mirrored BOE-side gap): the ledger payload has no "all allotments
 * with free capacity for this licence" list — `boe_allotment[].linked_allotments`
 * only ever contains allotments ALREADY allocated to a specific BOE. As a
 * pragmatic stand-in until a dedicated
 * `GET /licenses/<id>/available-allotments/` endpoint exists, this pulls the
 * distinct allotments already referenced anywhere on this licence so the
 * picker isn't empty — but it CANNOT show true remaining capacity per
 * allotment (not present in this payload), so remaining is left `null` and
 * the drawer surfaces a visible notice. Isolated in this one function so
 * swapping in a real search endpoint later is a one-line change at the call
 * site.
 */
function fetchAllotmentCandidates(boeAllotment: BoeAllotmentEntry[]): AllocationCandidate[] {
    const seen = new Map<number, AllocationCandidate>();
    for (const boe of boeAllotment) {
        for (const linked of boe.linked_allotments) {
            if (!seen.has(linked.allotment_item_id)) {
                seen.set(linked.allotment_item_id, {
                    id: linked.allotment_item_id,
                    label: linked.allotment_number,
                    sublabel: undefined,
                    remainingQty: null,
                    remainingCif: null,
                });
            }
        }
    }
    return Array.from(seen.values());
}

/**
 * Section 3 — BOE ↔ Allotment Reconciliation. Mirrors `InvoiceBoeSection.tsx`
 * one-for-one: expandable rows, a "Find Allotment" allocation drawer.
 */
export default function BoeAllotmentSection({ licenseId, boeAllotment }: BoeAllotmentSectionProps) {
    const { hasRole } = useContext(AuthContext);
    const queryClient = useQueryClient();

    const [expanded, setExpanded] = useState<Set<number>>(new Set());
    const [drawerBoe, setDrawerBoe] = useState<BoeAllotmentEntry | null>(null);

    // Per `LicenseBalanceLedgerPermission.write_action_roles`: BOE<->allotment
    // allocation requires BOE_MANAGER AND ALLOTMENT_MANAGER.
    const canAllocate = hasRole("BOE_MANAGER") && hasRole("ALLOTMENT_MANAGER");

    const allotmentCandidates = useMemo(() => fetchAllotmentCandidates(boeAllotment), [boeAllotment]);

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

            <BoeAllocationDrawer
                open={drawerBoe !== null}
                onClose={() => setDrawerBoe(null)}
                title={`Allocate BOE ${drawerBoe?.bill_of_entry_number ?? ""} to Allotment(s)`}
                description="Select one or more allotments to source this BOE from."
                qtyLabel="Qty"
                candidates={allotmentCandidates}
                targetRemainingQty={drawerBoe?.remaining_qty}
                targetRemainingCif={drawerBoe?.remaining_cif}
                confirmLabel="Allocate"
                onConfirm={handleAllocateConfirm}
                notice="No dedicated 'available allotments' search endpoint exists yet — this list shows allotments already referenced elsewhere on this licence as a placeholder and cannot show true remaining capacity. A GET /licenses/{id}/available-allotments/ endpoint is needed for accurate results."
            />
        </div>
    );
}
