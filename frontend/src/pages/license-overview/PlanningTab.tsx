import { useState } from "react";
import { AlertTriangle, Loader2, Target, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { useLicenseOverviewPlanning } from "./useLicenseOverviewPlanning";
import { extractApiError, fmtNum } from "./licenseOverviewHelpers";
import { planLicense } from "@/services/api/planningRuleApi";

interface PlanningTabProps {
    licenseId: string | number | undefined;
    isActive: boolean;
}

/**
 * Planning tab — SION plan-vs-usage utilization, from
 * `GET /licenses/<id>/plan-utilization/`. The `norm` field is license-level
 * (same value for every row), so it's shown once in a header line rather
 * than repeated as its own column in every row — reads cleaner for a value
 * that never varies within the table, and avoids a column that would be
 * 100% identical top-to-bottom.
 *
 * Quantity feasibility and shortage are supplied by the canonical backend
 * planning service. This component deliberately performs no planning maths.
 */
export default function PlanningTab({ licenseId, isActive }: PlanningTabProps) {
    const { data, isLoading, isError, error, refetch } = useLicenseOverviewPlanning(licenseId, isActive);
    const [isPlanning, setIsPlanning] = useState(false);
    const [showForceConfirm, setShowForceConfirm] = useState(false);

    const handlePlan = async (mode: "NEW" | "ALL") => {
        if (!licenseId || isPlanning) return;
        setIsPlanning(true);
        try {
            const result = await planLicense(Number(licenseId), mode);
            const siansExecuted = result?.total_results?.sions_executed || 0;
            const linesWritten = result?.total_results?.total_lines_written || 0;

            // Build result message based on what happened
            let message = "";
            if (linesWritten === 0) {
                message = "Planning already up to date. No new eligible items were found.";
            } else if (mode === "ALL") {
                message = `Force re-plan completed: ${siansExecuted} SION${siansExecuted !== 1 ? 's' : ''}, ${linesWritten} line${linesWritten !== 1 ? 's' : ''} processed`;
            } else {
                message = `Planning completed: ${siansExecuted} SION${siansExecuted !== 1 ? 's' : ''}, ${linesWritten} line${linesWritten !== 1 ? 's' : ''} planned`;
            }

            toast.success(message);
            // Refetch the planning data to show updated plan info
            refetch?.();
        } catch (error) {
            const message = error && typeof error === 'object' && 'response' in error
                ? (error as any).response?.data?.error || (error as any).response?.data?.detail || 'Failed to plan license'
                : 'Failed to plan license';
            toast.error(message);
        } finally {
            setIsPlanning(false);
            setShowForceConfirm(false);
        }
    };

    const handleAutoPlan = () => {
        handlePlan("NEW");
    };

    const handleForceReplan = () => {
        setShowForceConfirm(true);
    };

    if (!isActive) return null;

    if (isLoading) {
        return (
            <div role="status" aria-live="polite" className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Loading plan utilization…
            </div>
        );
    }

    if (isError) {
        return (
            <Alert variant="destructive">
                <AlertTriangle className="size-4" />
                <AlertDescription>{extractApiError(error, "Failed to load plan utilization.")}</AlertDescription>
            </Alert>
        );
    }

    const rows = data?.rows ?? [];
    const norm = data?.norm;

    return (
        <div>
            <div className="mb-6 flex items-center justify-between">
                <h3 className="flex items-center gap-2 text-lg font-semibold">
                    <div className="size-5 rounded-full bg-blue-100 flex items-center justify-center">
                        <div className="size-2 rounded-full bg-blue-600" />
                    </div>
                    Plan utilization
                </h3>
                <div className="flex items-center gap-2">
                    <Button
                        onClick={handleAutoPlan}
                        disabled={isPlanning || !norm}
                        size="sm"
                        variant="outline"
                        className="gap-2 text-amber-600 border-amber-200 hover:bg-amber-50"
                    >
                        {isPlanning ? (
                            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                        ) : (
                            <Target className="size-3.5" aria-hidden="true" />
                        )}
                        {isPlanning ? "Planning..." : "Auto Plan"}
                    </Button>
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button
                                variant="outline"
                                size="sm"
                                className="px-2"
                                disabled={isPlanning || !norm}
                            >
                                <ChevronDown className="size-4" aria-hidden="true" />
                                <span className="sr-only">Planning options</span>
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-48">
                            <DropdownMenuItem onClick={handleAutoPlan} disabled={isPlanning}>
                                Auto Plan — New Only
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={handleForceReplan} disabled={isPlanning}>
                                Force Re-plan
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>

            <div className="mb-4 flex items-center gap-4">
                <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">SION Norm</span>
                    <Badge variant={norm ? "info" : "secondary"}>{norm || "—"}</Badge>
                </div>
            </div>

            <Dialog open={showForceConfirm} onOpenChange={setShowForceConfirm}>
                <DialogContent>
                    <DialogTitle>Re-plan this license?</DialogTitle>
                    <DialogDescription className="py-4">
                        Existing planning for license {data?.license_number} will be
                        recalculated using the current saved {norm} rules.
                    </DialogDescription>
                    <div className="flex gap-2 justify-end">
                        <Button variant="outline" onClick={() => setShowForceConfirm(false)}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={() => handlePlan("ALL")}
                        >
                            Force Re-plan
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>

            <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-sm">
                    <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                        <tr>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Export Product</th>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">HSN Code</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Planned Qty</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Allocated Qty</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Available Qty</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Remaining Qty</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Shortage Qty</th>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.length === 0 && (
                            <tr>
                                <td colSpan={8} className="px-3 py-6 text-center text-muted-foreground">
                                    No export product groups on this licence.
                                </td>
                            </tr>
                        )}
                        {rows.map((row) => (
                            <tr key={row.group_id} className="border-t border-border/60 hover:bg-muted/20" data-planning-status={row.status}>
                                <td className="px-3 py-2">{row.description}</td>
                                <td className="px-3 py-2">{row.hs_code ?? "—"}</td>
                                {row.has_plan ? (
                                    <>
                                        <td className="px-3 py-2 text-right tabular-nums">{fmtNum(row.planned_qty)}</td>
                                        <td className="px-3 py-2 text-right tabular-nums">{fmtNum(row.allocated_qty)}</td>
                                        <td className="px-3 py-2 text-right tabular-nums">{fmtNum(row.available_qty)}</td>
                                        <td className="px-3 py-2 text-right tabular-nums">{fmtNum(row.remaining_qty)}</td>
                                        <td className={`px-3 py-2 text-right tabular-nums font-semibold ${row.status === "SHORT" ? "text-destructive" : ""}`}>{fmtNum(row.shortage_qty)}</td>
                                        <td className="px-3 py-2">
                                            <Badge variant={row.status === "FEASIBLE" ? "success" : "destructive"}>
                                                {row.status === "BLOCKED_UNIT_MISMATCH"
                                                    ? "Blocked: unit mismatch"
                                                    : row.status === "SHORT" ? `Short by ${fmtNum(row.shortage_qty)}` : "Feasible"}
                                            </Badge>
                                        </td>
                                    </>
                                ) : (
                                    <>
                                        <td className="px-3 py-2 text-right text-muted-foreground">—</td>
                                        <td className="px-3 py-2 text-right text-muted-foreground">—</td>
                                        <td className="px-3 py-2 text-right text-muted-foreground">—</td>
                                        <td className="px-3 py-2 text-right text-muted-foreground">—</td>
                                        <td className="px-3 py-2 text-right text-muted-foreground">—</td>
                                        <td className="px-3 py-2"><Badge variant="secondary">Unplanned</Badge></td>
                                    </>
                                )}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
