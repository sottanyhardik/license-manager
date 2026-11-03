import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { CIF_DECIMALS, NOT_COMPUTED, QTY_DECIMALS, formatDecimal, isNegativeDecimal } from "@/pages/licence-balances/format";
import type { Decimal } from "@/pages/licence-balances/types";

export interface ColumnHeader {
  label: string;
  /** Amount columns are right-aligned. */
  numeric?: boolean;
}

interface TransactionTableProps {
  caption: string;
  columns: ColumnHeader[];
  children: ReactNode;
}

/**
 * A data table that scrolls inside its own card. The page never scrolls
 * sideways because of a wide table.
 */
export function TransactionTable({ caption, columns, children }: TransactionTableProps) {
  return (
    <div className="max-w-full overflow-x-auto rounded-lg border bg-card">
      <table className="w-full min-w-[60rem] border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-muted/50 text-xs text-muted-foreground">
          <tr>
            {columns.map((column) => (
              <th key={column.label} scope="col" className={cn("px-3 py-2 font-medium", column.numeric ? "text-right" : "text-left")}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

/**
 * One amount cell. The value is formatted, never converted: the sign is kept,
 * a negative value is also coloured, and an absent value shows as not computed.
 */
export function AmountCell({ value, kind }: { value: Decimal | undefined; kind: "cif" | "qty" }) {
  const decimals = kind === "cif" ? CIF_DECIMALS : QTY_DECIMALS;
  const text = formatDecimal(value, decimals);
  return (
    <td
      className={cn(
        "whitespace-nowrap px-3 py-2 text-right tabular-nums",
        isNegativeDecimal(value) && "font-medium text-destructive",
        text === NOT_COMPUTED && "text-muted-foreground",
      )}
    >
      {text}
    </td>
  );
}

export function TextCell({ children, className }: { children: ReactNode; className?: string }) {
  return <td className={cn("px-3 py-2 align-top", className)}>{children}</td>;
}
