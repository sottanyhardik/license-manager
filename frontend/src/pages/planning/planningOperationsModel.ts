import type { PlanningDashboard, ReplanBatchStatus } from "@/services/api/planningRuleApi";

export const planningDashboardQueryKey = ["planning", "dashboard"] as const;

export const MAX_VISIBLE_BATCH_ERRORS = 10;

export type DashboardTone = "neutral" | "ok" | "warn" | "danger";

export type DashboardTile = { label: string; value: string | number; hint?: string; tone?: DashboardTone };

/** KPI tiles for the workbench strip.  Draft rules are "Not modelled", never zero. */
export function summaryTiles(data: PlanningDashboard): DashboardTile[] {
    const { totals, jobs } = data;
    return [
        { label: "Norms", value: totals.norms, hint: `${totals.norms_with_active_rules} with active rules` },
        { label: "Active rules", value: totals.active_rules },
        { label: "Inactive rules", value: totals.inactive_rules },
        totals.draft_rules == null
            ? { label: "Draft rules", value: "Not modelled", hint: "The rule model has no draft state" }
            : { label: "Draft rules", value: totals.draft_rules },
        { label: "Validation errors", value: totals.validation_errors, tone: totals.validation_errors ? "danger" : "ok" },
        { label: "Warnings", value: totals.warnings, hint: "Rules that match every item", tone: totals.warnings ? "warn" : "ok" },
        { label: "Pending jobs", value: jobs.pending },
        { label: "Failed jobs", value: jobs.failed, tone: jobs.failed ? "danger" : "ok" },
    ];
}

/** Request ids a retry must resubmit: every failed row, once each. */
export function retryableRequestIds(status: ReplanBatchStatus): number[] {
    return Array.from(new Set(status.errors.map((error) => error.request_id)));
}

