import Timeline, { type TimelineItem } from "@/components/Timeline";
import type { FinancialLedgerRow } from "./types";
import { fmtDate, fmtNum } from "./licenseBalanceHelpers";

interface BalanceTimelineProps {
    rows: FinancialLedgerRow[];
}

const DOT_BY_KIND: Record<string, string> = {
    opening: "bg-info",
    boe: "bg-success",
    allotment: "bg-warning",
    trade: "bg-primary",
    final: "bg-foreground",
};

/**
 * Section 4 — Timeline. A simple chronological vertical list built from the
 * already date-ordered `financial_ledger.rows`, skipping rows with no date
 * (the "Current Balance" summary row).
 */
export default function BalanceTimeline({ rows }: BalanceTimelineProps) {
    const items: TimelineItem[] = rows
        .filter((row) => row.date)
        .map((row) => {
            const amount = row.credit > 0 ? `+${fmtNum(row.credit)}` : `-${fmtNum(row.debit)}`;
            return {
                id: row.sr,
                dotClassName: row.mismatched ? "bg-destructive" : DOT_BY_KIND[row.row_kind] ?? "bg-primary",
                title: `${fmtDate(row.date)} — ${row.type}`,
                subtitle: [row.document_number, row.company].filter(Boolean).join(" · ") || undefined,
                meta: `${amount} · Running Balance: ${fmtNum(row.running_balance)}`,
            };
        });

    return <Timeline items={items} emptyMessage="No dated entries yet." />;
}
