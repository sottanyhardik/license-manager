import { DetailQueryBoundary } from "../DetailQueryBoundary";
import { FieldGrid, type FieldSpec } from "@/components/shared/FieldGrid";

const FIELDS: FieldSpec[] = [
    { key: "required_quantity", label: "Required Qty" },
    { key: "alloted_quantity", label: "Allotted Qty" },
    { key: "balanced_quantity", label: "Balanced Qty" },
    { key: "required_value", label: "Required Value" },
    { key: "allotted_value", label: "Allotted Value" },
    { key: "allotted_items_count", label: "Allotted Items" },
    { key: "allocated_licenses_count", label: "Allocated Licenses" },
];

/** Utilisation: backend-computed allotted/balanced figures from `allotments/:id/`, as received. */
export function UtilisationTab({ id }: { id: number }) {
    return (
        <DetailQueryBoundary id={id}>
            {(record) => <FieldGrid record={record} fields={FIELDS} />}
        </DetailQueryBoundary>
    );
}
