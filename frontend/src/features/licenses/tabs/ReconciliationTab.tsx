import { AlertTriangle, Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import FinalReconciliationSection from "@/pages/license-overview/FinalReconciliationSection";
import { extractApiError } from "@/pages/license-overview/licenseOverviewHelpers";

import { useLicenceLedger } from "../useLicenceLedger";

/**
 * Reconciliation tab: the overview page's per-licence Final Reconciliation
 * section, unchanged, from `balance-ledger/` → `reconciliation` (same cache
 * entry as the Overview summary, so opening it makes no new request).
 */
export default function ReconciliationTab({ licenseId }: { licenseId: number }) {
    const { data, isLoading, isError, error } = useLicenceLedger(licenseId);

    if (isLoading && !data) {
        return (
            <div role="status" className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Loading reconciliation…
            </div>
        );
    }
    if (isError || !data) {
        return (
            <Alert variant="destructive">
                <AlertTriangle className="size-4" aria-hidden="true" />
                <AlertDescription>{extractApiError(error, "Failed to load licence balance data.")}</AlertDescription>
            </Alert>
        );
    }
    return (
        <div className="max-w-xl">
            <FinalReconciliationSection reconciliation={data.reconciliation} />
        </div>
    );
}
