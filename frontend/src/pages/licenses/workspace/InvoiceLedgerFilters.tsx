import { useId, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LEDGER_ROW_TYPES, isLedgerFilterActive, type LedgerFilters, type NoteFilter } from "./invoiceLedgerModel";
import type { LedgerRowType } from "./types";

const TYPE_LABELS: Record<LedgerRowType, string> = {
  PURCHASE: "Purchase",
  SALE: "Sale",
  "CREDIT NOTE": "Credit note",
  "DEBIT NOTE": "Debit note",
};

const NOTE_LABELS: Record<NoteFilter, string> = {
  all: "All rows",
  credit: "Credit notes",
  debit: "Debit notes",
  none: "Invoices with no note",
};

const SELECT_CLASS =
  "h-10 w-full min-w-0 cursor-pointer rounded-lg border border-input bg-card px-3 text-sm shadow-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/30";

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  );
}

interface InvoiceLedgerFiltersProps {
  filters: LedgerFilters;
  onChange: (next: LedgerFilters) => void;
  onClear: () => void;
  companies: string[];
  currencies: string[];
  filteredCount: number;
  totalCount: number;
}

/**
 * Filters for the ledger rows. They change which rows are listed and never the
 * licence totals above them.
 */
export default function InvoiceLedgerFilters({
  filters,
  onChange,
  onClear,
  companies,
  currencies,
  filteredCount,
  totalCount,
}: InvoiceLedgerFiltersProps) {
  const idPrefix = useId();
  const active = isLedgerFilterActive(filters);

  const toggleType = (type: LedgerRowType, checked: boolean) => {
    const types = new Set(filters.types);
    if (checked) types.add(type);
    else types.delete(type);
    onChange({ ...filters, types });
  };

  return (
    <section aria-label="Filter ledger rows" className="flex flex-col gap-3 rounded-xl border bg-card p-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Field id={`${idPrefix}-from`} label="Date from">
          <Input
            id={`${idPrefix}-from`}
            type="date"
            value={filters.dateFrom}
            max={filters.dateTo || undefined}
            onChange={(event) => onChange({ ...filters, dateFrom: event.target.value })}
          />
        </Field>
        <Field id={`${idPrefix}-to`} label="Date to">
          <Input
            id={`${idPrefix}-to`}
            type="date"
            value={filters.dateTo}
            min={filters.dateFrom || undefined}
            onChange={(event) => onChange({ ...filters, dateTo: event.target.value })}
          />
        </Field>
        <Field id={`${idPrefix}-company`} label="Company">
          <select
            id={`${idPrefix}-company`}
            className={SELECT_CLASS}
            value={filters.company}
            onChange={(event) => onChange({ ...filters, company: event.target.value })}
          >
            <option value="">All companies</option>
            {companies.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </Field>
        <Field id={`${idPrefix}-note`} label="Notes">
          <select
            id={`${idPrefix}-note`}
            className={SELECT_CLASS}
            value={filters.note}
            onChange={(event) => onChange({ ...filters, note: event.target.value as NoteFilter })}
          >
            {(Object.keys(NOTE_LABELS) as NoteFilter[]).map((value) => (
              <option key={value} value={value}>
                {NOTE_LABELS[value]}
              </option>
            ))}
          </select>
        </Field>
        <Field id={`${idPrefix}-particulars`} label="Particulars">
          <Input
            id={`${idPrefix}-particulars`}
            type="search"
            placeholder="Customer or supplier name"
            value={filters.particulars}
            onChange={(event) => onChange({ ...filters, particulars: event.target.value })}
          />
        </Field>
        <Field id={`${idPrefix}-item`} label="Item">
          <Input
            id={`${idPrefix}-item`}
            type="search"
            placeholder="Item name"
            value={filters.item}
            onChange={(event) => onChange({ ...filters, item: event.target.value })}
          />
        </Field>
        <Field id={`${idPrefix}-invoice`} label="Invoice number">
          <Input
            id={`${idPrefix}-invoice`}
            type="search"
            placeholder="Invoice number"
            value={filters.invoice}
            onChange={(event) => onChange({ ...filters, invoice: event.target.value })}
          />
        </Field>
        {currencies.length > 1 && (
          <Field id={`${idPrefix}-currency`} label="Currency">
            <select
              id={`${idPrefix}-currency`}
              className={SELECT_CLASS}
              value={filters.currency}
              onChange={(event) => onChange({ ...filters, currency: event.target.value })}
            >
              <option value="">All currencies</option>
              {currencies.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
          </Field>
        )}
        <fieldset className="flex min-w-0 flex-col gap-1.5 sm:col-span-2 xl:col-span-2">
          <legend className="mb-1.5 text-sm leading-none font-medium">Type</legend>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {LEDGER_ROW_TYPES.map((type) => (
              <label key={type} className="inline-flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="size-4 cursor-pointer accent-primary"
                  checked={filters.types.has(type)}
                  onChange={(event) => toggleType(type, event.target.checked)}
                />
                {TYPE_LABELS[type]}
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p role="status" aria-live="polite" className="text-sm text-muted-foreground tabular-nums">
          {active ? `Filtered: ${filteredCount} of ${totalCount} rows` : `${totalCount} rows`}
        </p>
        {active && (
          <Button variant="outline" size="sm" onClick={onClear}>
            Clear filters
          </Button>
        )}
      </div>
    </section>
  );
}
