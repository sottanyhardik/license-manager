/**
 * Row layout for every generic master list (licence-register anatomy).
 *
 * One entry per master: the first column is the record identifier (opens the
 * record, monospace like the licence number), the rest are the compact row
 * columns with their grid widths. `details` are shown only when a row is
 * expanded. Fields come from the API rows (see each viewset's `list_display` /
 * serializer in `backend/apps/core/views/views.py`). A master without an entry
 * gets `defaultMasterColumns` from its `list_display`.
 */
import { formatMasterLabel } from "./masterDetailFields";

export interface MasterColumn {
    field: string;
    label?: string;
    /** CSS grid track, e.g. `minmax(10rem,2fr)`. */
    width?: string;
    mono?: boolean;
    align?: "start" | "end";
}

export interface MasterColumnConfig {
    columns: MasterColumn[];
    /** Secondary fields for the expanded row; shown only when present in the row data. */
    details?: string[];
}

const code = (field: string, label?: string, width = "minmax(6rem,8rem)"): MasterColumn => ({ field, label, width, mono: true });
const text = (field: string, label?: string, width = "minmax(10rem,1fr)"): MasterColumn => ({ field, label, width });
const num = (field: string, label?: string, width = "minmax(5rem,7rem)"): MasterColumn => ({ field, label, width, align: "end" });

export const MASTER_COLUMNS: Readonly<Record<string, MasterColumnConfig>> = {
    companies: {
        columns: [code("iec", "IEC", "minmax(7.5rem,9rem)"), text("name", "Name", "minmax(12rem,2fr)"), code("pan", "PAN", "minmax(7rem,8.5rem)"), code("gst_number", "GSTIN", "minmax(9rem,11rem)")],
        // Banking fields are only in the response for roles allowed to see them (CompanyPermission / serializer).
        details: ["contact_person", "email", "phone_number", "address", "address_line_1", "address_line_2", "bank_name", "ifsc_code", "account_type", "bank_account_number"],
    },
    ports: { columns: [code("code", "Code"), text("name", "Port", "minmax(12rem,3fr)")] },
    "hs-codes": {
        columns: [code("hs_code", "HS code", "minmax(7rem,9rem)"), text("product_description", "Description", "minmax(14rem,3fr)"), text("unit", "Unit", "minmax(4rem,6rem)"), num("unit_price", "Unit price")],
        details: ["basic_duty", "policy"],
    },
    "head-norms": { columns: [text("name", "Head norm", "minmax(12rem,3fr)")] },
    "sion-classes": {
        columns: [code("norm_class", "Norm class"), text("description", "Description", "minmax(14rem,3fr)"), text("head_norm_name", "Head norm", "minmax(8rem,1fr)")],
    },
    groups: { columns: [text("name", "Group", "minmax(12rem,3fr)")] },
    "item-names": {
        // The API row carries `norm_details` and `sion_norm_class_label` (no group name; `group` is an id or null).
        columns: [text("name", "Item", "minmax(12rem,2fr)"), text("norm_details", "Norms", "minmax(8rem,1fr)"), text("sion_norm_class_label", "SION class", "minmax(10rem,2fr)"), num("display_order", "Order", "minmax(4rem,5rem)"), num("restriction_percentage", "Restriction %")],
    },
    "scheme-codes": { columns: [code("code", "Code"), text("label", "Scheme", "minmax(12rem,3fr)")] },
    "notification-numbers": { columns: [code("code", "Notification", "minmax(7rem,9rem)"), text("label", "Description", "minmax(12rem,3fr)")] },
    "purchase-statuses": { columns: [code("code", "Code", "minmax(4rem,5rem)"), text("label", "Purchase status", "minmax(12rem,3fr)"), num("display_order", "Order", "minmax(4rem,5rem)")] },
    "transfer-letters": { columns: [text("name", "Transfer letter", "minmax(12rem,3fr)")], details: ["tl"] },
    "exchange-rates": {
        columns: [code("date", "Date", "minmax(6.5rem,8rem)"), num("usd", "USD"), num("euro", "EUR"), num("pound_sterling", "GBP"), num("chinese_yuan", "CNY")],
    },
    "unit-prices": { columns: [text("name", "Name", "minmax(10rem,2fr)"), text("label", "Label", "minmax(8rem,1fr)"), num("unit_price", "Unit price")] },
};

/** Never shown as row columns: ids, MDS sync internals, audit and status (status has its own badge). */
const NOT_A_COLUMN = new Set([
    "id", "uid", "synthetic_uid", "master_uid", "sync_version", "is_tombstone", "origin_server", "synced_at",
    "created_on", "created_by", "modified_on", "modified_by", "is_active",
]);

export function defaultMasterColumns(metadata: Record<string, any>): MasterColumnConfig {
    const fields: string[] = (metadata.list_display || []).filter((f: string) => !NOT_A_COLUMN.has(f));
    const [first, ...rest] = fields;
    return {
        columns: [
            ...(first ? [{ field: first, width: "minmax(8rem,1.5fr)", mono: true }] : []),
            ...rest.slice(0, 4).map(field => text(field)),
        ],
        details: rest.slice(4),
    };
}

export function resolveMasterColumns(entityName: string, metadata: Record<string, any>): MasterColumnConfig {
    return MASTER_COLUMNS[entityName] ?? defaultMasterColumns(metadata);
}

export function masterColumnLabel(column: MasterColumn, fieldMeta: Record<string, { label?: string } | undefined> = {}): string {
    return column.label ?? formatMasterLabel(column.field, fieldMeta);
}
