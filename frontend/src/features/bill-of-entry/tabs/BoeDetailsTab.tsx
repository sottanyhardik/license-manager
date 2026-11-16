import { useQuery } from "@tanstack/react-query";

import { boeApi } from "@/api";
import { InlineError, LoadingState } from "@/components/shared";

import { FieldGrid, type FieldSpec } from "@/components/shared/FieldGrid";
import { boeRecordKeys } from "../format";
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
export function BoeDetailsTab({ boeId, recordKey }: { boeId: number; recordKey: string }) {
    const { data, isPending, isError, error, refetch } = useQuery({
        queryKey: boeRecordKeys.detail(recordKey),
        queryFn: () => boeApi.fetchBOE<BoeListItem>(boeId),
    });
    if (isPending) return <LoadingState variant="skeleton-rows" rows={3} label="Loading bill of entry" />;
    if (isError || !data) return <InlineError error={error} onRetry={() => { void refetch(); }} title="Could not load bill of entry" />;
    return <FieldGrid record={data} fields={DETAIL_FIELDS} />;
}
