import { useState } from "react";
import { formatTruthyIndianNumber, formatTruthyInr } from "./masters/masterDisplayFormatters";

interface PlanningOption {
  id: number;
  item_name: string | null;
  planned_quantity: string;
  remaining_quantity: string;
  planned_cif_fc: string;
  remaining_cif_fc: string;
}

interface AvailableItem {
  id: number;
  import_item_id?: number;
  serial_number: string;
  license_number: string;
  license_id: number;
  license_date: string;
  license_expiry_date: string;
  exporter_name: string;
  notification_number: string;
  hs_code_label: string;
  product_description: string;
  description: string;
  available_quantity: string;
  balance_cif_fc: string;
  planning_options: PlanningOption[];
  has_plan?: boolean;
  remaining_planned_quantity?: string;
  remaining_planned_cif_fc?: string;
}

interface AllotmentItemPlanningCardProps {
  item: AvailableItem;
  allocationData: Record<string, any>;
  onAllocationChange: (itemId: string, allocation: { qty: string; cif_fc: string; plan_line_id?: number }) => void;
  unitPrice: number;
  maxQtyFromAllotment: number;
  maxValueFromAllotment: number;
  onAllocate: (item: AvailableItem) => void;
}

export default function AllotmentItemPlanningCard({
  item,
  allocationData,
  onAllocationChange,
  unitPrice,
  maxQtyFromAllotment,
  maxValueFromAllotment,
  onAllocate,
}: AllotmentItemPlanningCardProps) {
  const [selectedPlanLineId, setSelectedPlanLineId] = useState<number | null>(null);

  // Calculate max based on selected planning or item availability
  let maxQty = parseFloat(item.available_quantity || "0");
  let maxValue = parseFloat(item.balance_cif_fc || "0");

  if (item.planning_options && item.planning_options.length > 0) {
    if (selectedPlanLineId) {
      const selectedPlan = item.planning_options.find(p => p.id === selectedPlanLineId);
      if (selectedPlan) {
        maxQty = Math.min(maxQty, parseFloat(selectedPlan.remaining_quantity || "0"));
        maxValue = Math.min(maxValue, parseFloat(selectedPlan.remaining_cif_fc || "0"));
      }
    }
    // If planning exists but none selected, effectively disable allocation
    if (!selectedPlanLineId && item.planning_options.length > 0) {
      maxQty = 0;
      maxValue = 0;
    }
  }

  const effectiveMaxQty = Math.min(maxQty, maxQtyFromAllotment);
  const effectiveMaxValue = Math.min(maxValue, maxValueFromAllotment);

  const currentAllocation = allocationData[item.id] || {};
  const currentQty = parseFloat(currentAllocation.qty || "0");
  const currentValue = parseFloat(currentAllocation.cif_fc || "0");

  const isValid = currentQty <= effectiveMaxQty && currentValue <= effectiveMaxValue && currentQty > 0;

  return (
    <div className="border rounded-lg p-4 space-y-4">
      {/* ROW 1: License / Date / Exporter / Expiry / Notification */}
      <div className="grid grid-cols-5 gap-4 pb-4 border-b text-sm">
        <div>
          <div className="font-mono font-semibold text-base text-primary">{item.license_number}</div>
          <div className="text-xs text-muted-foreground">License</div>
        </div>
        <div>
          <div className="font-semibold">{item.license_date}</div>
          <div className="text-xs text-muted-foreground">Date</div>
        </div>
        <div>
          <div className="font-semibold">{item.exporter_name}</div>
          <div className="text-xs text-muted-foreground">Exporter</div>
        </div>
        <div>
          <div>Exp: {item.license_expiry_date}</div>
          <div className="text-xs text-muted-foreground">Expiry</div>
        </div>
        <div>
          <div>Notif: {item.notification_number}</div>
          <div className="text-xs text-muted-foreground">Notification</div>
        </div>
      </div>

      {/* ROW 2: Product Information */}
      <div className="grid grid-cols-2 gap-4 pb-4 border-b text-sm">
        <div>
          <div className="font-semibold">HS: {item.hs_code_label}</div>
          <div className="text-xs text-muted-foreground">HS Code</div>
        </div>
        <div>
          <div className="font-semibold">{item.product_description}</div>
          <div className="text-xs text-muted-foreground">Product</div>
        </div>
      </div>

      {/* ROW 3: Item / Serial / Planning / Allocation */}
      <div className="space-y-4">
        <div className="grid grid-cols-4 gap-4 text-sm">
          <div>
            <div className="font-semibold">SR: {item.serial_number}</div>
            <div className="text-xs text-muted-foreground">Serial</div>
          </div>
          <div>
            <div className="font-semibold">{formatTruthyIndianNumber(item.available_quantity, { maximumFractionDigits: 3 })}</div>
            <div className="text-xs text-muted-foreground">Available Qty</div>
          </div>
          <div>
            <div className="font-semibold">{formatTruthyInr(item.balance_cif_fc)}</div>
            <div className="text-xs text-muted-foreground">CIF FC</div>
          </div>
        </div>

        {/* Planning Selection */}
        {item.planning_options && item.planning_options.length > 0 ? (
          <div className="border rounded p-3 space-y-2">
            <label className="text-sm font-semibold">Planning Selection</label>
            <select
              value={selectedPlanLineId || ""}
              onChange={(e) => {
                const newId = e.target.value ? parseInt(e.target.value) : null;
                setSelectedPlanLineId(newId);
                onAllocationChange(item.id, { ...currentAllocation, plan_line_id: newId || undefined });
              }}
              className="w-full px-3 py-2 border rounded text-sm"
            >
              <option value="">-- Select Planning --</option>
              {item.planning_options.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  {plan.item_name || "Unplanned"} — {formatTruthyIndianNumber(plan.remaining_quantity, { maximumFractionDigits: 3 })} available
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="text-xs text-muted-foreground">No planning</div>
        )}

        {/* Allocation Controls */}
        {effectiveMaxQty > 0 && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-muted-foreground">MAX QTY: {Math.floor(effectiveMaxQty)}</label>
              <input
                type="number"
                value={currentQty}
                onChange={(e) => onAllocationChange(item.id, { ...currentAllocation, qty: e.target.value })}
                placeholder="Qty"
                className="w-full px-3 py-2 border rounded text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-muted-foreground">MAX VALUE: {formatTruthyInr(effectiveMaxValue)}</label>
              <input
                type="number"
                value={currentValue}
                onChange={(e) => onAllocationChange(item.id, { ...currentAllocation, cif_fc: e.target.value })}
                placeholder="CIF FC"
                className="w-full px-3 py-2 border rounded text-sm"
              />
            </div>
          </div>
        )}

        {/* Allocate Button */}
        {effectiveMaxQty > 0 && (
          <button
            onClick={() => onAllocate(item)}
            disabled={!isValid}
            className="w-full px-4 py-2 bg-primary text-primary-foreground rounded text-sm disabled:opacity-50"
          >
            Allocate {currentQty ? `${currentQty} / ${formatTruthyInr(currentValue)}` : ""}
          </button>
        )}

        {effectiveMaxQty === 0 && item.planning_options && item.planning_options.length > 0 && !selectedPlanLineId && (
          <div className="text-xs text-red-500 font-semibold">Select a planning option to allocate</div>
        )}
      </div>
    </div>
  );
}
