import { FieldGrid, type FieldSpec } from "@/components/shared/FieldGrid";
import { DetailQueryBoundary } from "../DetailQueryBoundary";
import { AllotmentItemsTab } from "./AllotmentItemsTab";

const FIELDS: FieldSpec[] = [
    { key: "required_quantity", label: "Requested Qty" },
    { key: "alloted_quantity", label: "Allocated Qty" },
    { key: "balanced_quantity", label: "Remaining Qty" },
    { key: "required_value", label: "Requested Value" },
    { key: "allotted_value", label: "Allocated Value" },
    { key: "allotted_items_count", label: "Allocation Records" },
    { key: "planning_mapping_status", label: "Allocation Mapping" },
];

/**
 * Allocation: backend-computed allotted / balanced figures from `allotments/:id/`
 * (as received — no client arithmetic) and every allocation record
 * (`allotment_details`) of the record.
 */
export function AllocationTab({ id }: { id: number }) {
    return (
        <DetailQueryBoundary id={id}>
            {(record) => (
                <div className="space-y-4">
                    <FieldGrid record={record} fields={FIELDS} />
                    <section aria-label="Allocation records">
                        <h4 className="mb-2 text-xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">Allocation records</h4>
                        <AllotmentItemsTab rows={record.allotment_details || []} />
                    </section>
                </div>
            )}
        </DetailQueryBoundary>
    );
}
