import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { CIF_DECIMALS, NOT_COMPUTED, QTY_DECIMALS, formatDecimal, isNegativeDecimal } from "./format";
import type { BalanceBlock } from "./types";

export type AmountField = "original" | "debited" | "allotted" | "invoiced" | "available";

interface BalanceAmountProps {
  block: BalanceBlock | undefined;
  field: AmountField;
  kind: "cif" | "qty";
  /** Emphasised (bold, the Available columns). */
  emphasis?: boolean;
  /** Item-level unit status. Quantities are withheld while the unit is unverified. */
  unitUnverified?: boolean;
  /** Unit to show when the block does not carry one. */
  unitFallback?: string | null;
  /** Shows the over-utilised badge beside a negative Available figure. Off where a status pill already says so. */
  overUtilisedBadge?: boolean;
}

/**
 * One CIF or quantity figure. Negative values are red with their sign, and
 * an over-utilised badge is shown next to a negative or flagged Available figure.
 * Quantities with an unverified unit show words, never a number.
 */
export default function BalanceAmount({
  block,
  field,
  kind,
  emphasis = false,
  unitUnverified = false,
  unitFallback,
  overUtilisedBadge = true,
}: BalanceAmountProps) {
  if (kind === "qty" && (unitUnverified || block?.status === "UNIT_UNVERIFIED")) {
    return <span className="text-xs italic text-muted-foreground">Unit unverified</span>;
  }

  const value = block?.[field];
  if (value === null || value === undefined || value.trim() === "") {
    return (
      <span className="text-muted-foreground">
        {NOT_COMPUTED}
        <span className="sr-only"> not computed</span>
      </span>
    );
  }

  const unit = kind === "qty" ? (block?.unit ?? unitFallback ?? null) : null;
  const formatted = formatDecimal(value, kind === "cif" ? CIF_DECIMALS : QTY_DECIMALS);
  // Over-utilisation is the backend's decision. A licence-level CIF figure is attribution, so it is never
  // shown red or badged as over-utilised by its own sign.
  const licenceControl = kind === "cif" && block?.cif_control === "LICENCE";
  const overUtilised = overUtilisedBadge && field === "available" && !licenceControl && block?.is_over_utilised === true;

  return (
    <span
      className={cn(
        "inline-flex items-center justify-end gap-2 whitespace-nowrap tabular-nums",
        emphasis && "font-semibold",
        !licenceControl && isNegativeDecimal(value) && "text-destructive",
      )}
    >
      <span>
        {formatted}
        {unit ? ` ${unit}` : ""}
      </span>
      {overUtilised ? <Badge variant="destructive">Over-utilised</Badge> : null}
    </span>
  );
}
