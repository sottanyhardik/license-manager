import type { RefObject } from "react";
import { Link } from "react-router-dom";
import { Pencil, RefreshCw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import IndividualItemCifSwitch from "@/components/IndividualItemCifSwitch";
import BalanceAmount from "@/pages/licence-balances/BalanceAmount";
import { StatusPill } from "@/pages/licence-balances/StatusPill";
import type { BalanceBlock, LicenceDetail } from "@/pages/licence-balances/types";
import LicenceActionsMenu, { type LicenceListActions } from "./LicenceWorkspaceActions";
import type { LicenceHeader } from "./types";

export type DataState = "loading" | "ready" | "error";

interface LicenceWorkspaceHeaderProps {
  licenceId: number;
  headingId: string;
  headingRef: RefObject<HTMLHeadingElement | null>;
  detail: LicenceDetail | undefined;
  detailState: DataState;
  header: LicenceHeader | undefined;
  canWrite: boolean;
  actions: LicenceListActions;
  onClose: () => void;
  onRefresh: () => void;
}

/**
 * The workspace header. The accordion row above it already shows the licence number,
 * status, dates, Available balance CIF, exporter, owner and norm class, so none of
 * those are repeated here. This header holds the operations, the fields the row does
 * not show, and the Available quantity.
 */
export default function LicenceWorkspaceHeader({
  licenceId,
  headingId,
  headingRef,
  detail,
  detailState,
  header,
  canWrite,
  actions,
  onClose,
  onRefresh,
}: LicenceWorkspaceHeaderProps) {
  const licenceNumber = detail?.licence_number ?? header?.license_number ?? null;

  return (
    <header className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h2
          id={headingId}
          ref={headingRef}
          tabIndex={-1}
          className="text-sm font-semibold uppercase tracking-wide text-muted-foreground outline-none"
        >
          Licence workspace
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          {header ? (
            <IndividualItemCifSwitch
              licenseId={licenceId}
              override={header.individual_item_cif_override}
              canWrite={canWrite}
            />
          ) : null}
          {canWrite ? (
            <Button asChild variant="outline" size="sm">
              <Link to={`/licenses/${licenceId}/edit`}>
                <Pencil className="size-4" aria-hidden="true" />
                Edit
              </Link>
            </Button>
          ) : null}
          <Button variant="outline" size="sm" onClick={onRefresh}>
            <RefreshCw className="size-4" aria-hidden="true" />
            Refresh
          </Button>
          <LicenceActionsMenu
            licenceId={licenceId}
            licenceNumber={licenceNumber}
            canWrite={canWrite}
            fetchingOwnership={actions.fetchingOwnership}
            onDelete={actions.onDelete}
            onFetchOwnership={actions.onFetchOwnership}
          />
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="size-4" aria-hidden="true" />
            Close
          </Button>
        </div>
      </div>

      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2 xl:grid-cols-4">
        <Field label="Importer" value={detail?.importer} />
        <Field label="IEC" value={header?.exporter_iec} />
        <Field label="Port" value={header?.port_name} />
        <Field label="Purchase status" value={header?.purchase_status_label} />
      </dl>

      <div className="grid gap-3 sm:grid-cols-2">
        <QuantityCard block={detail?.qty} state={detailState} licenceStatus={detail?.status} />
      </div>
    </header>
  );
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="break-words font-medium">{value ? value : "—"}</dd>
    </div>
  );
}

interface QuantityCardProps {
  block: BalanceBlock | undefined;
  state: DataState;
  /** The licence-level status: a figure is only "Reconciled" when the whole licence is. */
  licenceStatus?: string;
}

/** The available quantity, with its unit and its reconciliation or unit-verification status beside it. */
function QuantityCard({ block, state, licenceStatus }: QuantityCardProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-lg border bg-muted/30 px-4 py-3">
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Available quantity</p>
        <div className="mt-0.5 text-xl font-semibold">
          {block ? (
            <BalanceAmount block={block} field="available" kind="qty" emphasis overUtilisedBadge={false} />
          ) : state === "loading" ? (
            <Skeleton className="h-6 w-32" aria-hidden="true" />
          ) : (
            <span className="text-muted-foreground">—</span>
          )}
        </div>
      </div>
      {block ? <StatusPill status={licenceStatus ?? block.status} /> : null}
    </div>
  );
}
