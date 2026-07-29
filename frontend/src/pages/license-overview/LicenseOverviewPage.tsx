import { useCallback, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { FileSpreadsheet, FileText, Loader2 } from "lucide-react";

import api from "@/api/axios";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { openPdfPreview } from "@/utils/pdfPreview";
import { openAuthedFile } from "@/utils/documentDownload";

import { extractApiError } from "./licenseOverviewHelpers";
import { useLicenseOverviewSummary } from "./useLicenseOverviewSummary";
import OverviewTab from "./OverviewTab";
import BoesTab from "./BoesTab";
import AllotmentsTab from "./AllotmentsTab";
import PlanningTab from "./PlanningTab";
import ItemsTab from "./ItemsTab";
import InvoiceLedgerTab from "./InvoiceLedgerTab";

type TabId = "overview" | "boes" | "allotments" | "planning" | "items" | "invoice-ledger";

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
    const [searchParams, setSearchParams] = useSearchParams();

    const rawTab = searchParams.get("tab");
    const activeTab: TabId = TAB_IDS.has(rawTab ?? "") ? (rawTab as TabId) : "overview";

    const { data: summary } = useLicenseOverviewSummary(id, true);

    const [downloadingPdf, setDownloadingPdf] = useState(false);
    const [downloadingExcel, setDownloadingExcel] = useState(false);

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
            const response = await api.get(`licenses/${id}/balance-pdf/`, { responseType: "blob" });
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
            await openAuthedFile(`licenses/${id}/balance-excel/`, `${summary?.license_number || id}-balance.xlsx`);
            toast.success("Excel file downloaded successfully!");
        } catch {
            toast.error("Failed to generate Excel file");
        } finally {
            setDownloadingExcel(false);
        }
    };

    return (
        <div>
            <PageHeader
                pretitle="Licence"
                title={`License Overview — ${summary?.license_number ?? id}`}
                description={summary?.importer ?? undefined}
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
                    </>
                }
            />

            <Tabs value={activeTab} onValueChange={handleTabChange}>
                <TabsList className="mb-4 flex-wrap">
                    {TABS.map((t) => (
                        <TabsTrigger key={t.id} value={t.id}>{t.label}</TabsTrigger>
                    ))}
                </TabsList>

                <TabsContent value="overview">
                    <OverviewTab licenseId={id} isActive={activeTab === "overview"} />
                </TabsContent>
                <TabsContent value="boes">
                    <BoesTab licenseId={id} isActive={activeTab === "boes"} />
                </TabsContent>
                <TabsContent value="allotments">
                    <AllotmentsTab licenseId={id} isActive={activeTab === "allotments"} />
                </TabsContent>
                <TabsContent value="planning">
                    <PlanningTab licenseId={id} isActive={activeTab === "planning"} />
                </TabsContent>
                <TabsContent value="items">
                    <ItemsTab licenseId={id} isActive={activeTab === "items"} />
                </TabsContent>
                <TabsContent value="invoice-ledger">
                    <InvoiceLedgerTab licenseId={id} isActive={activeTab === "invoice-ledger"} />
                </TabsContent>
            </Tabs>
        </div>
    );
}
