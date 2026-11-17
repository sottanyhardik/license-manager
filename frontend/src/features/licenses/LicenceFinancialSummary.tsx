import { AlertTriangle, Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { StatusBadge } from "@/components/shared";
import { cn } from "@/lib/utils";
import type { CustomsLedgerSummary } from "@/pages/license-balance/types";
import { extractApiError } from "@/pages/license-overview/licenseOverviewHelpers";

import { FINANCIAL_SUMMARY_FIELDS } from "./financialSummaryFields";
import { formatCifUsd, isNegativeValue } from "./licenceFormat";
import { useLicenceLedger } from "./useLicenceLedger";

function hasValue(v: unknown): boolean {
    return v !== null && v !== undefined && v !== "";
}

function FinancialSummaryList({ summary }: { summary: CustomsLedgerSummary }) {
    return (
        <dl className="grid grid-cols-2 gap-1 rounded-lg border border-border bg-card p-1 sm:grid-cols-3 xl:grid-cols-6">
            {FINANCIAL_SUMMARY_FIELDS.filter((f) => hasValue(summary[f.key])).map((f) => {
                const value = summary[f.key];
                return (
                    <div key={f.key} className={cn("min-w-0 rounded-md px-2.5 py-1.5", f.emphasis && "bg-muted")}>
                        <dt className="truncate text-xs text-muted-foreground" title={f.label}>{f.label}</dt>
                        <dd
                            className={cn(
                                "mt-0.5 text-right text-sm font-medium tabular-nums text-foreground",
                                f.emphasis && "text-base font-semibold",
                                f.signed && isNegativeValue(value) && "text-destructive",
                            )}
                        >
                            {formatCifUsd(value)}
                        </dd>
                    </div>
                );
            })}
            {typeof summary.mismatched === "boolean" && (
                <div className="min-w-0 rounded-md px-2.5 py-1.5">
                    <dt className="truncate text-xs text-muted-foreground">Reconciliation</dt>
                    <dd className="mt-0.5 flex justify-end">
                        <StatusBadge
                            tone={summary.mismatched ? "danger" : "success"}
                            label={summary.mismatched ? "Reconciliation Failed" : "Reconciled"}
                        />
                    </dd>
                </div>
            )}
        </dl>
    );
}

/** Compact financial summary for one licence (shares the ledger query with the other card sections). */
export default function LicenceFinancialSummary({ licenseId }: { licenseId: number }) {
    const { data, isLoading, isError, error } = useLicenceLedger(licenseId);

    if (isLoading && !data) {
        return (
            <div role="status" className="flex items-center gap-2 px-1 py-3 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Loading financial summary…
            </div>
        );
    }
    if (isError) {
        return (
            <Alert variant="destructive">
                <AlertTriangle className="size-4" aria-hidden="true" />
                <AlertDescription>{extractApiError(error, "Failed to load licence balance data.")}</AlertDescription>
            </Alert>
        );
    }
    const summary = data?.customs_ledger?.summary;
    if (!summary) return null;

    return (
        <section aria-label="Financial summary">
            <FinancialSummaryList summary={summary} />
        </section>
    );
}
