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
    <div className="space-y-4 border rounded p-4">
      <div>
        <label className="block text-sm font-medium mb-2">Strategy</label>
        <select
          aria-label="Allocation strategy"
          value={strategy}
          onChange={(e) => handleStrategyChange(e.target.value as PlanningStrategy)}
          disabled={disabled}
          className="border border-gray-300 rounded px-2 py-1"
        >
          <option value="STANDARD">Standard (single item)</option>
          <option value="SPLIT_BY_UNIT_VALUE">Split by Unit Value</option>
          <option value="SPLIT_BY_PERCENT">Split by %</option>
        </select>
      </div>

      {showStrategyWarning && (
        <div className="bg-yellow-50 border border-yellow-200 rounded p-3">
          <p className="text-sm mb-2">Changing strategy will clear existing rows. Continue?</p>
          <div className="space-x-2">
            <button
              onClick={() => pendingStrategy && handleConfirmStrategyChange(pendingStrategy)}
              className="bg-yellow-600 text-white px-3 py-1 rounded text-sm"
            >
              Continue
            </button>
            <button
              onClick={() => { setShowStrategyWarning(false); setPendingStrategy(null); }}
              className="border border-gray-300 px-3 py-1 rounded text-sm"
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

      {strategy === "SPLIT_BY_PERCENT" && (
        <PercentageStrategySection
          sionId={sionId ?? 0}
          rows={value.percentage_rows || []}
          onChange={(rows) => onChange({ ...value, percentage_rows: rows })}
          disabled={disabled}
          errors={errors}
        />
      )}
    </div>
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
      <p className="text-xs text-gray-500">Rule name will be auto-derived from the selected item.</p>
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
  errors = {},
}: UnitValueStrategySectionProps) {
  const addRow = () => {
    onChange([...rows, { import_item: 0, min_unit_price: "0", max_unit_price: "0", preferred_unit_price: "0" }]);
  };

  const updateRow = (index: number, field: keyof UnitValueRow, value: any) => {
    const newRows = [...rows];
    (newRows[index] as any)[field] = value;
    onChange(newRows);
  };

  const removeRow = (index: number) => {
    onChange(rows.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-600">Select import items and define price ranges for allocation.</p>
      {rows.map((row, idx) => (
        <div key={idx} className="bg-gray-50 p-3 rounded space-y-2">
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
              <label className="text-xs text-gray-600">Min Unit Price</label>
              <input
                type="text"
                value={row.min_unit_price}
                inputMode="decimal"
                onChange={(e) => /^\d*(\.\d*)?$/.test(e.target.value) && updateRow(idx, "min_unit_price", e.target.value)}
                disabled={disabled}
                className="border border-gray-300 rounded px-2 py-1 w-full text-sm"
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="text-xs text-gray-600">Max Unit Price</label>
              <input
                type="text"
                value={row.max_unit_price}
                inputMode="decimal"
                onChange={(e) => /^\d*(\.\d*)?$/.test(e.target.value) && updateRow(idx, "max_unit_price", e.target.value)}
                disabled={disabled}
                className="border border-gray-300 rounded px-2 py-1 w-full text-sm"
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="text-xs text-gray-600">Preferred Unit Price</label>
              <input
                type="text"
                value={row.preferred_unit_price}
                inputMode="decimal"
                onChange={(e) => /^\d*(\.\d*)?$/.test(e.target.value) && updateRow(idx, "preferred_unit_price", e.target.value)}
                disabled={disabled}
                className="border border-gray-300 rounded px-2 py-1 w-full text-sm"
                placeholder="0.00"
              />
            </div>
          </div>
          <button
            onClick={() => removeRow(idx)}
            disabled={disabled}
            className="text-red-600 text-xs hover:underline"
          >
            Remove
          </button>
        </div>
      ))}
      <button
        onClick={addRow}
        disabled={disabled}
        className="bg-blue-500 text-white px-3 py-1 rounded text-sm"
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
  errors = {},
}: PercentageStrategySectionProps) {
  const totalPercentage = rows.reduce((sum, row) => sum + parseFloat(row.percentage || "0"), 0);

  const addRow = () => {
    onChange([...rows, { import_item: 0, percentage: "0", unit_price: "0" }]);
  };

  const updateRow = (index: number, field: keyof PercentageRow, value: any) => {
    const newRows = [...rows];
    (newRows[index] as any)[field] = value;
    onChange(newRows);
  };

  const removeRow = (index: number) => {
    onChange(rows.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-600">Percentages must sum to 100%. Each row has its own unit price for CIF calculation.</p>
      {rows.map((row, idx) => (
        <div key={idx} className="bg-gray-50 p-3 rounded space-y-2">
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
              <label className="text-xs text-gray-600">Percentage</label>
              <input
                type="text"
                value={row.percentage}
                inputMode="decimal"
                onChange={(e) => /^\d*(\.\d*)?$/.test(e.target.value) && updateRow(idx, "percentage", e.target.value)}
                disabled={disabled}
                className="border border-gray-300 rounded px-2 py-1 w-full text-sm"
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="text-xs text-gray-600">Unit Price</label>
              <input
                type="text"
                value={row.unit_price}
                inputMode="decimal"
                onChange={(e) => /^\d*(\.\d*)?$/.test(e.target.value) && updateRow(idx, "unit_price", e.target.value)}
                disabled={disabled}
                className="border border-gray-300 rounded px-2 py-1 w-full text-sm"
                placeholder="0.00"
              />
            </div>
          </div>
          <button
            onClick={() => removeRow(idx)}
            disabled={disabled}
            className="text-red-600 text-xs hover:underline"
          >
            Remove
          </button>
        </div>
      ))}
      <div className="bg-blue-50 p-2 rounded">
        <p className="text-sm font-medium">Total: {totalPercentage.toFixed(2)}%</p>
        {totalPercentage !== 100 && totalPercentage > 0 && (
          <p className="text-xs text-red-600">Must equal 100% to save</p>
        )}
      </div>
      <button
        onClick={addRow}
        disabled={disabled}
        className="bg-blue-500 text-white px-3 py-1 rounded text-sm"
      >
        + Add Item
      </button>
    </div>
  );
}
