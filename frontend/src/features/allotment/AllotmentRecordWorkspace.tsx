import { DetailTabs, type DetailTab } from "@/components/workspace";
import { AllotmentItemsTab } from "./tabs/AllotmentItemsTab";
import { DocumentsTab } from "./tabs/DocumentsTab";
import { EditOptionsTab } from "./tabs/EditOptionsTab";
import { LicenceMappingTab } from "./tabs/LicenceMappingTab";
import { OverviewTab } from "./tabs/OverviewTab";
import { UtilisationTab } from "./tabs/UtilisationTab";
import type { AllotmentCardAction, AllotmentRecord } from "./types";

type Props = { item: AllotmentRecord; actions: AllotmentCardAction[] };

/**
 * Expanded body of an allotment card. Tabs are lazy (only the active one
 * mounts) and keyed `allotment:<id>`, so switching records drops all state.
 * Allotment Details is first, so it is the default tab: expanding shows the
 * same table as before and makes no request.
 *
 * Omitted (no existing endpoint/data source): BOE Mapping, CIF Reservation,
 * Reconciliation, Activity.
 */
export function AllotmentRecordWorkspace({ item, actions }: Props) {
    const rows = item.allotment_details || [];
    const tabs: DetailTab[] = [
        { id: "details", label: "Allotment Details", render: () => <AllotmentItemsTab rows={rows} /> },
        { id: "overview", label: "Overview", render: () => <OverviewTab id={item.id} /> },
        { id: "licences", label: "Licence Mapping", render: () => <LicenceMappingTab id={item.id} /> },
        { id: "utilisation", label: "Utilisation", render: () => <UtilisationTab id={item.id} /> },
        { id: "documents", label: "Documents", render: () => <DocumentsTab rows={rows} actions={actions} /> },
        { id: "edit", label: "Edit Options", render: () => <EditOptionsTab actions={actions} /> },
    ];
    return <DetailTabs recordKey={`allotment:${item.id}`} tabs={tabs} />;
}
