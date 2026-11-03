import { useState, type ReactNode } from "react";
import { Link, useLocation, useParams, type To } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import BalanceSummaryPanels from "./BalanceSummaryPanels";
import ItemBalanceTable from "./ItemBalanceTable";
import LoadErrorPanel from "./LoadErrorPanel";
import MovementLedger from "./MovementLedger";
import { formatCif, formatIsoDate } from "./format";
import { responseStatus } from "./errors";
import { StatusReasonsButton } from "./StatusPill";
import { useLicenceBalanceDetail } from "./licenceBalanceQueries";
import type { LicenceDetail } from "./types";

const LIST_PATH = "/licence-balances";

/** Parses the `:licenceId` route param. Anything but a positive integer is treated as not found. */
function parseLicenceId(raw: string | undefined): number | null {
  if (!raw || !/^\d+$/.test(raw)) return null;
  const id = Number(raw);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

/** Returns to the list with the query string it was opened from, when the list passed one in location state. */
function backTarget(state: unknown): To {
  const from = (state as { from?: unknown } | null)?.from;
  return typeof from === "string" && from.startsWith("?") ? { pathname: LIST_PATH, search: from } : LIST_PATH;
}

/** `/licence-balances/:licenceId`. Licence summary, item table and the lazily loaded movement ledger. */
export default function LicenceBalanceDetail() {
  const { licenceId: licenceIdParam } = useParams();
  const location = useLocation();
  const licenceId = parseLicenceId(licenceIdParam);
  const query = useLicenceBalanceDetail(licenceId);
  const [ledgerItemId, setLedgerItemId] = useState<number | null>(null);

  const backLink = (
    <Link
      to={backTarget(location.state)}
      className="inline-flex w-fit items-center gap-1.5 rounded-md text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/40"
    >
      <ArrowLeft className="size-4" aria-hidden="true" />
      Back to licence balances
    </Link>
  );

  if (licenceId === null || (query.isError && responseStatus(query.error) === 404)) {
    return (
      <div className="flex flex-col gap-4 p-4 md:p-6">
        {backLink}
        <div className="rounded-lg border border-dashed bg-card p-8 text-center">
          <p className="font-medium">Licence not found</p>
          <p className="mt-1 text-sm text-muted-foreground">This licence could not be found.</p>
        </div>
      </div>
    );
  }

  if (query.isPending) {
    return (
      <div role="status" aria-live="polite" aria-label="Loading licence balance" className="flex flex-col gap-4 p-4 md:p-6">
        {backLink}
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (query.isError) {
    return (
      <div className="flex flex-col gap-4 p-4 md:p-6">
        {backLink}
        <LoadErrorPanel
          title="This licence balance could not be loaded."
          error={query.error}
          onRetry={() => void query.refetch()}
        />
      </div>
    );
  }

  return <LicenceDetailContent detail={query.data} backLink={backLink} ledgerItemId={ledgerItemId} onOpenLedger={setLedgerItemId} onCloseLedger={() => setLedgerItemId(null)} />;
}

interface LicenceDetailContentProps {
  detail: LicenceDetail;
  backLink: ReactNode;
  ledgerItemId: number | null;
  onOpenLedger: (itemId: number) => void;
  onCloseLedger: () => void;
}

function LicenceDetailContent({ detail, backLink, ledgerItemId, onOpenLedger, onCloseLedger }: LicenceDetailContentProps) {
  return (
    <div className="flex flex-col gap-6 p-4 md:p-6">
      {backLink}

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">{`Licence ${detail.licence_number}`}</h1>
          <p className="text-sm text-muted-foreground">
            {`${detail.importer} · Expires ${formatIsoDate(detail.expiry_date)}`}
          </p>
        </div>
        <StatusReasonsButton status={detail.status} flags={detail.flags} subject={`Licence ${detail.licence_number}`} />
      </header>

      <BalanceSummaryPanels summary={detail} />

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

      <section aria-labelledby="item-balances-heading" className="space-y-3">
        <h2 id="item-balances-heading" className="text-lg font-semibold">
          Items
        </h2>
        <ItemBalanceTable licenceId={detail.licence_id} items={detail.items} onOpenLedger={onOpenLedger} />
      </section>

      {ledgerItemId !== null ? (
        <MovementLedger
          key={`${detail.licence_id}-${ledgerItemId}`}
          licenceId={detail.licence_id}
          itemId={ledgerItemId}
          onClose={onCloseLedger}
        />
      ) : null}
    </div>
  );
}
