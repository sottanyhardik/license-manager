import { Fragment, useState, type ReactNode } from "react";
import { Link, NavLink, Route, Routes, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { acctGet, acctKeys, type Account, type Money } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { drCr, formatMoney, isMoneyInput } from "./money";
import { LedgerTable, type Ledger } from "./PartyLedger";
import { Amount, DataGrid, Field, inputCls, Panel, QueryState, StatusBadge } from "./ui";

const REPORTS = [
    ["trial-balance", "Trial Balance"], ["profit-loss", "Profit & Loss"], ["balance-sheet", "Balance Sheet"],
    ["cash-flow", "Cash Flow"], ["general-ledger", "General Ledger"], ["receivables-ageing", "Receivables Ageing"],
    ["payables-ageing", "Payables Ageing"], ["register", "Registers"], ["gst", "GST"], ["tds", "TDS"],
    ["trade-profitability", "Trade Profitability"], ["bank-book", "Bank Book"], ["cash-book", "Cash Book"],
    ["consolidated", "Consolidated"],
] as const;

function useReport<T>(name: string, extra: Record<string, string | number | undefined> = {}, enabled = true) {
    const { entityId, scope } = useAccounting();
    return useQuery({
        queryKey: acctKeys.of(entityId, "report", name, scope.fy, extra),
        queryFn: () => acctGet<T>(`reports/${name}/`, { ...scope, ...extra }),
        enabled,
    });
}

const glLink = (accountId: number | null) => (accountId ? `/accounting/reports/general-ledger?account=${accountId}` : undefined);

interface TbRow { account_id: number | null; code: string; name: string; group: string; opening_debit: Money; opening_credit: Money;
    debit: Money; credit: Money; closing_debit: Money; closing_credit: Money }

function TrialBalance() {
    const q = useReport<{ rows: TbRow[]; totals: Record<string, Money>; balanced: boolean }>("trial-balance");
    return (
        <QueryState isLoading={q.isLoading} error={q.error}>
            {q.data && (
                <Panel title={<span>Trial Balance <StatusBadge status={q.data.balanced ? "MATCHED" : "EXCEPTION"} /></span>}>
                    <DataGrid rows={q.data.rows} rowKey={(r) => `${r.account_id}-${r.code}`} caption="Trial balance" columns={[
                        { key: "c", header: "Code", cell: (r) => r.code },
                        { key: "n", header: "Account", cell: (r) => (r.account_id ? <Link className="text-blue-700 hover:underline" to={glLink(r.account_id)!}>{r.name}</Link> : r.name) },
                        { key: "g", header: "Group", cell: (r) => r.group },
                        { key: "od", header: "Opening Dr", numeric: true, cell: (r) => <Amount value={r.opening_debit} blankZero /> },
                        { key: "oc", header: "Opening Cr", numeric: true, cell: (r) => <Amount value={r.opening_credit} blankZero /> },
                        { key: "d", header: "Debit", numeric: true, cell: (r) => <Amount value={r.debit} blankZero /> },
                        { key: "cr", header: "Credit", numeric: true, cell: (r) => <Amount value={r.credit} blankZero /> },
                        { key: "cd", header: "Closing Dr", numeric: true, cell: (r) => <Amount value={r.closing_debit} blankZero /> },
                        { key: "cc", header: "Closing Cr", numeric: true, cell: (r) => <Amount value={r.closing_credit} blankZero /> },
                    ]} footer={<tr><td className="px-3 py-1.5" colSpan={3}>Total</td>
                        {(["opening_debit", "opening_credit", "debit", "credit", "closing_debit", "closing_credit"] as const).map((k) => (
                            <td key={k} className="px-3 py-1.5 text-right"><Amount value={q.data.totals[k]} /></td>))}</tr>} />
                </Panel>
            )}
        </QueryState>
    );
}

interface PlLine { label: string; amount: Money; accounts: { account_id: number; code: string; name: string; amount: Money }[] }
interface Pl { lines: Record<string, PlLine>; net_sales: Money; cogs: Money; gross_profit: Money; net_profit: Money; agrees_with_ledger: boolean }

function PlSection({ title, keys, pl }: { title: string; keys: string[]; pl: Pl }) {
    return (
        <>
            <tr><th colSpan={2} className="bg-slate-50 px-3 py-1.5 text-left text-xs uppercase tracking-wider text-slate-500">{title}</th></tr>
            {keys.map((k) => pl.lines[k]).filter((l) => l && l.amount !== "0.00").map((l) => (
                <Fragment key={l.label}>
                    <tr><td className="px-3 py-1 font-medium">{l.label}</td><td className="px-3 py-1 text-right"><Amount value={l.amount} /></td></tr>
                    {l.accounts.map((a) => (
                        <tr key={a.account_id} className="text-xs text-slate-500"><td className="px-6 py-0.5"><Link className="hover:underline" to={glLink(a.account_id)!}>{a.code} {a.name}</Link></td>
                            <td className="px-3 text-right tabular-nums">{formatMoney(a.amount)}</td></tr>))}
                </Fragment>
            ))}
        </>
    );
}

function ProfitLoss() {
    const q = useReport<Pl>("profit-loss");
    const monthly = useReport<{ month: string; net_sales: Money; gross_profit: Money; net_profit: Money }[]>("profit-loss-monthly");
    const total = (label: string, v: Money) => (
        <tr className="border-t-2 border-slate-300 font-semibold"><td className="px-3 py-1.5">{label}</td><td className="px-3 py-1.5 text-right"><Amount value={v} /></td></tr>);
    return (
        <QueryState isLoading={q.isLoading} error={q.error}>
            {q.data && (
                <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
                    <Panel title={<span>Profit &amp; Loss <StatusBadge status={q.data.agrees_with_ledger ? "MATCHED" : "EXCEPTION"} /></span>}>
                        <table className="w-full text-sm"><tbody>
                            <PlSection title="Revenue" keys={["gross_sales", "sales_returns"]} pl={q.data} />
                            {total("Net sales", q.data.net_sales)}
                            <PlSection title="Cost of goods sold" keys={["purchases", "stock_change", "freight", "insurance", "customs"]} pl={q.data} />
                            {total("Gross profit", q.data.gross_profit)}
                            <PlSection title="Expenses" keys={["commission_expense", "bank_charges", "operating_expenses", "interest_expense"]} pl={q.data} />
                            <PlSection title="Other income" keys={["forex", "commission_income", "interest_income", "other_income"]} pl={q.data} />
                            {total("Net profit", q.data.net_profit)}
                        </tbody></table>
                    </Panel>
                    <Panel title="By month">
                        <DataGrid rows={monthly.data ?? []} rowKey={(m) => m.month} caption="Monthly P&L" columns={[
                            { key: "m", header: "Month", cell: (m) => m.month },
                            { key: "s", header: "Net sales", numeric: true, cell: (m) => <Amount value={m.net_sales} blankZero /> },
                            { key: "g", header: "Gross", numeric: true, cell: (m) => <Amount value={m.gross_profit} blankZero /> },
                            { key: "n", header: "Net", numeric: true, cell: (m) => <Amount value={m.net_profit} blankZero /> },
                        ]} />
                    </Panel>
                </div>
            )}
        </QueryState>
    );
}

interface BsSide { head: string; label: string; amount: Money }

function BalanceSheet() {
    const q = useReport<{ assets: BsSide[]; liabilities: BsSide[]; total_assets: Money; total_liabilities: Money; balanced: boolean }>("balance-sheet");
    const side = (title: string, rows: BsSide[], total: Money) => (
        <Panel title={title}>
            <DataGrid rows={rows} rowKey={(r) => r.head} caption={title} columns={[
                { key: "l", header: "Head", cell: (r) => r.label },
                { key: "a", header: "Amount", numeric: true, cell: (r) => <Amount value={r.amount} /> },
            ]} footer={<tr><td className="px-3 py-1.5">Total</td><td className="px-3 py-1.5 text-right"><Amount value={total} /></td></tr>} />
        </Panel>);
    return (
        <QueryState isLoading={q.isLoading} error={q.error}>
            {q.data && (<>
                <p className="mb-2"><StatusBadge status={q.data.balanced ? "MATCHED" : "EXCEPTION"} /> <span className="text-sm text-slate-600">Assets = Liabilities + Capital + Profit &amp; Loss</span></p>
                <div className="grid gap-4 lg:grid-cols-2">
                    {side("Liabilities & capital", q.data.liabilities, q.data.total_liabilities)}
                    {side("Assets", q.data.assets, q.data.total_assets)}
                </div>
            </>)}
        </QueryState>
    );
}

function CashFlow() {
    const q = useReport<{ opening_cash: Money; closing_cash: Money; sections: Record<string, Money>; detail: Record<string, Record<string, Money>>; net_change: Money; agrees_with_ledger: boolean }>("cash-flow");
    return (
        <QueryState isLoading={q.isLoading} error={q.error}>
            {q.data && (
                <Panel title={<span>Cash flow (direct method) <StatusBadge status={q.data.agrees_with_ledger ? "MATCHED" : "EXCEPTION"} /></span>}>
                    <table className="w-full max-w-2xl text-sm"><tbody>
                        <tr><td className="px-3 py-1">Opening cash &amp; bank</td><td className="px-3 text-right"><Amount value={q.data.opening_cash} /></td></tr>
                        {(["operating", "investing", "financing"] as const).map((s) => (
                            <Fragment key={s}>
                                <tr className="font-semibold"><td className="px-3 py-1 capitalize">{s} activities</td><td className="px-3 text-right"><Amount value={q.data.sections[s]} /></td></tr>
                                {Object.entries(q.data.detail[s] ?? {}).map(([g, v]) => (
                                    <tr key={`${s}-${g}`} className="text-xs text-slate-500"><td className="px-6">{g}</td><td className="px-3 text-right tabular-nums">{formatMoney(v)}</td></tr>))}
                            </Fragment>))}
                        <tr className="border-t-2 border-slate-300 font-semibold"><td className="px-3 py-1">Closing cash &amp; bank</td><td className="px-3 text-right"><Amount value={q.data.closing_cash} /></td></tr>
                    </tbody></table>
                </Panel>
            )}
        </QueryState>
    );
}

function GeneralLedger() {
    const { entityId } = useAccounting();
    const [params, setParams] = useSearchParams();
    const account = params.get("account") ?? "";
    const accounts = useQuery({ queryKey: acctKeys.of(entityId, "accounts"), queryFn: () => acctGet<{ accounts: Account[] }>("accounts/", { entity: entityId }) });
    const q = useReport<Ledger>("general-ledger", { account }, !!account);
    return (
        <Panel title="General ledger" actions={
            <select className={`${inputCls} w-80`} aria-label="Account" value={account} onChange={(e) => setParams({ account: e.target.value })}>
                <option value="">Choose an account…</option>
                {(accounts.data?.accounts ?? []).map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}
            </select>}>
            {account ? <QueryState isLoading={q.isLoading} error={q.error}>{q.data && <LedgerTable ledger={q.data} voucherBase="/accounting/vouchers" />}</QueryState>
                : <p className="text-sm text-slate-500">Select an account, or click any figure in another report.</p>}
        </Panel>
    );
}

interface AgeRow { party_id: number; party: string; not_due: Money; total: Money; [bucket: string]: unknown;
    bills: { invoice_id: number; number: string; due_date: string | null; outstanding: Money; days_overdue: number }[] }

function Ageing({ receivable }: { receivable: boolean }) {
    const q = useReport<{ parties: AgeRow[]; totals: Record<string, Money> }>(receivable ? "receivables-ageing" : "payables-ageing");
    const buckets = ["not_due", "0-30", "31-60", "61-90", "91-180", "181-+"];
    return (
        <QueryState isLoading={q.isLoading} error={q.error}>
            {q.data && (
                <Panel title={receivable ? "Receivables ageing (by due date)" : "Payables ageing (by due date)"}>
                    <DataGrid rows={q.data.parties} rowKey={(r) => r.party_id} empty="Nothing outstanding." caption="Ageing" columns={[
                        { key: "p", header: "Party", cell: (r) => r.party },
                        ...buckets.map((b) => ({ key: b, header: b === "not_due" ? "Not due" : `${b.replace("-+", "+")} d`, numeric: true,
                            cell: (r: AgeRow) => <Amount value={r[b] as Money} blankZero /> })),
                        { key: "t", header: "Total", numeric: true, cell: (r) => <Amount value={r.total} /> },
                    ]} footer={<tr><td className="px-3 py-1.5">Total</td>{[...buckets, "total"].map((b) => <td key={b} className="px-3 py-1.5 text-right"><Amount value={q.data.totals[b]} blankZero /></td>)}</tr>} />
                </Panel>
            )}
        </QueryState>
    );
}

interface RegRow { invoice_id: number; number: string; date: string; kind: string; party: string; party_gstin: string | null; taxable: Money;
    cgst: Money; sgst: Money; igst: Money; gross: Money; tds_section: string; tds: Money; net: Money; status: string; outstanding: Money;
    voucher_id: number | null; voucher_number: string | null }

function RegisterTable({ rows, totals }: { rows: RegRow[]; totals?: Record<string, Money> }) {
    return (
        <DataGrid rows={rows} rowKey={(r) => r.invoice_id} empty="No documents in this period." caption="Register" columns={[
            { key: "d", header: "Date", cell: (r) => r.date },
            { key: "n", header: "Number", cell: (r) => <Link className="text-blue-700 hover:underline" to={`/accounting/invoices/${r.invoice_id}`}>{r.number}</Link> },
            { key: "p", header: "Party", cell: (r) => r.party },
            { key: "g", header: "GSTIN", cell: (r) => r.party_gstin ?? "" },
            { key: "t", header: "Taxable", numeric: true, cell: (r) => <Amount value={r.taxable} /> },
            { key: "cg", header: "CGST", numeric: true, cell: (r) => <Amount value={r.cgst} blankZero /> },
            { key: "sg", header: "SGST", numeric: true, cell: (r) => <Amount value={r.sgst} blankZero /> },
            { key: "ig", header: "IGST", numeric: true, cell: (r) => <Amount value={r.igst} blankZero /> },
            { key: "tds", header: "TDS", numeric: true, cell: (r) => <Amount value={r.tds} blankZero /> },
            { key: "net", header: "Net", numeric: true, cell: (r) => <Amount value={r.net} /> },
            { key: "o", header: "Outstanding", numeric: true, cell: (r) => <Amount value={r.outstanding} blankZero /> },
            { key: "s", header: "Status", cell: (r) => <StatusBadge status={r.status} /> },
        ]} footer={totals && <tr><td className="px-3 py-1.5" colSpan={4}>Total (posted)</td>
            {["taxable", "cgst", "sgst", "igst", "tds", "net", "outstanding"].map((k) => <td key={k} className="px-3 py-1.5 text-right"><Amount value={totals[k] ?? "0"} blankZero /></td>)}<td /></tr>} />
    );
}

function Registers() {
    const [params, setParams] = useSearchParams();
    const kind = params.get("kind") ?? "sales";
    const q = useReport<{ rows: RegRow[]; totals: Record<string, Money> }>("register", { kind });
    return (
        <Panel title="Registers" actions={
            <select className={inputCls} aria-label="Register" value={kind} onChange={(e) => setParams({ kind: e.target.value })}>
                {[["sales", "Sales"], ["purchase", "Purchase"], ["expense", "Expense"], ["commission", "Commission"], ["notes", "Debit/Credit notes"]]
                    .map(([v, l]) => <option key={v} value={v}>{l} register</option>)}</select>}>
            <QueryState isLoading={q.isLoading} error={q.error}>{q.data && <RegisterTable rows={q.data.rows} totals={q.data.totals} />}</QueryState>
        </Panel>
    );
}

function Gst() {
    const q = useReport<{ outward: { rows: RegRow[]; totals: Record<string, Money> }; inward: { rows: RegRow[]; totals: Record<string, Money> };
        output_tax: Money; input_tax: Money; net_payable: Money }>("gst");
    return (
        <QueryState isLoading={q.isLoading} error={q.error}>
            {q.data && (<div className="space-y-4">
                <Panel title="GST summary (from the tax ledgers)">
                    <dl className="grid grid-cols-3 gap-4 text-sm">
                        <div><dt className="text-xs text-slate-500">Output tax</dt><dd><Amount value={q.data.output_tax} /></dd></div>
                        <div><dt className="text-xs text-slate-500">Input tax credit</dt><dd><Amount value={q.data.input_tax} /></dd></div>
                        <div><dt className="text-xs text-slate-500">Net payable</dt><dd className="font-semibold"><Amount value={q.data.net_payable} /></dd></div>
                    </dl>
                    <p className="mt-2 text-xs text-slate-500">Trade-linked licence invoices carry no GST (Bill of Supply). The CA has to confirm this treatment.</p>
                </Panel>
                <Panel title="Outward supplies"><RegisterTable rows={q.data.outward.rows} totals={q.data.outward.totals} /></Panel>
                <Panel title="Inward supplies"><RegisterTable rows={q.data.inward.rows} totals={q.data.inward.totals} /></Panel>
            </div>)}
        </QueryState>
    );
}

function Tds() {
    const q = useReport<{ rows: RegRow[]; by_section: Record<string, Money>; tds_payable: Money; tds_receivable: Money }>("tds");
    return (
        <QueryState isLoading={q.isLoading} error={q.error}>
            {q.data && (<Panel title="TDS register">
                <dl className="mb-3 flex flex-wrap gap-6 text-sm">
                    <div><dt className="text-xs text-slate-500">TDS payable (ledger)</dt><dd><Amount value={q.data.tds_payable} /></dd></div>
                    <div><dt className="text-xs text-slate-500">TDS receivable (ledger)</dt><dd><Amount value={q.data.tds_receivable} /></dd></div>
                    {Object.entries(q.data.by_section).map(([s, v]) => <div key={s}><dt className="text-xs text-slate-500">Section {s}</dt><dd><Amount value={v} /></dd></div>)}
                </dl>
                <RegisterTable rows={q.data.rows} />
            </Panel>)}
        </QueryState>
    );
}

interface ProfitRow { trade_id: number; invoice_number: string; direction: string; licences: string[]; revenue: Money; direct_cost: Money; expenses: Money; profit: Money }

function TradeProfitability() {
    const q = useReport<{ rows: ProfitRow[]; totals: Record<string, Money> }>("trade-profitability");
    return (
        <QueryState isLoading={q.isLoading} error={q.error}>
            {q.data && (<Panel title="Trade-wise profitability (posted ledger lines tagged to each trade, incl. allocated expenses)">
                <DataGrid rows={q.data.rows} rowKey={(r) => r.trade_id} caption="Trade profitability" columns={[
                    { key: "t", header: "Trade", cell: (r) => <Link className="text-blue-700 hover:underline" to={`/trades/${r.trade_id}/edit`}>{r.invoice_number || `#${r.trade_id}`}</Link> },
                    { key: "d", header: "Type", cell: (r) => r.direction },
                    { key: "l", header: "Licences", cell: (r) => <span className="text-xs">{r.licences.join(", ")}</span> },
                    { key: "r", header: "Revenue", numeric: true, cell: (r) => <Amount value={r.revenue} blankZero /> },
                    { key: "c", header: "Direct cost", numeric: true, cell: (r) => <Amount value={r.direct_cost} blankZero /> },
                    { key: "e", header: "Expenses", numeric: true, cell: (r) => <Amount value={r.expenses} blankZero /> },
                    { key: "p", header: "Contribution", numeric: true, cell: (r) => <Amount value={r.profit} /> },
                ]} footer={<tr><td className="px-3 py-1.5" colSpan={3}>Total</td>{["revenue", "direct_cost", "expenses", "profit"].map((k) => <td key={k} className="px-3 py-1.5 text-right"><Amount value={q.data.totals[k]} /></td>)}</tr>} />
                <p className="mt-2 text-xs text-slate-500">A purchase leg shows its cost and the sale leg its revenue. Per-licence margin = the sum of both legs.</p>
            </Panel>)}
        </QueryState>
    );
}

function Books({ cash }: { cash: boolean }) {
    const q = useReport<Ledger[]>(cash ? "cash-book" : "bank-book");
    return (
        <QueryState isLoading={q.isLoading} error={q.error}>
            <div className="space-y-4">{(q.data ?? []).map((l) => (
                <Panel key={l.account_id} title={`${l.code} ${l.name} — closing ${drCr(l.closing)}`}><LedgerTable ledger={l} voucherBase="/accounting/vouchers" /></Panel>))}
                {q.data?.length === 0 && <p className="text-sm text-slate-500">No {cash ? "cash" : "bank"} accounts.</p>}</div>
        </QueryState>
    );
}

function Consolidated() {
    const { entities, fy } = useAccounting();
    const [ids, setIds] = useState<number[]>(entities.map((e) => e.id));
    const [reserve, setReserve] = useState("");
    const sortedIds = [...ids].sort((a, b) => a - b);
    const start = fy ? `${fy.slice(0, 4)}-04-01` : undefined;
    const end = fy ? `${Number(fy.slice(0, 4)) + 1}-03-31` : undefined;
    const q = useQuery({
        queryKey: [...acctKeys.all, "consolidated", sortedIds, fy, reserve],
        queryFn: () => acctGet<{ entities: { entity_id: number; name: string; net_sales: Money; gross_profit: Money; net_profit: Money }[];
            eliminations: { intercompany_sales: Money; intercompany_purchases: Money; eliminated: Money; unmatched_difference: Money; intercompany_balance_difference: Money };
            profit_and_loss: { net_sales: Money; gross_profit: Money; net_profit: Money }; warnings: string[];
            balance_sheet: { total_assets: Money; total_liabilities: Money } }>("reports/consolidated/", { entities: sortedIds.join(","), start, end, stock_reserve: isMoneyInput(reserve) ? reserve : undefined }),
        enabled: ids.length > 0,
    });
    const d = q.data;
    return (
        <Panel title="Consolidated reporting (separate from the statutory books of each entity)">
            <fieldset className="mb-3 flex flex-wrap gap-3 text-sm"><legend className="sr-only">Entities</legend>
                {entities.map((e) => <label key={e.id} className="flex items-center gap-1"><input type="checkbox" checked={ids.includes(e.id)}
                    onChange={(ev) => setIds(ev.target.checked ? [...ids, e.id] : ids.filter((x) => x !== e.id))} /> {e.name}</label>)}
            </fieldset>
            <div className="mb-3 max-w-sm"><Field label="Stock reserve (unrealised intercompany profit in closing stock)"
                hint="Entered by the accountant; cannot be derived from periodic-method books">
                <input inputMode="decimal" className={inputCls} value={reserve} onChange={(e) => setReserve(e.target.value)} /></Field></div>
            <QueryState isLoading={q.isLoading && ids.length > 0} error={q.error}>
                {d && (<div className="space-y-4">
                    {d.warnings.length > 0 && (
                        <ul role="alert" className="list-disc rounded-md border border-amber-200 bg-amber-50 p-3 pl-7 text-sm text-amber-900">
                            {d.warnings.map((w) => <li key={w}>{w}</li>)}</ul>)}
                    <DataGrid rows={d.entities} rowKey={(e) => e.entity_id} caption="Entity comparison" columns={[
                        { key: "n", header: "Entity", cell: (e) => e.name },
                        { key: "s", header: "Net sales", numeric: true, cell: (e) => <Amount value={e.net_sales} /> },
                        { key: "g", header: "Gross profit", numeric: true, cell: (e) => <Amount value={e.gross_profit} /> },
                        { key: "p", header: "Net profit", numeric: true, cell: (e) => <Amount value={e.net_profit} /> },
                    ]} footer={<tr><td className="px-3 py-1.5">Consolidated (after elimination)</td>
                        <td className="px-3 py-1.5 text-right"><Amount value={d.profit_and_loss.net_sales} /></td>
                        <td className="px-3 py-1.5 text-right"><Amount value={d.profit_and_loss.gross_profit} /></td>
                        <td className="px-3 py-1.5 text-right"><Amount value={d.profit_and_loss.net_profit} /></td></tr>} />
                    <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-5">
                        <Stat label="Intercompany sales" value={d.eliminations.intercompany_sales} />
                        <Stat label="Intercompany purchases" value={d.eliminations.intercompany_purchases} />
                        <Stat label="Eliminated" value={d.eliminations.eliminated} />
                        <Stat label="Unmatched intercompany" value={d.eliminations.unmatched_difference} warn />
                        <Stat label="Intercompany balance difference" value={d.eliminations.intercompany_balance_difference} warn />
                    </dl>
                </div>)}
            </QueryState>
        </Panel>
    );
}

function Stat({ label, value, warn }: { label: string; value: Money; warn?: boolean }): ReactNode {
    return <div><dt className="text-xs text-slate-500">{label}</dt><dd className={warn && value !== "0.00" ? "font-semibold text-red-700" : ""}><Amount value={value} /></dd></div>;
}

export default function Reports() {
    const tab = ({ isActive }: { isActive: boolean }) =>
        `whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-medium ${isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`;
    return (
        <div className="space-y-4">
            <nav aria-label="Reports" className="flex flex-wrap gap-1">{REPORTS.map(([to, label]) => <NavLink key={to} to={to} className={tab}>{label}</NavLink>)}</nav>
            <Routes>
                <Route index element={<TrialBalance />} />
                <Route path="trial-balance" element={<TrialBalance />} />
                <Route path="profit-loss" element={<ProfitLoss />} />
                <Route path="balance-sheet" element={<BalanceSheet />} />
                <Route path="cash-flow" element={<CashFlow />} />
                <Route path="general-ledger" element={<GeneralLedger />} />
                <Route path="receivables-ageing" element={<Ageing receivable />} />
                <Route path="payables-ageing" element={<Ageing receivable={false} />} />
                <Route path="register" element={<Registers />} />
                <Route path="gst" element={<Gst />} />
                <Route path="tds" element={<Tds />} />
                <Route path="trade-profitability" element={<TradeProfitability />} />
                <Route path="bank-book" element={<Books cash={false} />} />
                <Route path="cash-book" element={<Books cash />} />
                <Route path="consolidated" element={<Consolidated />} />
            </Routes>
        </div>
    );
}
