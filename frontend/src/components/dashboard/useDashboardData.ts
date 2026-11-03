import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import api from "@/api/axios";
import { dashboardApiContract, type DashboardQueryParams, type DashboardResponse } from "@/pages/dashboardContract";
import { parseDashboardPayload, parseDashboardSection, reportContractViolations, type RetryableSection } from "./payloadContract";

/** Shown in place of a section whose own retry request failed. The Retry action stays available. */
export const SECTION_RETRY_FAILED = "This section could not be loaded. Check the connection, then retry";

export type DashboardRequest = {
    companyId: number | null;
    dateFrom?: string;
    dateTo?: string;
};

export type DashboardDataState = {
    /** Last successful payload. Kept on screen while a newer request is pending or has failed. */
    data: DashboardResponse | null;
    /** No payload yet, and a request is in flight. */
    loading: boolean;
    /** A request is in flight after a payload already exists. */
    refreshing: boolean;
    /** The most recent request failed. The previous payload (if any) is still shown. */
    failed: boolean;
    /** Client clock time of the last successful response. */
    lastRefreshed: Date | null;
    refresh: () => void;
    /** Sections whose own retry request is in flight. */
    retrying: ReadonlySet<RetryableSection>;
    /** Refetches one section with `?section=`. Other sections are not touched. */
    retrySection: (section: RetryableSection) => void;
};

/**
 * Loads the dashboard payload. Scope changes re-fetch without `refresh=1`, so
 * the server cache can serve them. The Refresh action re-fetches with
 * `refresh=1`, so the server recomputes. A stale response never overwrites a newer one.
 */
export function useDashboardData(request: DashboardRequest): DashboardDataState {
    const [data, setData] = useState<DashboardResponse | null>(null);
    const [inFlight, setInFlight] = useState(false);
    const [failed, setFailed] = useState(false);
    const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
    const [retrying, setRetrying] = useState<ReadonlySet<RetryableSection>>(() => new Set());
    const retryingRef = useRef<ReadonlySet<RetryableSection>>(new Set());
    const latestRequest = useRef(0);
    const { companyId, dateFrom, dateTo } = request;
    const scopeRef = useRef<DashboardRequest>({ companyId, dateFrom, dateTo });
    useEffect(() => {
        scopeRef.current = { companyId, dateFrom, dateTo };
    }, [companyId, dateFrom, dateTo]);

    const load = useCallback(async (scope: DashboardRequest, forceRefresh: boolean) => {
        const requestId = ++latestRequest.current;
        const params: DashboardQueryParams = {};
        if (scope.companyId != null) params.company_id = scope.companyId;
        if (scope.dateFrom) params.date_from = scope.dateFrom;
        if (scope.dateTo) params.date_to = scope.dateTo;
        if (forceRefresh) params.refresh = "1";

        setInFlight(true);
        try {
            const { data: raw } = await api.get<unknown>(dashboardApiContract.endpoint, {
                params: Object.keys(params).length ? params : undefined,
            });
            if (requestId !== latestRequest.current) return;
            // Validate at the boundary: a payload that does not match the contract never reaches the page.
            const parsed = parseDashboardPayload(raw);
            if (parsed.violations.length > 0) reportContractViolations(parsed.violations);
            if (!parsed.ok) {
                setFailed(true);
                if (forceRefresh) toast.error("Could not refresh the dashboard. Showing the last successful result.");
                return;
            }
            setData(parsed.payload);
            setFailed(false);
            setLastRefreshed(new Date());
        } catch {
            if (requestId !== latestRequest.current) return;
            setFailed(true);
            if (forceRefresh) toast.error("Could not refresh the dashboard. Showing the last successful result.");
        } finally {
            if (requestId === latestRequest.current) setInFlight(false);
        }
    }, []);

    useEffect(() => {
        void load({ companyId, dateFrom, dateTo }, false);
    }, [companyId, dateFrom, dateTo, load]);

    const refresh = useCallback(() => {
        void load(scopeRef.current, true);
    }, [load]);

    const setRetryingFlag = useCallback((section: RetryableSection, on: boolean) => {
        const next = new Set(retryingRef.current);
        if (on) next.add(section);
        else next.delete(section);
        retryingRef.current = next;
        setRetrying(next);
    }, []);

    const retrySection = useCallback(
        async (section: RetryableSection) => {
            // A second click while the first request is in flight is not a second request.
            if (retryingRef.current.has(section)) return;
            const scope = scopeRef.current;
            const params: DashboardQueryParams & { section: RetryableSection } = { section, refresh: "1" };
            if (scope.companyId != null) params.company_id = scope.companyId;
            if (scope.dateFrom) params.date_from = scope.dateFrom;
            if (scope.dateTo) params.date_to = scope.dateTo;

            setRetryingFlag(section, true);
            try {
                const { data: raw } = await api.get<unknown>(dashboardApiContract.endpoint, { params });
                const parsed = parseDashboardSection(section, raw);
                if (parsed.violations.length > 0) reportContractViolations(parsed.violations);
                setData((previous) => (previous ? { ...previous, [section]: parsed.section } : previous));
            } catch {
                setData((previous) => (previous ? { ...previous, [section]: { error: SECTION_RETRY_FAILED } } : previous));
            } finally {
                setRetryingFlag(section, false);
            }
        },
        [setRetryingFlag],
    );

    return {
        data,
        loading: inFlight && data === null,
        refreshing: inFlight && data !== null,
        failed,
        lastRefreshed,
        refresh,
        retrying,
        retrySection,
    };
}
