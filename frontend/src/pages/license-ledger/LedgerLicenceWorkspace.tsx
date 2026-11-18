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
 * Cross-references switch tab and focus the record (invoice number / bank UTR). Every tab reuses an existing
 * component and endpoint; the backend's permission classes stay authoritative.
 */
import { useContext, useState } from "react";
import { AuthContext } from "@/context/AuthContext";
import { ROLES } from "@/routes/authorizationRoles";
import { DetailTabs, type DetailTab } from "@/components/workspace";
import LicenseLedgerDetail from "../LicenseLedgerDetail";
import LedgerFinancialTab from "./LedgerFinancialTab";
import { BankPaymentLedgerTab, PurchaseLedgerTab, SaleLedgerTab, type LedgerFocus } from "./PaymentLedgers";

/** Mirrors backend `LicensePermission.required_roles_for_read` (licence and invoice data). */
const LICENCE_DATA_READ_ROLES = [ROLES.LICENSE_MANAGER, ROLES.LICENSE_VIEWER, ROLES.TRADE_VIEWER, ROLES.TRADE_MANAGER];
/** Mirrors backend `AccountingPermission` reads. */
const ACCOUNTING_READ_ROLES = [ROLES.ACCOUNTS_VIEWER, ROLES.ACCOUNTS_MANAGER, ROLES.ACCOUNTS_APPROVER];

export type LedgerWorkspaceTab = "ledger" | "purchase" | "sale" | "bank";

export interface LedgerLicenceWorkspaceProps {
    licenseId: string;
    /** Company scoping the ledger (the old route's second segment). */
    companyId?: string;
    licenseNumber: string;
    licenseType: string;
    /** First tab. Unknown or retired tab names (old `?tab=` deep links) open the Ledger tab. */
    initialTab?: string;
}

const TAB_ALIASES: Record<string, LedgerWorkspaceTab> = {
    overview: "ledger", ledger: "ledger", transactions: "ledger", details: "ledger",
    invoices: "purchase", purchase: "purchase", "purchase-ledger": "purchase", sale: "sale", "sale-ledger": "sale",
    bank: "bank", "bank-ledger": "bank",
};

export default function LedgerLicenceWorkspace({ licenseId, companyId, licenseNumber, licenseType, initialTab }: LedgerLicenceWorkspaceProps) {
    const { hasAnyRole } = useContext(AuthContext);
    const [tab, setTab] = useState<string>(() => (initialTab ? TAB_ALIASES[initialTab] ?? "ledger" : "ledger"));
    const [focus, setFocus] = useState<{ purchase?: LedgerFocus; sale?: LedgerFocus; bank?: LedgerFocus }>({});
    const isDfia = licenseType === "DFIA";
    const numericId = Number(licenseId);
    const canReadLicence = isDfia && hasAnyRole(LICENCE_DATA_READ_ROLES);
    const canReadBank = isDfia && hasAnyRole(ACCOUNTING_READ_ROLES);

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

    const tabs: DetailTab[] = [
        {
            id: "ledger", label: "Ledger",
            render: () => <LedgerFinancialTab licenseId={licenseId} companyId={companyId} canReadLicence={canReadLicence} canSeeBank={canReadBank} onOpenInvoice={openInvoice} onOpenBank={openBank} />,
        },
        { id: "purchase", label: "Purchase Invoices", visible: canReadLicence, render: () => <PurchaseLedgerTab licenseId={numericId} focus={focus.purchase} onOpenBank={canReadBank ? openBank : undefined} /> },
        { id: "sale", label: "Sale Invoices", visible: canReadLicence, render: () => <SaleLedgerTab licenseId={numericId} focus={focus.sale} onOpenBank={canReadBank ? openBank : undefined} /> },
        { id: "bank", label: "Bank Payment Ledger", visible: canReadBank, render: () => <BankPaymentLedgerTab licenseId={numericId} focus={focus.bank} onOpenInvoice={canReadLicence ? openInvoice : undefined} /> },
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
