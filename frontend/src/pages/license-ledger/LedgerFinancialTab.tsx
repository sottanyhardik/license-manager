/**
 * Ledger tab of the licence workspace: the company-wise purchase/sale transaction table (canonical
 * `LicenseLedgerDetail`, section "ledger") with REFERENCES only — never a second copy of invoices or bank
 * transactions. Each purchase/sale row's Payment cell links to its owner:
 *   • invoice status (Paid / Partially paid / Unpaid, from the invoice ledger API) → Purchase / Sale Invoices tab,
 *     focused on that invoice;
 *   • bank status (accounting roles; posted bank allocations from the bank ledger API) → Bank Payment Ledger tab,
 *     focused on the bank transaction — "Not linked" when no allocation exists (never inferred from amounts).
 * The licence header and summary cards are permanent above the tabs and are not repeated here.
 */
import { StatusBadge, type Tone } from "@/components/shared";
import type { CanonicalTransaction } from "@/types/canonicalLedger";
import LicenseLedgerDetail from "../LicenseLedgerDetail";
import { useBankLedger, usePaymentLedgers, type TradePaymentStatus } from "./paymentLedgerApi";

const INVOICE_STATUS: Record<TradePaymentStatus, { tone: Tone; purchase: string; sale: string }> = {
    PAID: { tone: "success", purchase: "Paid", sale: "Received" },
    PARTIAL: { tone: "warning", purchase: "Partially paid", sale: "Partially received" },
    UNPAID: { tone: "danger", purchase: "Unpaid", sale: "Not received" },
};

export interface LedgerFinancialTabProps {
    licenseId: string;
    companyId?: string;
    /** Licence data read role (invoice ledger API) — invoice status links. */
    canReadLicence: boolean;
    /** Accounting read role (bank ledger API) — bank status links. */
    canSeeBank: boolean;
    onOpenInvoice: (direction: "PURCHASE" | "SALE", invoiceNumber: string) => void;
    onOpenBank: (reference: string) => void;
}

export default function LedgerFinancialTab({ licenseId, companyId, canReadLicence, canSeeBank, onOpenInvoice, onOpenBank }: LedgerFinancialTabProps) {
    const invoices = usePaymentLedgers(licenseId, canReadLicence);
    const bank = useBankLedger(licenseId, canSeeBank);
    const invoiceByTrade = new Map(
        [...(invoices.data?.purchase.rows ?? []).map(r => ({ ...r, direction: "PURCHASE" as const })),
            ...(invoices.data?.sale.rows ?? []).map(r => ({ ...r, direction: "SALE" as const }))].map(r => [r.trade_id, r]),
    );
    const bankByTrade = new Map((bank.data?.trades ?? []).map(t => [t.trade_id, t]));
    const hasLinks = (canReadLicence && invoices.data) || (canSeeBank && bank.data);

    const renderBankCell = hasLinks ? (txn: CanonicalTransaction) => {
        const tradeId = Number(txn.id);
        const invoice = invoiceByTrade.get(tradeId);
        const bankTrade = bankByTrade.get(tradeId);
        return (
            <div className="flex flex-wrap items-center gap-1.5">
                {invoice && (() => {
                    const state = INVOICE_STATUS[invoice.status];
                    const isPurchase = invoice.direction === "PURCHASE";
                    return (
                        <button type="button" onClick={() => onOpenInvoice(invoice.direction, invoice.invoice_number)}
                            aria-label={`Open ${isPurchase ? "purchase" : "sale"} invoice ${invoice.invoice_number}`}
                            className="rounded-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
                            <StatusBadge tone={state.tone} label={isPurchase ? state.purchase : state.sale} />
                        </button>
                    );
                })()}
                {canSeeBank && bankTrade && (bankTrade.allocations[0] ? (
                    <button type="button" onClick={() => onOpenBank(bankTrade.allocations[0].reference)}
                        aria-label={`Open bank transaction ${bankTrade.allocations[0].reference}`}
                        className="rounded-sm text-[11px] font-medium text-primary underline-offset-2 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50">
                        Bank: {bankTrade.allocations[0].reference}{bankTrade.allocations.length > 1 ? ` +${bankTrade.allocations.length - 1}` : ""}
                    </button>
                ) : <span className="text-[11px] text-muted-foreground">Bank: not linked</span>)}
            </div>
        );
    } : undefined;

    return <LicenseLedgerDetail embedded section="ledger" licenseId={licenseId} itemId={companyId} renderBankCell={renderBankCell} />;
}
