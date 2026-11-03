import { useState, type ReactNode } from "react";
import { ChevronDown, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  BASELINE_FLAGS_IS_NULL,
  BASELINE_IS_EXPIRED,
  activeFilterChips,
  isBaselineActive,
  type LicenseFieldErrors,
  type LicenseFilterChip,
  type LicenseListFilters as LicenseFilterValues,
  type LicenseListState,
  type MultiField,
  type TriState,
} from "../licenseListFilters";
import type { LicenseLabelLookup, ResolvedLicenseOption } from "../useLicenseFilterOptions";
import { ActiveFilterChips } from "./ActiveFilterChips";
import { DateRangeField } from "./DateRangeField";
import { FilterField } from "./FilterField";
import { MultiSelectFilter } from "./MultiSelectFilter";
import { NumberRangeField } from "./NumberRangeField";
import { SegmentedFilter, type SegmentedOption } from "./SegmentedFilter";

/** 220 px minimum per control; wide controls span two columns from sm up (see FilterField). */
const FILTER_GRID = "grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3";

const LICENCE_STATUS_OPTIONS: readonly SegmentedOption<TriState>[] = [
  { value: "all", label: "All" },
  { value: "False", label: "Not expired" },
  { value: "True", label: "Expired" },
];

const YES_NO_ALL_OPTIONS: readonly SegmentedOption<TriState>[] = [
  { value: "all", label: "All" },
  { value: "True", label: "Yes" },
  { value: "False", label: "No" },
];

export interface LicenseListFiltersProps {
  state: LicenseListState;
  labels: LicenseLabelLookup;
  errors: LicenseFieldErrors;
  searchDraft: string;
  onSearchDraftChange: (text: string) => void;
  onSearchSubmit: () => void;
  onFilterChange: (patch: Partial<LicenseFilterValues>) => void;
  onRemoveChip: (chip: LicenseFilterChip) => void;
  onClearAll: () => void;
  /** Right-hand side of the search row (result count, export, add). */
  toolbarEnd?: ReactNode;
}

/**
 * The licence filter panel. Stateless apart from the UI-only "More filters"
 * disclosure: every committed value flows through `onFilterChange`.
 */
export function LicenseListFilters({
  state,
  labels,
  errors,
  searchDraft,
  onSearchDraftChange,
  onSearchSubmit,
  onFilterChange,
  onRemoveChip,
  onClearAll,
  toolbarEnd,
}: LicenseListFiltersProps) {
  const { filters } = state;
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const chips = activeFilterChips(state, labels.labelFor);
  const baselineInEffect = isBaselineActive(filters);

  const primaryCount =
    filters.exporter.length +
    filters.purchase_status.length +
    (filters.search !== "" ? 1 : 0) +
    (filters.is_expired !== BASELINE_IS_EXPIRED ? 1 : 0) +
    (filters.flags__is_null !== BASELINE_FLAGS_IS_NULL ? 1 : 0);
  const advancedCount = Math.max(0, chips.length - primaryCount);

  const selectedFor = (field: MultiField): ResolvedLicenseOption[] =>
    (filters[field] as readonly (number | string)[]).map((value) => labels.resolve(field, String(value)));

  const idsOf = (values: string[]): number[] => values.map((value) => Number(value));

  const conflictWith = (opposite: readonly number[], oppositeLabel: string) => (value: string) =>
    opposite.includes(Number(value)) ? `Already in ${oppositeLabel}` : null;

  return (
    <section
      aria-label="Licence filters"
      data-testid="licence-filters"
      className="flex flex-col gap-4 rounded-lg border border-border/60 bg-card p-4 shadow-sm"
    >
      {/* Row 1: search, then result count and actions */}
      <div className="flex flex-wrap items-center gap-3">
      <div className="relative w-full max-w-[480px]">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <Input
          type="search"
          aria-label="Search licences"
          placeholder="Licence no., file no., exporter"
          value={searchDraft}
          onChange={(event) => onSearchDraftChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              onSearchSubmit();
            }
          }}
          className="pl-9"
          style={{ height: "var(--tb-control-height-compact)", minHeight: "var(--tb-control-height-compact)" }}
        />
      </div>
        {toolbarEnd && <div className="ml-auto flex flex-wrap items-center gap-2">{toolbarEnd}</div>}
      </div>

      {/* Row 2: primary toolbar */}
      <div className={FILTER_GRID}>
        <FilterField label="Exporter" wide>
          <MultiSelectFilter
            id="licence-filter-exporter"
            label="Exporter"
            source="companies"
            selected={selectedFor("exporter")}
            onChange={(values) => onFilterChange({ exporter: idsOf(values) })}
            conflictFor={conflictWith(filters.exclude_exporter, "Exclude exporter")}
            error={errors.exporter}
          />
        </FilterField>
        <FilterField label="Purchase status" wide>
          <MultiSelectFilter
            id="licence-filter-purchase-status"
            label="Purchase status"
            source="purchase-statuses"
            selected={selectedFor("purchase_status")}
            onChange={(values) => onFilterChange({ purchase_status: idsOf(values) })}
          />
        </FilterField>
        <FilterField label="Licence status">
          <SegmentedFilter
            label="Licence status"
            value={filters.is_expired}
            options={LICENCE_STATUS_OPTIONS}
            onChange={(value) => onFilterChange({ is_expired: value })}
          />
        </FilterField>
        <FilterField label="Flags is null" help="Yes = live balance below ₹200" id="licence-filter-flags">
          <SegmentedFilter
            label="Flags is null"
            describedBy="licence-filter-flags-help"
            value={filters.flags__is_null}
            options={YES_NO_ALL_OPTIONS}
            onChange={(value) => onFilterChange({ flags__is_null: value })}
          />
        </FilterField>
      </div>

      {/* Advanced disclosure (UI-only state; not in the URL) */}
      <div className="flex flex-col gap-3">
        <Button
          type="button"
          variant="outline"
          aria-expanded={advancedOpen}
          aria-controls="licence-filters-advanced"
          onClick={() => setAdvancedOpen((open) => !open)}
          className="self-start"
        >
          <ChevronDown className={cn("size-4 transition-transform", advancedOpen && "rotate-180")} aria-hidden="true" />
          More filters{advancedCount > 0 ? ` (${advancedCount})` : ""}
        </Button>

        <div id="licence-filters-advanced" hidden={!advancedOpen}>
          <div className={FILTER_GRID}>
            <FilterField label="Port">
              <MultiSelectFilter
                id="licence-filter-port"
                label="Port"
                source="ports"
                selected={selectedFor("port")}
                onChange={(values) => onFilterChange({ port: idsOf(values) })}
                conflictFor={conflictWith(filters.exclude_port, "Exclude port")}
                error={errors.port}
              />
            </FilterField>
            <FilterField label="Exclude port">
              <MultiSelectFilter
                id="licence-filter-exclude-port"
                label="Exclude port"
                source="ports"
                selected={selectedFor("exclude_port")}
                onChange={(values) => onFilterChange({ exclude_port: idsOf(values) })}
                conflictFor={conflictWith(filters.port, "Port")}
              />
            </FilterField>
            <FilterField label="Exclude exporter" wide>
              <MultiSelectFilter
                id="licence-filter-exclude-exporter"
                label="Exclude exporter"
                source="companies"
                selected={selectedFor("exclude_exporter")}
                onChange={(values) => onFilterChange({ exclude_exporter: idsOf(values) })}
                conflictFor={conflictWith(filters.exporter, "Exporter")}
              />
            </FilterField>
            <FilterField label="Notification number">
              <MultiSelectFilter
                id="licence-filter-notification-number"
                label="Notification number"
                source="notification-numbers"
                selected={selectedFor("notification_number")}
                onChange={(values) => onFilterChange({ notification_number: values })}
              />
            </FilterField>
            <FilterField label="Scheme code">
              <MultiSelectFilter
                id="licence-filter-scheme-code"
                label="Scheme code"
                source="scheme-codes"
                selected={selectedFor("scheme_code")}
                onChange={(values) => onFilterChange({ scheme_code: values })}
              />
            </FilterField>
            <FilterField label="Norm class">
              <MultiSelectFilter
                id="licence-filter-norm-class"
                label="Norm class"
                source="sion-classes"
                selected={selectedFor("export_license__norm_class")}
                onChange={(values) => onFilterChange({ export_license__norm_class: idsOf(values) })}
              />
            </FilterField>
            <FilterField label="Licence date" wide>
              <DateRangeField
                label="Licence date"
                from={filters.license_date__gte}
                to={filters.license_date__lte}
                error={errors.license_date ?? errors.license_date__gte ?? errors.license_date__lte}
                onCommit={(range) => onFilterChange({ license_date__gte: range.from, license_date__lte: range.to })}
              />
            </FilterField>
            <FilterField label="Expiry date" wide>
              <DateRangeField
                label="Expiry date"
                from={filters.license_expiry_date__gte}
                to={filters.license_expiry_date__lte}
                error={
                  errors.license_expiry_date ?? errors.license_expiry_date__gte ?? errors.license_expiry_date__lte
                }
                onCommit={(range) =>
                  onFilterChange({ license_expiry_date__gte: range.from, license_expiry_date__lte: range.to })
                }
              />
            </FilterField>
            <FilterField label="Balance CIF (₹)" wide>
              <NumberRangeField
                label="Balance CIF"
                min={filters.balance__balance_cif_min}
                max={filters.balance__balance_cif_max}
                error={errors.balance__balance_cif ?? errors.balance__balance_cif_min ?? errors.balance__balance_cif_max}
                onCommit={(range) =>
                  onFilterChange({ balance__balance_cif_min: range.min, balance__balance_cif_max: range.max })
                }
              />
            </FilterField>
            <FilterField label="Is planned">
              <SegmentedFilter
                label="Is planned"
                value={filters.is_planned}
                options={YES_NO_ALL_OPTIONS}
                onChange={(value) => onFilterChange({ is_planned: value })}
              />
            </FilterField>
          </div>
        </div>
      </div>

      {baselineInEffect && (
        <div
          data-testid="licence-baseline"
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted px-3 py-2 text-sm text-foreground"
        >
          <span>Hiding expired and null-balance licences</span>
          <Button
            type="button"
            variant="outline"
            onClick={() => onFilterChange({ is_expired: "all", flags__is_null: "all" })}
          >
            Show all
          </Button>
        </div>
      )}

      <ActiveFilterChips chips={chips} onRemove={onRemoveChip} onClearAll={onClearAll} />
    </section>
  );
}
