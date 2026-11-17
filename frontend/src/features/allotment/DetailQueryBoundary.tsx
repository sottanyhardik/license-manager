import type { ReactNode } from "react";
import { QueryBoundary } from "@/components/shared";
import { useAllotmentDetail } from "./useAllotmentDetail";
import type { AllotmentRecord } from "./types";

type Props = { id: number; children: (record: AllotmentRecord) => ReactNode };

/** Loading / error / data states for tabs backed by `allotments/:id/`. */
export function DetailQueryBoundary({ id, children }: Props) {
    const query = useAllotmentDetail(id);
    return (
        <QueryBoundary query={query} rows={3} loadingLabel="Loading allotment" errorTitle="Could not load allotment">
            {children}
        </QueryBoundary>
    );
}
