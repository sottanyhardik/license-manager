import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { fetchPlanningDashboard, type PlanningDashboard } from "@/services/api/planningRuleApi";
import { planningDashboardQueryKey, summaryTiles, type DashboardTile, type DashboardTone } from "./planningOperationsModel";

const displayDate = (value: string | null | undefined) => (value ? new Date(value).toLocaleString() : "Never");

const toneClass: Record<DashboardTone, string> = {
    neutral: "text-foreground",
    ok: "text-emerald-700 dark:text-emerald-400",
    warn: "text-amber-700 dark:text-amber-400",
    danger: "text-destructive",
};

function Tile({ label, value, hint, tone = "neutral" }: DashboardTile) {
    return (
        <div className="min-w-[8.5rem] flex-1 rounded-lg border bg-background px-3 py-2">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className={`mt-0.5 text-lg font-semibold tabular-nums ${toneClass[tone]}`}>{value}</dd>
            {hint ? <p className="text-[11px] text-muted-foreground">{hint}</p> : null}
        </div>
    );
}

export function PlanningDashboardStrip() {
    const query = useQuery<PlanningDashboard>({
        queryKey: planningDashboardQueryKey,
        queryFn: fetchPlanningDashboard,
        staleTime: 30_000,
    });

    if (query.isPending) {
        return (
            <section aria-label="Planning overview" className="rounded-lg border bg-card p-3">
                <p role="status" className="text-sm text-muted-foreground">Loading planning overview…</p>
            </section>
        );
    }
    if (query.isError || !query.data) {
        return (
            <section aria-label="Planning overview" className="flex items-center justify-between gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
                <p role="alert" className="text-sm text-destructive">The planning overview could not be loaded.</p>
                <Button variant="outline" size="sm" onClick={() => void query.refetch()}>Retry</Button>
            </section>
        );
    }

    const data = query.data;
    const tiles = summaryTiles(data);
    if (data.totals.norms === 0) {
        return (
            <section aria-label="Planning overview" className="rounded-lg border border-dashed bg-card p-4 text-center">
                <p className="text-sm text-muted-foreground">No active SION norms are configured yet.</p>
            </section>
        );
    }
    return (
        <section aria-label="Planning overview" className="rounded-lg border bg-card p-3">
            <dl className="flex flex-wrap gap-2">
                {tiles.map((tile) => <Tile key={tile.label} {...tile} />)}
            </dl>
            <p className="mt-2 text-xs text-muted-foreground">
                Last rule change: {displayDate(data.last_rule_change.modified_on)}
                {data.last_rule_change.modified_by ? ` by ${data.last_rule_change.modified_by}` : ""}
                {" · "}Last successful planning run: {displayDate(data.jobs.last_successful_execution)}
            </p>
        </section>
    );
}
