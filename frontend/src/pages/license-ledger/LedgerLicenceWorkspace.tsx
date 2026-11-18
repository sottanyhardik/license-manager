/**
 * LedgerLicenceWorkspace — one licence's complete ledger, inline in its Licence Ledger row (one-page ledger).
 *
 * Replaces the standalone `/license-ledger/:licenseId/:itemId` page; every tab reuses an existing component and
 * endpoint (nothing is recomputed here — the canonical CIF/balance figures come from the API):
 *   Overview      — licence header + reconciliation summary   (LicenseLedgerDetail, section="overview")
 *   Ledger        — purchase/sale transactions per company     (LicenseLedgerDetail, section="ledger")
 *   BOE & Allot.  — linked Bills of Entry + allotments          (licence register BoeAllotmentTab; DFIA)
 *   Invoices      — invoice ledger                              (licence register InvoicesTab; DFIA)
 *   Purchase / Sale Ledger — invoices + payment allocations     (PaymentLedgers; DFIA)
 *   Bank Payment Ledger — bank transactions touching the licence (PaymentLedgers; DFIA, accounting read roles)
 *   Documents     — ledger PDF / Excel / customs-ledger PDF, licence copy
 *   Edit          — the one licence / incentive form, embedded  (writers only; API enforces)
 *   History       — DGFT ownership / transfer history           (licence register HistoryTab; DFIA)
 * Tabs that need licence data are shown only to roles the backend's LicensePermission lets read it.
 */
import { lazy, Suspense, useContext, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileSpreadsheet, FileText, Loader2 } from "lucide-react";
import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { ROLES } from "@/routes/authorizationRoles";
import { DetailTabs, LicenceCopiesSection, type DetailTab } from "@/components/workspace";
import { LoadingState } from "@/components/shared";
import { Button } from "@/components/ui/button";
import BoeAllotmentTab from "@/features/licenses/tabs/BoeAllotmentTab";
import InvoicesTab from "@/features/licenses/tabs/InvoicesTab";
import HistoryTab from "@/features/licenses/tabs/HistoryTab";
import type { LicenceOwnershipData } from "@/features/licenses/types";
import { invalidateLicence } from "@/lib/queryKeys";
import {
    downloadCustomLedgerPdf, downloadLicenseLedgerExcel, licenseLedgerExportError, previewLicenseLedgerPdf,
} from "@/services/licenseLedgerExport";
import LicenseLedgerDetail from "../LicenseLedgerDetail";
import { BankPaymentLedgerTab, PurchaseLedgerTab, SaleLedgerTab } from "./PaymentLedgers";

const MasterForm = lazy(() => import("../masters/MasterForm"));

/** Mirrors backend `LicensePermission.required_roles_for_read` (licence, BOE/allotment, invoice and ownership data). */
const LICENCE_DATA_READ_ROLES = [ROLES.LICENSE_MANAGER, ROLES.LICENSE_VIEWER, ROLES.TRADE_VIEWER, ROLES.TRADE_MANAGER];

export type LedgerWorkspaceTab = "overview" | "ledger" | "boe-allotment" | "invoices" | "purchase-ledger" | "sale-ledger" | "bank-ledger" | "documents" | "edit" | "history";

export interface LedgerLicenceWorkspaceProps {
    licenseId: string;
    /** Company scoping the ledger (the old route's second segment). */
    companyId?: string;
    licenseNumber: string;
    licenseType: string;
    initialTab?: string;
}

/** Old detail-page section names that a deep link may carry. */
const TAB_ALIASES: Record<string, LedgerWorkspaceTab> = { transactions: "ledger", details: "overview", boe: "boe-allotment", allotments: "boe-allotment" };

export default function LedgerLicenceWorkspace({ licenseId, companyId, licenseNumber, licenseType, initialTab }: LedgerLicenceWorkspaceProps) {
    const { hasAnyRole } = useContext(AuthContext);
    const queryClient = useQueryClient();
    const [tab, setTab] = useState<string>(() => (initialTab ? TAB_ALIASES[initialTab] ?? initialTab : "overview"));
    const [ownership, setOwnership] = useState<LicenceOwnershipData | null>(null);
    const [ownershipLoading, setOwnershipLoading] = useState(false);
    const [exporting, setExporting] = useState<"pdf" | "xlsx" | "custom" | null>(null);

    const isDfia = licenseType === "DFIA";
    const numericId = Number(licenseId);
    const canReadLicence = isDfia && hasAnyRole(LICENCE_DATA_READ_ROLES);
    /** Mirrors backend `AccountingPermission` reads (bank transactions); the API stays authoritative (403 -> inline no-access). */
    const canReadBank = isDfia && hasAnyRole([ROLES.ACCOUNTS_VIEWER, ROLES.ACCOUNTS_MANAGER, ROLES.ACCOUNTS_APPROVER]);
    const canEdit = isDfia ? hasAnyRole([ROLES.LICENSE_MANAGER]) : hasAnyRole([ROLES.INCENTIVE_LICENSE_MANAGER]);

    const changeTab = (next: string) => {
        setTab(next);
        // Ownership is fetched on the first History visit (same endpoint as the licence register).
        if (next === "history" && !ownership && !ownershipLoading) {
            setOwnershipLoading(true);
            api.get(`license-actions/${licenseId}/ownership-data/`)
                .then(({ data }) => setOwnership(data))
                .catch(() => toast.error("Failed to load ownership data"))
                .finally(() => setOwnershipLoading(false));
        }
    };

    const runExport = async (kind: "pdf" | "xlsx" | "custom") => {
        if (exporting) return;
        setExporting(kind);
        const scope = { licenseId, itemId: companyId, licenseType };
        try {
            if (kind === "pdf") await previewLicenseLedgerPdf(scope);
            else if (kind === "xlsx") await downloadLicenseLedgerExcel(scope);
            else await downloadCustomLedgerPdf(licenseId);
        } catch (error) {
            toast.error(licenseLedgerExportError(error, "Failed to generate the document."));
        } finally {
            setExporting(null);
        }
    };

    const tabs: DetailTab[] = [
        { id: "overview", label: "Overview", render: () => <LicenseLedgerDetail embedded section="overview" licenseId={licenseId} itemId={companyId} /> },
        { id: "ledger", label: "Ledger", render: () => <LicenseLedgerDetail embedded section="ledger" licenseId={licenseId} itemId={companyId} /> },
        { id: "boe-allotment", label: "BOE & Allotments", visible: canReadLicence, render: () => <BoeAllotmentTab licenseId={numericId} /> },
        { id: "invoices", label: "Invoices", visible: canReadLicence, render: () => <InvoicesTab licenseId={numericId} /> },
        { id: "purchase-ledger", label: "Purchase Ledger", visible: canReadLicence, render: () => <PurchaseLedgerTab licenseId={numericId} /> },
        { id: "sale-ledger", label: "Sale Ledger", visible: canReadLicence, render: () => <SaleLedgerTab licenseId={numericId} /> },
        { id: "bank-ledger", label: "Bank Payment Ledger", visible: canReadBank, render: () => <BankPaymentLedgerTab licenseId={numericId} /> },
        {
            id: "documents",
            label: "Documents",
            render: () => (
                <div className="space-y-3">
                    <div role="group" aria-label="Ledger documents" className="flex flex-wrap items-center gap-2">
                        <Button type="button" size="sm" variant="outline" disabled={exporting !== null} onClick={() => { void runExport("pdf"); }} aria-label="Preview ledger PDF">
                            {exporting === "pdf" ? <Loader2 className="size-3.5 animate-spin" /> : <FileText className="size-3.5" />} Ledger PDF
                        </Button>
                        <Button type="button" size="sm" variant="outline" disabled={exporting !== null} onClick={() => { void runExport("xlsx"); }} aria-label="Download ledger Excel">
                            {exporting === "xlsx" ? <Loader2 className="size-3.5 animate-spin" /> : <FileSpreadsheet className="size-3.5" />} Ledger Excel
                        </Button>
                        {isDfia && (
                            <Button type="button" size="sm" variant="outline" disabled={exporting !== null} onClick={() => { void runExport("custom"); }} aria-label="Download customs ledger PDF">
                                {exporting === "custom" ? <Loader2 className="size-3.5 animate-spin" /> : <FileText className="size-3.5" />} Customs ledger PDF
                            </Button>
                        )}
                    </div>
                    {canReadLicence && (
                        <LicenceCopiesSection rows={[{ license_id: numericId, license_number: licenseNumber }]} emptyDescription="No licence copy." />
                    )}
                </div>
            ),
        },
        {
            id: "edit",
            label: "Edit",
            visible: canEdit,
            render: () => (
                <Suspense fallback={<LoadingState variant="spinner" label="Loading form" />}>
                    <MasterForm
                        embedded
                        entityName={isDfia ? "licenses" : "incentive-licenses"}
                        recordId={licenseId}
                        onSuccess={() => {
                            if (isDfia) void invalidateLicence(queryClient, numericId);
                        }}
                        onClose={() => setTab("overview")}
                    />
                </Suspense>
            ),
        },
        { id: "history", label: "History", visible: canReadLicence, render: () => <HistoryTab ownershipData={ownership} loading={ownershipLoading} /> },
    ];

    return (
        <DetailTabs
            recordKey={`ledger:${licenseId}:${companyId ?? ""}`}
            tabs={tabs}
            value={tab}
            onValueChange={changeTab}
            className="min-w-0 [&_[role=tablist]]:flex-nowrap [&_[role=tablist]]:overflow-x-auto [&_[role=tab]]:shrink-0"
            ariaLabel={`Licence ${licenseNumber} ledger sections`}
        />
    );
}
