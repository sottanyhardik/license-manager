/**
 * Generic master record layout: which tabs and accordion sections a record page
 * shows, derived from the backend metadata, the record's real values and the
 * per-master config in `masterColumns.ts`. One function for every master — a
 * master changes its page through configuration only. Empty sections and tabs
 * without real data are omitted; no field is invented.
 */
import type { FieldSpec } from "@/components/shared/FieldGrid";
import { masterColumnLabel, resolveMasterColumns, type MasterNestedCollection } from "./masterColumns";
import { formatMasterLabel, formatMasterValue, masterDetailFields, MASTER_AUDIT_FIELDS, readMasterField } from "./masterDetailFields";

export type MasterDetailSectionId = "general" | "additional" | "attachments" | "audit";

export interface MasterDetailSection {
    id: MasterDetailSectionId;
    title: string;
    fields: FieldSpec[];
}

export interface MasterDocument {
    key: string;
    label: string;
    /** Stored value (media URL or path) as received from the API. */
    url: string;
    filename: string;
    /** Rendered in the Document tab (Word .docx). */
    previewable: boolean;
}

export interface MasterRelatedCollection {
    collection: MasterNestedCollection;
    rows: Record<string, unknown>[];
}

export interface MasterDetailLayout {
    /** Summary fields: the master's list-row columns that have a value. */
    overview: FieldSpec[];
    /** Details tab accordion, in order, non-empty only. */
    sections: MasterDetailSection[];
    documents: MasterDocument[];
    related: MasterRelatedCollection[];
}

const SECTION_TITLES: Record<MasterDetailSectionId, string> = {
    general: "General information",
    additional: "Additional information",
    attachments: "Attachments and documents",
    audit: "Audit information",
};

export function documentFilename(url: string): string {
    const last = url.split("?")[0].split("/").filter(Boolean).pop() ?? url;
    try {
        return decodeURIComponent(last);
    } catch {
        return last;
    }
}

export function buildMasterDetailLayout(
    entity: string,
    metadata: Record<string, any>,
    record: Record<string, unknown>,
): MasterDetailLayout {
    const fieldMeta = metadata.field_meta || {};
    const config = resolveMasterColumns(entity, metadata);
    const documentKeys = new Set(config.documents ?? []);
    const hasValue = (key: string) => formatMasterValue(readMasterField(record, key)) !== null;
    const spec = (key: string): FieldSpec => ({ key, label: formatMasterLabel(key, fieldMeta) });

    const overview = config.columns
        .filter(column => hasValue(column.field))
        .map(column => ({ key: column.field, label: masterColumnLabel(column, fieldMeta) }));

    // General = what an editor maintains (form fields + list columns), as on the previous Details tab.
    const general = masterDetailFields(metadata, record).filter(f => !documentKeys.has(f.key));
    const generalKeys = new Set(general.map(f => f.key));
    const additional = (config.details ?? [])
        .filter(key => !generalKeys.has(key) && !documentKeys.has(key) && hasValue(key))
        .map(spec);

    const documents: MasterDocument[] = [...documentKeys]
        .filter(key => typeof record[key] === "string" && hasValue(key))
        .map(key => {
            const url = String(record[key]);
            const filename = documentFilename(url);
            return { key, label: formatMasterLabel(key, fieldMeta), url, filename, previewable: /\.docx$/i.test(filename) };
        });

    // "by" columns arrive as raw user ids on most masters; show them only when the API sends a name.
    const audit = MASTER_AUDIT_FIELDS.filter(f => f.key in record && (!f.key.endsWith("_by") || typeof record[f.key] === "string"));

    const sections: MasterDetailSection[] = [
        { id: "general" as const, title: SECTION_TITLES.general, fields: general },
        { id: "additional" as const, title: SECTION_TITLES.additional, fields: additional },
        { id: "attachments" as const, title: SECTION_TITLES.attachments, fields: documents.map(d => ({ key: d.key, label: d.label })) },
        { id: "audit" as const, title: SECTION_TITLES.audit, fields: [...audit] },
    ].filter(section => section.fields.length > 0);

    const related = (config.nested ?? [])
        .map(collection => ({ collection, rows: record[collection.field] }))
        .filter((c): c is MasterRelatedCollection => Array.isArray(c.rows) && c.rows.length > 0);

    return { overview, sections, documents, related };
}
