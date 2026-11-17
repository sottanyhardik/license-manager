import { useQuery } from "@tanstack/react-query";

import { boeApi } from "@/api";
import { QueryBoundary } from "@/components/shared";
import { qk } from "@/lib/queryKeys";

import { FieldGrid, type FieldSpec } from "@/components/shared/FieldGrid";
import type { BoeListItem } from "../types";

const DETAIL_FIELDS: FieldSpec[] = [
    { key: "exchange_rate", label: "Exchange Rate" },
    { key: "appraisement", label: "Appraisement" },
    { key: "ooc_date", label: "OOC Date" },
    { key: "cha", label: "CHA" },
    { key: "comments", label: "Comments" },
    { key: "planning_target_item_name", label: "Target Item" },
    { key: "is_fetch", label: "Fetched" },
    { key: "failed", label: "Fetch Failed" },
    { key: "created_on", label: "Created On" },
    { key: "created_by", label: "Created By" },
    { key: "modified_on", label: "Modified On" },
    { key: "modified_by", label: "Modified By" },
];

/** Full record from the existing `bill-of-entries/:id/` endpoint (same one the edit and transfer-letter pages read). */
export function BoeDetailsTab({ boeId }: { boeId: number }) {
    const query = useQuery({
        queryKey: qk.boes.detail(boeId),
        queryFn: () => boeApi.fetchBOE<BoeListItem>(boeId),
    });
    return (
        <QueryBoundary query={query} rows={3} loadingLabel="Loading bill of entry" errorTitle="Could not load bill of entry">
            {(data) => <FieldGrid record={data} fields={DETAIL_FIELDS} />}
        </QueryBoundary>
    );
}
