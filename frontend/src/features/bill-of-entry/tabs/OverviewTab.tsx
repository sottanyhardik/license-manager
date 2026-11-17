import { FieldGrid, type FieldSpec } from "@/components/shared/FieldGrid";
import { fmtFc2, fmtInrExact, fmtQty } from "../format";
import type { BoeListItem } from "../types";

/** Fields the list row already carries; amounts use the card formatters, other values as received. */
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

export interface OverviewTabProps {
    item: BoeListItem;
    /** Field keys already shown elsewhere on the page (e.g. detail header + figure tiles). */
    omit?: readonly string[];
}

export function OverviewTab({ item, omit = [] }: OverviewTabProps) {
    // Display-only formatting of backend values; nothing is recomputed. The record
    // view keeps the backend's full scale: INR to paise (DEC_0 = 0.00) and unit
    // price to 0.001 (get_unit_price), unlike the compact card.
    const record = {
        ...item,
        total_inr: fmtInrExact(item.total_inr),
        total_fc: fmtFc2(item.total_fc),
        total_quantity: fmtQty(item.total_quantity),
        unit_price: fmtQty(item.unit_price),
    };
    const fields = omit.length ? OVERVIEW_FIELDS.filter((f) => !omit.includes(f.key)) : OVERVIEW_FIELDS;
    return <FieldGrid record={record} fields={fields} />;
}
