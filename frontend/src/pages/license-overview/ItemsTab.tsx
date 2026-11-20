import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { invalidateMappingQueries } from "@/pages/mapping/invalidate";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useLicenseOverviewItems } from "./useLicenseOverviewItems";
import {
    importItemNamesKey,
    previewImportItemNames,
    revertImportItemNames,
    saveImportItemNames,
    useLicenseImportItemNames,
} from "./useLicenseImportItemNames";
import { licenseOverviewKeys } from "./useLicenseOverviewSummary";
import ImportItemNameCell from "./ImportItemNameCell";
import { canBeGlobal, combinationKey, displayName, rowItemIds, type ItemNameDraft } from "./importItemNameUtils";
import ImportItemNameSaveDialog from "./ImportItemNameSaveDialog";
import { ImportItemNameHistoryDialog, ImportItemNameRevertDialog } from "./ImportItemNameDialogs";
import { extractApiError, fmtNum, sortRows, type SortState } from "./licenseOverviewHelpers";
import SortableHeader from "./SortableHeader";
import type { ImportItemNameChange, ImportItemNamePreview, ImportItemNamePropagation, ImportItemNameRow, ImportItemNameScope, LicenseOverviewItemRow } from "./types";

interface ItemsTabProps {
    licenseId: string | number | undefined;
    isActive: boolean;
}

type SortKey = keyof LicenseOverviewItemRow | "item_name";

/**
 * Items tab — one row per import item's balance breakdown, from
 * `GET /licenses/<id>/overview-items/`. `balance_qty`/`balance_cif` here are
 * a NEW, display-only figure (`total - debited - allotted`) that is
 * intentionally distinct from the "available"/"balance" figures shown
 * elsewhere (e.g. the license accordion row) — see `types.ts`.
 *
 * Row count is small (per-item, not per-BOE), so this always renders as a
 * plain table with client-side sort — no cards-vs-table threshold needed.
 */
function propagationSummary(propagation: ImportItemNamePropagation[]): string {
    const sum = (key: "applied" | "licences" | "overridden" | "conflicts") => propagation.reduce((n, p) => n + p[key], 0);
    const applied = sum("applied");
    const licences = sum("licences");
    const overridden = sum("overridden");
    const conflicts = sum("conflicts");
    // Licence counts are per combination; combinations can share licences, so a sum would overcount — show it only for one.
    const where = propagation.length === 1
        ? ` on ${licences} licence${licences === 1 ? "" : "s"}`
        : ` across ${propagation.length} Description + HSN combinations`;
    return `Applied to ${applied} record${applied === 1 ? "" : "s"}${where}`
        + (overridden ? `; ${overridden} overridden` : "")
        + (conflicts ? `; ${conflicts} conflict${conflicts === 1 ? "" : "s"}` : "");
}

export default function ItemsTab({ licenseId, isActive }: ItemsTabProps) {
    const { data, isLoading, isError, error } = useLicenseOverviewItems(licenseId, isActive);
    const [sort, setSort] = useState<SortState<SortKey>>({ key: null, direction: "asc" });
    const queryClient = useQueryClient();
    const names = useLicenseImportItemNames(licenseId, isActive);
    const canEdit = names.data?.can_edit === true;
    const nameState: "loading" | "error" | "ready" = names.isError ? "error" : names.data ? "ready" : "loading";
    const nameById = useMemo(() => {
        const map = new Map<number, ImportItemNameRow>();
        for (const r of names.data?.rows ?? []) map.set(r.import_item_id, r);
        return map;
    }, [names.data]);

    const [drafts, setDrafts] = useState<Record<number, ItemNameDraft>>({});
    const [savingIds, setSavingIds] = useState<number[]>([]);
    const [conflictIds, setConflictIds] = useState<number[]>([]);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [historyId, setHistoryId] = useState<number | null>(null);
    const [revertId, setRevertId] = useState<number | null>(null);
    const [reverting, setReverting] = useState(false);
    const draftCount = Object.keys(drafts).length;
    const [reviewing, setReviewing] = useState(false);
    const [previews, setPreviews] = useState<ImportItemNamePreview[] | undefined>(undefined);
    const [previewLoading, setPreviewLoading] = useState(false);
    const [previewError, setPreviewError] = useState<string | null>(null);
    const [confirming, setConfirming] = useState(false);
    const [conflictReport, setConflictReport] = useState<ImportItemNamePropagation[]>([]);

    /** Display hint: rows sharing Description + HSN with a global draft "will follow" that draft. */
    const followers = useMemo(() => {
        const leaderByKey = new Map<string, number>();
        for (const idText of Object.keys(drafts)) {
            const id = Number(idText);
            const row = nameById.get(id);
            const key = row ? combinationKey(row) : null;
            if (key && drafts[id].scope === "global" && !leaderByKey.has(key)) leaderByKey.set(key, id);
        }
        const map = new Map<number, number>();
        for (const row of nameById.values()) {
            const key = combinationKey(row);
            const leader = key ? leaderByKey.get(key) : undefined;
            if (leader !== undefined && leader !== row.import_item_id) map.set(row.import_item_id, leader);
        }
        return map;
    }, [drafts, nameById]);

    const refreshAll = async () => {
        if (licenseId === undefined || licenseId === "") return;
        await Promise.all([
            queryClient.invalidateQueries({ queryKey: importItemNamesKey(licenseId) }),
            queryClient.invalidateQueries({ queryKey: licenseOverviewKeys.items(licenseId) }),
        ]);
        // A global (Description + HSN) decision changes Product Mapping's pending / approved lists too.
        invalidateMappingQueries(queryClient);
    };

    /** Show the rows the server returned immediately (no flash of the old values before the refetch). */
    const applyRows = (rows: ImportItemNameRow[] | undefined) => {
        if (licenseId === undefined || licenseId === "" || !rows) return;
        queryClient.setQueryData(importItemNamesKey(licenseId), (prev: { can_edit: boolean; rows: ImportItemNameRow[] } | undefined) =>
            prev ? { ...prev, rows } : prev);
    };

    const setDraft = (importItemId: number, itemId: number | null, label: string | null) => {
        const row = nameById.get(importItemId);
        const current = row ? rowItemIds(row) : [];
        const unchanged = itemId === null ? current.length === 0 : current.length === 1 && current[0] === itemId;
        setDrafts((prev) => {
            const next = { ...prev };
            if (unchanged) {
                delete next[importItemId];
            } else {
                const scope: ImportItemNameScope = prev[importItemId]?.scope ?? (canBeGlobal(row) ? "global" : "record");
                next[importItemId] = { itemId, label, scope };
                // Two global changes on one combination are a server 400: the other rows now follow this one.
                const key = row ? combinationKey(row) : null;
                if (scope === "global" && key) {
                    for (const idText of Object.keys(next)) {
                        const other = Number(idText);
                        const otherRow = nameById.get(other);
                        if (other !== importItemId && next[other].scope === "global" && otherRow && combinationKey(otherRow) === key) delete next[other];
                    }
                }
            }
            return next;
        });
        setConflictIds((prev) => prev.filter((id) => id !== importItemId));
    };

    const setScope = (importItemId: number, scope: ImportItemNameScope) => {
        setDrafts((prev) => {
            const cur = prev[importItemId];
            if (!cur || cur.scope === scope) return prev;
            const next = { ...prev, [importItemId]: { ...cur, scope } };
            const row = nameById.get(importItemId);
            const key = row ? combinationKey(row) : null;
            if (scope === "global" && key) {
                for (const idText of Object.keys(next)) {
                    const other = Number(idText);
                    const otherRow = nameById.get(other);
                    if (other !== importItemId && next[other].scope === "global" && otherRow && combinationKey(otherRow) === key) delete next[other];
                }
            }
            return next;
        });
    };

    const discardAll = () => {
        setDrafts({});
        setConflictIds([]);
        setSaveError(null);
    };

    const globalIds = () => Object.keys(drafts).map(Number).filter((id) => drafts[id].scope === "global");

    const loadPreview = async () => {
        if (licenseId === undefined || licenseId === "") return;
        setPreviewLoading(true);
        setPreviewError(null);
        try {
            setPreviews(await previewImportItemNames(licenseId, globalIds().map((id) => ({ import_item_id: id, item_id: drafts[id].itemId }))));
        } catch (err) {
            setPreviewError(extractApiError(err, "Could not check the affected records."));
        } finally {
            setPreviewLoading(false);
        }
    };

    /** "Save all": global drafts are confirmed against the server preview first; record-only drafts save directly. */
    const saveAll = () => {
        if (draftCount === 0) return;
        if (globalIds().length === 0) {
            void performSave();
            return;
        }
        setPreviews(undefined);
        setReviewing(true);
        void loadPreview();
    };

    const performSave = async () => {
        if (licenseId === undefined || licenseId === "" || draftCount === 0) return;
        const ids = Object.keys(drafts).map(Number);
        const changes: ImportItemNameChange[] = ids.map((id) => {
            const row = nameById.get(id) as ImportItemNameRow;
            const change: ImportItemNameChange = {
                import_item_id: id,
                item_id: drafts[id].itemId,
                expected_item_ids: rowItemIds(row),
                scope: drafts[id].scope,
            };
            if (drafts[id].scope === "global" && row.approval) change.expected_approval_version = row.approval.version;
            return change;
        });
        setSavingIds(ids);
        setSaveError(null);
        setConflictIds([]);
        setConfirming(true);
        try {
            const result = await saveImportItemNames(licenseId, changes);
            const propagation = result.propagation ?? [];
            toast.success(propagation.length > 0 ? propagationSummary(propagation) : `Saved ${result.saved} Item Name change${result.saved === 1 ? "" : "s"}`);
            setConflictReport(propagation.filter((p) => p.conflicts > 0));
            applyRows(result.rows);
            setDrafts({});
            setReviewing(false);
            await refreshAll();
        } catch (err) {
            setReviewing(false);
            const resp = (err as { response?: { status?: number; data?: { detail?: string; import_item_ids?: number[] } } }).response;
            if (resp?.status === 409) {
                setConflictIds(resp.data?.import_item_ids ?? []);
                setSaveError(resp.data?.detail ?? "Some rows were changed by someone else.");
            } else if (resp?.status === 403) {
                setSaveError("You do not have permission to change Item Names.");
            } else {
                setSaveError(extractApiError(err, "Failed to save Item Names."));
            }
        } finally {
            setSavingIds([]);
            setConfirming(false);
        }
    };

    const reloadConflicts = async () => {
        const stale = conflictIds;
        setDrafts((prev) => {
            const next = { ...prev };
            for (const id of stale) delete next[id];
            return next;
        });
        setConflictIds([]);
        setSaveError(null);
        await refreshAll();
    };

    const confirmRevert = async () => {
        if (licenseId === undefined || licenseId === "" || revertId === null) return;
        setReverting(true);
        try {
            const result = await revertImportItemNames(licenseId, [revertId]);
            applyRows(result.rows);
            toast.success(result.reapplied
                ? "Override removed — description mapping applied"
                : "Override removed — no active description mapping, links kept");
            setDrafts((prev) => {
                const next = { ...prev };
                delete next[revertId];
                return next;
            });
            setRevertId(null);
            await refreshAll();
        } catch (err) {
            setSaveError(extractApiError(err, "Failed to revert Item Name."));
            setRevertId(null);
        } finally {
            setReverting(false);
        }
    };

    const handleSort = (key: SortKey) => {
        setSort((prev) => ({
            key,
            direction: prev.key === key && prev.direction === "asc" ? "desc" : "asc",
        }));
    };

    const rows = useMemo(
        () => sortRows(
            data?.rows ?? [],
            sort,
            (row, key) => key === "item_name"
                ? displayName(nameById.get(row.id)).toLowerCase()
                : row[key] as string | number | null,
        ),
        [data, sort, nameById]
    );
    const footerTotals = data?.footer_totals;
    const effectiveBalance = (row: LicenseOverviewItemRow) => row.effective_balance_cif ?? row.balance_cif;

    if (!isActive) return null;

    if (isLoading) {
        return (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" /> Loading items…
            </div>
        );
    }

    if (isError) {
        return (
            <Alert variant="destructive">
                <AlertTriangle className="size-4" />
                <AlertDescription>{extractApiError(error, "Failed to load items.")}</AlertDescription>
            </Alert>
        );
    }

    const revertRow = revertId !== null ? nameById.get(revertId) : undefined;
    const historyRow = historyId !== null ? nameById.get(historyId) : undefined;

    return (
        <div className="space-y-2">
        {saveError && (
            <Alert variant="destructive" role="alert">
                <AlertTriangle className="size-4" />
                <AlertDescription className="flex flex-wrap items-center gap-2">
                    <span>{saveError}</span>
                    {conflictIds.length > 0 && (
                        <Button type="button" size="sm" variant="outline" onClick={() => { void reloadConflicts(); }}>
                            Reload these rows
                        </Button>
                    )}
                </AlertDescription>
            </Alert>
        )}
        {conflictReport.length > 0 && (
            <Alert role="status" aria-label="Item Name conflicts">
                <AlertTriangle className="size-4" />
                <AlertDescription className="space-y-1">
                    <div className="flex items-center justify-between gap-2">
                        <strong>Some licences were not changed because of conflicts</strong>
                        <Button type="button" size="sm" variant="ghost" onClick={() => setConflictReport([])}>Dismiss</Button>
                    </div>
                    <ul className="list-disc pl-5 text-xs">
                        {conflictReport.map((p) => (
                            <li key={p.import_item_id}>
                                <span title={p.combination.description}>{p.combination.description}</span> (HSN {p.combination.hsn_code || "none"}):{" "}
                                {p.conflict_licences.length > 0 ? p.conflict_licences.map((l) => l.license_number).join(", ") : `${p.conflicts} conflict${p.conflicts === 1 ? "" : "s"}`}
                            </li>
                        ))}
                    </ul>
                </AlertDescription>
            </Alert>
        )}
        <div className="max-h-[calc(100vh-15rem)] overflow-auto rounded-lg border border-border/70 bg-card">
            <table className="w-full min-w-[1400px] text-[13px]">
                <thead className="sticky top-0 z-[1] bg-muted/95 text-[10.5px] uppercase tracking-wide text-muted-foreground backdrop-blur">
                    <tr>
                        <SortableHeader label="Product Description" sortKey="description" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                        <SortableHeader label="Item Name" sortKey="item_name" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                        <SortableHeader label="HSN Code" sortKey="hs_code" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                        <SortableHeader label="Unit" sortKey="unit" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                        <SortableHeader label="Total Qty" sortKey="total_qty" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Total CIF" sortKey="total_cif" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Debited Qty" sortKey="debited_qty" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Debited CIF" sortKey="debited_cif" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Allotted Qty" sortKey="allotted_qty" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Allotted CIF" sortKey="allotted_cif" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Balance Qty" sortKey="balance_qty" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Balance CIF" sortKey="effective_balance_cif" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                    </tr>
                </thead>
                <tbody>
                    {rows.length === 0 && (
                        <tr>
                            <td colSpan={12} className="px-3 py-6 text-center text-muted-foreground">
                                No import items on this licence.
                            </td>
                        </tr>
                    )}
                    {rows.map((row) => (
                        <tr key={row.id} className="border-t border-border/60 hover:bg-muted/30">
                            <td className="max-w-[280px] truncate px-3 py-1.5" title={row.description ?? ""}>{row.description ?? "—"}</td>
                            <td className="px-3 py-1.5" data-column-id="item-name">
                                <ImportItemNameCell
                                    row={nameById.get(row.id)}
                                    state={nameState}
                                    canEdit={canEdit}
                                    draft={drafts[row.id]}
                                    saving={savingIds.includes(row.id)}
                                    conflict={conflictIds.includes(row.id)}
                                    followsLabel={followers.has(row.id) ? (nameById.get(followers.get(row.id) as number)?.description ?? "") : null}
                                    canGlobal={canBeGlobal(nameById.get(row.id))}
                                    onScope={(scope) => setScope(row.id, scope)}
                                    onDraft={(itemId, label) => setDraft(row.id, itemId, label)}
                                    onRetry={() => { void names.refetch(); }}
                                    onHistory={() => setHistoryId(row.id)}
                                    onRevert={() => setRevertId(row.id)}
                                />
                            </td>
                            <td className="px-3 py-1.5">{row.hs_code ?? "—"}</td>
                            <td className="px-3 py-1.5">{row.unit ?? "—"}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.total_qty)}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.total_cif)}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.debited_qty)}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.debited_cif)}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.allotted_qty)}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.allotted_cif)}</td>
                            <td className="px-3 py-1.5 text-right font-medium tabular-nums">{fmtNum(row.balance_qty)}</td>
                            <td className="px-3 py-1.5 text-right font-medium tabular-nums" title={row.balance_cif_source === "LICENSE" ? "Licence-level CIF" : "Individual item CIF"}>{fmtNum(effectiveBalance(row))}</td>
                        </tr>
                    ))}
                </tbody>
                {footerTotals && (
                    <tfoot className="border-t-2 border-border bg-muted/40 text-[13px] font-semibold">
                        <tr>
                            <td colSpan={5} className="px-3 py-2">Total</td>
                            <td data-column-id="total-cif" className="px-3 py-2 text-right tabular-nums">{fmtNum(footerTotals.total_cif ?? 0)}</td>
                            <td />
                            <td data-column-id="debited-cif" className="px-3 py-2 text-right tabular-nums">{fmtNum(footerTotals.debited_cif ?? 0)}</td>
                            <td />
                            <td data-column-id="allotted-cif" className="px-3 py-2 text-right tabular-nums">{fmtNum(footerTotals.allotted_cif ?? 0)}</td>
                            <td />
                            <td data-column-id="effective-balance-cif" className="px-3 py-2 text-right tabular-nums">{fmtNum(footerTotals.actual_effective_balance_cif ?? footerTotals.balance_cif ?? 0)}</td>
                        </tr>
                    </tfoot>
                )}
            </table>
            {draftCount > 0 && (
                <div className="sticky bottom-0 left-0 z-[2] flex items-center gap-3 border-t border-border bg-card/95 px-3 py-2 text-sm backdrop-blur" role="region" aria-label="Unsaved Item Name changes">
                    <span className="font-medium">{draftCount} unsaved change{draftCount === 1 ? "" : "s"}</span>
                    <Button type="button" size="sm" onClick={saveAll} disabled={savingIds.length > 0}>
                        {savingIds.length > 0 && <Loader2 className="size-4 animate-spin" />} Save all
                    </Button>
                    <Button type="button" size="sm" variant="outline" onClick={discardAll} disabled={savingIds.length > 0}>Discard</Button>
                </div>
            )}
        </div>
        {licenseId !== undefined && historyId !== null && (
            <ImportItemNameHistoryDialog
                licenseId={licenseId}
                importItemId={historyId}
                description={historyRow?.description ?? null}
                open
                onOpenChange={(o) => { if (!o) setHistoryId(null); }}
            />
        )}
        <ImportItemNameSaveDialog
            open={reviewing}
            drafts={globalIds().map((id) => ({ importItemId: id, itemName: drafts[id].itemId === null ? null : (drafts[id].label ?? `#${drafts[id].itemId}`) }))}
            recordOnlyCount={draftCount - globalIds().length}
            previews={previews}
            loading={previewLoading}
            error={previewError}
            saving={confirming}
            onRetry={() => { void loadPreview(); }}
            onCancel={() => setReviewing(false)}
            onConfirm={() => { void performSave(); }}
        />
        <ImportItemNameRevertDialog
            open={revertId !== null}
            description={revertRow?.description ?? null}
            mappingNames={revertRow?.description_mapping?.items.map((i) => i.name).join(", ") || "Not Mapped"}
            busy={reverting}
            onCancel={() => setRevertId(null)}
            onConfirm={() => { void confirmRevert(); }}
        />
        </div>
    );
}
