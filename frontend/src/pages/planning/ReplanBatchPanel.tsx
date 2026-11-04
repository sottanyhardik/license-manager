import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ReplanBatchStatus } from "@/services/api/planningRuleApi";
import { MAX_VISIBLE_BATCH_ERRORS, retryableRequestIds } from "./planningOperationsModel";

const TITLE: Record<ReplanBatchStatus["state"], string> = {
    RUNNING: "Planning in progress",
    SUCCEEDED: "All licences planned",
    PARTIAL_FAILURE: "Some licences failed",
    FAILED: "Planning failed",
};

const BADGE_VARIANT: Record<ReplanBatchStatus["state"], "default" | "secondary" | "destructive" | "outline"> = {
    RUNNING: "secondary",
    SUCCEEDED: "default",
    PARTIAL_FAILURE: "destructive",
    FAILED: "destructive",
};

export function ReplanBatchPanel({
    label, status, onRetry, retrying = false,
}: {
    label: string;
    status: ReplanBatchStatus;
    onRetry: (requestIds: number[]) => void;
    retrying?: boolean;
}) {
    const retryIds = retryableRequestIds(status);
    const canRetry = status.state !== "RUNNING" && retryIds.length > 0;
    const visible = status.errors.slice(0, MAX_VISIBLE_BATCH_ERRORS);
    const hidden = status.errors.length - visible.length;

    return (
        <section aria-label="Planning batch status" className="rounded-lg border bg-card p-3">
            <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold">{label}: {TITLE[status.state]}</h3>
                <Badge variant={BADGE_VARIANT[status.state]}>{status.state.replace("_", " ")}</Badge>
                <p className="text-xs text-muted-foreground tabular-nums">
                    {status.requested} requested · {status.succeeded} succeeded · {status.failed} failed · {status.skipped} skipped
                    {status.active ? ` · ${status.active} in progress` : ""}
                </p>
                {canRetry ? (
                    <Button className="ml-auto" size="sm" variant="outline" disabled={retrying} onClick={() => onRetry(retryIds)}>
                        Retry {retryIds.length} failed {retryIds.length === 1 ? "licence" : "licences"}
                    </Button>
                ) : null}
            </div>
            {status.unknown_request_ids.length ? (
                <p role="alert" className="mt-2 text-xs text-destructive">
                    {status.unknown_request_ids.length} request(s) could not be found, so they are counted as failed.
                </p>
            ) : null}
            {visible.length ? (
                <ul aria-label="Failed licences" className="mt-2 space-y-1 text-xs">
                    {visible.map((error) => (
                        <li key={`${error.request_id}-${error.sion_id ?? "x"}-${error.error_code}`} className="rounded border border-destructive/20 px-2 py-1">
                            <span className="font-medium">{error.license_number ?? `Licence ${error.license_id}`}</span>
                            {error.sion_id ? <span className="text-muted-foreground"> · SION {error.sion_id}</span> : null}
                            <span className="text-muted-foreground"> · {error.error_code}: </span>
                            <span>{error.error_message}</span>
                        </li>
                    ))}
                    {hidden > 0 ? <li className="text-muted-foreground">+{hidden} more</li> : null}
                </ul>
            ) : null}
            <p className="mt-2 text-[11px] text-muted-foreground">
                Started {status.started_at ? new Date(status.started_at).toLocaleString() : "—"}
                {status.completed_at ? ` · Completed ${new Date(status.completed_at).toLocaleString()}` : ""}
                {status.initiated_by ? ` · By ${status.initiated_by}` : ""}
            </p>
        </section>
    );
}
