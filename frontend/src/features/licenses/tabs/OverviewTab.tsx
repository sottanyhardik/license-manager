import { AlertTriangle } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { ModuleAccordion } from "@/components/workspace";
import FinancialLedgerTable from "@/pages/license-overview/FinancialLedgerTable";
import NoTradeActivityBanner from "@/pages/license-overview/NoTradeActivityBanner";

import LicenceFinancialSummary from "../LicenceFinancialSummary";
import { useLicenceLedger } from "../useLicenceLedger";

/** Financial ledger section body: the overview page's existing table, same gating (`has_trading_activity`). */
function FinancialLedgerSection({ licenseId }: { licenseId: number }) {
    const { data } = useLicenceLedger(licenseId);
    if (!data) return <p role="status" className="py-2 text-sm text-muted-foreground">Loading financial ledger…</p>;
    const summary = data.financial_ledger.summary;
    return (
        <div className="space-y-3">
            {summary.missing_purchase_warning?.show_warning && (
                <Alert variant="warning">
                    <AlertTriangle className="size-4" aria-hidden="true" />
                    <AlertDescription>{summary.missing_purchase_warning.message}</AlertDescription>
                </Alert>
            )}
            {summary.has_trading_activity ? <FinancialLedgerTable rows={data.financial_ledger.rows} /> : <NoTradeActivityBanner />}
        </div>
    );
}

/**
 * Overview tab: compact financial summary, then the overview page's detail
 * sections (collapsed, mounted only when opened). Identity lives in the card
 * header above the tabs, so it is not repeated here. Item rows are owned by
 * the Import Items tab.
 */
export default function OverviewTab({ licenseId }: { licenseId: number }) {
    return (
        <div className="space-y-3">
            <LicenceFinancialSummary licenseId={licenseId} />
            <ModuleAccordion
                persistKey={`license:${licenseId}:overview`}
                sections={[
                    { id: "financial-ledger", title: "Financial ledger", render: () => <FinancialLedgerSection licenseId={licenseId} /> },
                ]}
            />
        </div>
    );
}
