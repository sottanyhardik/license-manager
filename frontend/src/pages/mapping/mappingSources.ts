/** The three Mapping workspace sources (owner specs 2026-11-19). Each has its OWN source identity (strictly normalised
 *  original text) and its own saved mappings — never combined across sources:
 *    Licence Import Item: Original Item Description → Item Name(s) (`LicenseImportItemsModel.items`, multi);
 *    Allotment: Item Name* → Planning Target Item (`AllotmentModel.planning_target_item`, single FK);
 *    BOE: Product Name → Planning Target Item (`BillOfEntryModel.planning_target_item`, single FK).
 *  Item Names and Planning Target Items are the same canonical master (`core.ItemNameModel`). */
import type { FieldLabels } from "./FilterConditions";
import { FIELD_LABEL } from "./filterModel";

/** An entry of the canonical Item Name / Planning Target Item master (`ItemNameModel` id). */
export type Master = { item_id: number; name: string };
export type SourceKind = "import" | "boe" | "allotment";
export type SourceConfig = {
    kind: SourceKind;
    base: string;
    /** column header of the source text */
    sourceLabel: string;
    /** what the destination master is called on this table */
    noun: string;
    multi: boolean;
    /** HSN / SION columns (import descriptions only) */
    showCodes: boolean;
    recordNoun: string;
    rowNoun: string;
    tableLabel: string;
    searchLabel: string;
    placeholder: string;
    filterLabels: FieldLabels;
};

const API = "item-pivot/matching/item-name-mapping";

/** Global Description + HSN approvals (Licence Detail decisions) — listed separately from pending description work. */
export const APPROVALS_BASE = `${API}/import/approvals/`;

export const SOURCES: Record<SourceKind, SourceConfig> = {
    import: {
        kind: "import", base: `${API}/import/descriptions/`, sourceLabel: "Original Item Description", noun: "Item Name", multi: true, showCodes: true,
        recordNoun: "licence import record", rowNoun: "description", tableLabel: "Licence import item descriptions",
        searchLabel: "Search licence import item descriptions", placeholder: "Original description…", filterLabels: FIELD_LABEL,
    },
    allotment: {
        kind: "allotment", base: `${API}/allotment/names/`, sourceLabel: "Item Name*", noun: "Planning Target Item", multi: false, showCodes: false,
        recordNoun: "allotment record", rowNoun: "item name", tableLabel: "Allotment item names",
        searchLabel: "Search allotment item names", placeholder: "Allotment Item Name…", filterLabels: { description: "Item Name*" },
    },
    boe: {
        kind: "boe", base: `${API}/boe/names/`, sourceLabel: "Product Name", noun: "Planning Target Item", multi: false, showCodes: false,
        recordNoun: "BOE record", rowNoun: "product name", tableLabel: "BOE product names",
        searchLabel: "Search BOE product names", placeholder: "BOE Product Name…", filterLabels: { description: "Product Name" },
    },
};
