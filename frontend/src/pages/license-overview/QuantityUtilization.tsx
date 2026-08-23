import { cn } from "@/lib/utils";
import { fmtNum } from "./licenseOverviewHelpers";

/**
 * Read-only presentation of the canonical quantity values returned for one
 * licence import item.  This component deliberately performs no arithmetic:
 * BOE debits, allotments and plans can overlap in the domain, so callers must
 * pass the server-authoritative values rather than a client-side total.
 */
export interface QuantityUtilizationValues {
    totalQuantity?: number | null;
    boeDebitedQuantity?: number | null;
    allottedQuantity?: number | null;
    plannedQuantity?: number | null;
    actualAvailableQuantity?: number | null;
    planRemainingQuantity?: number | null;
}

interface QuantityMetricDefinition {
    key: keyof QuantityUtilizationValues;
    label: string;
    description: string;
    availability?: boolean;
}

const METRICS: QuantityMetricDefinition[] = [
    { key: "totalQuantity", label: "Total Qty", description: "Original eligible quantity on this import item." },
    { key: "boeDebitedQuantity", label: "BOE Debited", description: "Quantity actually debited through Bills of Entry." },
    { key: "allottedQuantity", label: "Allotted", description: "Quantity assigned through allotments under the current canonical rules." },
    { key: "plannedQuantity", label: "Planned", description: "Informational quantity reserved in planning; it does not reduce Actual Available Qty." },
    { key: "actualAvailableQuantity", label: "Actual Available", description: "Current server-authoritative available quantity." , availability: true },
    { key: "planRemainingQuantity", label: "Plan Remaining", description: "Remaining quantity on the active plan, when returned by the server.", availability: true },
];

export interface QuantityUtilizationProps {
    values: QuantityUtilizationValues;
    /** Optional source-supported unit. It is display-only and never inferred. */
    unit?: string | null;
    className?: string;
    /** Gives each repeated item strip a distinct accessible name. */
    label?: string;
}

function availabilityState(value: number | null | undefined, isAvailability: boolean): string | null {
    if (!isAvailability || value === null || value === undefined) return null;
    if (value < 0) return "Review: negative";
    if (value === 0) return "Exhausted";
    return null;
}

/**
 * Compact, accessible quantity strip used wherever the response carries the
 * canonical item values.  Missing fields remain an em dash; they are never
 * coerced to zero.  There is intentionally no stacked/percentage chart here
 * because the supplied utilization dimensions are not assumed to be mutually
 * exclusive.
 */
export default function QuantityUtilization({ values, unit, className, label = "Quantity utilization" }: QuantityUtilizationProps) {
    return (
        <section className={cn("rounded-lg border border-border/70 bg-muted/20 p-2", className)} aria-label={label}>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-3 xl:grid-cols-6">
                {METRICS.map((metric) => {
                    const value = values[metric.key];
                    const state = availabilityState(value, metric.availability === true);
                    const isNegative = typeof value === "number" && value < 0;

                    return (
                        <div key={metric.key} className="min-w-0" title={metric.description}>
                            <dt className="truncate text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                                {metric.label}
                            </dt>
                            <dd
                                className={cn(
                                    "mt-0.5 flex items-baseline gap-1 text-[13px] font-semibold tabular-nums",
                                    isNegative && "text-destructive",
                                    state === "Exhausted" && "text-warning"
                                )}
                            >
                                <span>{fmtNum(value, 3)}</span>
                                {unit ? <span className="truncate text-[10px] font-medium text-muted-foreground">{unit}</span> : null}
                            </dd>
                            {state ? <p className="mt-0.5 text-[10px] font-medium text-muted-foreground">{state}</p> : null}
                        </div>
                    );
                })}
            </dl>
        </section>
    );
}
