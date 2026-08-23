import { useState } from "react";
import { PlanningStrategy, UnitValueRow, PercentageRow } from "@/services/api/planningRuleApi";
import { SionImportItemAsyncSelect } from "./SionAsyncItemSelect";

interface Props {
  sionId?: number;
  value: any;
  onChange: (value: any) => void;
  disabled?: boolean;
  errors?: Record<string, string>;
  ruleId?: number;
  planningQuantity?: string;
  onStandardItemSelected?: (name: string) => void;
}

export function AllocationStrategyEditor({
  sionId,
  value = {},
  onChange,
  disabled = false,
  errors = {},
  onStandardItemSelected,
}: Props) {
  const strategy = value.strategy || "STANDARD";
  const [showStrategyWarning, setShowStrategyWarning] = useState(false);
  const [pendingStrategy, setPendingStrategy] = useState<PlanningStrategy | null>(null);

  const handleStrategyChange = (newStrategy: PlanningStrategy) => {
    if (value.strategy && value.strategy !== newStrategy && (value.unit_value_rows?.length || value.percentage_rows?.length)) {
      setShowStrategyWarning(true);
      setPendingStrategy(newStrategy);
    } else {
      onChange({ strategy: newStrategy, import_item: null, unit_value_rows: [], percentage_rows: [] });
    }
  };

  const handleConfirmStrategyChange = (newStrategy: PlanningStrategy) => {
    onChange({ strategy: newStrategy, import_item: null, unit_value_rows: [], percentage_rows: [] });
    setShowStrategyWarning(false);
    setPendingStrategy(null);
  };

  return (
    <section className="space-y-3 rounded-lg border border-border/70 bg-card p-3" aria-label="Allocation strategy settings">
      <div>
        <label className="mb-1 block text-xs font-semibold text-foreground">Strategy</label>
        <select
          aria-label="Allocation strategy"
          value={strategy}
          onChange={(e) => handleStrategyChange(e.target.value as PlanningStrategy)}
          disabled={disabled}
          className="h-8 rounded-md border border-input bg-background px-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="STANDARD">Standard (single item)</option>
          <option value="SPLIT_BY_UNIT_VALUE">Split by Unit Value</option>
          <option value="SPLIT_BY_PERCENT">Split by %</option>
        </select>
      </div>

      {showStrategyWarning && (
        <div className="rounded-md border border-warning/30 bg-warning/10 p-2.5" role="alert">
          <p className="mb-2 text-sm text-foreground">Changing strategy will clear existing rows. Continue?</p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => pendingStrategy && handleConfirmStrategyChange(pendingStrategy)}
              className="h-8 rounded-md bg-warning px-3 text-sm font-medium text-warning-foreground hover:bg-warning/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Continue
            </button>
            <button
              type="button"
              onClick={() => { setShowStrategyWarning(false); setPendingStrategy(null); }}
              className="h-8 rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {strategy === "STANDARD" && (
        <StandardStrategySection
          sionId={sionId ?? 0}
          importItem={value.import_item || null}
          onChange={(importItem) => onChange({ ...value, import_item: importItem })}
          onItemSelected={onStandardItemSelected}
          disabled={disabled}
          error={errors.import_item}
          className="max-w-md"
        />
      )}

      {strategy === "SPLIT_BY_UNIT_VALUE" && (
        <UnitValueStrategySection
          sionId={sionId ?? 0}
          rows={value.unit_value_rows || []}
          onChange={(rows) => onChange({ ...value, unit_value_rows: rows })}
          disabled={disabled}
          errors={errors}
        />
      )}
      {strategy === "SPLIT_BY_UNIT_VALUE" && errors.unit_value_rows && (
        <p role="alert" className="text-sm text-destructive">{errors.unit_value_rows}</p>
      )}

      {strategy === "SPLIT_BY_PERCENT" && (
        <PercentageStrategySection
          sionId={sionId ?? 0}
          rows={value.percentage_rows || []}
          onChange={(rows) => onChange({ ...value, percentage_rows: rows })}
          disabled={disabled}
          errors={errors}
        />
      )}
    </section>
  );
}

interface StandardStrategySectionProps {
  sionId: number;
  importItem: number | null;
  onChange: (itemId: number | null) => void;
  onItemSelected?: (name: string) => void;
  disabled?: boolean;
  error?: string;
  className?: string;
}

function StandardStrategySection({
  sionId,
  importItem,
  onChange,
  disabled = false,
  error,
  className,
  onItemSelected,
}: StandardStrategySectionProps) {
  return (
    <div className={`space-y-2 ${className || ""}`}>
      <label className="block text-sm font-medium">Select Import Item</label>
      <SionImportItemAsyncSelect
        sionId={sionId}
        value={importItem}
        onChange={(itemId, item) => {
          onChange(itemId);
          if (item) onItemSelected?.(item.name);
        }}
        disabled={disabled}
        error={error}
        placeholder="Search import item..."
      />
      <p className="text-xs text-muted-foreground">Rule name will be auto-derived from the selected item.</p>
    </div>
  );
}

interface UnitValueStrategySectionProps {
  sionId: number;
  rows: UnitValueRow[];
  onChange: (rows: UnitValueRow[]) => void;
  disabled?: boolean;
  errors?: Record<string, string>;
}

function UnitValueStrategySection({
  sionId,
  rows,
  onChange,
  disabled = false,
  errors: _errors = {},
}: UnitValueStrategySectionProps) {
  const addRow = () => {
    onChange([...rows, { import_item: 0, min_unit_price: "0", max_unit_price: "0", preferred_unit_price: "0" }]);
  };

  const updateRow = (index: number, field: keyof UnitValueRow, value: any) => {
    onChange(rows.map((row, rowIndex) =>
      rowIndex === index ? { ...row, [field]: value } : row,
    ));
  };

  const removeRow = (index: number) => {
    onChange(rows.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">Select import items and define price ranges for allocation.</p>
      {rows.map((row, idx) => (
        <div key={idx} className="space-y-2 rounded-md border border-border/70 bg-muted/20 p-2.5">
          <SionImportItemAsyncSelect
            sionId={sionId}
            value={row.import_item || null}
            onChange={(itemId) => updateRow(idx, "import_item", itemId || 0)}
            disabled={disabled}
            placeholder="Search import item..."
          />
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-xs text-muted-foreground">Min Unit Price</label>
              <input
                aria-label={`Minimum unit price row ${idx + 1}`}
                type="text"
                value={row.min_unit_price}
                inputMode="decimal"
                onChange={(e) => /^\d*(\.\d*)?$/.test(e.target.value) && updateRow(idx, "min_unit_price", e.target.value)}
                disabled={disabled}
                className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Max Unit Price</label>
              <input
                aria-label={`Maximum unit price row ${idx + 1}`}
                type="text"
                value={row.max_unit_price}
                inputMode="decimal"
                onChange={(e) => /^\d*(\.\d*)?$/.test(e.target.value) && updateRow(idx, "max_unit_price", e.target.value)}
                disabled={disabled}
                className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Preferred Unit Price</label>
              <input
                type="text"
                value={row.preferred_unit_price}
                inputMode="decimal"
                onChange={(e) => /^\d*(\.\d*)?$/.test(e.target.value) && updateRow(idx, "preferred_unit_price", e.target.value)}
                disabled={disabled}
                className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="0.00"
              />
            </div>
          </div>
          <button
            type="button"
            onClick={() => removeRow(idx)}
            disabled={disabled}
            className="text-xs font-medium text-destructive hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Remove
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={addRow}
        disabled={disabled}
        className="h-8 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        + Add Item
      </button>
    </div>
  );
}

interface PercentageStrategySectionProps {
  sionId: number;
  rows: PercentageRow[];
  onChange: (rows: PercentageRow[]) => void;
  disabled?: boolean;
  errors?: Record<string, string>;
}

function PercentageStrategySection({
  sionId,
  rows,
  onChange,
  disabled = false,
  errors: _errors = {},
}: PercentageStrategySectionProps) {
  const totalPercentage = rows.reduce((sum, row) => sum + parseFloat(row.percentage || "0"), 0);

  const addRow = () => {
    onChange([...rows, { import_item: 0, percentage: "0", unit_price: "0" }]);
  };

  const updateRow = (index: number, field: keyof PercentageRow, value: any) => {
    onChange(rows.map((row, rowIndex) =>
      rowIndex === index ? { ...row, [field]: value } : row,
    ));
  };

  const removeRow = (index: number) => {
    onChange(rows.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">Percentages must sum to 100%. Each row has its own unit price for CIF calculation.</p>
      {rows.map((row, idx) => (
        <div key={idx} className="space-y-2 rounded-md border border-border/70 bg-muted/20 p-2.5">
          <SionImportItemAsyncSelect
            sionId={sionId}
            value={row.import_item || null}
            onChange={(itemId) => updateRow(idx, "import_item", itemId || 0)}
            disabled={disabled}
            excludeIds={rows
              .filter((r, i) => i !== idx && r.import_item)
              .map((r) => r.import_item)
              .filter((id) => id > 0)}
            placeholder="Search import item..."
          />
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-xs text-muted-foreground">Percentage</label>
              <input
                aria-label={`Percentage row ${idx + 1}`}
                type="text"
                value={row.percentage}
                inputMode="decimal"
                onChange={(e) => /^\d*(\.\d*)?$/.test(e.target.value) && updateRow(idx, "percentage", e.target.value)}
                disabled={disabled}
                className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Unit Price</label>
              <input
                aria-label={`Unit price row ${idx + 1}`}
                type="text"
                value={row.unit_price}
                inputMode="decimal"
                onChange={(e) => /^\d*(\.\d*)?$/.test(e.target.value) && updateRow(idx, "unit_price", e.target.value)}
                disabled={disabled}
                className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="0.00"
              />
            </div>
          </div>
          <button
            type="button"
            onClick={() => removeRow(idx)}
            disabled={disabled}
            className="text-xs font-medium text-destructive hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Remove
          </button>
        </div>
      ))}
      <div className="rounded-md border border-primary/20 bg-primary/5 p-2">
        <p className="text-sm font-medium">Total: {totalPercentage.toFixed(2)}%</p>
        {Math.abs(totalPercentage - 100) > 0.001 && (
          <p className="text-xs text-destructive">
            {totalPercentage < 100
              ? `${(100 - totalPercentage).toFixed(2)}% remaining — Percentages must total 100%.`
              : `${(totalPercentage - 100).toFixed(2)}% over — Percentages must total 100%.`}
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={addRow}
        disabled={disabled}
        className="h-8 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        + Add Item
      </button>
    </div>
  );
}
