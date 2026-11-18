/** Types + react-query hooks for the Purchase / Sale / Bank Payment ledger tabs (decimals arrive as strings). */
import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";

export type TradePaymentStatus = "PAID" | "PARTIAL" | "UNPAID";

export interface TradePayment {
    id: number;
    date: string;
    amount: string;
    note: string;
    bank_reference: string | null;
}

export interface TradeLedgerRow {
    trade_id: number;
    invoice_number: string;
    invoice_date: string | null;
    company_name: string | null;
    amount: string;
    gst: null;
    total: string;
    licence_amount: string;
    settled: string;
    outstanding: string;
    status: TradePaymentStatus;
    payments: TradePayment[];
    document: { kind: "purchase_invoice_copy" | "generated_sale_invoice"; url: string } | null;
}

export interface TradeLedgerSection {
    summary: { invoice_count: number; total_amount: string; total_settled: string; total_outstanding: string };
    rows: TradeLedgerRow[];
}

export interface PaymentLedgers {
    purchase: TradeLedgerSection;
    sale: TradeLedgerSection;
}

export type BankReconciliation = "RECONCILED" | "PARTIAL" | "UNRECONCILED";

export interface BankLedgerRow {
    payment_id: number;
    date: string;
    bank_account: string;
    reference: string;
    mode: string;
    direction: "PAYMENT" | "RECEIPT";
    party: string;
    amount: string;
    status: string;
    allocated_to_licence: string;
    unallocated: string;
    /** `invoice_id` is null when the payment links to the licence trade directly (trade payment, no accounting invoice). */
    invoices: { invoice_id: number | null; number: string; trade_id: number | null; amount: string }[];
    reconciliation: BankReconciliation;
    /** Bank statement side: WITHDRAWAL (debit) / DEPOSIT (credit); payment direction when not yet matched. */
    bank_direction?: BankDirection;
    statement_lines: { id: number; txn_date: string; reference: string; amount: string; bank_direction?: BankDirection }[];
}

export type BankDirection = "WITHDRAWAL" | "DEPOSIT";

/** One bank allocation to a licence trade (settlement or trade-payment link). `counted` = POSTED payment. */
export interface TradeBankAllocation {
    payment_id: number;
    date: string;
    bank_account: string;
    reference: string;
    mode: string;
    bank_direction: BankDirection;
    bank_amount: string;
    allocated: string;
    payment_unallocated: string;
    invoice_number: string;
    reconciliation: BankReconciliation;
    status: string;
    counted: boolean;
}

/** Bank settlement of one licence trade (purchase paid out / sale received), from posted allocations only. */
export interface TradeBankSettlement {
    trade_id: number;
    direction: "PURCHASE" | "SALE";
    invoice_number: string;
    invoice_date: string | null;
    total: string;
    bank_settled: string;
    outstanding: string;
    status: TradePaymentStatus;
    linked: boolean;
    allocations: TradeBankAllocation[];
}

export interface BankLedger {
    summary: {
        transaction_count: number; total_payments: string; total_receipts: string; total_allocated: string; total_unallocated: string;
        total_withdrawals?: string; total_credits?: string; total_allocated_payments?: string; total_allocated_receipts?: string;
        total_unallocated_withdrawals?: string; total_unallocated_credits?: string;
        total_outstanding_purchase?: string; total_outstanding_sales?: string;
    };
    rows: BankLedgerRow[];
    trades?: TradeBankSettlement[];
}

export const paymentLedgerKeys = {
    trade: (licenseId: number | string) => ["licence-payment-ledgers", String(licenseId)] as const,
    bank: (licenseId: number | string) => ["licence-bank-ledger", String(licenseId)] as const,
};

/** One query shared by the Purchase and Sale tabs. Mounted only while a tab is active, so it is lazy. */
export function usePaymentLedgers(licenseId: number | string, enabled = true) {
    return useQuery<PaymentLedgers>({
        enabled,
        queryKey: paymentLedgerKeys.trade(licenseId),
        queryFn: async () => (await api.get(`licenses/${licenseId}/overview-payment-ledgers/`)).data as PaymentLedgers,
    });
}

export function useBankLedger(licenseId: number | string, enabled = true) {
    return useQuery<BankLedger>({
        enabled,
        queryKey: paymentLedgerKeys.bank(licenseId),
        queryFn: async () => (await api.get(`accounting/licence-bank-ledger/${licenseId}/`)).data as BankLedger,
    });
}

export function isForbidden(error: unknown): boolean {
    return (error as { response?: { status?: number } } | null)?.response?.status === 403;
}
