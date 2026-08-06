import { useContext, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, Loader2 } from "lucide-react";

import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { useLicenseBalanceLedger, licenseBalanceKeys } from "@/pages/license-balance/useLicenseBalanceLedger";
import { useLicenseOverviewSummary, licenseOverviewKeys } from "./useLicenseOverviewSummary";
import { extractApiError, fmtNum } from "./licenseOverviewHelpers";
import LicenseDetailsHeader from "./LicenseDetailsHeader";
import SionNormCard from "./SionNormCard";
import LicenseMetricsGrid from "./LicenseMetricsGrid";
import CustomsLedgerSection from "./CustomsLedgerSection";
import CustomsLedgerTable from "./CustomsLedgerTable";
import FinancialLedgerTable from "./FinancialLedgerTable";
import FinancialSummarySection from "./FinancialSummarySection";
import FinalReconciliationSection from "./FinalReconciliationSection";
import NoTradeActivityBanner from "./NoTradeActivityBanner";

interface OverviewTabProps {
    licenseId: string | number | undefined;
    isActive: boolean;
    showHiddenBoe: boolean;
    onShowHiddenBoeChange: (value: boolean) => void;
}

/**
 * Overview tab — license header fields + 7-card summary grid (from the new
 * lightweight `useLicenseOverviewSummary`), followed by the relocated
 * allocation-editing/Ledger/Reconciliation sections that used to make up the
 * whole of `LicenseBalanceWorkspace.tsx`. Those sections are still backed by
 * the EXISTING `useLicenseBalanceLedger` hook/endpoint (untouched) — only
 * fetched once this tab is active, by passing `undefined` as the license id
 * while inactive (same technique the hook already uses internally to gate
 * `enabled`, so the hook itself needed no changes).
 */
export default function OverviewTab({ licenseId, isActive, showHiddenBoe, onShowHiddenBoeChange }: OverviewTabProps) {
    const { hasRole } = useContext(AuthContext);
    const queryClient = useQueryClient();
    const [recalculating, setRecalculating] = useState(false);
    const [updatingPurchaseStatus, setUpdatingPurchaseStatus] = useState(false);
    const [editingPurchaseStatus, setEditingPurchaseStatus] = useState(false);

    const summaryQuery = useLicenseOverviewSummary(licenseId, isActive);
    const ledgerQuery = useLicenseBalanceLedger(isActive ? licenseId : undefined, showHiddenBoe);

    const canRecalculate = hasRole("LICENSE_MANAGER");
    // Purchase Status is a plain `LicenseDetailsModel` field (like any other
    // license field), so it's editable by the same role that can edit the
    // license itself, via the existing generic `PATCH licenses/{id}/`
    // endpoint — no new write endpoint needed.
    const canEditPurchaseStatus = hasRole("LICENSE_MANAGER");

    const handlePurchaseStatusChange = async (value: unknown) => {
        if (!licenseId) return;
        setUpdatingPurchaseStatus(true);
        try {
            await api.patch(`licenses/${licenseId}/`, { purchase_status: value ?? null });
            toast.success("Purchase status updated");
            queryClient.invalidateQueries({ queryKey: licenseOverviewKeys.summary(licenseId) });
        } catch (err) {
            toast.error(extractApiError(err, "Failed to update purchase status"));
        } finally {
            setUpdatingPurchaseStatus(false);
            setEditingPurchaseStatus(false);
        }
    };

    const handleRecalculate = async () => {
        if (!licenseId) return;
        setRecalculating(true);
        try {
            const { data: result } = await api.post(`licenses/${licenseId}/recalculate/`, {});
            toast.success(`Balance recalculated: $${fmtNum(result?.balance_cif)}`);
            queryClient.invalidateQueries({ queryKey: licenseBalanceKeys.ledger(licenseId) });
            queryClient.invalidateQueries({ queryKey: licenseOverviewKeys.summary(licenseId) });
        } catch (err) {
            toast.error(extractApiError(err, "Failed to recalculate balance"));
        } finally {
            setRecalculating(false);
        }
    };

    if (!isActive) return null;

    const { data: summary, isLoading: summaryLoading, isError: summaryError, error: summaryErrorObj } = summaryQuery;

    // UI-only visibility rule for THIS page: only a real Purchase or Sale
    // counts as "trade" for deciding whether to show the Financial Ledger/
    // Summary/Reconciliation cards — BOE debits, allotments, and the
    // opening/closing bookend rows do NOT count, even though they're still
    // real ledger rows and still drive every calculation untouched here.
    // Reuses the existing `has_trading_activity` flag (`= has_purchase or
    // has_sale`, see `license_balance_ledger_builder.build_financial_ledger`)
    // already returned by this page's ledger query — no new API, no backend
    // change, no re-derivation from `rows`/`row_kind`.
    const showFinancialSections = ledgerQuery.data?.financial_ledger.summary.has_trading_activity ?? false;

    return (
        <div>
            {/* `!summary` guard — same reasoning as the ledger spinner
                below: never swap already-rendered summary cards out for a
                spinner during a background refetch. */}
            {summaryLoading && !summary && (
                <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
                    <Loader2 className="size-4 animate-spin" /> Loading overview…
                </div>
            )}

            {summaryError && (
                <Alert variant="destructive">
                    <AlertTriangle className="size-4" />
                    <AlertDescription>{extractApiError(summaryErrorObj, "Failed to load license overview.")}</AlertDescription>
                </Alert>
            )}

            {summary && (
                <>
                    <LicenseDetailsHeader
                        summary={summary}
                        canRecalculate={canRecalculate}
                        recalculating={recalculating}
                        onRecalculate={handleRecalculate}
                        canEditPurchaseStatus={canEditPurchaseStatus}
                        editingPurchaseStatus={editingPurchaseStatus}
                        setEditingPurchaseStatus={setEditingPurchaseStatus}
                        updatingPurchaseStatus={updatingPurchaseStatus}
                        onPurchaseStatusChange={handlePurchaseStatusChange}
                    />

                    <div className="mt-8">
                        <SionNormCard licenseId={licenseId} isActive={isActive} />
                    </div>

                    <div className="mt-8">
                        <LicenseMetricsGrid summary={summary.summary} />
                    </div>
                </>
            )}

            <div className="mt-10 space-y-5">
                {/* `!ledgerQuery.data` guard: once the ledger has loaded once,
                    a later invalidateQueries()-triggered refetch (e.g. after a
                    hide/restore BOE action) must never swap this spinner back
                    in over already-rendered content — doing so would unmount
                    the whole card section and reflow the page height, which is
                    what caused the reported "confirmation jumps to top" bug
                    (the browser clamps scroll to the new, shorter height, then
                    jumps back once data reloads). Stale content stays visible
                    while `isFetching` refetches it in the background. */}
                {ledgerQuery.isLoading && !ledgerQuery.data && (
                    <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
                        <Loader2 className="size-4 animate-spin" /> Loading warnings &amp; ledgers…
                    </div>
                )}

                {ledgerQuery.isError && (
                    <Alert variant="destructive">
                        <AlertTriangle className="size-4" />
                        <AlertDescription>{extractApiError(ledgerQuery.error, "Failed to load licence balance data.")}</AlertDescription>
                    </Alert>
                )}

                {ledgerQuery.data && (
                    <>
                        {/* Always shown: a never-traded licence still gets a
                            meaningful Opening-Balance-only statement (see
                            `has_purchase` on the backend's opening-row gate). */}
                        {ledgerQuery.data.financial_ledger.summary.missing_purchase_warning.show_warning && (
                            <Alert variant="warning">
                                <AlertTriangle className="size-4" />
                                <AlertDescription>
                                    {ledgerQuery.data.financial_ledger.summary.missing_purchase_warning.message}
                                </AlertDescription>
                            </Alert>
                        )}

                        {showFinancialSections ? (
                            <Card>
                                <CardHeader>
                                    <CardTitle>Financial Ledger</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <FinancialLedgerTable rows={ledgerQuery.data.financial_ledger.rows} />
                                </CardContent>
                            </Card>
                        ) : (
                            <NoTradeActivityBanner />
                        )}

                        <Card>
                            <CardHeader>
                                <CardTitle>Customs Ledger — Running Balance</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <CustomsLedgerTable
                                    rows={ledgerQuery.data.customs_ledger.rows}
                                    summary={ledgerQuery.data.customs_ledger.summary}
                                    licenseId={licenseId}
                                    showHidden={showHiddenBoe}
                                    onShowHiddenChange={onShowHiddenBoeChange}
                                />
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader>
                                <CardTitle>Customs Ledger — Item Detail</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <CustomsLedgerSection licenseId={licenseId ?? ""} />
                            </CardContent>
                        </Card>

                        {showFinancialSections && (
                            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Financial Summary</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <FinancialSummarySection summary={ledgerQuery.data.financial_ledger.summary} />
                                    </CardContent>
                                </Card>

                                <Card>
                                    <CardHeader>
                                        <CardTitle>Final Reconciliation</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <FinalReconciliationSection reconciliation={ledgerQuery.data.reconciliation} />
                                    </CardContent>
                                </Card>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
