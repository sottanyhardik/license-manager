import type { ReactNode } from "react";

import { DetailTabs, type DetailTab } from "@/components/workspace";
import LicenseOverviewContent from "@/pages/license-overview/LicenseOverviewContent";

import OverviewTab from "./tabs/OverviewTab";
import ImportItemTab from "./tabs/ImportItemTab";
import BoeAllotmentTab from "./tabs/BoeAllotmentTab";
import InvoicesTab from "./tabs/InvoicesTab";
import ReconciliationTab from "./tabs/ReconciliationTab";
import { useLicenceLedger } from "./useLicenceLedger";

export type LicenseRecordTabId =
    | "overview"
    | "import-item"
    | "boe-allotment"
    | "invoices"
    | "plan"
    | "reconciliation"
    | "history";

export interface LicenseRecordWorkspaceProps {
    licenseId: number;
    licenseNumber?: string | null;
    canWrite: boolean;
    activeTab: LicenseRecordTabId;
    onTabChange: (tab: LicenseRecordTabId) => void;
    renderHistory: () => ReactNode;
}

/**
 * Tabs of one expanded licence (05 §16). Lazy (only the active body mounts),
 * keyed `license:<id>` so records never share panel state. Every body reuses an
 * existing component and endpoint; nothing is computed here.
 *
 * Tablist scrolls horizontally instead of wrapping (DetailTabs is shared, so
 * this is done from the outside via the root className).
 */
export default function LicenseRecordWorkspace({
    licenseId,
    licenseNumber,
    canWrite,
    activeTab,
    onTabChange,
    renderHistory,
}: LicenseRecordWorkspaceProps) {
    // Same gate as the /licenses/:id/overview page (OverviewTab `showFinancialSections`):
    // reconciliation is only shown once the licence has Purchase/Sale activity.
    // Shares the card's single balance-ledger cache entry (no extra request).
    const { data: ledger } = useLicenceLedger(licenseId);
    const hasTradingActivity = ledger?.financial_ledger.summary.has_trading_activity ?? false;

    const tabs: DetailTab[] = [
        { id: "overview", label: "Overview", render: () => <OverviewTab licenseId={licenseId} /> },
        { id: "import-item", label: "Import Items", render: () => <ImportItemTab licenseId={licenseId} /> },
        { id: "boe-allotment", label: "BOE & Allotment", render: () => <BoeAllotmentTab licenseId={licenseId} /> },
        { id: "invoices", label: "Invoices", render: () => <InvoicesTab licenseId={licenseId} /> },
        { id: "plan", label: "Planning", visible: canWrite, render: () => <LicenseOverviewContent licenseId={licenseId} activeTab="planning" mode="embedded" /> },
        { id: "reconciliation", label: "Reconciliation", visible: hasTradingActivity, render: () => <ReconciliationTab licenseId={licenseId} /> },
        { id: "history", label: "History", render: renderHistory },
    ];

    return (
        <DetailTabs
            recordKey={`license:${licenseId}`}
            tabs={tabs}
            value={activeTab}
            onValueChange={(id) => onTabChange(id as LicenseRecordTabId)}
            className="min-w-0 [&_[role=tablist]]:flex-nowrap [&_[role=tablist]]:overflow-x-auto [&_[role=tab]]:shrink-0"
            ariaLabel={`License ${licenseNumber || licenseId} sections`}
        />
    );
}
