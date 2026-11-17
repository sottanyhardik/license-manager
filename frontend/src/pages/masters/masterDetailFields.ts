/**
 * Field presentation shared by the generic master list and detail pages.
 * Values are shown as received from the API — nothing is computed here.
 */
import type { FieldSpec } from "@/components/shared/FieldGrid";

type FieldMeta = Record<string, { label?: string } | undefined>;

/** Audit columns carried by `AuditModel` masters; shown in their own section. */
export const MASTER_AUDIT_FIELDS: readonly FieldSpec[] = [
    { key: "created_on", label: "Created" },
    { key: "created_by", label: "Created by" },
    { key: "modified_on", label: "Last updated" },
    { key: "modified_by", label: "Updated by" },
];

const HIDDEN_DETAIL_FIELDS = new Set(["id", "uid", "synthetic_uid", ...MASTER_AUDIT_FIELDS.map(f => f.key)]);

export function formatMasterLabel(column: string, fieldMeta: FieldMeta = {}): string {
    return fieldMeta[column]?.label || column.replace(/__/g, " ").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

/** Display text for one received value; `null` means "no value" (caller shows an em dash). */
export function formatMasterValue(value: unknown): string | null {
    if (value === null || value === undefined || value === "") return null;
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (Array.isArray(value)) return value.map(formatMasterValue).filter(Boolean).join(", ") || null;
    if (typeof value === "object") {
        const named = value as Record<string, unknown>;
        const label = named.name ?? named.label ?? named.code;
        return label !== undefined ? String(label) : JSON.stringify(value);
    }
    return String(value);
}

/** Reads `a__b` list columns the way the API flattens them (`a_b`), falling back to the raw key. */
export function readMasterField(record: Record<string, unknown>, column: string): unknown {
    const flattened = column.replace(/__/g, "_");
    return record[flattened] !== undefined ? record[flattened] : record[column];
}

/**
 * Fields for the detail page: the form fields (what an editor can change),
 * then any list columns not already included. Ids, audit columns and nested
 * child lists (shown on their own masters) are excluded.
 */
export function masterDetailFields(metadata: Record<string, any>, record: Record<string, unknown>): FieldSpec[] {
    const fieldMeta: FieldMeta = metadata.field_meta || {};
    const ordered: string[] = [...(metadata.form_fields || []), ...(metadata.list_display || [])];
    const source = ordered.length ? ordered : Object.keys(record);
    return [...new Set(source)]
        .filter(key => !HIDDEN_DETAIL_FIELDS.has(key) && !Array.isArray(readMasterField(record, key)))
        .map(key => ({ key, label: formatMasterLabel(key, fieldMeta) }));
}

/** The record as display strings for `FieldGrid` (which renders values verbatim). */
export function formatMasterRecord(record: Record<string, unknown>, fields: readonly FieldSpec[]): Record<string, string | null> {
    // FK fields: the API often sends a readable companion next to the raw id.
    const readable = (key: string) => record[`${key}_detail`] ?? record[`${key}_name`] ?? record[`${key}_label`] ?? readMasterField(record, key);
    return Object.fromEntries(fields.map(f => [f.key, formatMasterValue(readable(f.key))]));
}
