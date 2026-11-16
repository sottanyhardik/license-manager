/**
 * API service for the Master-Data Service (MDS) status surface.
 *
 * Read-only. Backs the additive status card on the Settings page (ADR-001).
 * The master-data READ paths are unaffected — the backend still serves masters
 * from local mirror tables kept fresh by MDS; this only reports sync health.
 */

import api from "../../api/axios";

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

/**
 * Fetch the current Master-Data Service status.
 *
 * Read-only GET; does not mutate any master data.
 */
export const fetchMdsStatus = async (): Promise<MdsStatus> => {
    const response = await api.get("mds/status/");
    return response.data as MdsStatus;
};

export default {
    fetchMdsStatus,
};
