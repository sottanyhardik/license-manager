import { lazy, Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import type { Financial } from "@/pages/dashboardContract";
import { formatMoney, formatPercent } from "./formatters";
import type { BarPlotDatum } from "./BarPlot";

const BarPlot = lazy(() => import("./BarPlot"));

type FinancialOverviewProps = {
    financial: Financial;
    licencesHref: string;
};

type BridgeLine = {
    key: keyof Financial["bridge"];
    label: string;
    sign: "+" | "−" | "=";
    tone: "neutral" | "debit" | "credit" | "total";
};

/**
 * Values are shown exactly as the engine returned them, in the order of the
 * bridge identity. Nothing is recomputed here: the chart only plots them.
 */
const BRIDGE_LINES: BridgeLine[] = [
    { key: "authorized", label: "Authorised CIF", sign: "=", tone: "total" },
    { key: "previous_owner_utilisation", label: "Previous-owner utilisation", sign: "−", tone: "debit" },
    { key: "purchased_cif", label: "Purchased CIF", sign: "+", tone: "credit" },
    { key: "sale_utilisation", label: "Sale utilisation", sign: "−", tone: "debit" },
    { key: "boe_utilisation", label: "BOE utilisation", sign: "−", tone: "debit" },
    { key: "reserved", label: "Reserved (allotments)", sign: "−", tone: "debit" },
    { key: "rounding", label: "Rounding", sign: "+", tone: "neutral" },
    { key: "raw_available", label: "Available before floor", sign: "=", tone: "total" },
    { key: "over_utilisation_floor", label: "Over-utilisation floor", sign: "+", tone: "credit" },
    { key: "available", label: "Available CIF", sign: "=", tone: "total" },
];

const TONE_COLOUR: Record<BridgeLine["tone"], string> = {
    neutral: "#64748b",
    debit: "#dc2626",
    credit: "#16a34a",
    total: "#2563eb",
};

function toChartValue(value: string | undefined): number {
    const number = Number(value);
    return Number.isFinite(number) ? number : 0;
}

export default function FinancialOverview({ financial, licencesHref }: FinancialOverviewProps) {
    const { bridge } = financial;
    const chartData: BarPlotDatum[] = BRIDGE_LINES.map((line) => ({
        name: line.label,
        value: toChartValue(bridge[line.key]),
        colour: TONE_COLOUR[line.tone],
    }));

    return (
        <div className="space-y-4 p-4">
            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                <div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Committed</p>
                    <p className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                        {formatPercent(financial.committed_pct)}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">(Utilised + reserved) ÷ authorised</p>
                </div>
                <div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Licences in scope</p>
                    <p className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                        {financial.licences_in_scope.toLocaleString("en-US")}
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Over-utilised licences</p>
                    <p className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                        {financial.over_utilised_licences.toLocaleString("en-US")}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Floored at zero</p>
                </div>
                <div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Expired licences, available</p>
                    <p className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                        {formatMoney(financial.expired_available_cif, "cif")}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Included in available CIF</p>
                </div>
                <div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Balance source</p>
                    <p className="text-xs text-slate-700 dark:text-slate-300">Financial available balance (canonical engine)</p>
                </div>
            </div>

            <div role="img" aria-label="Bridge from authorised CIF to available CIF. The table below lists the same values.">
                <Suspense fallback={<Skeleton className="h-72 w-full" />}>
                    <BarPlot
                        data={chartData}
                        layout="vertical"
                        height={288}
                        labelWidth={170}
                        valueFormatter={(value) => formatMoney(value, "cif")}
                    />
                </Suspense>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <caption className="sr-only">Authorised to available CIF bridge</caption>
                    <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600 dark:bg-slate-900/50 dark:text-slate-300">
                        <tr className="border-b border-slate-200 dark:border-slate-800">
                            <th scope="col" className="px-4 py-2">Line</th>
                            <th scope="col" className="px-4 py-2 text-right">Amount (FC)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {BRIDGE_LINES.map((line) => (
                            <tr key={line.key} className="border-t border-slate-200 dark:border-slate-800">
                                <th scope="row" className="px-4 py-2 text-left text-xs font-normal text-slate-700 dark:text-slate-300">
                                    <span aria-hidden="true" className="mr-2 inline-block w-3 text-center font-semibold">{line.sign}</span>
                                    {line.label}
                                </th>
                                <td className="px-4 py-2 text-right text-xs tabular-nums text-slate-900 dark:text-slate-100">
                                    {formatMoney(bridge[line.key], "cif")}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <p className="text-xs text-slate-500 dark:text-slate-400">
                Reserved CIF is the engine&apos;s outstanding allotment figure, which does not yet release the unused part of a partly used
                allotment (ISS-008). Previous-owner rules are pending the business decision DEC-010.{" "}
                <a href={licencesHref} className="font-medium text-blue-600 hover:underline dark:text-blue-400">
                    Open licences
                </a>
            </p>
        </div>
    );
}
