import InvoiceLedgerTab from "@/pages/license-overview/InvoiceLedgerTab";

/** Invoices tab: the existing overview Invoice Ledger body (`licenses/:id/overview-invoice-ledger/`). */
export default function InvoicesTab({ licenseId }: { licenseId: number }) {
    return <InvoiceLedgerTab licenseId={licenseId} isActive />;
}
