/**
 * LedgerLicenceWorkspace — one licence's complete financial workspace, inline in its Licence Ledger row.
 * ONE continuous page (no tabs), in this order:
 *   1–3  Licence header, Total Purchase / Total Sale / Current Balance / P-L cards, company-wise transaction table
 *        with inline bank payment/receipt details                      (LedgerFinancialTab → LicenseLedgerDetail)
 *   4    Purchase invoices                                              (licence-payment-ledgers API)
 *   5    Sale invoices                                                  (licence-payment-ledgers API)
 *   6    Bank payment ledger — accounting roles only                    (licence-bank-ledger API, AccountingPermission)
 *   7    BOE & Allotments — expandable                                  (licence register BoeAllotmentTab)
 *   8    Documents & licence copy — inline actions (+ Edit for writers)
 *   9    Ownership history — expandable                                 (license-actions ownership-data)
 *   10   Inline edit form, when requested                               (the one licence / incentive form)
 * Every section reuses an existing component and endpoint; nothing is recomputed here. Sections that need licence
 * data are shown only to roles the backend's LicensePermission lets read it; the API stays authoritative.
 */
import { lazy, Suspense, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileSpreadsheet, FileText, Loader2, Pencil, X } from "lucide-react";
import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { ROLES } from "@/routes/authorizationRoles";
import { LicenceCopiesSection, ModuleAccordion } from "@/components/workspace";
import { LoadingState } from "@/components/shared";
import { Button } from "@/components/ui/button";
import BoeAllotmentTab from "@/features/licenses/tabs/BoeAllotmentTab";
import HistoryTab from "@/features/licenses/tabs/HistoryTab";
import type { LicenceOwnershipData } from "@/features/licenses/types";
import { invalidateLicence } from "@/lib/queryKeys";
import {
    downloadCustomLedgerPdf, downloadLicenseLedgerExcel, licenseLedgerExportError, previewLicenseLedgerPdf,
} from "@/services/licenseLedgerExport";
import LedgerFinancialTab from "./LedgerFinancialTab";
import { BankPaymentLedgerTab, PurchaseLedgerTab, SaleLedgerTab } from "./PaymentLedgers";

const MasterForm = lazy(() => import("../masters/MasterForm"));

/** Mirrors backend `LicensePermission.required_roles_for_read` (licence, BOE/allotment, invoice and ownership data). */
const LICENCE_DATA_READ_ROLES = [ROLES.LICENSE_MANAGER, ROLES.LICENSE_VIEWER, ROLES.TRADE_VIEWER, ROLES.TRADE_MANAGER];
/** Mirrors backend `AccountingPermission` reads. */
const ACCOUNTING_READ_ROLES = [ROLES.ACCOUNTS_VIEWER, ROLES.ACCOUNTS_MANAGER, ROLES.ACCOUNTS_APPROVER];

export interface LedgerLicenceWorkspaceProps {
    licenseId: string;
    /** Company scoping the ledger (the old route's second segment). */
    companyId?: string;
    licenseNumber: string;
    licenseType: string;
    /** Old `?tab=` deep links: `edit` opens the inline edit form; other values just open the workspace. */
    initialTab?: string;
}

/** A titled block of the continuous workspace (not a tab). */
function WorkspaceBlock({ label, children }: { label: string; children: ReactNode }) {
    return (
        <section aria-label={label} className="min-w-0 space-y-1.5">
            <p className="text-[0.7rem] font-semibold uppercase tracking-[0.06em] text-muted-foreground">{label}</p>
            {children}
        </section>
    );
}

/** Ownership / DGFT transfer history, fetched when its section is opened (same endpoint as the licence register). */
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
    const [exporting, setExporting] = useState<"pdf" | "xlsx" | "custom" | null>(null);
    const isDfia = licenseType === "DFIA";
    const numericId = Number(licenseId);
    const canReadLicence = isDfia && hasAnyRole(LICENCE_DATA_READ_ROLES);
    const canReadBank = isDfia && hasAnyRole(ACCOUNTING_READ_ROLES);
    const canEdit = isDfia ? hasAnyRole([ROLES.LICENSE_MANAGER]) : hasAnyRole([ROLES.INCENTIVE_LICENSE_MANAGER]);
    const [editing, setEditing] = useState(() => canEdit && initialTab === "edit");
    const editRef = useRef<HTMLElement>(null);
    useEffect(() => {
        if (editing) editRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }, [editing]);

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

    return (
        <div className="min-w-0 space-y-4" data-testid="ledger-licence-workspace">
            {/* 1–3: licence header, financial cards, company-wise transactions with inline bank details */}
            <LedgerFinancialTab licenseId={licenseId} companyId={companyId} canSeeBank={canReadBank} />

            {/* 4–5: purchase and sale invoices (paid / received, outstanding, allocations, invoice documents) */}
            {canReadLicence && (
                <>
                    <WorkspaceBlock label="Purchase invoices"><PurchaseLedgerTab licenseId={numericId} /></WorkspaceBlock>
                    <WorkspaceBlock label="Sale invoices"><SaleLedgerTab licenseId={numericId} /></WorkspaceBlock>
                </>
            )}

            {/* 6: bank payment ledger — accounting roles only (the API enforces AccountingPermission) */}
            {canReadBank && (
                <WorkspaceBlock label="Bank payment ledger"><BankPaymentLedgerTab licenseId={numericId} /></WorkspaceBlock>
            )}

            {/* 7: BOE & allotments — expandable */}
            {canReadLicence && (
                <ModuleAccordion
                    persistKey={`ledger:${licenseId}:boe`}
                    sections={[{ id: "boe-allotments", title: "BOE & Allotments", render: () => <BoeAllotmentTab licenseId={numericId} /> }]}
                />
            )}

            {/* 8: documents & licence copy — inline actions (+ Edit for authorised writers) */}
            <WorkspaceBlock label="Documents & licence copy">
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
                    {canEdit && (
                        <Button type="button" size="sm" variant={editing ? "secondary" : "outline"} onClick={() => setEditing(v => !v)} aria-expanded={editing} aria-controls={`ledger-edit-${licenseId}`}>
                            <Pencil className="size-3.5" aria-hidden="true" /> {editing ? "Close edit" : "Edit licence"}
                        </Button>
                    )}
                </div>
                {canReadLicence && (
                    <LicenceCopiesSection rows={[{ license_id: numericId, license_number: licenseNumber }]} emptyDescription="No licence copy." />
                )}
            </WorkspaceBlock>

            {/* 9: ownership history — expandable */}
            {canReadLicence && (
                <ModuleAccordion
                    persistKey={`ledger:${licenseId}:history`}
                    sections={[{ id: "ownership-history", title: "Ownership History", render: () => <OwnershipHistory licenseId={licenseId} /> }]}
                />
            )}

            {/* 10: inline edit form, when requested (writers only; the API enforces permissions) */}
            {canEdit && editing && (
                <section ref={editRef} id={`ledger-edit-${licenseId}`} aria-label={`Edit licence ${licenseNumber}`} className="min-w-0 rounded-lg border border-ring/40 p-3">
                    <div className="mb-2 flex items-center justify-between">
                        <p className="text-xs font-semibold text-foreground">Edit licence {licenseNumber}</p>
                        <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)} aria-label="Close edit form">
                            <X className="size-3.5" aria-hidden="true" />
                        </Button>
                    </div>
                    <Suspense fallback={<LoadingState variant="spinner" label="Loading form" />}>
                        <MasterForm
                            embedded
                            entityName={isDfia ? "licenses" : "incentive-licenses"}
                            recordId={licenseId}
                            onSuccess={() => {
                                if (isDfia) void invalidateLicence(queryClient, numericId);
                                void queryClient.invalidateQueries({ queryKey: ["licence-payment-ledgers", licenseId] });
                            }}
                            onClose={() => setEditing(false)}
                        />
                    </Suspense>
                </section>
            )}
        </div>
    );
}
