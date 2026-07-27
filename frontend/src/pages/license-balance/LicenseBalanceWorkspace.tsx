import { useContext, useState } from "react";
import { useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, FileSpreadsheet, FileText, Loader2, RefreshCw, X } from "lucide-react";

import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { openPdfPreview } from "@/utils/pdfPreview";
import { openAuthedFile } from "@/utils/documentDownload";
import { useConfirmDialog } from "@/hooks/useConfirmDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import PageHeader from "@/components/PageHeader";

import { useLicenseBalanceLedger, licenseBalanceKeys } from "./useLicenseBalanceLedger";
import { extractApiError, fmtNum, integrityScoreBadgeVariant } from "./licenseBalanceHelpers";
import FinancialLedgerTable from "./FinancialLedgerTable";
import InvoiceBoeSection from "./InvoiceBoeSection";
import BoeAllotmentSection from "./BoeAllotmentSection";
import BalanceTimeline from "./BalanceTimeline";
import CustomsLedgerSection from "./CustomsLedgerSection";
import FinancialSummarySection from "./FinancialSummarySection";
import FinalReconciliationSection from "./FinalReconciliationSection";

/**
 * Licence Balance & Financial Reconciliation Workspace — full-page
 * replacement for `LicenseBalanceModal.tsx` (the modal stays in place for
 * now; this is additive). Every section reads from the single
 * `GET /licenses/<id>/balance-ledger/` dataset via `useLicenseBalanceLedger`.
 */
export default function LicenseBalanceWorkspace() {
    const { id } = useParams<{ id: string }>();
    const { hasRole } = useContext(AuthContext);
    const queryClient = useQueryClient();
    const { confirmDangerousAction, confirmDialog } = useConfirmDialog();

    const { data, isLoading, isError, error } = useLicenseBalanceLedger(id);
    const [dismissedWarnings, setDismissedWarnings] = useState<Set<number>>(new Set());
    const [downloadingPdf, setDownloadingPdf] = useState(false);
    const [downloadingExcel, setDownloadingExcel] = useState(false);
    const [recalculating, setRecalculating] = useState(false);

    const canRecalculate = hasRole("LICENSE_MANAGER");

    const handleDownloadPdf = async () => {
        if (!id) return;
        setDownloadingPdf(true);
        try {
            const response = await api.get(`licenses/${id}/balance-pdf/`, { responseType: "blob" });
            openPdfPreview(response.data, `${data?.license.license_number || id}-balance.pdf`);
        } catch (err) {
            toast.error(extractApiError(err, "Failed to generate PDF file"));
        } finally {
            setDownloadingPdf(false);
        }
    };

    const handleDownloadExcel = async () => {
        if (!id) return;
        setDownloadingExcel(true);
        try {
            await openAuthedFile(`licenses/${id}/balance-excel/`, `${data?.license.license_number || id}-balance.xlsx`);
            toast.success("Excel file downloaded successfully!");
        } catch {
            toast.error("Failed to generate Excel file");
        } finally {
            setDownloadingExcel(false);
        }
    };

    const handleRecalculate = async () => {
        if (!id) return;
        const confirmed = await confirmDangerousAction(
            "Recalculate Licence Balance",
            "This recalculates every import item's balance and refreshes this licence's denormalized balance. Continue?"
        );
        if (!confirmed) return;

        setRecalculating(true);
        try {
            const { data: result } = await api.post(`licenses/${id}/recalculate/`, {});
            toast.success(`Balance recalculated: $${fmtNum(result?.balance_cif)}`);
            queryClient.invalidateQueries({ queryKey: licenseBalanceKeys.ledger(id) });
        } catch (err) {
            toast.error(extractApiError(err, "Failed to recalculate balance"));
        } finally {
            setRecalculating(false);
        }
    };

    if (isLoading) {
        return (
            <div className="flex flex-col items-center gap-2 py-16 text-center">
                <Loader2 className="size-8 animate-spin text-primary" />
                <p className="text-muted-foreground">Loading balance workspace…</p>
            </div>
        );
    }

    if (isError || !data) {
        return (
            <Alert variant="destructive">
                <AlertTriangle className="size-4" />
                <AlertDescription>{extractApiError(error, "Failed to load licence balance data.")}</AlertDescription>
            </Alert>
        );
    }

    const { license, financial_ledger, invoice_boe, boe_allotment, reconciliation, warnings } = data;
    const visibleWarnings = warnings.filter((_, idx) => !dismissedWarnings.has(idx));

    return (
        <div>
            <PageHeader
                pretitle="Licence"
                title={`Balance Workspace — ${license.license_number ?? id}`}
                description={license.exporter ?? undefined}
                actions={
                    <>
                        <Button size="sm" variant="outline" onClick={handleDownloadPdf} disabled={downloadingPdf}>
                            {downloadingPdf ? <Loader2 className="size-4 animate-spin" /> : <FileText className="size-4" />}
                            Download PDF
                        </Button>
                        <Button size="sm" variant="outline" onClick={handleDownloadExcel} disabled={downloadingExcel}>
                            {downloadingExcel ? <Loader2 className="size-4 animate-spin" /> : <FileSpreadsheet className="size-4" />}
                            Download Excel
                        </Button>
                        {canRecalculate && (
                            <Button size="sm" onClick={handleRecalculate} disabled={recalculating}>
                                {recalculating ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                                Recalculate
                            </Button>
                        )}
                    </>
                }
            />

            {/* Header stats */}
            <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
                {[
                    ["License Date", license.license_date ?? "—"],
                    ["License Expiry", license.license_expiry_date ?? "—"],
                    ["Original CIF", fmtNum(license.original_cif)],
                    ["Original Qty", fmtNum(license.original_qty)],
                    ["Current Balance CIF", fmtNum(license.current_balance_cif)],
                    ["Current Balance Qty", fmtNum(license.current_balance_qty)],
                    ["Difference", fmtNum(license.difference)],
                ].map(([label, value]) => (
                    <div key={label} className="rounded-lg border border-border/70 bg-card px-3 py-2.5">
                        <div className="text-[10.5px] font-semibold uppercase tracking-widest text-muted-foreground">
                            {label}
                        </div>
                        <div className="mt-0.5 text-sm font-semibold tabular-nums text-foreground">{value}</div>
                    </div>
                ))}
                <div className="rounded-lg border border-border/70 bg-card px-3 py-2.5">
                    <div className="text-[10.5px] font-semibold uppercase tracking-widest text-muted-foreground">
                        Financial Integrity
                    </div>
                    <div className="mt-0.5">
                        <Badge variant={integrityScoreBadgeVariant(license.financial_integrity_score)}>
                            {fmtNum(license.financial_integrity_score, 1)}%
                        </Badge>
                    </div>
                </div>
            </div>

            {/* Warnings */}
            {visibleWarnings.length > 0 && (
                <div className="mb-5 space-y-2">
                    {warnings.map((warning, idx) =>
                        dismissedWarnings.has(idx) ? null : (
                            <Alert key={idx} variant="destructive" className="pr-10">
                                <AlertTriangle className="size-4" />
                                <AlertDescription>{warning}</AlertDescription>
                                <button
                                    type="button"
                                    onClick={() => setDismissedWarnings((prev) => new Set(prev).add(idx))}
                                    aria-label="Dismiss warning"
                                    className="absolute right-3 top-3 cursor-pointer text-destructive/70 hover:text-destructive"
                                >
                                    <X className="size-4" />
                                </button>
                            </Alert>
                        )
                    )}
                </div>
            )}

            <div className="space-y-5">
                <Card>
                    <CardHeader>
                        <CardTitle>Financial Ledger</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <FinancialLedgerTable rows={financial_ledger.rows} />
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-4">
                        <InvoiceBoeSection licenseId={id ?? ""} invoices={invoice_boe} boeAllotment={boe_allotment} />
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-4">
                        <BoeAllotmentSection licenseId={id ?? ""} boeAllotment={boe_allotment} />
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle>Timeline</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <BalanceTimeline rows={financial_ledger.rows} />
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle>Customs Ledger</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <CustomsLedgerSection licenseId={id ?? ""} />
                    </CardContent>
                </Card>

                <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                    <Card>
                        <CardHeader>
                            <CardTitle>Financial Summary</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <FinancialSummarySection summary={financial_ledger.summary} />
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Final Reconciliation</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <FinalReconciliationSection reconciliation={reconciliation} />
                        </CardContent>
                    </Card>
                </div>
            </div>

            {confirmDialog}
        </div>
    );
}
