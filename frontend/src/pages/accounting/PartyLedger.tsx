import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { acctGet, acctKeys, type Money } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { drCr } from "./money";
import PartyPicker, { type Party } from "./PartyPicker";
import { Amount, DataGrid, Field, Panel, QueryState, StatusBadge } from "./ui";

export interface LedgerRow {
    voucher_id: number; voucher_number: string; voucher_type: string; date: string; narration: string; debit: Money;
    credit: Money; balance: Money; source_type: string; source_id: number | null; trade_id: number | null; status: string;
}
export interface Ledger { account_id: number | null; code?: string; name?: string; opening: Money; closing: Money; rows: LedgerRow[] }

export function LedgerTable({ ledger, voucherBase = "../vouchers" }: { ledger: Ledger; voucherBase?: string }) {
    return (
        <DataGrid rows={ledger.rows} rowKey={(r) => `${r.voucher_id}-${r.date}-${r.balance}`} caption="Ledger" empty="No entries in this period."
                  footer={<tr><td className="px-3 py-1.5" colSpan={5}>Opening {drCr(ledger.opening)}</td>
                      <td className="px-3 py-1.5 text-right" colSpan={2}>Closing {drCr(ledger.closing)}</td></tr>}
                  columns={[
                      { key: "date", header: "Date", cell: (r) => r.date },
                      { key: "v", header: "Voucher", cell: (r) => <Link className="text-blue-700 hover:underline" to={`${voucherBase}/${r.voucher_id}`}>{r.voucher_number}</Link> },
                      { key: "t", header: "Type", cell: (r) => r.voucher_type.replace(/_/g, " ") },
                      { key: "n", header: "Narration", cell: (r) => <span className="line-clamp-1">{r.narration}</span> },
                      { key: "tr", header: "Trade", cell: (r) => (r.trade_id ? <Link className="text-blue-700" to={`/trades/${r.trade_id}/edit`}>#{r.trade_id}</Link> : "") },
                      { key: "dr", header: "Debit", numeric: true, cell: (r) => <Amount value={r.debit} blankZero /> },
                      { key: "cr", header: "Credit", numeric: true, cell: (r) => <Amount value={r.credit} blankZero /> },
                      { key: "bal", header: "Balance", numeric: true, cell: (r) => drCr(r.balance) },
                  ]} />
    );
}

interface PartyLedgerData extends Ledger {
    open_bills: { invoice_id: number; number: string; kind: string; date: string; due_date: string | null; amount: Money;
        outstanding: Money; status: string; trade_id: number | null }[];
}

export default function PartyLedger() {
    const { entityId, scope } = useAccounting();
    const [party, setParty] = useState<Party | null>(null);
    const q = useQuery({
        queryKey: acctKeys.of(entityId, "party-ledger", party?.id, scope.fy),
        queryFn: () => acctGet<PartyLedgerData>("reports/party-ledger/", { ...scope, party: party?.id }),
        enabled: !!party,
    });
    return (
        <div className="space-y-4">
            <Panel title="Party ledger (customer / supplier / agent — one ledger per party)">
                <div className="max-w-xl"><Field label="Party"><PartyPicker value={party} onChange={setParty} /></Field></div>
            </Panel>
            {party && (
                <QueryState isLoading={q.isLoading} error={q.error}>
                    {q.data && (<>
                        <Panel title={`Ledger — ${party.name}`}><LedgerTable ledger={q.data} /></Panel>
                        <Panel title="Outstanding bills (bill-wise)">
                            <DataGrid rows={q.data.open_bills} rowKey={(b) => b.invoice_id} empty="Nothing outstanding." caption="Open bills" columns={[
                                { key: "no", header: "Bill", cell: (b) => <Link className="text-blue-700 hover:underline" to={`../invoices/${b.invoice_id}`}>{b.number}</Link> },
                                { key: "k", header: "Kind", cell: (b) => b.kind.replace(/_/g, " ") },
                                { key: "d", header: "Date", cell: (b) => b.date },
                                { key: "due", header: "Due", cell: (b) => b.due_date ?? "—" },
                                { key: "a", header: "Amount", numeric: true, cell: (b) => <Amount value={b.amount} /> },
                                { key: "o", header: "Outstanding", numeric: true, cell: (b) => <Amount value={b.outstanding} /> },
                                { key: "s", header: "Status", cell: (b) => <StatusBadge status={b.status} /> },
                            ]} />
                        </Panel>
                    </>)}
                </QueryState>
            )}
        </div>
    );
}
