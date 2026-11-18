import { useQuery } from "@tanstack/react-query";

import api from "@/api/axios";
import { ActivityTimeline, type ActivityItem } from "@/components/shared";

type LogRow = { id: number; username: string; action: string; endpoint: string; method: string; timestamp: string; status_code: number | null };

/** What an audited request did, from its API path (the audit log records the request, not field values). */
function describe(row: LogRow): { action: string; tone: ActivityItem["tone"] } {
    const path = row.endpoint;
    if (path.includes("/allocate-items/")) return { action: "Allocated to licence", tone: "success" };
    if (path.includes("/delete-item/")) return { action: "Allocation released", tone: "danger" };
    if (path.endsWith("/copy/")) return { action: "Copied", tone: "info" };
    if (row.action === "CREATE") return { action: "Created", tone: "success" };
    if (row.action === "DELETE") return { action: "Deleted", tone: "danger" };
    return { action: "Edited", tone: "info" };
}

const fetchPrefix = async (prefix: string, signal: AbortSignal) =>
    (await api.get("masters/activity-logs/", { params: { endpoint_prefix: prefix, changes_only: 1, limit: 200 }, signal })).data as LogRow[];

/**
 * History: successful writes to this allotment (`/api/allotments/:id/…`) and
 * its allocation actions (`/api/allotment-actions/:id/…`: allocate, release),
 * newest first, from the audit log (user managers only — the API enforces it).
 */
export function HistoryTab({ id }: { id: number }) {
    const history = useQuery({
        queryKey: ["allotment-history", id],
        queryFn: async ({ signal }) => {
            const [record, actions] = await Promise.all([
                fetchPrefix(`/api/allotments/${id}/`, signal),
                fetchPrefix(`/api/allotment-actions/${id}/`, signal),
            ]);
            return [...record, ...actions].sort((a, b) => b.timestamp.localeCompare(a.timestamp));
        },
    });
    const items: ActivityItem[] = (history.data ?? []).map((row) => {
        const { action, tone } = describe(row);
        return { id: row.id, at: row.timestamp, actor: row.username || undefined, action, tone, detail: <span className="font-mono text-[11px] text-muted-foreground">{row.method} {row.endpoint}</span> };
    });
    return (
        <div className="space-y-2">
            <ActivityTimeline
                items={items}
                state={history.isPending ? { status: "loading" } : history.isError ? { status: "error", error: history.error } : { status: "success" }}
                emptyLabel="No recorded changes or allocation actions for this allotment yet."
                onRetry={() => { void history.refetch(); }}
            />
            <p className="text-xs text-muted-foreground">The audit log records each change request (who, when, what action); field-level previous / new values are not stored.</p>
        </div>
    );
}
