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
import type { Tone } from "@/components/shared/tone";
import { formatMasterLabel } from "./masterDetailFields";

export interface MasterColumn {
    field: string;
    label?: string;
    /** CSS grid track, e.g. `minmax(10rem,2fr)`. */
    width?: string;
    mono?: boolean;
    align?: "start" | "end";
    /** Display format; values are shown as received otherwise. `inr` = the register's ₹ formatter (no recomputation). */
    format?: "inr";
}

export interface MasterColumnConfig {
    columns: MasterColumn[];
    /** Secondary fields for the expanded row; shown only when present in the row data. */
    details?: string[];
    /**
     * Child collections in the row data (e.g. SION class -> export/import norms), shown as compact
     * tables in the expanded row. Only non-empty collections render.
     */
    nested?: MasterNestedCollection[];
    /** File fields (stored media paths) shown under Attachments; a `.docx` also gets the Document tab viewer. */
    documents?: string[];
    /** A server-provided status field shown as a badge next to Active/Inactive (e.g. incentive sold status). */
    badge?: { field: string; label: string; values: Record<string, { label: string; tone: Tone }>; fallback?: { label: string; tone: Tone } };
    /** Date field (DD-MM-YYYY or ISO) whose past value shows an "Expired" badge — same rule the register used. */
    expiryField?: string;
}

export interface MasterNestedCollection {
    field: string;
    label: string;
    columns: MasterColumn[];
}

const code = (field: string, label?: string, width = "minmax(6rem,8rem)"): MasterColumn => ({ field, label, width, mono: true });
const text = (field: string, label?: string, width = "minmax(10rem,1fr)"): MasterColumn => ({ field, label, width });
const num = (field: string, label?: string, width = "minmax(5rem,7rem)"): MasterColumn => ({ field, label, width, align: "end" });
const inr = (field: string, label?: string, width = "minmax(6rem,8rem)"): MasterColumn => ({ field, label, width, align: "end", format: "inr" });

export const MASTER_COLUMNS: Readonly<Record<string, MasterColumnConfig>> = {
    companies: {
        columns: [code("iec", "IEC", "minmax(7.5rem,9rem)"), text("name", "Name", "minmax(12rem,2fr)"), code("pan", "PAN", "minmax(7rem,8.5rem)"), code("gst_number", "GSTIN", "minmax(9rem,11rem)")],
        // Banking fields are only in the response for roles allowed to see them (CompanyPermission / serializer).
        details: ["contact_person", "email", "phone_number", "address", "address_line_1", "address_line_2", "bank_name", "ifsc_code", "account_type", "bank_account_number"],
        documents: ["logo", "signature", "stamp"],
    },
    ports: { columns: [code("code", "Code"), text("name", "Port", "minmax(12rem,3fr)")] },
    "hs-codes": {
        columns: [code("hs_code", "HS code", "minmax(7rem,9rem)"), text("product_description", "Description", "minmax(14rem,3fr)"), text("unit", "Unit", "minmax(4rem,6rem)"), num("unit_price", "Unit price")],
        details: ["basic_duty", "policy"],
    },
    "head-norms": { columns: [text("name", "Head norm", "minmax(12rem,3fr)")] },
    "sion-classes": {
        columns: [code("norm_class", "Norm class"), text("description", "Description", "minmax(14rem,3fr)"), text("head_norm_name", "Head norm", "minmax(8rem,1fr)")],
        // Fields from SionNormClassNestedSerializer (backend/apps/core/serializers/models.py).
        nested: [
            { field: "export_norm", label: "Export items", columns: [text("description", "Description"), num("quantity", "Quantity"), text("unit", "Unit")] },
            { field: "import_norm", label: "Import items", columns: [num("serial_number", "Sr"), text("description", "Description"), text("hsn_code_label", "HSN code"), num("quantity", "Quantity"), text("unit", "Unit")] },
            { field: "notes", label: "Notes", columns: [text("note_text", "Note")] },
            { field: "conditions", label: "Conditions", columns: [text("condition_text", "Condition")] },
        ],
    },
    groups: { columns: [text("name", "Group", "minmax(12rem,3fr)")] },
    "item-names": {
        // The API row carries `norm_details` and `sion_norm_class_label` (no group name; `group` is an id or null).
        columns: [text("name", "Item", "minmax(12rem,2fr)"), text("norm_details", "Norms", "minmax(8rem,1fr)"), text("sion_norm_class_label", "SION class", "minmax(10rem,2fr)"), num("display_order", "Order", "minmax(4rem,5rem)"), num("restriction_percentage", "Restriction %")],
    },
    "scheme-codes": { columns: [code("code", "Code"), text("label", "Scheme", "minmax(12rem,3fr)")] },
    "notification-numbers": { columns: [code("code", "Notification", "minmax(7rem,9rem)"), text("label", "Description", "minmax(12rem,3fr)")] },
    "purchase-statuses": { columns: [code("code", "Code", "minmax(4rem,5rem)"), text("label", "Purchase status", "minmax(12rem,3fr)"), num("display_order", "Order", "minmax(4rem,5rem)")] },
    "transfer-letters": { columns: [text("name", "Transfer letter", "minmax(12rem,3fr)")], details: ["tl"], documents: ["tl"] },
    "exchange-rates": {
        // Rates are the row's content: they share the width (values shown exactly as stored, never rounded).
        columns: [code("date", "Date", "minmax(6.5rem,8rem)"), num("usd", "USD", "minmax(5rem,1fr)"), num("euro", "EUR", "minmax(5rem,1fr)"), num("pound_sterling", "GBP", "minmax(5rem,1fr)"), num("chinese_yuan", "CNY", "minmax(5rem,1fr)")],
    },
    "unit-prices": { columns: [text("name", "Name", "minmax(10rem,2fr)"), text("label", "Label", "minmax(8rem,1fr)"), num("unit_price", "Unit price")] },
};

/** Never shown as row columns: ids, MDS sync internals, audit and status (status has its own badge). */
const NOT_A_COLUMN = new Set([
    "id", "uid", "synthetic_uid", "master_uid", "sync_version", "is_tombstone", "origin_server", "synced_at",
    "created_on", "created_by", "modified_on", "modified_by", "is_active",
]);

/**
 * Business registers (not masters) that use the same generic rows + inline record, keyed by entity.
 * Fields from each viewset's list serializer (incentive: `backend/apps/license/views_incentive.py`).
 */
export const REGISTER_COLUMNS: Readonly<Record<string, MasterColumnConfig>> = {
    "incentive-licenses": {
        columns: [
            code("license_number", "Licence", "minmax(7.5rem,9rem)"),
            text("license_type", "Type", "minmax(4rem,5rem)"),
            code("license_date", "Date", "minmax(6rem,7rem)"),
            code("license_expiry_date", "Expiry", "minmax(6rem,7rem)"),
            text("exporter_name", "Exporter", "minmax(10rem,2fr)"),
            text("port_name", "Port", "minmax(6rem,1fr)"),
            inr("license_value", "Value"),
            inr("sold_value", "Sold"),
            inr("balance_value", "Balance"),
        ],
        details: ["exporter_iec", "notes"],
        badge: {
            field: "sold_status",
            label: "Sold",
            // Same labels/tones as the former incentive cards: anything not YES/PARTIAL is Available.
            values: {
                YES: { label: "Sold", tone: "danger" },
                PARTIAL: { label: "Partial", tone: "warning" },
            },
            fallback: { label: "Available", tone: "success" },
        },
        expiryField: "license_expiry_date",
    },
};

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
    return MASTER_COLUMNS[entityName] ?? REGISTER_COLUMNS[entityName] ?? defaultMasterColumns(metadata);
}

export function masterColumnLabel(column: MasterColumn, fieldMeta: Record<string, { label?: string } | undefined> = {}): string {
    return column.label ?? formatMasterLabel(column.field, fieldMeta);
}
