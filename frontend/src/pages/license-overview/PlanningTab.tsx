import { AlertTriangle, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useLicenseOverviewPlanning } from "./useLicenseOverviewPlanning";
import { extractApiError, fmtNum } from "./licenseOverviewHelpers";

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
    const { data, isLoading, isError, error } = useLicenseOverviewPlanning(licenseId, isActive);

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
            <div className="mb-3 flex items-center gap-2">
                <span className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">SION Norm</span>
                <Badge variant={norm ? "info" : "secondary"}>{norm || "—"}</Badge>
            </div>

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
