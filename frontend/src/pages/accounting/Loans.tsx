import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { acctGet, acctKeys, acctPost, type BankAccount, type Money } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { useGuardedAction } from "./useGuardedAction";
import { isMoneyInput } from "./money";
import PartyPicker, { type Party } from "./PartyPicker";
import { Amount, DataGrid, Field, inputCls, notifyError, Panel, QueryState, StatusBadge } from "./ui";

interface Loan {
    id: number; party: string; direction: "GIVEN" | "TAKEN"; loan_type: string; principal: Money; interest_rate: Money; compound: boolean;
    start_date: string; maturity_date: string | null; status: string; principal_outstanding: Money; interest_outstanding: Money;
    principal_account_id: number; interest_account_id: number;
    accruals: { period_start: string; period_end: string; amount: Money; voucher_id: number | null }[];
}

const today = () => new Date().toISOString().slice(0, 10);

function LoanActions({ loan, onDone }: { loan: Loan; onDone: () => void }) {
    const [f, setF] = useState({ date: today(), principal: "", interest: "", tds: "" });
    const { guard, dialog } = useGuardedAction();
    const act = useMutation({
        mutationFn: (action: string) => acctPost(`loans/${loan.id}/${action}/`, { ...f, principal: f.principal || "0", interest: f.interest || "0", tds: f.tds || "0" }),
        onSuccess: (_d, a) => { toast.success(`${a} posted`); onDone(); }, onError: notifyError,
    });
    if (loan.status === "CLOSED") return <span className="text-xs text-slate-500">Closed</span>;
    return (
        <div className="flex flex-wrap items-end gap-1">
            <input type="date" className={`${inputCls} w-36`} aria-label="Date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} />
            <Button size="sm" variant="outline" disabled={act.isPending} onClick={() => void guard({
                title: "Accrue interest", confirmText: "Accrue", message: `Post interest on loan with ${loan.party} up to ${f.date}?`,
            }, () => act.mutate("accrue"))}>Accrue to date</Button>
            <input inputMode="decimal" className={`${inputCls} w-28`} placeholder="Principal" aria-label="Principal repaid" value={f.principal} onChange={(e) => setF({ ...f, principal: e.target.value })} />
            <input inputMode="decimal" className={`${inputCls} w-24`} placeholder="Interest" aria-label="Interest paid" value={f.interest} onChange={(e) => setF({ ...f, interest: e.target.value })} />
            <input inputMode="decimal" className={`${inputCls} w-20`} placeholder="TDS" aria-label="TDS" value={f.tds} onChange={(e) => setF({ ...f, tds: e.target.value })} />
            <Button size="sm" disabled={!(f.principal || f.interest) || act.isPending} onClick={() => void guard({
                title: "Record repayment", confirmText: "Post",
                message: `Principal ₹ ${f.principal || "0"}, interest ₹ ${f.interest || "0"}, TDS ₹ ${f.tds || "0"} on ${f.date}?`,
            }, () => act.mutate("repay"))}>Record repayment</Button>
            <Button size="sm" variant="ghost" disabled={act.isPending} onClick={() => void guard({
                title: "Close loan", severity: "danger", confirmText: "Close", message: "Close the loan? No further interest will accrue.",
            }, () => act.mutate("close"))}>Close</Button>
            {dialog}
        </div>
    );
}

export default function Loans() {
    const { entityId } = useAccounting();
    const qc = useQueryClient();
    const refresh = () => qc.invalidateQueries({ queryKey: acctKeys.entity(entityId) });
    const loans = useQuery({ queryKey: acctKeys.of(entityId, "loans"), queryFn: () => acctGet<Loan[]>("loans/", { entity: entityId }) });
    const banks = useQuery({ queryKey: acctKeys.of(entityId, "banks"), queryFn: () => acctGet<BankAccount[]>("bank-accounts/", { entity: entityId }) });
    const [party, setParty] = useState<Party | null>(null);
    const [f, setF] = useState({ direction: "TAKEN", principal: "", interest_rate: "", start_date: today(), maturity_date: "", bank_account_id: "", compound: false, repayment_type: "FLEXIBLE", loan_type: "" });
    const create = useMutation({
        mutationFn: () => acctPost("loans/", { entity: entityId, party_id: party?.id, ...f, maturity_date: f.maturity_date || null }),
        onSuccess: () => { toast.success("Loan created and disbursed"); void refresh(); }, onError: notifyError,
    });
    return (
        <div className="space-y-4">
            <Panel title="New loan">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-5">
                    <Field label="Direction"><select className={inputCls} value={f.direction} onChange={(e) => setF({ ...f, direction: e.target.value })}>
                        <option value="TAKEN">Loan taken (borrowing)</option><option value="GIVEN">Loan given</option></select></Field>
                    <div className="sm:col-span-2"><Field label="Lender / borrower"><PartyPicker value={party} onChange={setParty} /></Field></div>
                    <Field label="Principal"><input inputMode="decimal" className={inputCls} value={f.principal} onChange={(e) => setF({ ...f, principal: e.target.value })} /></Field>
                    <Field label="Interest % p.a."><input inputMode="decimal" className={inputCls} value={f.interest_rate} onChange={(e) => setF({ ...f, interest_rate: e.target.value })} /></Field>
                    <Field label="Start"><input type="date" className={inputCls} value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} /></Field>
                    <Field label="Maturity"><input type="date" className={inputCls} value={f.maturity_date} onChange={(e) => setF({ ...f, maturity_date: e.target.value })} /></Field>
                    <Field label="Bank"><select className={inputCls} value={f.bank_account_id} onChange={(e) => setF({ ...f, bank_account_id: e.target.value })}>
                        <option value="">Select…</option>{(banks.data ?? []).map((b) => <option key={b.id} value={b.id}>{b.bank_name} {b.account_number}</option>)}</select></Field>
                    <Field label="Repayment"><select className={inputCls} value={f.repayment_type} onChange={(e) => setF({ ...f, repayment_type: e.target.value })}>
                        <option>FLEXIBLE</option><option>EMI</option><option>BULLET</option></select></Field>
                    <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={f.compound} onChange={(e) => setF({ ...f, compound: e.target.checked })} /> Compound unpaid interest</label>
                </div>
                <p className="mt-2 text-xs text-slate-500">Interest is actual/365 on each day's closing balance, posted monthly. Principal never goes to P&amp;L.</p>
                <div className="mt-3 text-right"><Button disabled={!party || !f.bank_account_id || !isMoneyInput(f.principal) || !f.interest_rate || create.isPending} onClick={() => create.mutate()}>Create &amp; disburse</Button></div>
            </Panel>
            <Panel title="Loan register">
                <QueryState isLoading={loans.isLoading} error={loans.error}>
                    <DataGrid rows={loans.data ?? []} rowKey={(l) => l.id} empty="No loans." caption="Loans" columns={[
                        { key: "p", header: "Party", cell: (l) => l.party },
                        { key: "d", header: "Type", cell: (l) => (l.direction === "GIVEN" ? "Given" : "Taken") },
                        { key: "r", header: "Rate", numeric: true, cell: (l) => `${l.interest_rate}%` },
                        { key: "po", header: "Principal o/s", numeric: true, cell: (l) => <Amount value={l.principal_outstanding} to={`/accounting/reports/general-ledger?account=${l.principal_account_id}`} /> },
                        { key: "io", header: "Interest o/s", numeric: true, cell: (l) => <Amount value={l.interest_outstanding} to={`/accounting/reports/general-ledger?account=${l.interest_account_id}`} /> },
                        { key: "s", header: "Status", cell: (l) => <StatusBadge status={l.status === "ACTIVE" ? "OPEN" : "RESOLVED"} /> },
                        { key: "a", header: "Actions", cell: (l) => <LoanActions loan={l} onDone={() => void refresh()} /> },
                        { key: "x", header: "Last accrual", cell: (l) => { const a = l.accruals[l.accruals.length - 1]; return a ? (a.voucher_id ? <Link className="text-blue-700" to={`/accounting/vouchers/${a.voucher_id}`}>{a.period_end}</Link> : a.period_end) : "—"; } },
                    ]} />
                </QueryState>
            </Panel>
        </div>
    );
}
