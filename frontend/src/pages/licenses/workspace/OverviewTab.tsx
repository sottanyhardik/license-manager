import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import BalanceSummaryPanels from "@/pages/licence-balances/BalanceSummaryPanels";
import { formatCif } from "@/pages/licence-balances/format";
import { describeFlag } from "@/pages/licence-balances/labels";
import type { LicenceDetail } from "@/pages/licence-balances/types";

/** Features the workspace does not have yet. Listed so nobody mistakes them for empty data. */
const NOT_YET_AVAILABLE = [
  { name: "Planning", detail: "Planned allocation and plan revisions." },
  { name: "History", detail: "Ownership history and transfer records." },
  { name: "Purchases and transfers", detail: "Purchase and transfer records for this licence." },
  { name: "Financial ledger", detail: "The CIF transaction ledger across all items." },
];

/**
 * Licence-level breakdown, review flags and the legacy comparison. The available
 * figures and the reconciliation status are in the header, so they are not repeated here.
 */
export default function OverviewTab({ detail }: { detail: LicenceDetail }) {
  return (
    <div className="flex flex-col gap-3">
      {/* The previous-owner BOE debit is shown inside the balance panels, as a part of Used through BOEs. */}
      <BalanceSummaryPanels summary={detail} showAvailable={false} />

      <section aria-labelledby="overview-flags-heading" className="space-y-2">
        <h3 id="overview-flags-heading" className="text-sm font-semibold">
          Review flags
        </h3>
        {detail.flags.length === 0 ? (
          <p className="text-sm text-muted-foreground">No review flags are recorded for this licence.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {detail.flags.map((code) => {
              const flag = describeFlag(code);
              return (
                <li key={code} className="rounded-md border bg-muted/30 p-3">
                  <p>{flag.text}</p>
                  {flag.known ? <p className="mt-1 font-mono text-xs text-muted-foreground">{flag.code}</p> : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {detail.legacy_status === "MISMATCH" ? (
        <div
          role="note"
          data-testid="legacy-note"
          className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100"
        >
          <p className="font-medium">Legacy comparison: review required</p>
          <p className="mt-1">
            {`Legacy balance engine shows ${formatCif(detail.legacy_balance_cif)} USD; the figure above is the reconciled item calculation. Review required.`}
          </p>
        </div>
      ) : null}

      <NotYetAvailable />
    </div>
  );
}

function NotYetAvailable() {
  return (
    <Card className="border-dashed shadow-none" aria-labelledby="not-yet-available-heading">
      <CardHeader>
        <CardTitle id="not-yet-available-heading" className="text-sm">
          Not yet available in this build
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-sm text-muted-foreground">
          These sections are not part of this build. No data is shown for them here.
        </p>
        <ul className="grid gap-2 text-sm sm:grid-cols-2">
          {NOT_YET_AVAILABLE.map((item) => (
            <li key={item.name} className="rounded-md bg-muted/40 p-3">
              <p className="font-medium">{item.name}</p>
              <p className="text-xs text-muted-foreground">{item.detail}</p>
              <p className="mt-1 text-xs font-medium text-muted-foreground">Not yet available</p>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
