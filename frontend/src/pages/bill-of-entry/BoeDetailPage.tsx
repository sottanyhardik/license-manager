import { useCallback, useContext, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, FileQuestion, TriangleAlert } from "lucide-react";

import { boeApi } from "@/api";
import { EmptyState, QueryBoundary, StatusBadge } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { ModuleWorkspace } from "@/components/workspace";
import { AuthContext } from "@/context/AuthContext";
import { useConfirmDialog } from "@/hooks/useConfirmDialog";
import { buildBoeRecordTabs } from "@/features/bill-of-entry/boeRecordTabs";
import { useBoeRowActions, type BoeRowActionContext } from "@/features/bill-of-entry/useBoeRowActions";
import { fmtFc2, fmtInrExact, fmtQty } from "@/features/bill-of-entry/format";
import { boeInvoiceBadge } from "@/features/bill-of-entry/invoiceStatus";
import type { BoeDetailRow, BoeListItem } from "@/features/bill-of-entry/types";
import { qk } from "@/lib/queryKeys";
import { shouldRetryQuery } from "@/api/queryClient";
import { restoreFilterState } from "@/utils/filterPersistence";
import { BOE_TRANSFER_LETTER_ROLES, ROLES } from "@/routes/authorizationRoles";
import BoeMergeModal from "@/pages/masters/BoeMergeModal";

const ENTITY = "bill-of-entries";
const LIST_PATH = "/bill-of-entries";
/** Shown by the page header and BoeFigures tiles; omitted from the Overview tab. */
const DETAIL_HEADER_FIELDS = [
    "bill_of_entry_number", "bill_of_entry_date", "port_name", "company_name",
    "total_inr", "total_fc", "total_quantity", "unit_price",
] as const;

type MergeSource = { id: number; bill_of_entry_number: string };

const statusOf = (err: unknown) => (err as { response?: { status?: number } } | null)?.response?.status;

/** Return to the register; the saved filters are restored by MasterList via the shared "return to list" flag. */
function useBackToRegister() {
    const navigate = useNavigate();
    return useCallback(() => {
        try {
            sessionStorage.setItem("allotmentListFilters", JSON.stringify({ returnTo: "list", timestamp: Date.now() }));
        } catch { /* storage unavailable: fall back to default filters */ }
        navigate(LIST_PATH);
    }, [navigate]);
}

/** Headline figures (backend values, display-formatting only): right-aligned, tabular numerals. */
function BoeFigures({ item }: { item: BoeListItem }) {
    const figures = [
        { label: "CIF (INR)", value: fmtInrExact(item.total_inr) },
        { label: "CIF (FC)", value: fmtFc2(item.total_fc) },
        { label: "Qty (MT)", value: fmtQty(item.total_quantity) },
        { label: "Unit Price", value: fmtQty(item.unit_price) },
    ];
    return (
        <>
            {figures.map((f) => (
                <div key={f.label} className="flex items-baseline justify-between gap-2 rounded-lg border border-border bg-card px-3 py-1.5 sm:block sm:py-2">
                    <div className="text-[0.66rem] font-semibold uppercase tracking-[0.06em] text-muted-foreground">{f.label}</div>
                    <div className="text-right text-base sm:mt-0.5 sm:text-lg font-semibold tabular-nums text-foreground">{f.value}</div>
                </div>
            ))}
        </>
    );
}

function NotFound({ onBack }: { onBack: () => void }) {
    return (
        <EmptyState
            size="page"
            icon={FileQuestion}
            title="Bill of entry not found"
            description="It may have been deleted or merged into another bill of entry."
            action={<Button variant="outline" size="sm" onClick={onBack}><ArrowLeft className="size-4" aria-hidden="true" /> Back to Bills of Entry</Button>}
        />
    );
}

/**
 * Dedicated BOE record page (`/bill-of-entries/:id`), the Licence-overview
 * pattern: shared ModuleWorkspace header + `?tab=` tabs (Overview default),
 * the same tab set and ActionMenu actions as the expanded register card.
 * Data: `qk.boes.detail(id)` via typed boeApi (shared cache with the BOE
 * Details tab). Role gating: route is BOE_LIST_ROLES; write/TL actions use the
 * same flags as the card.
 */
export default function BoeDetailPage() {
    const { id } = useParams<{ id: string }>();
    const back = useBackToRegister();
    const validId = id !== undefined && /^\d+$/.test(id);

    const query = useQuery({
        queryKey: qk.boes.detail(id ?? ""),
        queryFn: () => boeApi.fetchBOE<BoeListItem>(id as string),
        enabled: validId,
        retry: (count, err) => statusOf(err) !== 404 && shouldRetryQuery(count, err),
    });

    if (!validId || (query.isError && statusOf(query.error) === 404)) {
        return <div className="mx-auto max-w-[1600px]"><NotFound onBack={back} /></div>;
    }

    return (
        <div className="mx-auto max-w-[1600px]">
            <QueryBoundary query={query} loadingLabel="Loading bill of entry" errorTitle="Could not load bill of entry">
                {(item) => <BoeDetailView item={item} onBack={back} />}
            </QueryBoundary>
        </div>
    );
}

function BoeDetailView({ item, onBack }: { item: BoeListItem; onBack: () => void }) {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const { hasAnyRole } = useContext(AuthContext);
    const { confirmDelete, confirmDangerousAction, confirmDialog } = useConfirmDialog();

    const canWrite = hasAnyRole([ROLES.BOE_MANAGER]);
    const canTransferLetter = hasAnyRole(BOE_TRANSFER_LETTER_ROLES);
    // Edit persists the register's filters; reuse the saved ones so it never clobbers them.
    const saved = useMemo(() => restoreFilterState(ENTITY) as
        { filters?: Record<string, unknown>; pagination?: { currentPage?: number; pageSize?: number } } | null, []);

    const invalidateList = useCallback(() => {
        void queryClient.invalidateQueries({ queryKey: ["entity-list", ENTITY] });
    }, [queryClient]);

    const goTransferLetter = useCallback((boeId: number) => navigate(`/bill-of-entries/${boeId}/generate-transfer-letter`), [navigate]);

    // --- merge (same endpoints/modal as the register) ---
    const [mergeOpen, setMergeOpen] = useState(false);
    const [candidates, setCandidates] = useState<MergeSource[]>([]);
    const [candidatesLoading, setCandidatesLoading] = useState(false);
    const [source, setSource] = useState<MergeSource | null>(null);
    const [mergeLoading, setMergeLoading] = useState(false);
    const [mergeError, setMergeError] = useState("");

    const closeMerge = () => { setMergeOpen(false); setSource(null); setCandidates([]); };
    const openMerge = async (target: BoeListItem) => {
        setSource(null);
        setMergeError("");
        setMergeOpen(true);
        setCandidatesLoading(true);
        try {
            const resp = await boeApi.fetchBOEList<{ results?: MergeSource[] }>({ search: target.bill_of_entry_number, is_invoice: "all", page_size: 50 });
            setCandidates((resp.results || []).filter((b) => b.id !== target.id && b.bill_of_entry_number === target.bill_of_entry_number));
        } catch {
            toast.error("Failed to load merge candidates");
        } finally {
            setCandidatesLoading(false);
        }
    };
    const doMerge = async () => {
        if (!source) return;
        setMergeLoading(true);
        setMergeError("");
        try {
            const resp = await boeApi.mergeBOE(item.id, source.id);
            toast.success(boeApi.describeBoeMerge(resp, item.id));
            closeMerge();
            invalidateList();
            void queryClient.invalidateQueries({ queryKey: qk.boes.all });
        } catch (err) {
            const msg = boeApi.extractBoeError(err, "Failed to merge BOE");
            setMergeError(msg);
            toast.error(msg);
        } finally {
            setMergeLoading(false);
        }
    };

    const handleDelete = async (target: BoeListItem) => {
        if (!(await confirmDelete("this record"))) return;
        try {
            await boeApi.deleteBOE(target.id);
            toast.success("Record deleted successfully");
            invalidateList();
            queryClient.removeQueries({ queryKey: qk.boes.detail(String(target.id)) });
            onBack();
        } catch (err) {
            const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
            toast.error(detail || "Failed to delete record");
        }
    };

    const ctx: BoeRowActionContext = {
        canWrite, canTransferLetter, entityName: ENTITY,
        filterParams: saved?.filters ?? {},
        currentPage: saved?.pagination?.currentPage ?? 1,
        pageSize: saved?.pagination?.pageSize ?? 25,
        navigate,
        onDelete: (target) => { void handleDelete(target); },
        invalidateList, confirmDangerousAction,
        onTransferLetter: goTransferLetter,
        onMerge: (target) => { void openMerge(target); },
    };
    const { actions } = useBoeRowActions(item, ctx);

    const invoiceBadge = boeInvoiceBadge(item);
    const number = item.bill_of_entry_number || String(item.id);
    const disputes = ((item.item_details || []) as BoeDetailRow[]).filter((r) => r.is_dispute).length;
    // The page header (number, date, port, company) and the figure tiles already show
    // these fields, so the Overview tab does not repeat them.
    const tabs = buildBoeRecordTabs(item, {
        onTransferLetter: canTransferLetter ? () => goTransferLetter(item.id) : undefined,
        overviewOmit: DETAIL_HEADER_FIELDS,
    });

    return (
        <>
            <ModuleWorkspace
                title={`BOE ${number}`}
                breadcrumbs={[{ label: "Bills of Entry", to: LIST_PATH }, { label: number }]}
                meta={
                    <>
                        <span className="text-sm text-muted-foreground">
                            {[item.bill_of_entry_date, item.port_name].filter(Boolean).join(" · ")}
                        </span>
                        {item.company_name && <span className="text-sm font-medium text-foreground">{item.company_name}</span>}
                        {invoiceBadge && (
                            <StatusBadge tone={invoiceBadge.tone} label={invoiceBadge.label} className={invoiceBadge.muted ? "opacity-60" : undefined} />
                        )}
                        {disputes > 0 && (
                            <StatusBadge tone="danger" icon={TriangleAlert} label={`${disputes} Dispute${disputes > 1 ? "s" : ""}`} />
                        )}
                    </>
                }
                kpis={<BoeFigures item={item} />}
                secondaryActions={actions}
                primaryAction={
                    <Button variant="outline" size="sm" onClick={onBack}>
                        <ArrowLeft className="size-4" aria-hidden="true" /> Back
                    </Button>
                }
                tabs={tabs}
                defaultTab="overview"
            />
            {confirmDialog}
            {mergeOpen && (
                <BoeMergeModal
                    mergeBoeTarget={item}
                    closeMergeModal={closeMerge}
                    mergeCandidatesLoading={candidatesLoading}
                    mergeCandidates={candidates}
                    mergeBoeSource={source}
                    setMergeBoeSource={setSource}
                    mergeBoeLoading={mergeLoading}
                    mergeError={mergeError}
                    doMerge={() => { void doMerge(); }}
                />
            )}
        </>
    );
}
