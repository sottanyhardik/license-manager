/**
 * Generic master record page (`/masters/:entity/:id`) for every registered
 * master. Same anatomy as the BOE / licence record workspaces: shared
 * `ModuleWorkspace` header (breadcrumbs, status, primary + secondary actions)
 * and tabs. Fields come from the backend list metadata; history is the real
 * audit log (`ActivityLog`) for this record's URL — nothing is synthesised.
 */
import { useContext, useMemo } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api from "../../api/axios";
import { AuthContext } from "../../context/AuthContext";
import { ROLES } from "../../routes/authorizationRoles";
import { masterEntities } from "../../routes/config";
import { ModuleWorkspace, WorkspaceSection, type WorkspaceTab } from "@/components/workspace";
import { ActivityTimeline, EmptyState, InlineError, LoadingState, StatusBadge, type ActionMenuItem, type ActivityItem } from "@/components/shared";
import { FieldGrid } from "@/components/shared/FieldGrid";
import { Button } from "@/components/ui/button";
import { formatMasterRecord, formatMasterValue, masterDetailFields, MASTER_AUDIT_FIELDS, readMasterField } from "./masterDetailFields";

interface ActivityLogRow {
    id: number;
    username: string;
    action: string;
    timestamp: string;
    status_code: number | null;
}

const HISTORY_LABEL: Record<string, string> = { CREATE: "Created", UPDATE: "Updated", DELETE: "Deleted" };
const HISTORY_TONE: Record<string, ActivityItem["tone"]> = { CREATE: "success", UPDATE: "info", DELETE: "danger" };

export default function MasterDetail() {
    const { entity = "", id = "" } = useParams();
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const { isSuperAdmin, hasRole } = useContext(AuthContext);
    const canWrite = isSuperAdmin() || hasRole(ROLES.USER_MANAGER);
    const config = masterEntities.find(m => m.entity === entity);
    // `id` is decoded by the router (`025/2023`); the API path re-encodes it.
    const apiPath = `masters/${entity}/${encodeURIComponent(id)}/`;
    const listPath = `/masters/${entity}`;
    const editPath = `${listPath}/${encodeURIComponent(id)}/edit`;

    const metadata = useQuery({
        queryKey: ["master-meta", entity],
        queryFn: async ({ signal }) => (await api.get(`masters/${entity}/`, { params: { page_size: 1 }, signal })).data,
        enabled: Boolean(config),
        staleTime: 5 * 60_000,
    });
    const record = useQuery({
        queryKey: ["master-record", entity, id],
        queryFn: async ({ signal }) => (await api.get(apiPath, { signal })).data as Record<string, unknown>,
        enabled: Boolean(config),
    });

    const fields = useMemo(
        () => (record.data && metadata.data ? masterDetailFields(metadata.data, record.data) : []),
        [record.data, metadata.data],
    );

    if (!config) {
        return <EmptyState size="page" title="Unknown master" description={`“${entity}” is not a registered master.`} action={<Button asChild variant="outline" size="sm"><Link to="/masters">All masters</Link></Button>} />;
    }
    if (record.isPending || metadata.isPending) return <LoadingState variant="page" label={`Loading ${config.label}`} />;
    if (record.isError) {
        const status = (record.error as { response?: { status?: number } })?.response?.status;
        return status === 404
            ? <EmptyState size="page" title="Record not found" description={`No ${config.label.toLowerCase()} record “${id}”.`} action={<Button asChild variant="outline" size="sm"><Link to={listPath}>Back to {config.label}</Link></Button>} />
            : <InlineError error={record.error} onRetry={() => { void record.refetch(); }} title={`Could not load this ${config.label.toLowerCase()} record`} />;
    }
    if (metadata.isError) return <InlineError error={metadata.error} onRetry={() => { void metadata.refetch(); }} title={`Could not load ${config.label} fields`} />;

    const data = record.data;
    const primaryColumn: string | undefined = metadata.data?.list_display?.[0];
    const title = formatMasterValue(primaryColumn ? readMasterField(data, primaryColumn) : undefined) ?? id;
    // "by" columns arrive as raw user ids on most masters; show them only when the API sends a name.
    const auditFields = MASTER_AUDIT_FIELDS.filter(f => f.key in data && (!f.key.endsWith("_by") || typeof data[f.key] === "string"));

    const remove = async () => {
        try {
            await api.delete(apiPath);
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: ["entity-list", entity] }),
                queryClient.invalidateQueries({ queryKey: ["master-count", entity] }),
            ]);
            toast.success(`${config.label} record deleted`);
            // Leave the page first so the mounted record query cannot refetch the deleted row (404 flash).
            navigate(listPath);
            queryClient.removeQueries({ queryKey: ["master-record", entity, id] });
        } catch (err) {
            toast.error(deleteErrorMessage(err, `Failed to delete this ${config.label.toLowerCase()} record`));
        }
    };

    const secondaryActions: ActionMenuItem[] = canWrite ? [{
        id: "delete",
        label: "Delete",
        icon: Trash2,
        tone: "danger",
        confirm: { title: `Delete ${title}?`, description: "This cannot be undone. Records still used elsewhere cannot be deleted.", confirmLabel: "Delete", tone: "danger" },
        onSelect: () => { void remove(); },
    }] : [];

    const tabs: WorkspaceTab[] = [
        {
            id: "details",
            label: "Details",
            render: () => (
                <div className="space-y-6 rounded-lg border border-border bg-card p-4">
                    <WorkspaceSection title="Record">
                        <FieldGrid record={formatMasterRecord(data, fields)} fields={fields} />
                    </WorkspaceSection>
                    {auditFields.length > 0 && (
                        <WorkspaceSection title="Audit">
                            <FieldGrid record={formatMasterRecord(data, auditFields)} fields={auditFields} />
                        </WorkspaceSection>
                    )}
                </div>
            ),
        },
        {
            id: "history",
            label: "History",
            // The audit log API is restricted to user managers (UserManagementPermission).
            anyRole: [ROLES.USER_MANAGER],
            render: () => <MasterHistory endpoint={`/api/masters/${entity}/${id}/`} />,
        },
    ];

    return (
        <ModuleWorkspace
                title={title}
                breadcrumbs={[{ label: "Masters", to: "/masters" }, { label: config.label, to: listPath }, { label: title }]}
                meta={
                    <>
                        <span className="text-sm text-muted-foreground">{config.label}</span>
                        {"is_active" in data && (
                            <StatusBadge tone={data.is_active ? "success" : "neutral"} label={data.is_active ? "Active" : "Inactive"} />
                        )}
                        {!canWrite && <span className="text-xs text-muted-foreground">View only</span>}
                    </>
                }
                primaryAction={canWrite ? (
                    <Button asChild size="sm">
                        <Link to={editPath}><Pencil className="size-4" aria-hidden="true" /> Edit</Link>
                    </Button>
                ) : undefined}
                secondaryActions={secondaryActions}
                tabs={tabs}
                defaultTab="details"
            />
    );
}

/** First readable message from a DRF error body (`detail`, `error`, `non_field_errors`, a list, or a field error). */
function deleteErrorMessage(err: unknown, fallback: string): string {
    const body = (err as { response?: { data?: unknown } })?.response?.data;
    const first = (value: unknown): string | undefined => {
        if (typeof value === "string" && value) return value;
        if (Array.isArray(value)) return value.map(first).find(Boolean);
        if (value && typeof value === "object") {
            const record = value as Record<string, unknown>;
            return first(record.detail) ?? first(record.error) ?? first(record.non_field_errors) ?? Object.values(record).map(first).find(Boolean);
        }
        return undefined;
    };
    return first(body) ?? fallback;
}

/** Successful writes to this record's API URL, newest first, from the audit log. */
function MasterHistory({ endpoint }: { endpoint: string }) {
    const history = useQuery({
        queryKey: ["master-history", endpoint],
        queryFn: async ({ signal }) => (await api.get("masters/activity-logs/", {
            params: { endpoint, changes_only: 1, limit: 100 },
            signal,
        })).data as ActivityLogRow[],
    });
    const items: ActivityItem[] = (history.data ?? []).map(row => ({
        id: row.id,
        at: row.timestamp,
        actor: row.username || undefined,
        action: HISTORY_LABEL[row.action] ?? row.action,
        tone: HISTORY_TONE[row.action],
    }));
    return (
        <div className="rounded-lg border border-border bg-card p-4">
            <ActivityTimeline
                items={items}
                state={history.isPending ? { status: "loading" } : history.isError ? { status: "error", error: history.error } : { status: "success" }}
                emptyLabel="No recorded changes for this record yet. Creation is not logged per record."
                onRetry={() => { void history.refetch(); }}
            />
        </div>
    );
}
