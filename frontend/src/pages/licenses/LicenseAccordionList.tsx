/**
 * The `/licenses` accordion. Each row is one licence. Its header is the licence
 * summary, shown collapsed or expanded. The open row shows the licence workspace
 * underneath. Only one row is open at a time, and the parent decides which one
 * (the choice lives in the URL).
 *
 * The workspace element is passed only to the open row. Collapsed rows receive
 * `null`, so no workspace is mounted or fetched for them.
 */
import { memo, useCallback, type MouseEvent, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { toast } from "sonner";
import api from "@/api/axios";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatCif, isNegativeDecimal } from "@/pages/licence-balances/format";
import { openPdfPreview } from "@/utils/pdfPreview";
import LicenceStatusBadge from "./LicenceStatusBadge";
import type { LicenseListItem } from "./useLicenseListQuery";

export interface LicenseAccordionListProps {
  loading: boolean;
  data: LicenseListItem[];
  /** The open licence, or null. Its row shows `workspace` when the licence is on this page. */
  expandedLicenceId: number | null;
  onToggleLicence: (licenceId: number) => void;
  /** The inline workspace for the open licence. Rendered only inside that licence's row. */
  workspace: ReactNode;
}

// ─────────────────────────────────────────────────────────────────────────────
// Pure helpers
// ─────────────────────────────────────────────────────────────────────────────

/** The left accent follows the stored status: red for expired, green for planned, and blue otherwise. */
function borderAccentCls(item: LicenseListItem): string {
  if (item.licence_status_code === "EXPIRED") return "border-l-destructive";
  if (item.is_manually_planned) return "border-l-emerald-500";
  return "border-l-primary";
}

// ─────────────────────────────────────────────────────────────────────────────
// Row
// ─────────────────────────────────────────────────────────────────────────────

interface SummaryFieldProps {
  label: string;
  value: string | null | undefined;
}

/** One label and value of the summary. A missing value shows a dash. */
function SummaryField({ label, value }: SummaryFieldProps) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="break-words text-sm font-medium text-foreground">{value || "—"}</dd>
    </div>
  );
}

interface LicenseAccordionRowProps {
  item: LicenseListItem;
  expanded: boolean;
  onToggle: (licenceId: number) => void;
  /** `null` unless this row is the open one. */
  workspace: ReactNode;
}

const LicenseAccordionRow = memo(function LicenseAccordionRow({
  item,
  expanded,
  onToggle,
  workspace,
}: LicenseAccordionRowProps) {
  const panelId = `license-content-${item.id}`;
  const number = item.license_number || String(item.id);
  const availableCif = item.available_cif;
  const negativeCif = availableCif !== null && isNegativeDecimal(availableCif);

  // The licence number opens the merged documents PDF. It sits above the toggle, so its click does not toggle the row.
  const handleOpenMergedPdf = useCallback(
    async (event: MouseEvent) => {
      event.stopPropagation();
      if (!item.has_tl && !item.has_copy) return;
      try {
        const response = await api.get(`licenses/${item.id}/merged-documents/`, { responseType: "blob" });
        openPdfPreview(response.data as Blob, `${item.license_number || item.id}-documents.pdf`);
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 404) {
          toast.warning("Document files are not available on this server.");
        } else {
          toast.error("Failed to load license documents");
        }
      }
    },
    [item.has_tl, item.has_copy, item.id, item.license_number],
  );

  return (
    <article
      aria-label={`License ${number}`}
      data-expanded={expanded ? "true" : undefined}
      className={cn(
        "license-row overflow-hidden rounded-xl border border-l-[3px] bg-card shadow-sm transition-shadow",
        expanded ? "shadow-md ring-2 ring-primary/60" : "hover:shadow-md",
        borderAccentCls(item),
      )}
    >
      <div
        onClick={(event) => {
          // The licence number and the chevron handle their own clicks. Any other click on the summary toggles the row.
          if ((event.target as Element).closest("button, a")) return;
          onToggle(item.id);
        }}
        className="grid cursor-pointer grid-cols-1 gap-3 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start sm:gap-x-6"
      >
        <div className="grid min-w-0 gap-2">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <button
              type="button"
              onClick={handleOpenMergedPdf}
              aria-label={`View documents for license ${number}`}
              className={cn(
                "shrink-0 font-mono text-lg font-bold tracking-tight",
                "underline-offset-2 focus-visible:rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                item.has_tl || item.has_copy
                  ? "cursor-pointer text-primary hover:underline focus-visible:underline"
                  : "cursor-default text-foreground",
              )}
            >
              {number}
            </button>

            <LicenceStatusBadge code={item.licence_status_code} label={item.licence_status_label} />

            <dl className="flex flex-wrap items-center gap-x-5 gap-y-1">
              <SummaryField label="Licence date" value={item.license_date} />
              <SummaryField label="Expiry date" value={item.license_expiry_date} />
              <SummaryField label="Ledger date" value={item.ledger_date} />
            </dl>
          </div>

          <dl className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,11rem),1fr))] gap-x-6 gap-y-1">
            <SummaryField label="Exporter" value={item.exporter_name} />
            <SummaryField label="Current owner" value={item.current_owner_name} />
            <SummaryField label="Norm class" value={item.get_norm_class} />
          </dl>
        </div>

        <div className="flex items-center justify-between gap-4 sm:justify-end">
          <div className="text-right">
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Available balance CIF (USD)</p>
            <p
              className={cn(
                "whitespace-nowrap text-base font-bold tabular-nums",
                negativeCif ? "text-destructive" : "text-foreground",
              )}
            >
              {formatCif(availableCif ?? undefined)}
            </p>
          </div>
          <button
            type="button"
            onClick={() => onToggle(item.id)}
            aria-expanded={expanded}
            aria-controls={expanded ? panelId : undefined}
            aria-label={`${expanded ? "Collapse" : "Expand"} licence ${number}`}
            className="inline-flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ChevronDown
              className={cn("size-4 transition-transform duration-200", expanded && "rotate-180")}
              aria-hidden="true"
            />
          </button>
        </div>
      </div>

      {/* The panel sits outside the summary, so clicks inside the workspace never toggle the row. */}
      {expanded && (
        <div
          id={panelId}
          role="region"
          aria-label={`Workspace for licence ${number}`}
          className="border-t border-border/60 bg-muted/20 p-3 md:p-4"
        >
          {workspace}
        </div>
      )}
    </article>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Skeleton
// ─────────────────────────────────────────────────────────────────────────────

function LicenseSkeleton() {
  return (
    <div className="space-y-2">
      {[80, 65, 90, 70, 75].map((w, i) => (
        <div key={i} className="overflow-hidden rounded-xl border border-border/60 bg-card px-4 py-3">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-4">
              <Skeleton className="h-5 rounded" style={{ width: `${w * 2}px` }} />
              <Skeleton className="h-5 w-16 rounded-full" />
              <Skeleton className="ml-auto h-8 w-40 rounded" />
            </div>
            <Skeleton className="h-4 w-80 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// List
// ─────────────────────────────────────────────────────────────────────────────

export default function LicenseAccordionList({
  loading,
  data,
  expandedLicenceId,
  onToggleLicence,
  workspace,
}: LicenseAccordionListProps) {
  if (loading) return <LicenseSkeleton />;

  return (
    <div className="license-list flex flex-col gap-2" role="list" aria-label="Licences">
      {data.map((item) => {
        const expanded = item.id === expandedLicenceId;
        return (
          <LicenseAccordionRow
            key={item.id}
            item={item}
            expanded={expanded}
            onToggle={onToggleLicence}
            workspace={expanded ? workspace : null}
          />
        );
      })}
    </div>
  );
}
