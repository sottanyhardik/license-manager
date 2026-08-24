import { useCallback, useContext, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileSpreadsheet, FileText, Loader2, Target } from "lucide-react";

import api from "@/api/axios";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import PermissionGate from "@/components/PermissionGate";
import { AuthContext } from "@/context/AuthContext";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { openPdfPreview } from "@/utils/pdfPreview";
import { openAuthedFile, openDocument } from "@/utils/documentDownload";

import { extractApiError } from "./licenseOverviewHelpers";
import { licenseOverviewKeys, useLicenseOverviewSummary } from "./useLicenseOverviewSummary";
import { licenseBalanceKeys } from "@/pages/license-balance/useLicenseBalanceLedger";
import OverviewTab from "./OverviewTab";
import BoesTab from "./BoesTab";
import AllotmentsTab from "./AllotmentsTab";
import PlanningEditor from "@/components/planning/PlanningEditor";
import ItemsTab from "./ItemsTab";
import InvoiceLedgerTab from "./InvoiceLedgerTab";
import ReplanStatus from "./ReplanStatus";
import { autoPlanLicense } from "@/services/api/planningRuleApi";

type TabId = "overview" | "boes" | "allotments" | "planning" | "items" | "invoice-ledger";
type LicenseDocument = { id: number; type: string; file: string };

const TABS: { id: TabId; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "boes", label: "BOEs" },
    { id: "allotments", label: "Allotments" },
    { id: "planning", label: "Planning" },
    { id: "items", label: "Items" },
    { id: "invoice-ledger", label: "Invoice Ledger" },
];
const TAB_IDS = new Set<string>(TABS.map((t) => t.id));

/**
 * License Overview dashboard — page shell. Fetches nothing itself except
 * the lightweight header summary (used for the PDF/Excel filename); each
 * tab fetches its own data lazily via its own hook, gated on `isActive` so
 * switching tabs is the only thing that triggers a new fetch (some licenses
 * have 1000+ BOEs — eagerly fetching all 6 tabs on load would defeat the
 * point of this dashboard).
 *
 * The active tab is a URL search param (`?tab=boes`) via `useSearchParams`
 * (react-router-dom v7, same hook already used elsewhere in this app) so the
 * view is deep-linkable and survives refresh/back-forward.
 *
 * PDF/Excel export buttons are wired to the SAME `balance-pdf`/`balance-excel`
 * endpoints `LicenseBalanceWorkspace.tsx` already used — their content is a
 * separate, later backend task. Excel uses the shared `openAuthedFile`
 * helper; PDF fetches a blob then hands it to `openPdfPreview`, exactly as
 * the old workspace page did.
 */
export default function LicenseOverviewPage() {
    const { id } = useParams<{ id: string }>();
    const queryClient = useQueryClient();
    const { hasRole } = useContext(AuthContext);
    const [searchParams, setSearchParams] = useSearchParams();
    const [isAutoPlanning, setIsAutoPlanning] = useState(false);

    const rawTab = searchParams.get("tab");
    // `plan` was used by legacy deep links. Keep it as an input alias while
    // rendering the one authoritative Planning tab/editor.
    const normalizedTab = rawTab === "plan" ? "planning" : rawTab;
    const activeTab: TabId = TAB_IDS.has(normalizedTab ?? "") ? (normalizedTab as TabId) : "overview";

    const { data: summary } = useLicenseOverviewSummary(id, true);
    // There is no documents-only endpoint. Reuse the exact retrieve response
    // already consumed by the Balance item matrix under the same query key.
    const detailsQuery = useQuery({
        queryKey: ["license-balance-customs-ledger", String(id ?? "")],
        queryFn: async () => (await api.get(`licenses/${id}/`)).data as { license_documents?: LicenseDocument[] },
        enabled: Boolean(id),
    });
    const documents = detailsQuery.data?.license_documents ?? [];
    const licenceCopies = documents.filter((document) => document.type === "LICENSE COPY" && Boolean(document.file));
    const transferLetters = documents.filter((document) => document.type === "TRANSFER LETTER" && Boolean(document.file));

    const openStoredDocument = useCallback(async (document: LicenseDocument) => {
        try {
            await openDocument(document.file);
        } catch (err) {
            toast.error(extractApiError(err, "Unable to open this document. Please try again."));
        }
    }, []);

    const [downloadingPdf, setDownloadingPdf] = useState(false);
    const [downloadingExcel, setDownloadingExcel] = useState(false);
    const [showHiddenBoe, setShowHiddenBoe] = useState(false);

    const refreshPlanningDependents = useCallback(() => {
        if (!id) return;
        // The editor reloads its own persisted plan. Refresh every cached
        // overview projection that canonically incorporates those plans.
        void queryClient.invalidateQueries({ queryKey: licenseOverviewKeys.summary(id) });
        void queryClient.invalidateQueries({ queryKey: licenseOverviewKeys.items(id) });
        void queryClient.invalidateQueries({ queryKey: licenseOverviewKeys.planning(id) });
        void queryClient.invalidateQueries({ queryKey: licenseBalanceKeys.ledger(id) });
    }, [id, queryClient]);

    const handleAutoPlan = useCallback(async () => {
        if (!id || isAutoPlanning) return;
        setIsAutoPlanning(true);
        try {
            const result = await autoPlanLicense(Number(id));
            refreshPlanningDependents();
            toast.success(result.message || "Licence planning has completed.");
        } catch (err) {
            toast.error(extractApiError(err, "Failed to auto-plan licence."));
        } finally {
            setIsAutoPlanning(false);
        }
    }, [id, isAutoPlanning, refreshPlanningDependents]);

    const handleTabChange = useCallback(
        (value: string) => {
            const next = new URLSearchParams(searchParams);
            if (value === "overview") next.delete("tab");
            else next.set("tab", value);
            setSearchParams(next, { replace: true });
        },
        [searchParams, setSearchParams]
    );

    const handleDownloadPdf = async () => {
        if (!id) return;
        setDownloadingPdf(true);
        try {
            const response = await api.get(`licenses/${id}/balance-pdf/`, {
                responseType: "blob",
                params: showHiddenBoe ? { show_hidden: true } : undefined,
            });
            openPdfPreview(response.data, `${summary?.license_number || id}-balance.pdf`);
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
            const query = showHiddenBoe ? "?show_hidden=true" : "";
            await openAuthedFile(`licenses/${id}/balance-excel/${query}`, `${summary?.license_number || id}-balance.xlsx`);
            toast.success("Excel file downloaded successfully!");
        } catch (err) {
            toast.error(extractApiError(err, "Failed to generate Excel file"));
        } finally {
            setDownloadingExcel(false);
        }
    };

    return (
        <div className="license-overview-page mx-auto max-w-[1600px] space-y-3">
            <PageHeader
                className="mb-0 rounded-xl border border-border/70 bg-card px-4 py-3 shadow-sm sm:px-5"
                pretitle="Licence"
                title={`License Overview — ${summary?.license_number ?? id}`}
                description={summary?.importer ?? undefined}
                actions={
                    <>
                        <PermissionGate role="LICENSE_MANAGER" anyRole={undefined}>
                            <Button size="sm" onClick={() => void handleAutoPlan()} disabled={isAutoPlanning}>
                                {isAutoPlanning ? <Loader2 className="size-4 animate-spin" /> : <Target className="size-4" />}
                                {isAutoPlanning ? "Planning…" : "Auto Plan"}
                            </Button>
                        </PermissionGate>
                        {!detailsQuery.isLoading && licenceCopies.map((document, index) => (
                            <Button key={document.id} size="sm" variant="outline" onClick={() => void openStoredDocument(document)}>
                                {licenceCopies.length === 1 ? "View Licence Copy" : `View Licence Copy ${index + 1}`}
                            </Button>
                        ))}
                        {!detailsQuery.isLoading && transferLetters.map((document, index) => (
                            <Button key={document.id} size="sm" variant="outline" onClick={() => void openStoredDocument(document)}>
                                {transferLetters.length === 1 ? "View TL" : `View TL ${index + 1}`}
                            </Button>
                        ))}
                        <Button size="sm" variant="outline" onClick={handleDownloadPdf} disabled={downloadingPdf}>
                            {downloadingPdf ? <Loader2 className="size-4 animate-spin" /> : <FileText className="size-4" />}
                            Download PDF
                        </Button>
                        <Button size="sm" variant="outline" onClick={handleDownloadExcel} disabled={downloadingExcel}>
                            {downloadingExcel ? <Loader2 className="size-4 animate-spin" /> : <FileSpreadsheet className="size-4" />}
                            Download Excel
                        </Button>
                    </>
                }
            />

            {id && <ReplanStatus licenseId={id} />}

            <Tabs value={activeTab} onValueChange={handleTabChange}>
                <TabsList className="sticky top-2 z-10 mb-0 flex h-auto w-full flex-nowrap justify-start gap-1 overflow-x-auto rounded-xl border border-border/70 bg-card/95 p-1.5 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-card/90">
                    {TABS.map((t) => (
                        <TabsTrigger key={t.id} value={t.id}>{t.label}</TabsTrigger>
                    ))}
                </TabsList>

                <TabsContent value="overview" className="mt-3">
                    <OverviewTab
                        licenseId={id}
                        isActive={activeTab === "overview"}
                        showHiddenBoe={showHiddenBoe}
                        onShowHiddenBoeChange={setShowHiddenBoe}
                    />
                </TabsContent>
                <TabsContent value="boes" className="mt-3">
                    <BoesTab licenseId={id} isActive={activeTab === "boes"} />
                </TabsContent>
                <TabsContent value="allotments" className="mt-3">
                    <AllotmentsTab licenseId={id} isActive={activeTab === "allotments"} />
                </TabsContent>
                <TabsContent value="planning" className="mt-3">
                    {id && (
                        <PlanningEditor
                            licenseId={parseInt(id, 10)}
                            licenseNumber={summary?.license_number || ""}
                            balanceCif={summary?.balance_cif ? parseFloat(String(summary.balance_cif)) : 0}
                            canWrite={hasRole("LICENSE_MANAGER")}
                            onSaved={refreshPlanningDependents}
                        />
                    )}
                </TabsContent>
                <TabsContent value="items" className="mt-3">
                    <ItemsTab licenseId={id} isActive={activeTab === "items"} />
                </TabsContent>
                <TabsContent value="invoice-ledger" className="mt-3">
                    <InvoiceLedgerTab licenseId={id} isActive={activeTab === "invoice-ledger"} />
                </TabsContent>
            </Tabs>
        </div>
    );
}
