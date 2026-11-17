import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { acctPost, type Money } from "@/api/accountingApi";

import { formatMoney, isMoneyInput, isZero, sumMoney } from "./money";
import PartyPicker, { type Party } from "./PartyPicker";
import { Amount, inputCls, notifyError, Panel } from "./ui";

/** The bank line being split (a "BU : <batch>" bulk upload, or any line paid to several parties). */
export interface SplitLine { id: number; txn_date: string; narration: string; amount: Money; direction: "RECEIPT" | "PAYMENT" }
export interface SplitResult { line_id: number; payments: { id: number; voucher: string; party_id: number; party: string; amount: Money }[] }

interface PlanRow {
    party_id: number; party: string; amount: Money; advance: Money;
    allocations: { invoice_id: number; number: string; date: string; outstanding: Money; amount: Money }[];
}
interface Row { key: number; party: Party | null; amount: string }

let nextKey = 1;
const blank = (): Row => ({ key: nextKey++, party: null, amount: "" });

/**
 * Split one bank line into one payment/receipt per party. Each row settles that party's bills oldest
 * first (any excess = advance). Save is enabled only when the rows add up to the bank amount; the
 * server books every row or none and matches them all to the line.
 */
export default function BankLineSplit({ line, onDone, onCancel }: {
    line: SplitLine; onDone: (r: SplitResult) => void; onCancel: () => void;
}) {
    const [rows, setRows] = useState<Row[]>([blank(), blank()]);
    const complete = rows.filter((r) => r.party && isMoneyInput(r.amount) && !isZero(r.amount));
    const allComplete = complete.length === rows.length && rows.length > 0;
    const total = sumMoney(complete.map((r) => r.amount));
    const left = sumMoney([line.amount, `-${total}`]);
    const payload = complete.map((r) => ({ party_id: (r.party as Party).id, amount: r.amount }));
    const plan = useQuery({
        queryKey: ["accounting", "split-plan", line.id, payload],
        queryFn: () => acctPost<{ rows: PlanRow[] }>(`statement-lines/${line.id}/split/`, { rows: payload, dry_run: true }),
        enabled: payload.length > 0,
    });
    const save = useMutation({
        mutationFn: () => acctPost<SplitResult>(`statement-lines/${line.id}/split/`, { rows: payload }),
        onSuccess: onDone,
        onError: notifyError,
    });
    const update = (key: number, patch: Partial<Row>) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
    const planFor = (i: number) => { const at = complete.indexOf(rows[i]); return at >= 0 ? plan.data?.rows[at] : undefined; };
    const balanced = allComplete && isZero(left);
    const side = line.direction === "PAYMENT" ? "Paid to" : "Received from";

    return (
        <Panel title={`Split bank line — ${line.txn_date} · ₹ ${formatMoney(line.amount)}`} actions={
            <Button size="sm" variant="ghost" onClick={onCancel}>Close</Button>}>
            <p className="mb-3 break-all text-sm text-slate-600">{line.narration}</p>
            <div className="space-y-3" role="group" aria-label="Split rows">
                {rows.map((r, i) => {
                    const pr = r.party && isMoneyInput(r.amount) ? planFor(i) : undefined;
                    return (
                        <div key={r.key} className="grid grid-cols-1 gap-2 rounded-lg border border-slate-200 p-3 sm:grid-cols-[minmax(0,2fr)_10rem_auto]">
                            <PartyPicker value={r.party} label={`${side} (row ${i + 1})`} onChange={(p) => update(r.key, { party: p })} />
                            <input inputMode="decimal" className={`${inputCls} text-right`} aria-label={`Amount row ${i + 1}`} placeholder="Amount"
                                   value={r.amount} onChange={(e) => update(r.key, { amount: e.target.value })} />
                            <Button size="sm" variant="ghost" className="text-red-700" disabled={rows.length === 1}
                                    aria-label={`Remove row ${i + 1}`} onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))}>Remove</Button>
                            {pr && (
                                <div className="text-xs text-slate-600 sm:col-span-3">
                                    {pr.allocations.length === 0 && <span>No open bills on or before {line.txn_date}.</span>}
                                    {pr.allocations.map((a) => <span key={a.invoice_id} className="mr-3">{a.number} · <Amount value={a.amount} /></span>)}
                                    {!isZero(pr.advance) && <span className="text-amber-700">Advance <Amount value={pr.advance} /></span>}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
                <div className="flex items-center gap-3">
                    <Button size="sm" variant="outline" onClick={() => setRows((rs) => [...rs, blank()])}>Add row</Button>
                    {allComplete && !left.startsWith("-") && !isZero(left) && (
                        <Button size="sm" variant="ghost" onClick={() => update(rows[rows.length - 1].key, { amount: sumMoney([rows[rows.length - 1].amount, left]) })}>
                            Put remaining ₹ {formatMoney(left)} on the last row</Button>)}
                </div>
                <span role="status" aria-live="polite">
                    Rows <b>{formatMoney(total)}</b> of <b>{formatMoney(line.amount)}</b> ·{" "}
                    {isZero(left) ? <b className="text-emerald-700">balanced</b>
                        : <b className={left.startsWith("-") ? "text-red-700" : "text-amber-700"}>{left.startsWith("-") ? "over by" : "left"} ₹ {formatMoney(left.replace("-", ""))}</b>}
                </span>
                <Button disabled={!balanced || save.isPending} onClick={() => save.mutate()}>
                    {save.isPending ? "Saving…" : `Save split (${rows.length} ${line.direction === "PAYMENT" ? "payments" : "receipts"})`}</Button>
            </div>
        </Panel>
    );
}
