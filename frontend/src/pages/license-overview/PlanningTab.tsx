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
 * "Available Qty/CIF" and "Remaining Qty/CIF" are two columns showing the
 * SAME `remaining_quantity`/`remaining_cif_fc` values on purpose — the
 * backend's `plan_status_for()` has no distinct "Available" concept (see
 * `types.ts`). Rows with `has_plan === false` render "—" for every numeric
 * column (more honest than a fabricated `0` for a group with no plan at all).
 */
export default function PlanningTab({ licenseId, isActive }: PlanningTabProps) {
    const { data, isLoading, isError, error } = useLicenseOverviewPlanning(licenseId, isActive);

    if (!isActive) return null;

    if (isLoading) {
        return (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" /> Loading plan utilization…
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
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Planned CIF</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Available Qty</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Available CIF</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Remaining Qty</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Remaining CIF</th>
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
                            <tr key={row.group_id} className="border-t border-border/60 hover:bg-muted/20">
                                <td className="px-3 py-2">{row.description}</td>
                                <td className="px-3 py-2">{row.hs_code ?? "—"}</td>
                                {row.has_plan ? (
                                    <>
                                        <td className="px-3 py-2 text-right tabular-nums">{fmtNum(row.original_quantity)}</td>
                                        <td className="px-3 py-2 text-right tabular-nums">{fmtNum(row.original_cif_fc)}</td>
                                        <td className="px-3 py-2 text-right tabular-nums">{fmtNum(row.remaining_quantity)}</td>
                                        <td className="px-3 py-2 text-right tabular-nums">{fmtNum(row.remaining_cif_fc)}</td>
                                        <td className="px-3 py-2 text-right tabular-nums">{fmtNum(row.remaining_quantity)}</td>
                                        <td className="px-3 py-2 text-right tabular-nums">{fmtNum(row.remaining_cif_fc)}</td>
                                    </>
                                ) : (
                                    <>
                                        <td className="px-3 py-2 text-right text-muted-foreground">—</td>
                                        <td className="px-3 py-2 text-right text-muted-foreground">—</td>
                                        <td className="px-3 py-2 text-right text-muted-foreground">—</td>
                                        <td className="px-3 py-2 text-right text-muted-foreground">—</td>
                                        <td className="px-3 py-2 text-right text-muted-foreground">—</td>
                                        <td className="px-3 py-2 text-right text-muted-foreground">—</td>
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
