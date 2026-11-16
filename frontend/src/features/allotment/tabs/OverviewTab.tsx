import { ModuleAccordion } from "@/components/workspace";
import { DetailQueryBoundary } from "../DetailQueryBoundary";
import { FieldGrid, type FieldSpec } from "@/components/shared/FieldGrid";

const SECTIONS: { id: string; title: string; defaultOpen?: boolean; fields: FieldSpec[] }[] = [
    { id: "details", title: "Allotment", defaultOpen: true, fields: [
        { key: "invoice", label: "Invoice" },
        { key: "type", label: "Type" },
        { key: "item_name", label: "Item" },
        { key: "company_name", label: "Company" },
        { key: "related_company_name", label: "Related Company" },
        { key: "port_name", label: "Port" },
        { key: "is_boe", label: "BOE" },
        { key: "is_approved", label: "Approved" },
    ] },
    { id: "shipment", title: "Shipment & contact", fields: [
        { key: "estimated_arrival_date", label: "Estimated Arrival" },
        { key: "bl_detail", label: "BL Detail" },
        { key: "contact_person", label: "Contact Person" },
        { key: "contact_number", label: "Contact Number" },
    ] },
    { id: "value", title: "Requested value", fields: [
        { key: "required_quantity", label: "Required Qty" },
        { key: "unit_value_per_unit", label: "Unit Value" },
        { key: "cif_fc", label: "CIF (FC)" },
        { key: "exchange_rate", label: "Exchange Rate" },
        { key: "cif_inr", label: "CIF (INR)" },
        { key: "required_value", label: "Required Value" },
    ] },
    { id: "planning", title: "Planning target", fields: [
        { key: "planning_target_item_name", label: "Target Item" },
        { key: "planning_target_sion", label: "Target SION" },
        { key: "planning_mapping_status", label: "Mapping Status" },
        { key: "planning_mapping_source", label: "Mapping Source" },
    ] },
    { id: "record", title: "Record", fields: [
        { key: "created_on", label: "Created On" },
        { key: "created_by", label: "Created By" },
        { key: "modified_on", label: "Modified On" },
        { key: "modified_by", label: "Modified By" },
    ] },
];

/** Overview: `allotments/:id/` header fields, as received. */
export function OverviewTab({ id }: { id: number }) {
    return (
        <DetailQueryBoundary id={id}>
            {(record) => (
                <ModuleAccordion
                    persistKey={`allotment:${id}:overview`}
                    sections={SECTIONS.map((s) => ({
                        id: s.id, title: s.title, defaultOpen: s.defaultOpen,
                        render: () => <FieldGrid record={record} fields={s.fields} />,
                    }))}
                />
            )}
        </DetailQueryBoundary>
    );
}
