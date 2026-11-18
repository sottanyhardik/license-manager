import { lazy, Suspense } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { LoadingState } from "@/components/shared";
import { qk } from "@/lib/queryKeys";

const MasterForm = lazy(() => import("@/pages/masters/MasterForm"));

/**
 * Inline allotment edit: the existing allotment form (same fields, serializer
 * validation, PATCH endpoint and audit log) embedded in the record. Save
 * refreshes this record and the register in place; Save / Cancel return to
 * Overview. Filters, page and scroll are untouched because nothing navigates.
 */
export function EditTab({ id, onDone }: { id: number; onDone: () => void }) {
    const queryClient = useQueryClient();
    return (
        <Suspense fallback={<LoadingState variant="spinner" label="Loading allotment form" />}>
            <MasterForm
                embedded
                entityName="allotments"
                recordId={id}
                onSuccess={() => {
                    void queryClient.invalidateQueries({ queryKey: qk.allotments.detail(id) });
                    void queryClient.invalidateQueries({ queryKey: ["entity-list", "allotments"] });
                    onDone();
                }}
                onClose={onDone}
            />
        </Suspense>
    );
}
