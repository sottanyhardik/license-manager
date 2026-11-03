import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import BalanceAmount from "./BalanceAmount";
import { formatCif, formatIsoDate, isNegativeDecimal } from "./format";
import type { OptionalColumnId } from "./columns";
import { StatusReasonsButton } from "./StatusPill";
import type { LicenceSummary } from "./types";

interface LicenceBalanceTableProps {
  rows: LicenceSummary[];
  visible: ReadonlySet<OptionalColumnId>;
}

const CELL = "px-3 py-2 align-middle";
const HEAD = "px-3 py-2 align-bottom font-medium";

interface HeadProps {
  children: ReactNode;
  align?: "left" | "right";
  unit?: string;
  emphasis?: boolean;
}

/** Header cell. The currency goes on its own line so the label text stays exact. */
function Head({ children, align = "right", unit, emphasis = false }: HeadProps) {
  return (
    <th
      scope="col"
      className={cn(HEAD, align === "right" ? "text-right" : "text-left", emphasis && "text-foreground")}
    >
      <span className="block">{children}</span>
      {unit ? <span className="block text-[10px] font-normal text-muted-foreground">{unit}</span> : null}
    </th>
  );
}

function legacyBadge(row: LicenceSummary) {
  if (row.legacy_status === "MISMATCH") return <Badge variant="outline">Mismatch</Badge>;
  if (row.legacy_status === "RECONCILED") return <Badge variant="outline">Matches</Badge>;
  return null;
}

/**
 * Licence-level balance table. Columns come from the compact default plus the
 * user's optional selections; each optional quantity sits beside its CIF column.
 */
export default function LicenceBalanceTable({ rows, visible }: LicenceBalanceTableProps) {
  const location = useLocation();
  const has = (id: OptionalColumnId) => visible.has(id);

  return (
    <div className="overflow-x-auto rounded-lg border bg-card">
      <table data-testid="balance-table" className="w-full min-w-[56rem] border-collapse text-sm">
        <caption className="sr-only">Licence item balances, one row per licence</caption>
        <thead className="bg-muted/50 text-xs text-muted-foreground">
          <tr>
            <Head align="left">Licence number</Head>
            <Head align="left">Importer</Head>
            <Head align="left">Expiry</Head>
            <Head unit="USD">Original CIF</Head>
            {has("qtyOriginal") ? <Head>Original qty</Head> : null}
            <Head unit="USD">Used through BOEs (debited)</Head>
            {has("qtyDebited") ? <Head>Debited qty</Head> : null}
            <Head unit="USD">Reserved for customers (allotted)</Head>
            {has("qtyAllotted") ? <Head>Allotted qty</Head> : null}
            <Head unit="USD">Invoiced</Head>
            {has("qtyInvoiced") ? <Head>Invoiced qty</Head> : null}
            <Head unit="USD" emphasis>
              Available CIF
            </Head>
            <Head emphasis>Available qty</Head>
            {has("legacy") ? <Head unit="USD">Legacy balance</Head> : null}
            <Head align="left">Status</Head>
            <Head align="left">
              <span className="sr-only">Actions</span>
            </Head>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.licence_id} className="border-t transition-colors hover:bg-muted/40">
              <th scope="row" className={cn(CELL, "text-left font-medium whitespace-nowrap")}>
                {row.licence_number}
              </th>
              <td className={cn(CELL, "text-left")}>{row.importer}</td>
              <td className={cn(CELL, "text-left whitespace-nowrap")}>{formatIsoDate(row.expiry_date)}</td>

              <td className={cn(CELL, "text-right")}>
                <BalanceAmount block={row.cif} field="original" kind="cif" />
              </td>
              {has("qtyOriginal") ? (
                <td className={cn(CELL, "text-right")}>
                  <BalanceAmount block={row.qty} field="original" kind="qty" />
                </td>
              ) : null}

              <td className={cn(CELL, "text-right")}>
                <BalanceAmount block={row.cif} field="debited" kind="cif" />
              </td>
              {has("qtyDebited") ? (
                <td className={cn(CELL, "text-right")}>
                  <BalanceAmount block={row.qty} field="debited" kind="qty" />
                </td>
              ) : null}

              <td className={cn(CELL, "text-right")}>
                <BalanceAmount block={row.cif} field="allotted" kind="cif" />
              </td>
              {has("qtyAllotted") ? (
                <td className={cn(CELL, "text-right")}>
                  <BalanceAmount block={row.qty} field="allotted" kind="qty" />
                </td>
              ) : null}

              <td className={cn(CELL, "text-right")}>
                <BalanceAmount block={row.cif} field="invoiced" kind="cif" />
              </td>
              {has("qtyInvoiced") ? (
                <td className={cn(CELL, "text-right")}>
                  <BalanceAmount block={row.qty} field="invoiced" kind="qty" />
                </td>
              ) : null}

              <td className={cn(CELL, "bg-muted/20 text-right")}>
                <BalanceAmount block={row.cif} field="available" kind="cif" emphasis />
              </td>
              <td className={cn(CELL, "bg-muted/20 text-right")}>
                <BalanceAmount block={row.qty} field="available" kind="qty" emphasis />
              </td>

              {has("legacy") ? (
                <td className={cn(CELL, "text-right")}>
                  <span className="inline-flex items-center justify-end gap-2 whitespace-nowrap tabular-nums">
                    <span className={cn(isNegativeDecimal(row.legacy_balance_cif) && "text-destructive")}>
                      {formatCif(row.legacy_balance_cif)}
                    </span>
                    {legacyBadge(row)}
                  </span>
                </td>
              ) : null}

              <td className={cn(CELL, "text-left")}>
                <StatusReasonsButton status={row.status} flags={row.flags} subject={row.licence_number} />
              </td>
              <td className={cn(CELL, "text-left")}>
                <Link
                  to={`/licence-balances/${row.licence_id}`}
                  state={{ from: location.search }}
                  aria-label={`Open ${row.licence_number}`}
                  className={buttonVariants({ variant: "outline", size: "sm" })}
                >
                  Open
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
