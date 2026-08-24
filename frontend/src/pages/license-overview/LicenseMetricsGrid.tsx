import { DollarSign, FileText, Layers, PieChart, Target, TrendingDown, Wallet } from "lucide-react";

import StatCard from "./StatCard";
import { fmtNum } from "./licenseOverviewHelpers";
import type { LicenseOverviewSummaryCounts } from "./types";
import IndividualItemCifSwitch from "@/components/IndividualItemCifSwitch";

interface LicenseMetricsGridProps {
    summary: LicenseOverviewSummaryCounts;
    licenseId: string | number;
    override?: boolean | null;
    canWrite: boolean;
}

/**
 * The Overview tab's metric grid — replaces the old flat 7-`SummaryCard` row.
 * Fixed card order across both rows (never re-sorts, no per-user layout):
 *   Row 1 — Total BOEs / Total Allotments / Planned CIF
 *   Row 2 — Total CIF / Debited CIF / Allotted CIF / Balance CIF (highlighted)
 * Two separate grids (rather than one grid with column spans) keep each row's
 * column count independent per breakpoint while guaranteeing no horizontal
 * scroll: 1/row on mobile, 2/row on tablet, the full row on desktop.
 */
export default function LicenseMetricsGrid({ summary, licenseId, override, canWrite }: LicenseMetricsGridProps) {
    return (
        <div className="space-y-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <StatCard
                    icon={FileText}
                    title="Total BOEs"
                    value={fmtNum(summary.total_boes, 0)}
                    helper="Bills of entry linked"
                    accent="blue"
                />
                <StatCard
                    icon={Layers}
                    title="Total Allotments"
                    value={fmtNum(summary.total_allotments, 0)}
                    helper="Allotment records"
                    accent="indigo"
                />
                <StatCard
                    icon={Target}
                    title="Planned CIF"
                    value={fmtNum(summary.total_planned_cif)}
                    helper="Utilization planning"
                    accent="purple"
                />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard
                    icon={DollarSign}
                    title="Total CIF"
                    value={fmtNum(summary.total_cif)}
                    helper="License CIF value"
                    accent="orange"
                />
                <StatCard
                    icon={TrendingDown}
                    title="Debited CIF"
                    value={fmtNum(summary.total_debited_cif)}
                    helper="Consumed via BOEs"
                    accent="red"
                />
                <StatCard
                    icon={PieChart}
                    title="Allotted CIF"
                    value={fmtNum(summary.total_allotted_cif)}
                    helper="Reserved via allotments"
                    accent="cyan"
                />
                <StatCard
                    icon={Wallet}
                    title="Balance CIF"
                    value={fmtNum(summary.total_balance_cif)}
                    helper="Available to utilize"
                    accent="green"
                    highlighted
                    footer={<IndividualItemCifSwitch licenseId={licenseId} override={override} canWrite={canWrite} className="mt-1 border-t border-border/50 pt-2" />}
                />
            </div>
        </div>
    );
}
