/** One mirrored model's sync state, as reported by GET /api/mds/status/. */
export interface MdsModelStatus {
    /** Django-style label, e.g. "masters.Company". */
    model_label: string;
    /** ISO timestamp of the last successful sync, or null if never synced. */
    last_synced_at: string | null;
    /** Rows currently held in the local mirror table. */
    count: number;
}

/** Shape of GET /api/mds/status/. */
export interface MdsStatus {
    /** Whether MDS integration is turned on for this deployment. */
    enabled: boolean;
    /** Base URL of the central Master-Data Service. */
    base_url: string;
    /** Per-model mirror status. */
    models: MdsModelStatus[];
    /** Overall health rollup computed by the backend. */
    healthy: boolean;
}
