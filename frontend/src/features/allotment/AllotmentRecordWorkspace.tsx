import { useContext } from "react";

import { DetailTabs, type DetailTab } from "@/components/workspace";
import { AuthContext } from "@/context/AuthContext";
import { BOE_LIST_ROLES, ROLES } from "@/routes/authorizationRoles";
import { AllocateTab } from "./tabs/AllocateTab";
import { AllocationTab } from "./tabs/AllocationTab";
import { AllottedLicencesTab } from "./tabs/AllottedLicencesTab";
import { BoeTab } from "./tabs/BoeTab";
import { DocumentsTab } from "./tabs/DocumentsTab";
import { EditTab } from "./tabs/EditTab";
import { HistoryTab } from "./tabs/HistoryTab";
import { OverviewTab } from "./tabs/OverviewTab";
import type { AllotmentCardAction, AllotmentRecord } from "./types";

export type AllotmentTabId = "overview" | "licences" | "allocation" | "allocate" | "boe" | "documents" | "edit" | "history";

type Props = {
    item: AllotmentRecord;
    actions: AllotmentCardAction[];
    canWrite: boolean;
    activeTab: AllotmentTabId;
    onTabChange: (tab: AllotmentTabId) => void;
};

/**
 * Expanded body of an allotment row. Tabs are lazy (only the active one mounts)
 * and keyed `allotment:<id>`, so switching records drops all state. Every tab
 * reads an existing endpoint; nothing is computed here. Hidden when they have
 * no data or permission:
 *
 * - Allocate Licence / Edit — allotment write access (the API still enforces it);
 * - BOE — only when the allotment is BOE-linked and the user can read BOEs;
 * - History — the audit log API is restricted to user managers.
 */
export function AllotmentRecordWorkspace({ item, actions, canWrite, activeTab, onTabChange }: Props) {
    const { hasAnyRole } = useContext(AuthContext);
    const rows = item.allotment_details || [];
    const licenceCount = new Set(rows.map((r) => r.license_number).filter(Boolean)).size;
    const canViewBoes = !!item.is_boe && hasAnyRole(BOE_LIST_ROLES);
    const tabs: DetailTab[] = [
        { id: "overview", label: "Overview", render: () => <OverviewTab id={item.id} /> },
        {
            id: "licences", label: `Allotted Licences (${licenceCount})`,
            render: () => <AllottedLicencesTab id={item.id} canWrite={canWrite} canViewBoes={canViewBoes} onAllocate={() => onTabChange("allocate")} onViewBoes={() => onTabChange("boe")} />,
        },
        { id: "allocation", label: "Allocation", render: () => <AllocationTab id={item.id} /> },
        { id: "allocate", label: "Allocate Licence", visible: canWrite, render: () => <AllocateTab id={item.id} /> },
        { id: "boe", label: "BOE", visible: canViewBoes, render: () => <BoeTab id={item.id} /> },
        { id: "documents", label: "Documents", render: () => <DocumentsTab rows={rows} actions={actions} /> },
        { id: "edit", label: "Edit", visible: canWrite, render: () => <EditTab id={item.id} onDone={() => onTabChange("overview")} /> },
        { id: "history", label: "History", visible: hasAnyRole([ROLES.USER_MANAGER]), render: () => <HistoryTab id={item.id} /> },
    ];
    return (
        <DetailTabs
            recordKey={`allotment:${item.id}`}
            tabs={tabs}
            value={activeTab}
            onValueChange={(id) => onTabChange(id as AllotmentTabId)}
            className="min-w-0 [&_[role=tablist]]:flex-nowrap [&_[role=tablist]]:overflow-x-auto [&_[role=tab]]:shrink-0"
            ariaLabel={`Allotment #${item.id} sections`}
        />
    );
}
