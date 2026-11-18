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
    statement_lines: { id: number; txn_date: string; reference: string; amount: string }[];
}

export interface BankLedger {
    summary: { transaction_count: number; total_payments: string; total_receipts: string; total_allocated: string; total_unallocated: string };
    rows: BankLedgerRow[];
}

export const paymentLedgerKeys = {
    trade: (licenseId: number | string) => ["licence-payment-ledgers", String(licenseId)] as const,
    bank: (licenseId: number | string) => ["licence-bank-ledger", String(licenseId)] as const,
};

/** One query shared by the Purchase and Sale tabs. Mounted only while a tab is active, so it is lazy. */
export function usePaymentLedgers(licenseId: number | string) {
    return useQuery<PaymentLedgers>({
        queryKey: paymentLedgerKeys.trade(licenseId),
        queryFn: async () => (await api.get(`licenses/${licenseId}/overview-payment-ledgers/`)).data as PaymentLedgers,
    });
}

export function useBankLedger(licenseId: number | string) {
    return useQuery<BankLedger>({
        queryKey: paymentLedgerKeys.bank(licenseId),
        queryFn: async () => (await api.get(`accounting/licence-bank-ledger/${licenseId}/`)).data as BankLedger,
    });
}

export function isForbidden(error: unknown): boolean {
    return (error as { response?: { status?: number } } | null)?.response?.status === 403;
}
