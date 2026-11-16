import { FieldGrid, type FieldSpec } from "@/components/shared/FieldGrid";
import type { BoeListItem } from "../types";

/** Fields the list row already carries; values exactly as received. */
const OVERVIEW_FIELDS: FieldSpec[] = [
    { key: "bill_of_entry_number", label: "BOE Number" },
    { key: "bill_of_entry_date", label: "BOE Date" },
    { key: "port_name", label: "Port" },
    { key: "company_name", label: "Company" },
    { key: "product_name", label: "Product" },
    { key: "invoice_no", label: "Invoice No" },
    { key: "invoice_date", label: "Invoice Date" },
    { key: "licenses", label: "Licenses" },
    { key: "total_inr", label: "CIF (INR)" },
    { key: "total_fc", label: "CIF (FC)" },
    { key: "total_quantity", label: "Qty (MT)" },
    { key: "unit_price", label: "Unit Price" },
];

export function OverviewTab({ item }: { item: BoeListItem }) {
    return <FieldGrid record={item} fields={OVERVIEW_FIELDS} />;
}
