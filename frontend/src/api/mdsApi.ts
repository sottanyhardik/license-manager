/**
 * API service for the Master-Data Service (MDS) status surface.
 *
 * Read-only. Backs the additive status card on the Settings page (ADR-001).
 * The master-data READ paths are unaffected — the backend still serves masters
 * from local mirror tables kept fresh by MDS; this only reports sync health.
 */

import api from "./axios";
import type { MdsModelStatus, MdsStatus } from "@/types/api/mds";

export type { MdsModelStatus, MdsStatus };

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
