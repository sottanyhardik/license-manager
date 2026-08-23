import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ScrollText } from "lucide-react";

import api from "@/api/axios";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatDateTime } from "@/utils/dateFormatter";
import { getErrorMessage } from "@/utils/errorUtils";
import { pick, reconActionMeta, reconKeys, unwrapList, type ReconRow } from "./reconciliationHelpers";

/**
 * Compact, always-visible recent-activity list below the 8 tabs — modeled on
 * admin/ActivityLog.tsx's ACTION_META chip-per-action pattern, scaled down to
 * a lightweight list rather than the full filterable page (that page already
 * exists at /admin/activity-log for anyone who needs the full history view).
 */
export default function ReconciliationAuditLog() {
    const [scope, setScope] = useState<"today" | "all">("today");

    const { data, isLoading, isError, error } = useQuery({
        queryKey: reconKeys.auditLog(scope),
        queryFn: async () => {
            const params = scope === "today" ? { scope: "today" } : {};
            const { data } = await api.get("reconciliation/audit-log/", { params });
            return unwrapList(data);
        },
    });

    const rows = data ?? [];

    return (
        <Card className="mt-4">
            <CardHeader className="flex flex-row items-center justify-between border-b">
                <CardTitle className="flex items-center gap-2 text-sm">
                    <ScrollText className="size-4 text-muted-foreground" aria-hidden="true" />
                    Recent Reconciliation Activity
                </CardTitle>
                <div className="flex gap-1">
                    <Button
                        variant={scope === "today" ? "secondary" : "ghost"}
                        size="sm"
                        onClick={() => setScope("today")}
                    >
                        Today
                    </Button>
                    <Button
                        variant={scope === "all" ? "secondary" : "ghost"}
                        size="sm"
                        onClick={() => setScope("all")}
                    >
                        All History
                    </Button>
                </div>
            </CardHeader>
            <CardContent className="max-h-72 overflow-y-auto p-0">
                {isLoading ? (
                    <div className="space-y-2 p-4">
                        {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-8 w-full rounded-md" />)}
                    </div>
                ) : isError ? (
                    <p className="p-4 text-xs text-destructive">{getErrorMessage(error) || "Failed to load audit log."}</p>
                ) : rows.length === 0 ? (
                    <p className="p-4 text-xs text-muted-foreground">No reconciliation activity {scope === "today" ? "today" : "yet"}.</p>
                ) : (
                    <ul className="divide-y divide-border">
                        {rows.map((row, idx) => <AuditLogRow key={String(pick(row, "id") ?? idx)} row={row} />)}
                    </ul>
                )}
            </CardContent>
        </Card>
    );
}

/**
 * `ReconciliationLog`'s `_serialize_log` (`backend/apps/reconciliation/views.py`)
 * returns flat `trade_id`/`invoice_number` and `bill_of_entry_id`/
 * `bill_of_entry_number` pairs (plus `license_item_id` with no label) rather
 * than nested objects — prefer the human-readable number, fall back to the
 * raw id, and try a couple of alternate/nested shapes defensively in case
 * this serialization changes.
 */
function describeTarget(row: ReconRow): string | null {
    const direct = pick(row, "target_label", "target", "trade_label", "boe_label", "bill_of_entry_label", "label");
    if (direct != null) return String(direct);

    const invoiceNumber = pick(row, "invoice_number");
    if (invoiceNumber != null) return String(invoiceNumber);
    const boeNumber = pick(row, "bill_of_entry_number");
    if (boeNumber != null) return String(boeNumber);

    for (const key of ["trade", "bill_of_entry", "license_item"]) {
        const val = (row as Record<string, unknown>)[key];
        if (val === null || val === undefined) continue;
        if (typeof val === "object") {
            return String(pick(val as ReconRow, "invoice_number", "bill_of_entry_number", "label", "id") ?? "");
        }
        return String(val);
    }

    const fallbackId = pick(row, "trade_id", "bill_of_entry_id", "license_item_id");
    return fallbackId != null ? String(fallbackId) : null;
}

function AuditLogRow({ row }: { row: ReconRow }) {
    const action = String(pick(row, "action") ?? "");
    const { chipClass, Icon } = reconActionMeta(action);
    const target = describeTarget(row);
    const user = pick(row, "user", "user_name", "created_by", "created_by_name");
    const createdOn = pick(row, "created_on", "created_at", "timestamp");
    const reason = pick(row, "reason", "note");

    return (
        <li className="flex items-start gap-3 px-4 py-2.5 text-xs">
            <span className={cn("mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md", chipClass)}>
                <Icon className="size-3.5" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
                    <span className="font-semibold text-foreground">{action.replace(/_/g, " ") || "ACTION"}</span>
                    {target != null && <span className="text-muted-foreground">· {String(target)}</span>}
                </div>
                {reason != null && String(reason).trim() !== "" && (
                    <p className="mt-0.5 truncate text-muted-foreground" title={String(reason)}>{String(reason)}</p>
                )}
            </div>
            <div className="shrink-0 text-right text-muted-foreground">
                {user != null && <div>{String(user)}</div>}
                <div>{createdOn != null ? formatDateTime(String(createdOn)) : "—"}</div>
            </div>
        </li>
    );
}
