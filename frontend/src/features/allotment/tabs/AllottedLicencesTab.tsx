import { useState } from "react";
import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ArrowDownToLine, FileText, Undo2 } from "lucide-react";

import api from "@/api/axios";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState, StatusBadge, type Tone } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { displayValue } from "@/lib/display";
import { invalidateLicence, qk } from "@/lib/queryKeys";
import { formatCifUsd } from "@/features/licenses/licenceFormat";
import type { LicenseListItem } from "@/features/licenses/types";
import { formatTruthyIndianNumber } from "@/pages/masters/masterDisplayFormatters";
import { DetailQueryBoundary } from "../DetailQueryBoundary";
import type { AllotmentDetailRow, AllotmentRecord } from "../types";

type LicenceSummary = Pick<LicenseListItem, "id" | "license_number" | "get_norm_class" | "get_balance_cif">;
/** One row of `licenses/:id/overview-allotments/` (licence balance engine). */
type LicenceAllotmentRow = { allotment_number: string; quantity: string; cif_fc: string; outstanding_cif_fc: string; status: string };

const qty = (v: unknown) => formatTruthyIndianNumber(v as string, { maximumFractionDigits: 3 }, "0");
const STATUS_TONE: Record<string, Tone> = { "Linked to BOE": "success", Approved: "info", Allotted: "primary", Pending: "warning" };
const TH = "px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-muted-foreground";
const TD = "px-3 py-2 align-top";

interface LicenceGroup { licenceId: number | null; number: string; rows: AllotmentDetailRow[] }

function groupByLicence(rows: AllotmentDetailRow[]): LicenceGroup[] {
    const groups = new Map<string, LicenceGroup>();
    for (const row of rows) {
        const number = String(row.license_number ?? "—");
        const group = groups.get(number) ?? { licenceId: (row.license_id as number | null) ?? null, number, rows: [] };
        group.rows.push(row);
        groups.set(number, group);
    }
    return [...groups.values()];
}

/**
 * Per licence, while this tab is open only: the licence register row (SION,
 * authoritative available CIF) and the licence's own allotment ledger row for
 * THIS allotment (outstanding reservation + status from the balance engine) —
 * the same records the licence workspace's "BOE & Allotment" tab shows.
 */
function useLicenceSides(allotmentId: number, groups: LicenceGroup[]) {
    const summaries = useQueries({
        queries: groups.map((g) => ({
            queryKey: ["allotment-licence-summary", g.number],
            queryFn: async ({ signal }: { signal: AbortSignal }) => {
                const { data } = await api.get("licenses/", { params: { license_number: g.number, page_size: 1 }, signal });
                return ((data?.results ?? data ?? []) as LicenceSummary[]).find((r) => r.license_number === g.number) ?? null;
            },
            staleTime: 30_000, retry: false,
        })),
    });
    const ledgers = useQueries({
        queries: groups.map((g) => ({
            queryKey: ["allotment-licence-ledger", g.licenceId, allotmentId],
            enabled: g.licenceId != null,
            queryFn: async ({ signal }: { signal: AbortSignal }) => {
                const { data } = await api.get(`licenses/${g.licenceId}/overview-allotments/`, { signal });
                return ((data ?? []) as LicenceAllotmentRow[]).find((r) => r.allotment_number === `ALT-${allotmentId}`) ?? null;
            },
            staleTime: 30_000, retry: false,
        })),
    });
    return groups.map((g, i) => ({ group: g, summary: summaries[i], ledger: ledgers[i] }));
}

function Pending({ q, children }: { q: { isPending: boolean; isError: boolean; data?: unknown; fetchStatus?: string }; children: () => React.ReactNode }) {
    if (q.isPending && q.fetchStatus !== "idle") return <span className="text-muted-foreground">…</span>;
    if (q.isError || !q.data) return <span className="text-muted-foreground" title="Not available for your role or no ledger row">—</span>;
    return <>{children()}</>;
}

type TableProps = {
    record: AllotmentRecord;
    canWrite: boolean;
    canViewBoes: boolean;
    onAllocate: () => void;
    onViewBoes: () => void;
};

function AllottedLicencesTable({ record, canWrite, canViewBoes, onAllocate, onViewBoes }: TableProps) {
    const queryClient = useQueryClient();
    const rows = record.allotment_details || [];
    const sides = useLicenceSides(record.id, groupByLicence(rows));
    const [releasing, setReleasing] = useState<AllotmentDetailRow | null>(null);

    // Existing release endpoint: removes the allocation and restores the licence item's availability.
    const release = useMutation({
        mutationFn: (row: AllotmentDetailRow) => api.delete(`allotment-actions/${record.id}/delete-item/${row.id}/`).then((r) => r.data),
        onSuccess: (data, row) => {
            toast.success(data?.message || "Allocation released");
            void queryClient.invalidateQueries({ queryKey: qk.allotments.detail(record.id) });
            void queryClient.invalidateQueries({ queryKey: ["entity-list", "allotments"] });
            void queryClient.invalidateQueries({ queryKey: ["allotment-licence-ledger"] });
            void queryClient.invalidateQueries({ queryKey: ["allotment-licence-summary"] });
            if (row.license_id) void invalidateLicence(queryClient, row.license_id as number);
        },
        onError: (err: unknown) => toast.error((err as { response?: { data?: { error?: string } } })?.response?.data?.error || "Failed to release allocation"),
        onSettled: () => setReleasing(null),
    });

    const toolbar = (
        <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">
                Allocation records of this allotment, grouped by licence. Outstanding and status come from each licence's balance ledger;
                a BOE-linked allotment is consumed by its BOE and is not reserved again.
            </p>
            <div className="flex gap-2">
                {canViewBoes && <Button type="button" size="sm" variant="outline" onClick={onViewBoes}><FileText className="size-4" />View BOEs</Button>}
                {canWrite && <Button type="button" size="sm" onClick={onAllocate}><ArrowDownToLine className="size-4" />Allocate Licence</Button>}
            </div>
        </div>
    );

    if (!rows.length) {
        return (
            <div className="space-y-3">
                {toolbar}
                <EmptyState title="No licences allocated" description="This allotment has no allocation records yet." />
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {toolbar}
            <div className="overflow-x-auto rounded-lg border border-border/70">
                <table className="w-full min-w-[980px] text-sm" aria-label="Allotted licences">
                    <thead className="bg-muted/50">
                        <tr>
                            <th className={TH}>Licence</th><th className={TH}>Type</th><th className={TH}>Exporter</th><th className={TH}>SION</th>
                            <th className={TH}>Item (Sl#)</th><th className={`${TH} text-right`}>Allocated Qty</th><th className={`${TH} text-right`}>Allocated CIF (FC)</th>
                            <th className={`${TH} text-right`}>Outstanding (FC)</th><th className={`${TH} text-right`}>Available CIF</th><th className={TH}>Status</th>
                            {canWrite && <th className={TH}><span className="sr-only">Actions</span></th>}
                        </tr>
                    </thead>
                    {sides.map(({ group, summary, ledger }) => (
                        <tbody key={group.number} className="border-t border-border/70">
                            {group.rows.map((row, index) => (
                                <tr key={String(row.id ?? index)} className="border-t border-border/40 first:border-t-0">
                                    {index === 0 && <>
                                        <td className={`${TD} whitespace-nowrap`} rowSpan={group.rows.length}>
                                            {group.licenceId ? <Link to={`/licenses/${group.licenceId}`} className="font-mono font-semibold text-primary underline-offset-2 hover:underline">{group.number}</Link> : <span className="font-mono">{group.number}</span>}
                                        </td>
                                        <td className={TD} rowSpan={group.rows.length}>{displayValue(row.purchase_status)}</td>
                                        <td className={TD} rowSpan={group.rows.length}>{displayValue(row.exporter)}</td>
                                        <td className={TD} rowSpan={group.rows.length}><Pending q={summary}>{() => summary.data?.get_norm_class || "—"}</Pending></td>
                                    </>}
                                    <td className={TD}><span className="block max-w-[16rem] truncate" title={String(row.product_description ?? "")}>{displayValue(row.product_description)}</span><span className="text-xs text-muted-foreground">Sl# {displayValue(row.serial_number)}</span></td>
                                    <td className={`${TD} text-right tabular-nums`}>{qty(row.qty)}</td>
                                    <td className={`${TD} text-right tabular-nums`}>{formatCifUsd(row.cif_fc)}</td>
                                    {index === 0 && <>
                                        <td className={`${TD} text-right tabular-nums`} rowSpan={group.rows.length}><Pending q={ledger}>{() => formatCifUsd(ledger.data!.outstanding_cif_fc)}</Pending></td>
                                        <td className={`${TD} text-right tabular-nums`} rowSpan={group.rows.length}><Pending q={summary}>{() => formatCifUsd(summary.data!.get_balance_cif)}</Pending></td>
                                        <td className={TD} rowSpan={group.rows.length}><Pending q={ledger}>{() => <StatusBadge tone={STATUS_TONE[ledger.data!.status] ?? "neutral"} label={ledger.data!.status} />}</Pending></td>
                                    </>}
                                    {canWrite && (
                                        <td className={`${TD} whitespace-nowrap`}>
                                            <Button type="button" size="sm" variant="ghost" disabled={release.isPending || row.id == null} onClick={() => setReleasing(row)} aria-label={`Release allocation ${group.number} Sl# ${row.serial_number}`}>
                                                <Undo2 className="size-3.5" />Release
                                            </Button>
                                        </td>
                                    )}
                                </tr>
                            ))}
                        </tbody>
                    ))}
                </table>
            </div>
            <ConfirmDialog
                show={!!releasing}
                title="Release allocation?"
                message={releasing ? `Release ${qty(releasing.qty)} (${formatCifUsd(releasing.cif_fc)}) allocated from licence ${releasing.license_number} Sl# ${releasing.serial_number}? The licence item's availability is restored and the release is recorded in the audit log.` : ""}
                severity="danger"
                confirmText={release.isPending ? "Releasing…" : "Release"}
                onConfirm={() => releasing && release.mutate(releasing)}
                onCancel={() => setReleasing(null)}
            />
        </div>
    );
}

/** Allotted Licences: actual allocation records (`allotments/:id/` details), by licence, with release + allocate actions. */
export function AllottedLicencesTab(props: Omit<TableProps, "record"> & { id: number }) {
    const { id, ...rest } = props;
    return (
        <DetailQueryBoundary id={id}>
            {(record) => <AllottedLicencesTable record={record} {...rest} />}
        </DetailQueryBoundary>
    );
}
