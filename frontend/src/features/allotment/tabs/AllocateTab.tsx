import { lazy, Suspense, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { LoadingState } from "@/components/shared";

const AllotmentAction = lazy(() => import("@/pages/AllotmentAction"));

/**
 * Allocate Licence: the existing allocation workflow (`/allotments/:id/allocate`)
 * embedded inline — eligible-licence search, quantity / CIF entry with the same
 * `allocate-items` validation (licence entitlement, remaining allotment qty and
 * CIF, plan caps, duplicate merge) and release. It refreshes the shared
 * `allotments/:id/` cache itself; the register row and licence-side views are
 * refreshed when the tab closes.
 */
export function AllocateTab({ id }: { id: number }) {
    const queryClient = useQueryClient();
    useEffect(() => () => {
        void queryClient.invalidateQueries({ queryKey: ["entity-list", "allotments"] });
        void queryClient.invalidateQueries({ queryKey: ["allotment-licence-ledger"] });
        void queryClient.invalidateQueries({ queryKey: ["allotment-licence-summary"] });
    }, [queryClient]);
    return (
        <div className="h-[min(860px,calc(100dvh-12rem))] min-h-[520px] overflow-hidden rounded-lg border border-border/70">
            <Suspense fallback={<LoadingState variant="spinner" label="Loading allocation workspace" />}>
                <AllotmentAction allotmentId={id} isModal onClose={undefined} />
            </Suspense>
        </div>
    );
}
