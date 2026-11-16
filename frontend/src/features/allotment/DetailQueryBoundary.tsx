import type { ReactNode } from "react";
import { InlineError, LoadingState } from "@/components/shared";
import { useAllotmentDetail } from "./useAllotmentDetail";
import type { AllotmentRecord } from "./types";

type Props = { id: number; children: (record: AllotmentRecord) => ReactNode };

/** Loading / error / data states for tabs backed by `allotments/:id/`. */
export function DetailQueryBoundary({ id, children }: Props) {
    const { data, isPending, isError, error, refetch } = useAllotmentDetail(id);
    if (isPending) return <LoadingState variant="skeleton-rows" rows={3} label="Loading allotment" />;
    if (isError || !data) return <InlineError error={error} onRetry={() => { void refetch(); }} title="Could not load allotment" />;
    return <>{children(data)}</>;
}
