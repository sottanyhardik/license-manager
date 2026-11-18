/**
 * MasterRecordPanel: the complete record of any registered master, rendered
 * inline inside its expanded list row (`GenericMasterCards`) — the licence
 * register pattern (`LicenceCard` → `LicenseRecordWorkspace`), not a separate
 * page. `/masters/:entity/:id` opens the list with this panel expanded.
 *
 * Tabs come from one generic layout (`buildMasterDetailLayout`) and the
 * master's metadata: Overview, Details (accordion), Edit (the generic
 * `MasterForm`, embedded — save/cancel stay in the row; writers only),
 * Documents (stored files + .docx preview), Related records (configured child
 * collections) and History (real audit log, user managers only) — each only
 * when the master supports it. Nothing is synthesised or master-specific.
 */
import { useContext, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { toast } from "sonner";
import api from "../../api/axios";
import { AuthContext } from "../../context/AuthContext";
import { ROLES } from "../../routes/authorizationRoles";
import { DetailTabs, ModuleAccordion, type AccordionSection, type DetailTab } from "@/components/workspace";
import { DocxViewer } from "@/components/documents/DocxViewer";
import { ActivityTimeline, EmptyState, InlineError, LoadingState, type ActivityItem } from "@/components/shared";
import { FieldGrid } from "@/components/shared/FieldGrid";
import { Button } from "@/components/ui/button";
import { openDocument, toProtectedMediaPath } from "../../utils/documentDownload";
import { formatMasterRecord } from "./masterDetailFields";
import { buildMasterDetailLayout, type MasterDocument } from "./masterDetailLayout";
import { resolveMasterColumns } from "./masterColumns";
import { formatTruthyInr } from "./masterDisplayFormatters";
import { NestedRows } from "./tables/NestedRows";
import MasterForm from "./MasterForm";

interface ActivityLogRow {
    id: number;
    username: string;
    action: string;
    timestamp: string;
    status_code: number | null;
}

export interface MasterRecordPanelProps {
    entity: string;
    /** Raw record lookup (`7`, `025/2023`) — the API path re-encodes it. */
    lookup: string;
    /** Accessible name prefix, e.g. "Exchange Rates 01-11-2026". */
    label: string;
    /** First tab to show (old `?tab=details` / `/edit` links); unknown/hidden ids fall back to Overview. */
    initialTab?: string;
    /** A later request to switch tab (e.g. row menu "Edit" on an open record); `n` changes per request. */
    tabRequest?: { tab: string; n: number };
    /** Shows the Edit tab (same write rule as the row's Edit/Delete); the API still enforces permissions. */
    canWrite?: boolean;
    /** API collection path (default `masters/<entity>/`; e.g. `incentive-licenses/`). */
    apiBase?: string;
}

/** Old tab ids from earlier links. */
const TAB_ALIASES: Record<string, string> = { document: "documents" };
const tabId = (tab: string | undefined) => (tab ? TAB_ALIASES[tab] ?? tab : "overview");

const HISTORY_LABEL: Record<string, string> = { CREATE: "Created", UPDATE: "Updated", DELETE: "Deleted" };
const HISTORY_TONE: Record<string, ActivityItem["tone"]> = { CREATE: "success", UPDATE: "info", DELETE: "danger" };
const LABEL_CLASS = "text-[0.66rem] font-semibold uppercase tracking-[0.06em] text-muted-foreground";

export default function MasterRecordPanel({ entity, lookup, label, initialTab, tabRequest, canWrite = false, apiBase }: MasterRecordPanelProps) {
    const collection = apiBase ?? `masters/${entity}/`;
    const { hasAnyRole } = useContext(AuthContext);
    const queryClient = useQueryClient();
    const [tab, setTab] = useState(() => tabId(initialTab));
    const requestedTab = tabRequest?.tab;
    const requestNonce = tabRequest?.n;
    useEffect(() => {
        if (requestedTab) setTab(tabId(requestedTab));
    }, [requestedTab, requestNonce]);
    const apiPath = `${collection}${encodeURIComponent(lookup)}/`;

    const metadata = useQuery({
        queryKey: ["master-meta", entity],
        queryFn: async ({ signal }) => (await api.get(collection, { params: { page_size: 1 }, signal })).data,
        staleTime: 5 * 60_000,
    });
    const record = useQuery({
        queryKey: ["master-record", entity, lookup],
        queryFn: async ({ signal }) => (await api.get(apiPath, { signal })).data as Record<string, unknown>,
    });

    const layout = useMemo(
        () => (record.data && metadata.data ? buildMasterDetailLayout(entity, metadata.data, record.data) : null),
        [entity, record.data, metadata.data],
    );

    if (record.isPending || metadata.isPending) return <LoadingState variant="spinner" label={`Loading ${label}`} />;
    if (record.isError) {
        const status = (record.error as { response?: { status?: number } })?.response?.status;
        return status === 404
            ? <EmptyState title="Record not found" description={`No record “${lookup}”. It may have been deleted.`} />
            : <InlineError error={record.error} onRetry={() => { void record.refetch(); }} title="Could not load this record" />;
    }
    if (metadata.isError || !layout) {
        return <InlineError error={metadata.error} onRetry={() => { void metadata.refetch(); }} title="Could not load this record's fields" />;
    }

    const data = record.data;
    const { overview, sections, documents, related } = layout;
    const preview = documents.find(d => d.previewable);
    // Overview shows `inr` columns with the register's ₹ formatter (display only; values come from the API).
    const inrFields = new Set(resolveMasterColumns(entity, metadata.data ?? {}).columns.filter(c => c.format === "inr").map(c => c.field));
    const overviewRecord = Object.fromEntries(Object.entries(formatMasterRecord(data, overview))
        .map(([key, value]) => [key, inrFields.has(key) && value !== null ? formatTruthyInr(data[key] as number | string, "—") : value]));

    const accordion: AccordionSection[] = sections.map(section => ({
        id: section.id,
        title: section.title,
        defaultOpen: section.id !== "audit",
        render: () => <FieldGrid record={formatMasterRecord(data, section.fields)} fields={section.fields} />,
    }));

    const tabs: DetailTab[] = [
        {
            id: "overview",
            label: "Overview",
            render: () => (
                <div className="space-y-3">
                    {overview.length > 0
                        ? <FieldGrid record={overviewRecord} fields={overview} />
                        : <p className="text-sm text-muted-foreground">No summary fields recorded for this record.</p>}
                </div>
            ),
        },
        {
            id: "details",
            label: "Details",
            render: () => <ModuleAccordion sections={accordion} persistKey={`master:${entity}:details`} />,
        },
        {
            id: "edit",
            label: "Edit",
            visible: canWrite,
            render: () => (
                <MasterForm
                    key={`${entity}:${lookup}`}
                    embedded
                    entityName={entity}
                    recordId={lookup}
                    // The form toasts and refreshes the list + record; history gains the new UPDATE entry.
                    onSuccess={() => { void queryClient.invalidateQueries({ queryKey: ["master-history"] }); }}
                    onClose={() => setTab("overview")}
                />
            ),
        },
        {
            id: "documents",
            label: "Documents",
            visible: documents.length > 0,
            render: () => (
                <div className="space-y-3">
                    <AttachmentList documents={documents} />
                    {preview && <DocumentPreview preview={preview} />}
                </div>
            ),
        },
        {
            id: "related",
            label: `Related records (${related.reduce((total, c) => total + c.rows.length, 0)})`,
            visible: related.length > 0,
            render: () => (
                <div className="space-y-4">
                    {related.map(c => <NestedRows key={c.collection.field} collection={c.collection} rows={c.rows} />)}
                </div>
            ),
        },
        {
            id: "history",
            label: "History",
            // The audit log API is restricted to user managers (UserManagementPermission).
            visible: hasAnyRole([ROLES.USER_MANAGER]),
            // Same audit endpoint string as the request log records (raw, unencoded key).
            render: () => <MasterHistory endpoint={`/api/${collection}${lookup}/`} />,
        },
    ];

    return (
        <DetailTabs
            recordKey={`${entity}:${lookup}`}
            tabs={tabs}
            value={tab}
            onValueChange={setTab}
            ariaLabel={`${label} sections`}
        />
    );
}

/** The record's Word document rendered in the app (fetched through the authenticated media endpoint). */
function DocumentPreview({ preview }: { preview: MasterDocument }) {
    return (
        <div className="space-y-3">
            <dl className="flex flex-wrap gap-x-6 gap-y-1">
                <div className="min-w-0">
                    <dt className={LABEL_CLASS}>{preview.label}</dt>
                    <dd className="break-all font-mono text-xs">{preview.filename}</dd>
                </div>
                <div>
                    <dt className={LABEL_CLASS}>Format</dt>
                    <dd className="text-xs">Word document (.docx)</dd>
                </div>
            </dl>
            <DocxViewer path={toProtectedMediaPath(preview.url)} filename={preview.filename} />
        </div>
    );
}

/** Stored files of a record with an authenticated download (never a public /media link). */
function AttachmentList({ documents }: { documents: MasterDocument[] }) {
    const download = (doc: MasterDocument) => {
        openDocument(doc.url, doc.filename).catch(() => toast.error(`Could not download ${doc.filename}`));
    };
    return (
        <ul className="divide-y divide-border rounded-md border border-border" aria-label="Attachments">
            {documents.map(doc => (
                <li key={doc.key} className="flex min-w-0 items-center gap-3 px-3 py-2">
                    <div className="min-w-0 flex-1">
                        <p className={LABEL_CLASS}>{doc.label}</p>
                        <p className="truncate font-mono text-xs" title={doc.filename}>{doc.filename}</p>
                    </div>
                    <Button type="button" size="sm" variant="outline" onClick={() => download(doc)} aria-label={`Download ${doc.filename}`}>
                        <Download className="size-4" aria-hidden="true" /> Download
                    </Button>
                </li>
            ))}
        </ul>
    );
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
        <ActivityTimeline
            items={items}
            state={history.isPending ? { status: "loading" } : history.isError ? { status: "error", error: history.error } : { status: "success" }}
            emptyLabel="No recorded changes for this record yet. Creation is not logged per record."
            onRetry={() => { void history.refetch(); }}
        />
    );
}
