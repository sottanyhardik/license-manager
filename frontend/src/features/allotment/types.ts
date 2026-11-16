/** Loose shape of an allotment row as returned by `allotments/` and `allotments/:id/` (AllotmentSerializer). */
export type AllotmentValue = string | number | boolean | null | undefined;

export interface AllotmentDetailRow {
    id?: number;
    license_id?: number | null;
    license_number?: string | null;
    [field: string]: unknown;
}

export interface AllotmentRecord {
    id: number;
    invoice?: string | null;
    allotment_details?: AllotmentDetailRow[];
    [field: string]: unknown;
}

/** Same context the list passes to its card actions. */
export interface AllotmentActionContext {
    canWrite: boolean;
    entityName: string;
    filterParams: Record<string, unknown>;
    currentPage: number;
    pageSize: number;
    navigate: (path: string) => void;
    onDelete: (item: AllotmentRecord) => void;
}

export interface AllotmentCardAction {
    icon: string;
    title: string;
    tone?: string;
    onClick: () => void | Promise<void>;
}
