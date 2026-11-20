import type { ImportItemNameRow, ImportItemNameScope } from "./types";

export interface ItemNameDraft {
    itemId: number | null;
    label: string | null;
    scope: ImportItemNameScope;
}

export const rowItemIds = (row: ImportItemNameRow) => row.items.map((i) => i.id);

export function displayName(row: ImportItemNameRow | undefined): string {
    return row ? row.items.map((i) => i.name).join(", ") : "";
}

/** A blank description can never be a global key. */
export const canBeGlobal = (row: ImportItemNameRow | undefined) => !!row?.description?.trim();

/**
 * Display-only grouping hint ("will follow"): whitespace/case-insensitive description + trimmed HSN.
 * The server's strict normalisation decides what is really applied; the preview shows the real counts.
 */
export function combinationKey(row: ImportItemNameRow): string | null {
    const description = (row.description ?? "").trim().replace(/\s+/g, " ").toLowerCase();
    if (!description) return null;
    return `${description}\u0000${(row.hs_code ?? "").trim()}`;
}
