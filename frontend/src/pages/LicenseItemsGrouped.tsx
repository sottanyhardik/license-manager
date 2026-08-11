import { useState } from "react";
import { Link } from "react-router-dom";
import { Building2, Calendar, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatTruthyIndianNumber, formatTruthyInr } from "./masters/masterDisplayFormatters";
import { openPdfPreview } from "../utils/pdfPreview";
import { saveFilterState } from "../utils/filterPersistence";
import api from "../api/axios";
import { toast } from "sonner";
import ConditionBadge from "../components/ConditionBadge";

interface AvailableItem {
  id: number;
  license_id?: number;
  license_number: string;
  serial_number: string | number;
  license_date?: string;
  exporter_name?: string;
  license_expiry_date?: string;
  notification_number?: string;
  description: string;
  hs_code_label?: string;
  product_description?: string;
  available_quantity: string;
  balance_cif_fc: string;
  condition_type?: string;
  planning_options?: Array<{ id: number; item_name: string | null; remaining_quantity: string; remaining_cif_fc: string }>;
  [key: string]: any;
}

interface LicenseItemsGroupedProps {
  availableItems: AvailableItem[];
  allocationData: Record<string, any>;
  onAllocationChange: (itemId: string, allocation: Record<string, any>) => void;
  onAllocate: (item: AvailableItem) => void;
  unitPrice: number;
  maxQtyFromAllotment: number;
  maxValueFromAllotment: number;
  pageSize: number;
}

export default function LicenseItemsGrouped({
  availableItems,
  allocationData,
  onAllocationChange,
  onAllocate,
  unitPrice,
  maxQtyFromAllotment,
  maxValueFromAllotment,
  pageSize,
}: LicenseItemsGroupedProps) {
  const [selectedPlanning, setSelectedPlanning] = useState<Record<number, number>>({});

  // Group items by license_id
  const groupedByLicense: Record<string, AvailableItem[]> = {};
  availableItems.forEach((item) => {
    const licenseId = item.license_id || item.license || "unknown";
    if (!groupedByLicense[licenseId]) {
      groupedByLicense[licenseId] = [];
    }
    groupedByLicense[licenseId].push(item);
  });

  const licenses = Object.entries(groupedByLicense);

  return (
    <div className="space-y-6">
      {licenses.map(([licenseId, licenseItems]) => {
        const firstItem = licenseItems[0];

        return (
          <div key={licenseId} className="border rounded-lg overflow-hidden">
            {/* ROW 1: License Header */}
            <div className="bg-muted/40 border-b px-4 py-3">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div className="flex items-center gap-3 flex-wrap">
                  <button
                    onClick={async () => {
                      try {
                        const response = await api.get(`licenses/${licenseId}/merged-documents/`, {
                          responseType: "blob",
                        });
                        openPdfPreview(response.data, `${firstItem.license_number}-copy.pdf`);
                      } catch {
                        toast.error("Failed to load license document");
                      }
                    }}
                    title="View license document"
                    className="inline-flex items-center gap-1 bg-transparent border-none p-0 cursor-pointer font-bold text-sm text-primary underline decoration-dotted underline-offset-2"
                  >
                    <FileText className="size-4" />
                    {firstItem.license_number}
                  </button>

                  {firstItem.license_date && (
                    <span className="text-sm text-muted-foreground">{firstItem.license_date}</span>
                  )}

                  {firstItem.exporter_name && (
                    <span className="flex items-center gap-1 text-sm text-muted-foreground">
                      <Building2 className="size-3" />
                      {firstItem.exporter_name}
                    </span>
                  )}

                  {firstItem.license_expiry_date && (
                    <span className="flex items-center gap-1 text-sm text-muted-foreground">
                      <Calendar className="size-3" />
                      Exp: {firstItem.license_expiry_date}
                    </span>
                  )}

                  {firstItem.notification_number && (
                    <span className="text-sm text-muted-foreground">Notif: {firstItem.notification_number}</span>
                  )}
                </div>
              </div>
            </div>

            {/* Items in this license group */}
            <div className="divide-y">
              {licenseItems.map((item) => {
                const currentAllocation = allocationData[item.id] || {};
                const currentQty = parseFloat(currentAllocation.qty || "0");
                const currentValue = parseFloat(currentAllocation.cif_fc || "0");
                const selectedPlanId = selectedPlanning[item.id];
                const selectedPlan = selectedPlanId && item.planning_options
                  ? item.planning_options.find((p) => p.id === selectedPlanId)
                  : null;

                // Calculate max based on planning or item availability
                let maxQty = parseFloat(item.available_quantity || "0");
                let maxValue = parseFloat(item.balance_cif_fc || "0");

                if (item.planning_options && item.planning_options.length > 0) {
                  if (selectedPlanId && selectedPlan) {
                    maxQty = Math.min(maxQty, parseFloat(selectedPlan.remaining_quantity || "0"));
                    maxValue = Math.min(maxValue, parseFloat(selectedPlan.remaining_cif_fc || "0"));
                  } else {
                    // Planning exists but none selected
                    maxQty = 0;
                    maxValue = 0;
                  }
                }

                const effectiveMaxQty = Math.min(maxQty, maxQtyFromAllotment);
                const effectiveMaxValue = Math.min(maxValue, maxValueFromAllotment);
                const isValid = currentQty <= effectiveMaxQty && currentValue <= effectiveMaxValue && currentQty > 0;

                return (
                  <div key={item.id} className="p-4 space-y-3">
                    {/* ROW 2: Item/Product Info */}
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-sm">{item.description || item.product_description}</span>
                        {item.hs_code_label && (
                          <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">
                            HS: {item.hs_code_label}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        SR #{item.serial_number} • Available: {formatTruthyIndianNumber(item.available_quantity, { maximumFractionDigits: 3 })} • CIF FC: {formatTruthyInr(item.balance_cif_fc)} • Avg: {unitPrice > 0 ? (parseFloat(item.balance_cif_fc || "0") / parseFloat(item.available_quantity || "1")).toFixed(2) : "—"}
                      </div>
                    </div>

                    {/* ROW 3: Planning Selection */}
                    {item.planning_options && item.planning_options.length > 0 ? (
                      <div className="border rounded p-3 space-y-2 bg-muted/20">
                        <label className="text-xs font-semibold block">Planning Selection</label>
                        <select
                          value={selectedPlanId || ""}
                          onChange={(e) => {
                            const newId = e.target.value ? parseInt(e.target.value) : null;
                            setSelectedPlanning((prev) => ({
                              ...prev,
                              [item.id]: newId || undefined,
                            }));
                            onAllocationChange(item.id, {
                              ...currentAllocation,
                              plan_line_id: newId || undefined,
                            });
                          }}
                          className="w-full px-2 py-1.5 border rounded text-xs"
                        >
                          <option value="">-- Select Planning --</option>
                          {item.planning_options.map((plan) => (
                            <option key={plan.id} value={plan.id}>
                              {plan.item_name || "Unplanned"} — {formatTruthyIndianNumber(plan.remaining_quantity, { maximumFractionDigits: 3 })} available
                            </option>
                          ))}
                        </select>
                        {selectedPlan && (
                          <div className="text-xs text-muted-foreground mt-2 p-2 bg-background rounded">
                            MAX QTY: {Math.floor(parseFloat(selectedPlan.remaining_quantity || "0"))} | MAX VALUE: {formatTruthyInr(selectedPlan.remaining_cif_fc)}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-xs text-muted-foreground italic">No planning for this item</div>
                    )}

                    {/* Allocation Controls */}
                    {effectiveMaxQty > 0 && (
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div>
                          <label className="font-semibold text-muted-foreground">QTY (Max: {Math.floor(effectiveMaxQty)})</label>
                          <input
                            type="number"
                            value={currentQty}
                            onChange={(e) =>
                              onAllocationChange(item.id, {
                                ...currentAllocation,
                                qty: e.target.value,
                              })
                            }
                            placeholder="Qty"
                            className="w-full px-2 py-1 border rounded text-xs"
                          />
                        </div>
                        <div>
                          <label className="font-semibold text-muted-foreground">VALUE (Max: {formatTruthyInr(effectiveMaxValue)})</label>
                          <input
                            type="number"
                            value={currentValue}
                            onChange={(e) =>
                              onAllocationChange(item.id, {
                                ...currentAllocation,
                                cif_fc: e.target.value,
                              })
                            }
                            placeholder="CIF FC"
                            className="w-full px-2 py-1 border rounded text-xs"
                          />
                        </div>
                        <div className="flex flex-col justify-end">
                          <button
                            onClick={() => onAllocate(item)}
                            disabled={!isValid}
                            className="w-full px-2 py-1 bg-primary text-primary-foreground rounded text-xs font-semibold disabled:opacity-50"
                          >
                            Allocate
                          </button>
                        </div>
                      </div>
                    )}

                    {!effectiveMaxQty && item.planning_options && item.planning_options.length > 0 && !selectedPlanId && (
                      <div className="text-xs text-red-500 font-semibold">Select planning to allocate</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
