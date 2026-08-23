import { Info } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

/**
 * Shown in place of the Financial Ledger card (and gates the Financial
 * Summary / Final Reconciliation cards below it) on the Overview page only,
 * when a license has no Purchase or Sale yet (`financial_ledger.summary.
 * has_trading_activity === false`). Non-dismissible; neutral (`default`)
 * variant, not a warning/error state. Purely presentational — the license
 * still has real BOE/allotment/ledger data, it's just not "trade" for the
 * purpose of this page.
 */
export default function NoTradeActivityBanner() {
    return (
        // `Alert` defaults to `role="alert"` (assertive live region), meant
        // for urgent/error announcements. This banner is purely
        // informational and typically mounts after the ledger query
        // resolves (not on initial paint), so an assertive role would
        // interrupt screen-reader users to announce routine, non-critical
        // text. `role="status"` (implicit `aria-live="polite"`) is the
        // correct level here — it still gets announced, just without
        // interrupting.
        <Alert variant="default" role="status">
            <Info className="size-4" />
            <AlertDescription>
                <p className="font-medium text-foreground">No trade activity has been recorded for this license yet.</p>
                <p className="text-muted-foreground">
                    Financial reporting will automatically appear after the first Purchase or Sale associated with
                    this license.
                </p>
            </AlertDescription>
        </Alert>
    );
}
