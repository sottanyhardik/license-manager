/** Loose shape of a `bill-of-entries/` row (BillOfEntrySerializer); values are rendered as received. */
export type BoeListItem = { id: number; [field: string]: any };

/** One `item_details` row (RowDetailsSerializer). */
export interface BoeDetailRow {
    id?: number;
    license_id?: number | null;
    license_number?: string | null;
    is_dispute?: boolean;
    [field: string]: unknown;
}
