/**
 * Typed client for /api/accounting/ (backend/apps/accounting/urls.py).
 * Money fields are Decimal strings; never convert them to numbers for arithmetic.
 */
import api from "./axios";

export type Money = string;

export interface Paged<T> {
    count: number;
    page: number;
    page_size: number;
    next: number | null;
    previous: number | null;
    results: T[];
}

export interface EntityBooks {
    id: number;
    company_id: number;
    name: string;
    gstin: string | null;
    pan: string | null;
    state_code: string;
    books_start_date: string;
    default_credit_days: number;
    require_maker_checker: boolean;
    is_active: boolean;
    financial_years?: FinancialYear[];
}

export interface FinancialYear {
    id: number;
    label: string;
    start_date: string;
    end_date: string;
    status: string;
    periods: { id: number; period_no: number; start_date: string; end_date: string; status: string }[];
}

export interface DiscoveredEntity {
    company_id: number;
    name: string;
    gstin: string | null;
    own_side_documents: number;
    has_books: boolean;
    books_active: boolean;
    books_start_date: string | null;
}

export interface Account {
    id: number;
    code: string;
    name: string;
    group_id: number;
    group: string;
    nature: string;
    report_head: string;
    kind: string;
    system_role: string | null;
    party_id: number | null;
    intercompany_entity_id: number | null;
    is_active: boolean;
}

export interface VoucherLine {
    line_no: number;
    account_id: number;
    account_code: string;
    account: string;
    debit: Money;
    credit: Money;
    narration: string;
    trade_id: number | null;
}

export interface Voucher {
    id: number;
    number: string | null;
    voucher_type: string;
    date: string;
    status: string;
    narration: string;
    total: Money;
    source_type: string;
    source_id: number | null;
    source_event: string;
    reversal_of_id: number | null;
    reversed_by_id?: number | null;
    posted_by: string | null;
    created_by: string | null;
    lines?: VoucherLine[];
    audit?: { action: string; actor: string | null; at: string; detail: Record<string, unknown> }[];
}

export interface Invoice {
    id: number;
    kind: string;
    number: string;
    party_id: number;
    party: string;
    party_reference: string;
    date: string;
    due_date: string | null;
    taxable_amount: Money;
    cgst: Money;
    sgst: Money;
    igst: Money;
    roundoff: Money;
    gross_amount: Money;
    tds_section: string | null;
    tds_amount: Money;
    net_amount: Money;
    status: string;
    payment_status: string;
    settled: Money;
    outstanding: Money;
    trade_id: number | null;
    voucher_id: number | null;
    voucher_number: string | null;
    narration: string;
    lines?: { line_no: number; account: string; description: string; amount: Money; gst_rate: Money;
        cgst: Money; sgst: Money; igst: Money; trade_id: number | null }[];
    settlements?: { id: number; amount: Money; voucher_id: number; voucher_number: string; date: string;
        is_active: boolean }[];
}

export interface Payment {
    id: number;
    direction: "PAYMENT" | "RECEIPT";
    party_id: number;
    party: string;
    bank_account_id: number;
    date: string;
    amount: Money;
    tds_amount: Money;
    mode: string;
    reference: string;
    status: string;
    voucher_id: number | null;
    voucher_number: string | null;
    trade_payment_id: number | null;
    unallocated: Money | null;
}

export interface TradeRow {
    trade_id: number;
    direction: string;
    invoice_number: string;
    invoice_date: string;
    party: string | null;
    trade_total: Money;
    accounting_status: string;
    invoice_id: number | null;
    invoice_status: string | null;
    voucher_id: number | null;
    voucher_number: string | null;
    payment_status: string | null;
    outstanding: Money | null;
    trade_payments: number;
    unaccounted_payment_ids: number[];
    is_paired: boolean;
}

export interface BankAccount {
    id: number;
    account_id: number;
    bank_name: string;
    account_number: string;
    ifsc: string;
    is_cash: boolean;
    book_balance: Money;
}

export interface BankMatch {
    id: number;
    voucher_id: number;
    voucher_number: string;
    amount: Money;
    method: string;
    is_active: boolean;
}

export interface StatementLine {
    id: number;
    txn_date: string;
    value_date: string | null;
    narration: string;
    reference: string;
    debit: Money;
    credit: Money;
    balance: Money | null;
    status: string;
    matched_amount: Money;
    unmatched: Money;
    matches: BankMatch[];
}

export interface Candidate {
    voucher: Voucher;
    unmatched: Money;
    score: number;
    signals: string[];
    party: string;
}

export interface SuspenseRow {
    id: number;
    amount: Money;
    is_receipt: boolean;
    reason: string;
    status: string;
    owner: string | null;
    date: string;
    age_days: number;
    statement_line_id: number | null;
    resolution_note: string;
}

export type Params = Record<string, string | number | undefined | null>;

function clean(params: Params): Record<string, string | number> {
    const out: Record<string, string | number> = {};
    for (const [k, v] of Object.entries(params)) {
        if (v !== undefined && v !== null && v !== "") out[k] = v;
    }
    return out;
}

const BASE = "accounting";

export async function acctGet<T>(path: string, params: Params = {}): Promise<T> {
    const { data } = await api.get(`${BASE}/${path}`, { params: clean(params) });
    return data as T;
}

export async function acctPost<T>(path: string, body: unknown = {}): Promise<T> {
    const { data } = await api.post(`${BASE}/${path}`, body);
    return data as T;
}

export async function acctPatch<T>(path: string, body: unknown = {}): Promise<T> {
    const { data } = await api.patch(`${BASE}/${path}`, body);
    return data as T;
}

export async function acctDelete<T>(path: string): Promise<T> {
    const { data } = await api.delete(`${BASE}/${path}`);
    return data as T;
}

export async function uploadStatement(bankId: number, file: File, columnMapping?: Record<string, string>) {
    const form = new FormData();
    form.append("file", file);
    if (columnMapping && Object.keys(columnMapping).length) form.append("column_mapping", JSON.stringify(columnMapping));
    const { data } = await api.post(`${BASE}/bank-accounts/${bankId}/statements/`, form, {
        headers: { "Content-Type": "multipart/form-data" },
    });
    return data as { id: number; rows_total: number; rows_new: number; rows_duplicate: number; rows_rejected: number;
        errors: { row: number; error: string }[]; column_mapping: Record<string, string> };
}

/** Query-key factory for the accounting workspace (invalidate by entity). */
export const acctKeys = {
    all: ["accounting"] as const,
    entity: (entityId: number | null) => ["accounting", entityId] as const,
    of: (entityId: number | null, ...rest: unknown[]) => ["accounting", entityId, ...rest] as const,
};

/* ---- Frontend round 2026-11-17: shapes of reports/dashboard/, parties/summary/, audit/ ---- */

/** GET reports/dashboard/ (selectors/reports.py dashboard()). */
export interface AccountingDashboardData {
    entity_id: number; start: string; end: string;
    sales: Money; purchases: Money; gross_profit: Money; net_profit: Money; bank_balance: Money; cash_balance: Money;
    receivables: Money; payables: Money; overdue_receivables: Money; overdue_payables: Money; draft_vouchers: number;
    unposted_invoices: number; unmatched_bank_lines: number; open_suspense: number; gst_net_payable: Money;
    tds_payable: Money; loan_outstanding: Money;
    /** Additive: posted payments / receipts not yet allocated to bills. Absent on older servers. */
    advances_paid?: Money; advances_received?: Money;
}

/** One row of GET parties/summary/ (selectors/reports.py party_summary()). Balance is debit-positive. */
export interface PartySummaryRow {
    party_id: number; party: string; gstin: string | null; account_id: number; account_code: string;
    balance: Money; receivable: Money; payable: Money; open_bills: number; open_payable_bills: number;
    is_customer: boolean; is_supplier: boolean; is_active: boolean;
}

export interface PartySummary {
    as_of: string;
    parties: PartySummaryRow[];
    totals: { debit_balance: Money; credit_balance: Money; receivable: Money; payable: Money };
}

/** One row of GET audit/ (paged). */
export interface AuditEvent {
    id: number; action: string; object_type: string; object_id: number | null; at: string;
    detail: Record<string, unknown>; actor: string | null;
}

export interface AccountGroup { id: number; code: string; name: string; nature: string; report_head: string }

/** GET accounts/ */
export interface ChartData {
    accounts: Account[];
    groups: AccountGroup[];
    cost_centres: { id: number; code: string; name: string }[];
}

/** One row of GET reports/trial-balance/ (used for per-ledger balances on master screens). */
export interface TrialBalanceRow {
    account_id: number | null; code: string; name: string; group: string; nature: string; kind: string;
    opening_debit: Money; opening_credit: Money; debit: Money; credit: Money; closing_debit: Money; closing_credit: Money;
}
