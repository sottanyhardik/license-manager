import { useState } from "react";

import { ActionMenu, type ActionMenuItem } from "@/components/shared";
import { DetailTabs } from "@/components/workspace";

import { buildBoeRecordTabs } from "./boeRecordTabs";
import type { BoeListItem } from "./types";

export type BoeRecordTabId =
    | "overview"
    | "boe-details"
    | "import-items"
    | "licence-mapping"
    | "allotment-mapping"
    | "documents";

export interface BoeRecordWorkspaceProps {
    item: BoeListItem;
    /** Optional consolidated actions (shared ActionMenu); the register table keeps them in its row menu instead. */
    actionItems?: ActionMenuItem[];
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
    const label = item.bill_of_entry_number || item.id;

    const tabs = buildBoeRecordTabs(item, { onTransferLetter });

    return (
        <div role="region" id={`boe-content-${item.id}`} aria-label={`BOE ${label} details`}>
            {actionItems && (
                <div className="mb-2 flex justify-end">
                    <ActionMenu items={actionItems} label={`Actions for BOE ${label}`} trigger="button" />
                </div>
            )}
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
