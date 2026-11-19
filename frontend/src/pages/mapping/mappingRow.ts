/** Row model + status rules shared by the three Mapping tabs (suggestions never count as a selection). */
import type { ReactNode } from "react";

import type { Tone } from "@/components/shared";

export type MappingRow = {
    key: string;
    description: string;
    /** Source-specific context under the description (BOE no/date, licence, source count…). */
    source: ReactNode;
    hsn: string[];
    sion: string[];
    suggestion: { name: string | null; confidence?: number | null; explanation?: string } | null;
    /** Item Names legitimate for this row (listed first in the selector). */
    legitimate: { item_id: number; name: string | null }[];
    conflicts: string[];
    /** Non-null → the row cannot be approved with a single Item Name here (e.g. multi-product wording). */
    reviewRequired: string | null;
    /** Server would refuse approval (e.g. a conflicting import-item match). */
    blocked: boolean;
    /** Approvable individually only (e.g. multi-product BOE wording) — never in bulk. */
    individualOnly?: boolean;
    /** BOE / allotment header ids behind this row (the identity sent on approval). */
    recordIds?: number[];
    /** Optional inline review panel (multi-product classification) shown under the row when expanded. */
    review?: ReactNode;
};

export type RowStatus = "PENDING" | "READY" | "CONFLICT" | "REVIEW";
export const STATUS: Record<RowStatus, { label: string; tone: Tone }> = {
    PENDING: { label: "Pending", tone: "neutral" },
    READY: { label: "Ready to approve", tone: "success" },
    CONFLICT: { label: "Conflict", tone: "warning" },
    REVIEW: { label: "Review required", tone: "danger" },
};

export function rowStatus(row: MappingRow, picked: number | null | undefined): RowStatus {
    if (row.reviewRequired) return "REVIEW";
    if (row.blocked || row.conflicts.length) return "CONFLICT";
    return picked ? "READY" : "PENDING";
}

/** Approvable = an explicitly selected Item Name id, no review requirement, not blocked by the server rules. */
export const approvable = (row: MappingRow, picked: number | null | undefined) => !!picked && !row.reviewRequired && !row.blocked;
