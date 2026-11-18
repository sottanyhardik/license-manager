/**
 * LedgerLicenceWorkspace — one licence's financial workspace, inline in its Licence Ledger row.
 *
 * Single owner per piece of data (no record or summary is shown twice):
 *   PERMANENT  licence header + Total Purchase / Total Sale / Current Balance / P-L cards (licence-level, canonical
 *              backend figures — LicenseLedgerDetail section "overview")
 *   Ledger                company-wise purchase/sale transactions + references (invoice / bank status links)
 *   Purchase Invoices     purchase invoices, paid / outstanding, trade payment allocations (invoice-level totals)
 *   Sale Invoices         sale invoices, received / outstanding                              (invoice-level totals)
 *   Bank Payment Ledger   bank withdrawals / credits and their allocations (licence-linked bank totals) — accounting roles
 *   BOE & Allotments      linked BOEs and allotments
 *   Documents             ledger PDF / Excel / customs ledger PDF, licence copy
 *   Ownership History     DGFT ownership / transfer history
 *   Edit                  the one licence / incentive form (writers)
 * Cross-references switch tab and focus the record (invoice number / bank UTR). Every tab reuses an existing
 * component and endpoint; the backend's permission classes stay authoritative.
 */
import { lazy, Suspense, useContext, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileSpreadsheet, FileText, Loader2 } from "lucide-react";
import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { ROLES } from "@/routes/authorizationRoles";
import { DetailTabs, LicenceCopiesSection, type DetailTab } from "@/components/workspace";
import { LoadingState } from "@/components/shared";
import { Button } from "@/components/ui/button";
import BoeAllotmentTab from "@/features/licenses/tabs/BoeAllotmentTab";
import HistoryTab from "@/features/licenses/tabs/HistoryTab";
import type { LicenceOwnershipData } from "@/features/licenses/types";
import { invalidateLicence } from "@/lib/queryKeys";
import {
    downloadCustomLedgerPdf, downloadLicenseLedgerExcel, licenseLedgerExportError, previewLicenseLedgerPdf,
} from "@/services/licenseLedgerExport";
import LicenseLedgerDetail from "../LicenseLedgerDetail";
import LedgerFinancialTab from "./LedgerFinancialTab";
import { BankPaymentLedgerTab, PurchaseLedgerTab, SaleLedgerTab, type LedgerFocus } from "./PaymentLedgers";

const MasterForm = lazy(() => import("../masters/MasterForm"));

/** Mirrors backend `LicensePermission.required_roles_for_read` (licence, BOE/allotment, invoice and ownership data). */
const LICENCE_DATA_READ_ROLES = [ROLES.LICENSE_MANAGER, ROLES.LICENSE_VIEWER, ROLES.TRADE_VIEWER, ROLES.TRADE_MANAGER];
/** Mirrors backend `AccountingPermission` reads. */
const ACCOUNTING_READ_ROLES = [ROLES.ACCOUNTS_VIEWER, ROLES.ACCOUNTS_MANAGER, ROLES.ACCOUNTS_APPROVER];

export type LedgerWorkspaceTab = "ledger" | "purchase" | "sale" | "bank" | "boe" | "documents" | "history" | "edit";

export interface LedgerLicenceWorkspaceProps {
    licenseId: string;
    /** Company scoping the ledger (the old route's second segment). */
    companyId?: string;
    licenseNumber: string;
    licenseType: string;
    /** First tab (old `?tab=` deep links are mapped onto the current tabs). */
    initialTab?: string;
}

const TAB_ALIASES: Record<string, LedgerWorkspaceTab> = {
    overview: "ledger", ledger: "ledger", transactions: "ledger", details: "ledger",
    invoices: "purchase", purchase: "purchase", "purchase-ledger": "purchase", sale: "sale", "sale-ledger": "sale",
    bank: "bank", "bank-ledger": "bank", boe: "boe", "boe-allotment": "boe", allotments: "boe",
    documents: "documents", history: "history", edit: "edit",
};

/** Ownership / DGFT transfer history (same endpoint as the licence register). */
function OwnershipHistory({ licenseId }: { licenseId: string }) {
    const ownership = useQuery<LicenceOwnershipData>({
        queryKey: ["licence-ownership", licenseId],
        queryFn: async () => (await api.get(`license-actions/${licenseId}/ownership-data/`)).data as LicenceOwnershipData,
    });
    return <HistoryTab ownershipData={ownership.data ?? null} loading={ownership.isPending} />;
}

export default function LedgerLicenceWorkspace({ licenseId, companyId, licenseNumber, licenseType, initialTab }: LedgerLicenceWorkspaceProps) {
    const { hasAnyRole } = useContext(AuthContext);
    const queryClient = useQueryClient();
    const [tab, setTab] = useState<string>(() => (initialTab ? TAB_ALIASES[initialTab] ?? "ledger" : "ledger"));
    const [focus, setFocus] = useState<{ purchase?: LedgerFocus; sale?: LedgerFocus; bank?: LedgerFocus }>({});
    const [exporting, setExporting] = useState<"pdf" | "xlsx" | "custom" | null>(null);
    const isDfia = licenseType === "DFIA";
    const numericId = Number(licenseId);
    const canReadLicence = isDfia && hasAnyRole(LICENCE_DATA_READ_ROLES);
    const canReadBank = isDfia && hasAnyRole(ACCOUNTING_READ_ROLES);
    const canEdit = isDfia ? hasAnyRole([ROLES.LICENSE_MANAGER]) : hasAnyRole([ROLES.INCENTIVE_LICENSE_MANAGER]);

    const openInvoice = (direction: "PURCHASE" | "SALE", invoiceNumber: string) => {
        const target = direction === "PURCHASE" ? "purchase" : "sale";
        setFocus(f => ({ ...f, [target]: { key: invoiceNumber, n: (f[target]?.n ?? 0) + 1 } }));
        setTab(target);
    };
    const openBank = (reference: string) => {
        if (!canReadBank) return;
        setFocus(f => ({ ...f, bank: { key: reference, n: (f.bank?.n ?? 0) + 1 } }));
        setTab("bank");
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
        {
            id: "ledger", label: "Ledger",
            render: () => <LedgerFinancialTab licenseId={licenseId} companyId={companyId} canReadLicence={canReadLicence} canSeeBank={canReadBank} onOpenInvoice={openInvoice} onOpenBank={openBank} />,
        },
        { id: "purchase", label: "Purchase Invoices", visible: canReadLicence, render: () => <PurchaseLedgerTab licenseId={numericId} focus={focus.purchase} onOpenBank={canReadBank ? openBank : undefined} /> },
        { id: "sale", label: "Sale Invoices", visible: canReadLicence, render: () => <SaleLedgerTab licenseId={numericId} focus={focus.sale} onOpenBank={canReadBank ? openBank : undefined} /> },
        { id: "bank", label: "Bank Payment Ledger", visible: canReadBank, render: () => <BankPaymentLedgerTab licenseId={numericId} focus={focus.bank} onOpenInvoice={canReadLicence ? openInvoice : undefined} /> },
        { id: "boe", label: "BOE & Allotments", visible: canReadLicence, render: () => <BoeAllotmentTab licenseId={numericId} /> },
        {
            id: "documents", label: "Documents",
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
                    {canReadLicence && <LicenceCopiesSection rows={[{ license_id: numericId, license_number: licenseNumber }]} emptyDescription="No licence copy." />}
                </div>
            ),
        },
        { id: "history", label: "Ownership History", visible: canReadLicence, render: () => <OwnershipHistory licenseId={licenseId} /> },
        {
            id: "edit", label: "Edit", visible: canEdit,
            render: () => (
                <Suspense fallback={<LoadingState variant="spinner" label="Loading form" />}>
                    <MasterForm
                        embedded
                        entityName={isDfia ? "licenses" : "incentive-licenses"}
                        recordId={licenseId}
                        onSuccess={() => {
                            if (isDfia) void invalidateLicence(queryClient, numericId);
                            void queryClient.invalidateQueries({ queryKey: ["licence-payment-ledgers", licenseId] });
                        }}
                        onClose={() => setTab("ledger")}
                    />
                </Suspense>
            ),
        },
    ];

    return (
        <div className="min-w-0 space-y-3" data-testid="ledger-licence-workspace">
            {/* PERMANENT — licence header + licence-level summary cards; never repeated inside a tab. */}
            <LicenseLedgerDetail embedded section="overview" licenseId={licenseId} itemId={companyId} />
            <DetailTabs
                recordKey={`ledger:${licenseId}:${companyId ?? ""}`}
                tabs={tabs}
                value={tab}
                onValueChange={setTab}
                className="min-w-0 [&_[role=tablist]]:flex-nowrap [&_[role=tablist]]:overflow-x-auto [&_[role=tab]]:shrink-0"
                ariaLabel={`Licence ${licenseNumber} ledger sections`}
            />
        </div>
    );
}
