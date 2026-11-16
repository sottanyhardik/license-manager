import { useState } from "react";

import { DetailTabs, type DetailTab } from "@/components/workspace";

import { BoeItemsTable } from "./BoeItemsTable";
import { OverviewTab } from "./tabs/OverviewTab";
import { BoeDetailsTab } from "./tabs/BoeDetailsTab";
import { LicenceMappingTab } from "./tabs/LicenceMappingTab";
import { AllotmentMappingTab } from "./tabs/AllotmentMappingTab";
import { DocumentsTab } from "./tabs/DocumentsTab";
import { EditOptionsTab } from "./tabs/EditOptionsTab";
import type { BoeDetailRow, BoeListItem } from "./types";

export type BoeRecordTabId =
    | "overview"
    | "boe-details"
    | "import-items"
    | "licence-mapping"
    | "allotment-mapping"
    | "documents"
    | "edit-options";

export interface BoeRecordWorkspaceProps {
    item: BoeListItem;
    canWrite: boolean;
    onEdit: () => void;
    onTransferLetter: () => void;
    onMerge: () => void;
}

/**
 * Record workspace for one expanded BOE card (05 §16), keyed `boe:<id>`. Only the
 * active tab mounts; each body reuses card data or an existing endpoint and
 * renders values as received.
 *
 * Opens on Import Items, the card's previous expanded body.
 * Omitted (no per-BOE data source): Invoices, Reconciliation, Activity.
 */
export default function BoeRecordWorkspace({ item, canWrite, onEdit, onTransferLetter, onMerge }: BoeRecordWorkspaceProps) {
    const [tab, setTab] = useState<BoeRecordTabId>("import-items");
    const recordKey = `boe:${item.id}`;
    const rows: BoeDetailRow[] = item.item_details || [];
    const label = item.bill_of_entry_number || item.id;

    const tabs: DetailTab[] = [
        { id: "overview", label: "Overview", render: () => <OverviewTab item={item} /> },
        { id: "boe-details", label: "BOE Details", render: () => <BoeDetailsTab boeId={item.id} recordKey={recordKey} /> },
        { id: "import-items", label: "Import Items", render: () => <BoeItemsTable rows={rows} /> },
        { id: "licence-mapping", label: "Licence Mapping", render: () => <LicenceMappingTab rows={rows} /> },
        { id: "allotment-mapping", label: "Allotment Mapping", render: () => <AllotmentMappingTab allotment={item.allotment} /> },
        {
            id: "documents",
            label: "Documents",
            render: () => (
                <DocumentsTab boeNumber={item.bill_of_entry_number} boePdfCopy={item.boe_pdf_copy} rows={rows} onTransferLetter={onTransferLetter} />
            ),
        },
        {
            id: "edit-options",
            label: "Edit Options",
            render: () => <EditOptionsTab canWrite={canWrite} onEdit={onEdit} onTransferLetter={onTransferLetter} onMerge={onMerge} />,
        },
    ];

    return (
        <div role="region" id={`boe-content-${item.id}`} aria-label={`BOE ${label} details`}>
            <DetailTabs
                recordKey={recordKey}
                tabs={tabs}
                value={tab}
                onValueChange={(id) => setTab(id as BoeRecordTabId)}
                className="min-h-[120px]"
                ariaLabel={`BOE ${label} sections`}
            />
        </div>
    );
}
