import { useContext, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";

import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { useLicenseBalanceLedger, licenseBalanceKeys } from "@/pages/license-balance/useLicenseBalanceLedger";
import { useLicenseOverviewSummary, licenseOverviewKeys } from "./useLicenseOverviewSummary";
import { extractApiError, fmtDate, fmtNum, licenseOverviewStatusVariant } from "./licenseOverviewHelpers";
import SummaryCard from "./SummaryCard";
import CustomsLedgerSection from "./CustomsLedgerSection";
import CustomsLedgerTable from "./CustomsLedgerTable";
import FinancialLedgerTable from "./FinancialLedgerTable";
import FinancialSummarySection from "./FinancialSummarySection";
import FinalReconciliationSection from "./FinalReconciliationSection";

interface OverviewTabProps {
    licenseId: string | number | undefined;
    isActive: boolean;
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
export default function OverviewTab({ licenseId, isActive }: OverviewTabProps) {
    const { hasRole } = useContext(AuthContext);
    const queryClient = useQueryClient();
    const [recalculating, setRecalculating] = useState(false);

    const summaryQuery = useLicenseOverviewSummary(licenseId, isActive);
    const ledgerQuery = useLicenseBalanceLedger(isActive ? licenseId : undefined);

    const canRecalculate = hasRole("LICENSE_MANAGER");

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

    return (
        <div className="space-y-5">
            {summaryLoading && (
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
                    <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-border/70 bg-card px-4 py-3">
                        <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3 lg:grid-cols-6">
                            <HeaderField label="License Number" value={summary.license_number ?? "—"} />
                            <HeaderField label="Authorisation Number" value={summary.authorisation_number ?? "—"} />
                            <HeaderField label="File Number" value={summary.file_number ?? "—"} />
                            <HeaderField label="License Date" value={fmtDate(summary.license_date)} />
                            <HeaderField label="Expiry Date" value={fmtDate(summary.license_expiry_date)} />
                            <HeaderField label="Importer" value={summary.importer ?? "—"} />
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                            <Badge variant={licenseOverviewStatusVariant(summary.status)}>{summary.status}</Badge>
                            {canRecalculate && (
                                <Button size="sm" variant="outline" onClick={handleRecalculate} disabled={recalculating}>
                                    {recalculating ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                                    Recalculate
                                </Button>
                            )}
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                        <SummaryCard label="Total BOEs" value={fmtNum(summary.summary.total_boes, 0)} />
                        <SummaryCard label="Total Allotments" value={fmtNum(summary.summary.total_allotments, 0)} />
                        <SummaryCard label="Planned CIF" value={fmtNum(summary.summary.total_planned_cif)} />
                        <SummaryCard label="Total CIF" value={fmtNum(summary.summary.total_cif)} size="lg" />
                        <SummaryCard label="Debited CIF" value={fmtNum(summary.summary.total_debited_cif)} />
                        <SummaryCard label="Allotted CIF" value={fmtNum(summary.summary.total_allotted_cif)} />
                        <SummaryCard label="Balance CIF" value={fmtNum(summary.summary.total_balance_cif)} variant="success" size="lg" />
                    </div>
                </>
            )}

            {ledgerQuery.isLoading && (
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
                    {/* Financial Ledger only appears when this licence has been
                        traded (Purchase and/or Sale) — a licence with neither has
                        nothing this section adds over the Customs Ledger below, so
                        it's hidden entirely rather than shown empty or opening-
                        balance-only. See `has_trading_activity` on the backend. */}
                    {ledgerQuery.data.financial_ledger.summary.has_trading_activity && (
                        <>
                            {ledgerQuery.data.financial_ledger.summary.missing_purchase_warning.show_warning && (
                                <Alert variant="warning">
                                    <AlertTriangle className="size-4" />
                                    <AlertDescription>
                                        {ledgerQuery.data.financial_ledger.summary.missing_purchase_warning.message}
                                    </AlertDescription>
                                </Alert>
                            )}
                            <Card>
                                <CardHeader>
                                    <CardTitle>Financial Ledger</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <FinancialLedgerTable rows={ledgerQuery.data.financial_ledger.rows} />
                                </CardContent>
                            </Card>
                        </>
                    )}

                    <Card>
                        <CardHeader>
                            <CardTitle>Customs Ledger — Running Balance</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <CustomsLedgerTable rows={ledgerQuery.data.customs_ledger.rows} summary={ledgerQuery.data.customs_ledger.summary} />
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
                </>
            )}
        </div>
    );
}

function HeaderField({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <div className="text-[10.5px] font-semibold uppercase tracking-widest text-muted-foreground/70">{label}</div>
            <div className="mt-0.5 truncate text-sm font-medium text-foreground">{value}</div>
        </div>
    );
}
