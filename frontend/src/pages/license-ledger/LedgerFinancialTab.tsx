/**
 * Ledger tab of the inline licence workspace (one-page Licence Ledger): the licence financial view
 * (licence header, Total Purchase / Total Sale / Current Balance / Loss-Profit cards, company-wise transaction
 * table — the canonical `LicenseLedgerDetail`) plus BANK details for every purchase and sale.
 *
 * Bank figures come from `GET accounting/licence-bank-ledger/<id>/` (`trades` + `summary`): allocations of real
 * bank payments/receipts to the licence's invoices through settlements or trade-payment links — never inferred
 * from amounts. Only POSTED payments make an invoice paid; drafts are listed as "not counted". Bank direction is
 * the bank statement side (WITHDRAWAL / DEBIT, DEPOSIT / CREDIT). Users without an accounting role see the
 * ledger without bank details (the API refuses them).
 */
import { ChevronDown, Landmark } from "lucide-react";
import { InlineError, StatusBadge, type Tone } from "@/components/shared";
import { cn } from "@/lib/utils";
import { formatIndianNumber } from "@/utils/numberFormatter";
import type { CanonicalTransaction } from "@/types/canonicalLedger";
import LicenseLedgerDetail from "../LicenseLedgerDetail";
import { isForbidden, useBankLedger, type BankDirection, type BankReconciliation, type TradeBankSettlement, type TradePaymentStatus } from "./paymentLedgerApi";

function money(value: string | number | null | undefined): string {
    if (value === null || value === undefined || value === "") return "—";
    const n = Number(value);
    if (Number.isNaN(n)) return String(value);
    return `${n < 0 ? "-" : ""}₹${formatIndianNumber(Math.abs(n))}`;
}

const STATUS: Record<TradePaymentStatus, { tone: Tone; purchase: string; sale: string }> = {
    PAID: { tone: "success", purchase: "Paid", sale: "Received" },
    PARTIAL: { tone: "warning", purchase: "Partially paid", sale: "Partially received" },
    UNPAID: { tone: "danger", purchase: "Unpaid", sale: "Not received" },
};
const RECON: Record<BankReconciliation, { tone: Tone; label: string }> = {
    RECONCILED: { tone: "success", label: "Reconciled" },
    PARTIAL: { tone: "warning", label: "Partially reconciled" },
    UNRECONCILED: { tone: "neutral", label: "Unreconciled" },
};
const SIDE: Record<BankDirection, { tone: Tone; label: string }> = {
    WITHDRAWAL: { tone: "danger", label: "WITHDRAWAL / DEBIT" },
    DEPOSIT: { tone: "success", label: "DEPOSIT / CREDIT" },
};

export interface LedgerFinancialTabProps {
    licenseId: string;
    companyId?: string;
    /** Accounting read role (bank ledger API) — otherwise bank details are omitted. */
    canSeeBank: boolean;
}

export default function LedgerFinancialTab({ licenseId, companyId, canSeeBank }: LedgerFinancialTabProps) {
    const bank = useBankLedger(licenseId, canSeeBank);
    const settlements = new Map<number, TradeBankSettlement>((bank.data?.trades ?? []).map(t => [t.trade_id, t]));
    const s = bank.data?.summary;

    let bankSummary: React.ReactNode;
    if (!canSeeBank || (bank.isError && isForbidden(bank.error))) {
        bankSummary = <p className="text-xs text-muted-foreground">Bank payment and receipt details are shown to accounting roles.</p>;
    } else if (bank.isError) {
        bankSummary = <InlineError error={bank.error} onRetry={() => { void bank.refetch(); }} title="Could not load bank details" />;
    } else if (bank.isPending || !s) {
        bankSummary = <p role="status" className="text-xs text-muted-foreground">Loading bank details…</p>;
    } else {
        const items = [
            ["Total Bank Withdrawals", s.total_withdrawals],
            ["Total Bank Credits", s.total_credits],
            ["Total Allocated Payments", s.total_allocated_payments],
            ["Total Allocated Receipts", s.total_allocated_receipts],
            ["Total Unallocated Withdrawals", s.total_unallocated_withdrawals],
            ["Total Unallocated Credits", s.total_unallocated_credits],
            ["Total Outstanding Purchase Invoices", s.total_outstanding_purchase],
            ["Total Outstanding Sales Invoices", s.total_outstanding_sales],
        ] as const;
        bankSummary = (
            <section aria-label="Bank movement summary" className="rounded-lg border border-border bg-card px-3 py-2 shadow-sm">
                <p className="mb-1.5 flex flex-wrap items-center gap-1.5 text-xs font-semibold text-foreground">
                    <Landmark className="size-3.5" aria-hidden="true" /> Bank movement
                    <span className="font-normal text-muted-foreground">— licence-linked only (bank items allocated to this licence's invoices; other account activity excluded)</span>
                </p>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-4">
                    {items.map(([label, value]) => (
                        <div key={label} className="min-w-0">
                            <dt className="text-[0.66rem] font-semibold uppercase tracking-[0.06em] text-muted-foreground">{label}</dt>
                            <dd className="text-sm font-semibold tabular-nums text-foreground">{money(value)}</dd>
                        </div>
                    ))}
                </dl>
            </section>
        );
    }

    const renderBankCell = canSeeBank && bank.data ? (txn: CanonicalTransaction, ui: { expanded: boolean; toggle: () => void; detailsId: string }) => {
        const t = settlements.get(Number(txn.id));
        if (!t) return <span className="text-muted-foreground">Not linked</span>;
        const state = STATUS[t.status];
        const isPurchase = t.direction === "PURCHASE";
        return (
            <button
                type="button"
                onClick={ui.toggle}
                aria-expanded={ui.expanded}
                aria-controls={ui.detailsId}
                aria-label={`Bank details for invoice ${t.invoice_number}`}
                className="inline-flex cursor-pointer items-center gap-1 rounded-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >
                <ChevronDown className={cn("size-3 shrink-0 transition-transform motion-reduce:transition-none", !ui.expanded && "-rotate-90")} aria-hidden="true" />
                <StatusBadge tone={t.linked ? state.tone : "neutral"} label={t.linked ? (isPurchase ? state.purchase : state.sale) : "Not linked"} />
            </button>
        );
    } : undefined;

    const renderBankDetails = (txn: CanonicalTransaction) => {
        const t = settlements.get(Number(txn.id));
        if (!t) return null;
        const isPurchase = t.direction === "PURCHASE";
        return (
            <div className="space-y-2" role="region" aria-label={`Bank details for invoice ${t.invoice_number}`}>
                <dl className="flex flex-wrap gap-x-6 gap-y-1 text-xs">
                    <div><dt className="inline text-muted-foreground">Invoice amount </dt><dd className="inline font-semibold tabular-nums">{money(t.total)}</dd></div>
                    <div><dt className="inline text-muted-foreground">{isPurchase ? "Paid" : "Received"} (posted bank) </dt><dd className="inline font-semibold tabular-nums">{money(t.bank_settled)}</dd></div>
                    <div><dt className="inline text-muted-foreground">Outstanding </dt><dd className={cn("inline font-semibold tabular-nums", Number(t.outstanding) > 0 && "text-destructive")}>{money(t.outstanding)}</dd></div>
                </dl>
                {t.allocations.length === 0 ? (
                    <p className="text-xs text-muted-foreground">Not linked / Unallocated — no bank {isPurchase ? "payment" : "receipt"} is allocated to this invoice.</p>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full border-collapse text-xs" aria-label={`Bank transactions for invoice ${t.invoice_number}`}>
                            <thead>
                                <tr className="border-b text-left text-muted-foreground">
                                    <th className="px-2 py-1 font-semibold">Date</th>
                                    <th className="px-2 py-1 font-semibold">Bank account</th>
                                    <th className="px-2 py-1 font-semibold">UTR / Reference</th>
                                    <th className="px-2 py-1 font-semibold">Bank side</th>
                                    <th className="px-2 py-1 text-right font-semibold">Bank amount</th>
                                    <th className="px-2 py-1 text-right font-semibold">Allocated to invoice</th>
                                    <th className="px-2 py-1 text-right font-semibold">Unallocated on payment</th>
                                    <th className="px-2 py-1 font-semibold">Reconciliation</th>
                                </tr>
                            </thead>
                            <tbody>
                                {t.allocations.map(a => (
                                    <tr key={`${a.payment_id}-${a.invoice_number}`} className={cn("border-b border-border/50", !a.counted && "opacity-70")}>
                                        <td className="whitespace-nowrap px-2 py-1">{a.date}</td>
                                        <td className="px-2 py-1">{a.bank_account}</td>
                                        <td className="px-2 py-1 font-mono">{a.reference || "—"}</td>
                                        <td className="px-2 py-1"><StatusBadge tone={SIDE[a.bank_direction].tone} label={SIDE[a.bank_direction].label} /></td>
                                        <td className="px-2 py-1 text-right tabular-nums">{money(a.bank_amount)}</td>
                                        <td className="px-2 py-1 text-right font-semibold tabular-nums">{money(a.allocated)}</td>
                                        <td className="px-2 py-1 text-right tabular-nums">{money(a.payment_unallocated)}</td>
                                        <td className="px-2 py-1">
                                            <StatusBadge tone={RECON[a.reconciliation].tone} label={RECON[a.reconciliation].label} />
                                            {!a.counted && <span className="ml-1 text-muted-foreground">({a.status.toLowerCase()}, not counted)</span>}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        );
    };

    return (
        <LicenseLedgerDetail
            embedded
            section="all"
            licenseId={licenseId}
            itemId={companyId}
            bankSummary={bankSummary}
            renderBankCell={renderBankCell}
            renderBankDetails={renderBankCell ? renderBankDetails : undefined}
        />
    );
}
