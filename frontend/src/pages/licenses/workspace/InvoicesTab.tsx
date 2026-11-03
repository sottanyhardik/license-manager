import { useMemo, useRef, useState } from "react";
import { Columns3, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import AsyncGate, { EmptyPanel } from "./AsyncGate";
import InvoiceDetailPanel from "./InvoiceDetailPanel";
import InvoiceLedgerCompanySection from "./InvoiceLedgerCompanySection";
import InvoiceLedgerFilters from "./InvoiceLedgerFilters";
import InvoiceLedgerSummaryCards from "./InvoiceLedgerSummary";
import {
  isLockedColumn,
  ledgerColumns,
  useInvoiceColumns,
  type LedgerColumn,
  type LedgerColumnId,
} from "./invoiceLedgerColumns";
import { buildLedgerCsv, downloadLedgerCsv, ledgerExportFileName, type ExportLedgerRow } from "./invoiceLedgerCsv";
import { uniqueCurrency } from "./invoiceLedgerFormat";
import {
  DEFAULT_LEDGER_FILTERS,
  countNotesByTrade,
  isLedgerFilterActive,
  rowMatchesFilters,
  type LedgerFilters,
} from "./invoiceLedgerModel";
import { useLicenceInvoiceLedger } from "./licenceWorkspaceQueries";
import type { InvoiceLedger, LedgerRow } from "./types";

interface OpenRow {
  row: LedgerRow;
  /** The invoice link that opened the panel. Focus returns to it on close. */
  trigger: HTMLElement | null;
}

interface InvoicesTabProps {
  licenceId: number;
  licenceNumber?: string | null;
}

/**
 * Purchase and sale ledger for one licence, grouped by company. The data
 * comes from `licence-balances/{id}/invoice-ledger/`. This component filters,
 * sorts and pages the rows. It never adds up money.
 */
export default function InvoicesTab({ licenceId, licenceNumber = null }: InvoicesTabProps) {
  const query = useLicenceInvoiceLedger(licenceId);

  return (
    <AsyncGate
      data={query.data}
      isError={query.isError}
      error={query.error}
      onRetry={() => void query.refetch()}
      loadingLabel="Loading purchase and sale ledger"
      errorTitle="The purchase and sale ledger could not be loaded."
    >
      {(ledger) => <InvoiceLedgerView ledger={ledger} licenceId={licenceId} licenceNumber={licenceNumber} />}
    </AsyncGate>
  );
}

function InvoiceLedgerView({
  ledger,
  licenceId,
  licenceNumber,
}: {
  ledger: InvoiceLedger;
  licenceId: number;
  licenceNumber: string | null;
}) {
  const { summary, companies } = ledger;
  const rootRef = useRef<HTMLDivElement>(null);
  const [filters, setFilters] = useState<LedgerFilters>(DEFAULT_LEDGER_FILTERS);
  const [open, setOpen] = useState<OpenRow | null>(null);
  const { hidden, setColumnVisible } = useInvoiceColumns();

  const allRows = useMemo(() => companies.flatMap((company) => company.rows), [companies]);
  const notesByTrade = useMemo(() => countNotesByTrade(allRows), [allRows]);
  const currencies = useMemo(
    () => [...new Set(allRows.map((row) => row.source.currency))].filter(Boolean).sort(),
    [allRows],
  );
  // One currency labels the CIF columns. Mixed currencies fall back to a neutral "CIF" label.
  const currency = uniqueCurrency(allRows) ?? (allRows.length === 0 ? summary.currency : "CIF");
  const allColumns = ledgerColumns(currency);
  const visibleColumns = allColumns.filter((column) => !hidden.has(column.id));

  const sections = companies
    .filter((company) => filters.company === "" || company.company === filters.company)
    .map((company) => ({
      company: company.company,
      balance: company.balance_cif,
      rows: company.rows.filter((row) => rowMatchesFilters(row, filters, notesByTrade)),
    }));
  const filteredCount = sections.reduce((total, section) => total + section.rows.length, 0);
  const filtersActive = isLedgerFilterActive(filters);

  const exportRows: ExportLedgerRow[] = sections.flatMap((section) =>
    section.rows.map((row) => ({ company: section.company, row })),
  );

  const openRow = (row: LedgerRow, trigger?: HTMLElement) => {
    setOpen((previous) => ({ row, trigger: trigger ?? previous?.trigger ?? null }));
  };

  // Focus goes back to the link that opened the panel. If that link is no longer
  // on screen (a filter hid it), focus goes to the tab so keyboard users stay in place.
  const closePanel = () => {
    const trigger = open?.trigger;
    setOpen(null);
    if (trigger && trigger.isConnected) trigger.focus();
    else rootRef.current?.focus();
  };

  const handleExport = () => {
    downloadLedgerCsv(ledgerExportFileName(licenceNumber, licenceId), buildLedgerCsv(exportRows, currency));
  };

  return (
    <div ref={rootRef} tabIndex={-1} className="flex flex-col gap-4 outline-none">
      <InvoiceLedgerSummaryCards summary={summary} />

      {allRows.length === 0 ? (
        <EmptyPanel>No purchase or sale transactions on this licence</EmptyPanel>
      ) : (
        <>
          <InvoiceLedgerFilters
            filters={filters}
            onChange={setFilters}
            onClear={() => setFilters(DEFAULT_LEDGER_FILTERS)}
            companies={companies.map((company) => company.company)}
            currencies={currencies}
            filteredCount={filteredCount}
            totalCount={allRows.length}
          />

          <div className="flex flex-wrap items-center justify-end gap-2">
            <ColumnMenu columns={allColumns} hidden={hidden} onChange={setColumnVisible} />
            <Button variant="outline" size="sm" onClick={handleExport} disabled={exportRows.length === 0}>
              <Download aria-hidden="true" />
              Export CSV
            </Button>
          </div>

          <div className={cn(open && "xl:grid xl:grid-cols-[minmax(0,1fr)_24rem] xl:items-start xl:gap-4")}>
            {open && (
              <InvoiceDetailPanel
                row={open.row}
                ledgerRows={allRows}
                currency={currency}
                onClose={closePanel}
                onOpenRow={(row) => openRow(row)}
              />
            )}

            <div className="flex min-w-0 flex-col gap-4">
              {sections.map((section, index) => (
                <InvoiceLedgerCompanySection
                  key={`${index}-${section.company}`}
                  company={section.company}
                  balance={section.balance}
                  currency={currency}
                  rows={section.rows}
                  columns={visibleColumns}
                  filtersActive={filtersActive}
                  selectedLineId={open?.row.line_id ?? null}
                  onOpenRow={(row, trigger) => openRow(row, trigger)}
                />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/** Shows or hides the optional columns. Particulars, Invoice and Type always stay visible. */
function ColumnMenu({
  columns,
  hidden,
  onChange,
}: {
  columns: LedgerColumn[];
  hidden: ReadonlySet<LedgerColumnId>;
  onChange: (id: LedgerColumnId, visible: boolean) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <Columns3 aria-hidden="true" />
          Columns
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel>Show columns</DropdownMenuLabel>
        <p className="px-2 pb-1 text-xs text-muted-foreground">Particulars, Invoice and Type always show.</p>
        <DropdownMenuSeparator />
        {columns.map((column) => (
          <DropdownMenuCheckboxItem
            key={column.id}
            checked={!hidden.has(column.id)}
            disabled={isLockedColumn(column.id)}
            // Keep the menu open so several columns can be changed in one visit.
            onSelect={(event) => event.preventDefault()}
            onCheckedChange={(checked) => onChange(column.id, checked === true)}
          >
            {column.label}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
