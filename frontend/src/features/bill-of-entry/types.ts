/** Loose shape of a `bill-of-entries/` row (BillOfEntrySerializer); values are rendered as received. */
export type BoeListItem = {
    id: number;
    /** Backend-computed; see `invoiceStatus.ts`. */
    invoice_status?: "hidden" | "invoiced" | "invoice_no_recorded" | "not_invoiced";
    invoice_status_label?: string;
    [field: string]: any;
};

/** One `item_details` row (RowDetailsSerializer). */
export interface BoeDetailRow {
    id?: number;
    license_id?: number | null;
    license_number?: string | null;
    is_dispute?: boolean;
    [field: string]: unknown;
}
