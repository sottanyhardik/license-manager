/** Card formatters, moved unchanged from the MasterList BOE block. Display-only. */
export const fmtInr = (val: unknown) => val ? `₹${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—';
export const fmtQty = (val: unknown) => val ? Number(val).toLocaleString('en-IN', { maximumFractionDigits: 3 }) : '—';

/** Query keys for record-tab data; every key carries the `boe:<id>` record key. */
export const boeRecordKeys = {
    detail: (recordKey: string) => ["boe-record", recordKey, "detail"] as const,
};
