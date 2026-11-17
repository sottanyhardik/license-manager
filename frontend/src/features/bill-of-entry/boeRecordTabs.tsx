import type { DetailTab } from "@/components/workspace";

import { BoeItemsTable } from "./BoeItemsTable";
import { OverviewTab } from "./tabs/OverviewTab";
import { BoeDetailsTab } from "./tabs/BoeDetailsTab";
import { LicenceMappingTab } from "./tabs/LicenceMappingTab";
import { AllotmentMappingTab } from "./tabs/AllotmentMappingTab";
import { DocumentsTab } from "./tabs/DocumentsTab";
import type { BoeDetailRow, BoeListItem } from "./types";

/**
 * The one BOE tab set, shared by the expanded card (DetailTabs) and the
 * dedicated /bill-of-entries/:id page (ModuleWorkspace). Lazy: each `render`
 * runs only while its tab is active.
 */
export function buildBoeRecordTabs(
    item: BoeListItem,
    { onTransferLetter }: { onTransferLetter?: () => void } = {},
): DetailTab[] {
    const rows: BoeDetailRow[] = item.item_details || [];
    return [
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
}
