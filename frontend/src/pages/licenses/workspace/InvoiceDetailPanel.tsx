import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { formatCifAmount, formatExchangeRate, formatInrAmount, formatLedgerDate } from "./invoiceLedgerFormat";
import type { LedgerMatchedOriginal, LedgerRow } from "./types";

const NOTE_TYPES = new Set(["CREDIT NOTE", "DEBIT NOTE"]);

/** The ledger row an original reference points at. Matched by line first, then by trade and side. */
function findOriginal(ledgerRows: readonly LedgerRow[], reference: LedgerMatchedOriginal): LedgerRow | undefined {
  return (
    ledgerRows.find((row) => row.line_id === reference.line_id) ??
    ledgerRows.find((row) => row.trade_id === reference.trade_id && row.type === reference.side)
  );
}

function Detail({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium text-muted-foreground">{term}</dt>
      <dd className="mt-0.5 text-sm break-words text-foreground tabular-nums">{children}</dd>
    </div>
  );
}

function SubSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5 border-t pt-3">
      <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{title}</h4>
      {children}
    </div>
  );
}

interface InvoiceDetailPanelProps {
  row: LedgerRow;
  /** Every row of the licence, so originals and notes can be found across companies. */
  ledgerRows: readonly LedgerRow[];
  currency: string;
  onClose: () => void;
  onOpenRow: (row: LedgerRow) => void;
}

/**
 * Detail for one ledger row. It opens in place beside or above the tables and
 * never navigates away. Focus moves here on open. The caller returns focus to
 * the invoice link on close.
 */
export default function InvoiceDetailPanel({ row, ledgerRows, currency, onClose, onOpenRow }: InvoiceDetailPanelProps) {
  const headingId = useId();
  const panelRef = useRef<HTMLElement>(null);

  // Focus moves into the panel whenever it shows a different row, including
  // when the user opens an original or a note from inside it.
  useEffect(() => {
    panelRef.current?.focus();
  }, [row.line_id]);

  const original = row.matched_original ? findOriginal(ledgerRows, row.matched_original) : undefined;
  const notes = ledgerRows.filter(
    (candidate) =>
      candidate.line_id !== row.line_id &&
      NOTE_TYPES.has(candidate.type) &&
      candidate.matched_original?.trade_id === row.trade_id,
  );
  const isSale = row.sale_cif !== null || row.sale_bill_inr !== null;
  const signedCif = row.sale_cif ?? row.purchase_cif;
  const signedBill = row.sale_bill_inr ?? row.purchase_bill_inr;

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
    }
  };

  return (
    <section
      ref={panelRef}
      tabIndex={-1}
      aria-labelledby={headingId}
      data-testid="invoice-detail"
      onKeyDown={handleKeyDown}
      className="flex min-w-0 flex-col gap-4 rounded-xl border bg-card p-4 shadow-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 xl:sticky xl:top-4 xl:col-start-2 xl:row-start-1"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Invoice details</p>
          <h3 id={headingId} className="text-base font-semibold break-all text-foreground">
            {row.invoice}
          </h3>
        </div>
        <Button variant="ghost" size="icon" aria-label="Close invoice details" onClick={onClose}>
          <X aria-hidden="true" />
        </Button>
      </div>

      <dl className="grid gap-x-4 gap-y-3 sm:grid-cols-2">
        <Detail term="Invoice">{row.invoice}</Detail>
        <Detail term="Type">{row.type}</Detail>
        <Detail term="Date">{formatLedgerDate(row.date)}</Detail>
        <Detail term="Counterparty">{row.particulars}</Detail>
        <Detail term="Company">{row.holder_company}</Detail>
        <Detail term="Items">{row.items}</Detail>
        <Detail term={`CIF (${currency})`}>
          <span className={cn(isSale ? "text-destructive" : "text-success")}>{formatCifAmount(signedCif)}</span>
        </Detail>
        <Detail term={isSale ? "Sale bill (₹)" : "Purchase bill (₹)"}>{formatInrAmount(signedBill)}</Detail>
        <Detail term="CIF (₹)">{formatInrAmount(row.cif_inr)}</Detail>
        {row.exchange_rate !== null && <Detail term="Exchange rate">{formatExchangeRate(row.exchange_rate)}</Detail>}
        <Detail term="Effect">{row.effect}</Detail>
        <Detail term="Status">{row.status}</Detail>
      </dl>

      <div className="flex flex-col gap-3">
        <SubSection title="Matched original">
          {row.matched_original === null ? (
            <p className="text-sm text-muted-foreground">None</p>
          ) : (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="break-all">
                {row.matched_original.invoice} ({row.matched_original.side.toLowerCase()})
              </span>
              {original ? (
                <Button variant="outline" size="sm" onClick={() => onOpenRow(original)}>
                  Open original
                </Button>
              ) : (
                <span className="text-muted-foreground">The original is not in this ledger.</span>
              )}
            </div>
          )}
        </SubSection>

        <SubSection title="Related BOEs">
          {row.related_boes.length === 0 ? (
            <p className="text-sm text-muted-foreground">None linked</p>
          ) : (
            <ul className="list-inside list-disc text-sm">
              {row.related_boes.map((boe) => (
                <li key={boe} className="break-all">
                  {boe}
                </li>
              ))}
            </ul>
          )}
        </SubSection>

        <SubSection title="Related allotments">
          <p className="text-sm text-muted-foreground">Not recorded for trades</p>
        </SubSection>

        <SubSection title="Credit and debit notes">
          {notes.length === 0 ? (
            <p className="text-sm text-muted-foreground">None</p>
          ) : (
            <ul className="flex flex-col gap-1.5 text-sm">
              {notes.map((note) => (
                <li key={note.line_id}>
                  <button
                    type="button"
                    onClick={() => onOpenRow(note)}
                    className="text-left break-all text-primary underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/40"
                  >
                    {note.invoice}
                  </button>
                  <span className="ml-2 text-xs text-muted-foreground">{note.effect}</span>
                </li>
              ))}
            </ul>
          )}
        </SubSection>

        <SubSection title="Audit history">
          <p className="text-sm text-muted-foreground">Not yet available</p>
        </SubSection>
      </div>
    </section>
  );
}
