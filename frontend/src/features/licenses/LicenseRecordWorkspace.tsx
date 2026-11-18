import { lazy, Suspense, useEffect, useMemo, useRef, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { DetailTabs, type DetailTab } from "@/components/workspace";
import { LoadingState } from "@/components/shared";
import { invalidateLicence } from "@/lib/queryKeys";
import LicenseOverviewContent from "@/pages/license-overview/LicenseOverviewContent";

import OverviewTab from "./tabs/OverviewTab";
import ImportItemTab from "./tabs/ImportItemTab";
import BoeAllotmentTab from "./tabs/BoeAllotmentTab";
import InvoicesTab from "./tabs/InvoicesTab";
import ReconciliationTab from "./tabs/ReconciliationTab";
import { useLicenceLedger } from "./useLicenceLedger";

// The one licence form (same fields, validation, API and permissions as /licenses/:id/edit), embedded in the
// expanded licence. Lazy so the register does not load the form until a writer opens Edit.
const MasterForm = lazy(() => import("@/pages/masters/MasterForm"));

export type LicenseRecordTabId =
    | "overview"
    | "import-item"
    | "boe-allotment"
    | "invoices"
    | "plan"
    | "reconciliation"
    | "edit"
    | "history";

export interface LicenseRecordWorkspaceProps {
    licenseId: number;
    licenseNumber?: string | null;
    canWrite: boolean;
    activeTab: LicenseRecordTabId;
    onTabChange: (tab: LicenseRecordTabId) => void;
    renderHistory: () => ReactNode;
}

/** Trailing debounce so a burst of per-row plan saves triggers one refetch, not one each. */
const PLAN_SAVED_DEBOUNCE_MS = 300;

/**
 * Card Planning tab. Mirrors LicenseOverviewPage: after a plan save the licence
 * detail prefix is invalidated so overview, items and ledger refresh (D5).
 * The editor fires `onSaved` per row; `invalidateQueries` cancels and restarts
 * an in-flight refetch, so saves are coalesced here. A pending invalidation is
 * flushed on unmount (tab switch) so a save is never left stale.
 */
function PlanningTab({ licenseId }: { licenseId: number }) {
    const queryClient = useQueryClient();
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

    const onSaved = useMemo(() => () => {
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => {
            timer.current = null;
            void invalidateLicence(queryClient, licenseId);
        }, PLAN_SAVED_DEBOUNCE_MS);
    }, [queryClient, licenseId]);

    useEffect(() => () => {
        if (timer.current) {
            clearTimeout(timer.current);
            timer.current = null;
            void invalidateLicence(queryClient, licenseId);
        }
    }, [queryClient, licenseId]);

    return <LicenseOverviewContent licenseId={licenseId} activeTab="planning" mode="embedded" onSaved={onSaved} />;
}

/**
 * Inline licence edit (Edit tab): save refreshes this licence and the register in place; Save/Cancel return
 * to Overview. List filters, page and scroll are untouched because nothing navigates.
 */
function EditTab({ licenseId, onDone }: { licenseId: number; onDone: () => void }) {
    const queryClient = useQueryClient();
    return (
        <Suspense fallback={<LoadingState variant="spinner" label="Loading licence form" />}>
            <MasterForm
                embedded
                entityName="licenses"
                recordId={licenseId}
                onSuccess={() => {
                    void invalidateLicence(queryClient, licenseId);
                    void queryClient.invalidateQueries({ queryKey: ["entity-list", "licenses"] });
                }}
                onClose={onDone}
            />
        </Suspense>
    );
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
        { id: "plan", label: "Planning", visible: canWrite, render: () => <PlanningTab licenseId={licenseId} /> },
        { id: "reconciliation", label: "Reconciliation", visible: hasTradingActivity, render: () => <ReconciliationTab licenseId={licenseId} /> },
        // Same write rule as the action menu's Edit (LICENSE_MANAGER); the API enforces LicensePermission on save.
        { id: "edit", label: "Edit", visible: canWrite, render: () => <EditTab licenseId={licenseId} onDone={() => onTabChange("overview")} /> },
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
