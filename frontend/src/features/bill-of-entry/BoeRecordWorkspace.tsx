import { useState } from "react";

import { ActionMenu, type ActionMenuItem } from "@/components/shared";
import { DetailTabs, type DetailTab } from "@/components/workspace";

import { BoeItemsTable } from "./BoeItemsTable";
import { OverviewTab } from "./tabs/OverviewTab";
import { BoeDetailsTab } from "./tabs/BoeDetailsTab";
import { LicenceMappingTab } from "./tabs/LicenceMappingTab";
import { AllotmentMappingTab } from "./tabs/AllotmentMappingTab";
import { DocumentsTab } from "./tabs/DocumentsTab";
import type { BoeDetailRow, BoeListItem } from "./types";

export type BoeRecordTabId =
    | "overview"
    | "boe-details"
    | "import-items"
    | "licence-mapping"
    | "allotment-mapping"
    | "documents";

export interface BoeRecordWorkspaceProps {
    item: BoeListItem;
    /** Consolidated Edit / Transfer Letter / Merge / ... actions (shared ActionMenu). */
    actionItems: ActionMenuItem[];
    onTransferLetter?: () => void;
}

/**
 * Record workspace for one expanded BOE card (05 §16), keyed `boe:<id>`. Only the
 * active tab mounts; each body reuses card data or an existing endpoint and
 * renders values as received.
 *
 * Opens on Overview (D11). Card actions live in the shared ActionMenu.
 * Omitted (no per-BOE data source): Invoices, Reconciliation, Activity.
 */
export default function BoeRecordWorkspace({ item, actionItems, onTransferLetter }: BoeRecordWorkspaceProps) {
    const [tab, setTab] = useState<BoeRecordTabId>("overview");
    const recordKey = `boe:${item.id}`;
    const rows: BoeDetailRow[] = item.item_details || [];
    const label = item.bill_of_entry_number || item.id;

    const tabs: DetailTab[] = [
        { id: "overview", label: "Overview", render: () => <OverviewTab item={item} /> },
        { id: "boe-details", label: "BOE Details", render: () => <BoeDetailsTab boeId={item.id} /> },
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
    ];

    return (
        <div role="region" id={`boe-content-${item.id}`} aria-label={`BOE ${label} details`}>
            <div className="mb-2 flex justify-end">
                <ActionMenu items={actionItems} label={`Actions for BOE ${label}`} trigger="button" />
            </div>
            <DetailTabs
                recordKey={recordKey}
                tabs={tabs}
                value={tab}
                onValueChange={(id) => setTab(id as BoeRecordTabId)}
                className="min-h-[120px] min-w-0 [&_[role=tablist]]:flex-nowrap [&_[role=tablist]]:overflow-x-auto [&_[role=tab]]:shrink-0"
                ariaLabel={`BOE ${label} sections`}
            />
        </div>
    );
}
