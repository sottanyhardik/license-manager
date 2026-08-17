import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { RuleAllocationStrategy, SplitAllocationBucket, SplitAllocationConfig } from "@/services/api/planningRuleApi";
import { useState, useMemo, useEffect } from "react";

const DEFAULT_SPLIT_CONFIG: SplitAllocationConfig = {
    algorithm: "SPLIT_BY_UNIT_VALUE",
    basis: "BALANCE_CIF_PER_QUANTITY",
    buckets: [
        { code: "SWP", min_price: "0.00", max_price: "1.50", reference_price: "1.50" },
        { code: "DWP", min_price: "1.50", max_price: "6.50", reference_price: "6.50" },
    ],
};

type PercentageAllocationRow = {
    id: string;
    output_code: string;
    percentage: string;
};

type PercentageAllocationConfig = {
    algorithm: "SPLIT_BY_PERCENTAGE";
    rows: PercentageAllocationRow[];
};

type PercentageAllocationInfo = {
    strategy: "SPLIT_BY_PERCENTAGE";
    sion_id?: number;
    output_item_id?: number;
    percentage_rules?: Array<{
        rule_id: number;
        output_code: string;
        percentage: string;
    }>;
};

type Props = {
    value: RuleAllocationStrategy;
    onChange: (value: RuleAllocationStrategy) => void;
    disabled?: boolean;
    errors?: Record<string, string>;
    ruleId?: number;
};

const decimalPattern = /^\d*(\.\d*)?$/;

function convertLegacyPercentageConfig(legacyConfig: PercentageAllocationInfo): PercentageAllocationConfig {
    if (legacyConfig.percentage_rules && legacyConfig.percentage_rules.length > 0) {
        return {
            algorithm: "SPLIT_BY_PERCENTAGE",
            rows: legacyConfig.percentage_rules.map((rule, idx) => ({
                id: `row-${idx}`,
                output_code: rule.output_code,
                percentage: rule.percentage,
            })),
        };
    }
    return { algorithm: "SPLIT_BY_PERCENTAGE", rows: [] };
}

/** Configures boundaries only. Split arithmetic remains exclusively backend-owned. */
export function AllocationStrategyEditor({ value, onChange, disabled = false, errors = {}, ruleId }: Props) {
    const splitConfig = value.strategy === "SPLIT_BY_UNIT_VALUE" ? value.config : null;
    const legacyPercentageConfig = value.strategy === "SPLIT_BY_PERCENTAGE" ? (value.config as PercentageAllocationInfo) : null;

    const [percentageRows, setPercentageRows] = useState<PercentageAllocationRow[]>(() => {
        if (legacyPercentageConfig) {
            return convertLegacyPercentageConfig(legacyPercentageConfig);
        }
        return [];
    });

    const percentageTotalPercentage = useMemo(() => {
        return percentageRows.reduce((sum, row) => {
            const pct = parseFloat(row.percentage) || 0;
            return sum + pct;
        }, 0);
    }, [percentageRows]);

    useEffect(() => {
        if (legacyPercentageConfig && value.strategy === "SPLIT_BY_PERCENTAGE") {
            setPercentageRows(convertLegacyPercentageConfig(legacyPercentageConfig));
        }
    }, [legacyPercentageConfig, value.strategy]);

    const changeStrategy = async (strategy: string) => {
        if (strategy === "SPLIT_BY_UNIT_VALUE") {
            onChange({ strategy: "SPLIT_BY_UNIT_VALUE", config: DEFAULT_SPLIT_CONFIG });
        } else if (strategy === "SPLIT_BY_PERCENTAGE") {
            if (ruleId) {
                try {
                    const allocation = await (await import("@/services/api/planningRuleApi")).fetchRuleAllocationStrategy(ruleId);
                    onChange(allocation);
                    if (allocation.strategy === "SPLIT_BY_PERCENTAGE") {
                        setPercentageRows(convertLegacyPercentageConfig(allocation.config as PercentageAllocationInfo));
                    }
                } catch {
                    onChange({ strategy: "SPLIT_BY_PERCENTAGE", config: { algorithm: "SPLIT_BY_PERCENTAGE", rows: [] } });
                    setPercentageRows([]);
                }
            } else {
                onChange({ strategy: "SPLIT_BY_PERCENTAGE", config: { algorithm: "SPLIT_BY_PERCENTAGE", rows: [] } });
                setPercentageRows([]);
            }
        } else {
            onChange({ strategy: "STANDARD" });
        }
    };

    const changeBucket = (index: number, field: keyof SplitAllocationBucket, nextValue: string) => {
        if (!splitConfig || (field !== "code" && !decimalPattern.test(nextValue))) return;
        const buckets = splitConfig.buckets.map((bucket, bucketIndex) => bucketIndex === index ? { ...bucket, [field]: nextValue } : bucket);
        onChange({ strategy: "SPLIT_BY_UNIT_VALUE", action_id: value.action_id, config: { ...splitConfig, buckets } });
    };

    const addBucket = () => {
        if (!splitConfig) return;
        const lastBucket = splitConfig.buckets[splitConfig.buckets.length - 1];
        if (!lastBucket) return;
        const newMin = lastBucket.max_price;
        const newMax = (parseFloat(lastBucket.max_price) + 5).toFixed(2);
        const newRef = newMax;
        const newBuckets = [...splitConfig.buckets, { code: `O${splitConfig.buckets.length}`, min_price: newMin, max_price: newMax, reference_price: newRef }];
        onChange({ strategy: "SPLIT_BY_UNIT_VALUE", action_id: value.action_id, config: { ...splitConfig, buckets: newBuckets } });
    };

    const removeBucket = (index: number) => {
        if (!splitConfig || splitConfig.buckets.length < 2) return;
        const newBuckets = splitConfig.buckets.filter((_, i) => i !== index);
        onChange({ strategy: "SPLIT_BY_UNIT_VALUE", action_id: value.action_id, config: { ...splitConfig, buckets: newBuckets } });
    };

    const changePercentageRow = (index: number, field: keyof PercentageAllocationRow, nextValue: string) => {
        if (field === "percentage" && !decimalPattern.test(nextValue)) return;
        const newRows = percentageRows.map((row, rowIndex) =>
            rowIndex === index ? { ...row, [field]: nextValue } : row
        );
        setPercentageRows(newRows);
        onChange({
            strategy: "SPLIT_BY_PERCENTAGE",
            action_id: value.action_id,
            config: { algorithm: "SPLIT_BY_PERCENTAGE", rows: newRows },
        });
    };

    const addPercentageRow = () => {
        const newRow: PercentageAllocationRow = {
            id: `row-${Date.now()}`,
            output_code: "",
            percentage: "0.00",
        };
        const newRows = [...percentageRows, newRow];
        setPercentageRows(newRows);
        onChange({
            strategy: "SPLIT_BY_PERCENTAGE",
            action_id: value.action_id,
            config: { algorithm: "SPLIT_BY_PERCENTAGE", rows: newRows },
        });
    };

    const removePercentageRow = (index: number) => {
        if (percentageRows.length < 1) return;
        const newRows = percentageRows.filter((_, i) => i !== index);
        setPercentageRows(newRows);
        onChange({
            strategy: "SPLIT_BY_PERCENTAGE",
            action_id: value.action_id,
            config: { algorithm: "SPLIT_BY_PERCENTAGE", rows: newRows },
        });
    };

    return <section aria-labelledby="allocation-strategy-heading" className="space-y-3 border-t pt-4">
        <div>
            <h3 id="allocation-strategy-heading" className="text-sm font-semibold">Planning Strategy</h3>
            <p className="text-xs text-muted-foreground">Matching selects candidates; this strategy allocates their current remaining quantity and CIF.</p>
        </div>
        <label className="block max-w-xs text-xs">Strategy
            <select aria-label="Allocation strategy" value={value.strategy} disabled={disabled} onChange={(event) => changeStrategy(event.target.value)} className="mt-1 h-9 w-full rounded-md border bg-background px-2 text-sm">
                <option value="STANDARD">Standard</option>
                <option value="SPLIT_BY_UNIT_VALUE">Split by Unit Value</option>
                <option value="SPLIT_BY_PERCENTAGE">Split by %</option>
            </select>
        </label>
        {splitConfig && <div className="rounded-md border bg-muted/20 p-3">
            <p className="mb-2 text-xs text-muted-foreground"><strong>Split Allocation</strong> · Basis: Balance CIF / Available Quantity. Price boundaries are saved in the planning action configuration.</p>
            <div className="overflow-x-auto"><table className="w-full min-w-[600px] text-xs">
                <thead><tr className="border-b text-left text-muted-foreground"><th className="pb-2">Bucket</th><th className="pb-2">Minimum</th><th className="pb-2">Maximum</th><th className="pb-2">Reference Price</th><th className="pb-2 w-8"></th></tr></thead>
                <tbody>{splitConfig.buckets.map((bucket, index) => <tr key={`${bucket.code}-${index}`} className="border-b last:border-0">
                    <td className="py-2"><input aria-label={`Bucket ${index + 1} code`} value={bucket.code} disabled={disabled} onChange={(event) => changeBucket(index, "code", event.target.value.toUpperCase())} className="h-8 w-24 rounded border bg-background px-2 font-medium" /></td>
                    {(["min_price", "max_price", "reference_price"] as const).map((field) => <td key={field} className="py-2"><input aria-label={`${bucket.code} ${field.replace(/_/g, " ")}`} inputMode="decimal" value={bucket[field]} disabled={disabled} onChange={(event) => changeBucket(index, field, event.target.value)} className="h-8 w-28 rounded border bg-background px-2 tabular-nums" /></td>)}
                    <td className="py-2"><button type="button" onClick={() => removeBucket(index)} disabled={disabled || splitConfig.buckets.length < 3} className="flex size-5 items-center justify-center rounded text-muted-foreground/50 hover:bg-destructive/10 hover:text-destructive transition-colors disabled:opacity-50" aria-label={`Remove bucket ${index + 1}`}><Trash2 className="size-3" /></button></td>
                </tr>)}</tbody>
            </table></div>
            <div className="mt-2 flex gap-2">
                <Button type="button" size="sm" variant="outline" onClick={addBucket} disabled={disabled}> + Add Bucket</Button>
            </div>
            {errors.split && <p className="mt-2 text-xs text-destructive">{errors.split}</p>}
        </div>}

        {value.strategy === "SPLIT_BY_PERCENTAGE" && <div className="rounded-md border bg-muted/20 p-3">
            <p className="mb-2 text-xs text-muted-foreground"><strong>Percentage Allocation</strong> · Basis: Planning Quantity / Available Capacity. Percentages are saved in the planning action configuration.</p>
            {percentageRows && percentageRows.length > 0 ? (
                <div className="overflow-x-auto"><table className="w-full min-w-[600px] text-xs">
                    <thead><tr className="border-b text-left text-muted-foreground"><th className="pb-2">Input / Bucket</th><th className="pb-2">Percentage</th><th className="pb-2 w-8"></th></tr></thead>
                    <tbody>{percentageRows.map((row, index) => <tr key={row.id} className="border-b last:border-0">
                        <td className="py-2"><input aria-label={`Percentage row ${index + 1} input code`} value={row.output_code} disabled={disabled} onChange={(event) => changePercentageRow(index, "output_code", event.target.value.toUpperCase())} className="h-8 w-40 rounded border bg-background px-2 font-medium" /></td>
                        <td className="py-2"><div className="flex items-center gap-1"><input aria-label={`${row.output_code} percentage`} inputMode="decimal" value={row.percentage} disabled={disabled} onChange={(event) => changePercentageRow(index, "percentage", event.target.value)} className="h-8 w-20 rounded border bg-background px-2 tabular-nums" /><span className="text-muted-foreground">%</span></div></td>
                        <td className="py-2"><button type="button" onClick={() => removePercentageRow(index)} disabled={disabled} className="flex size-5 items-center justify-center rounded text-muted-foreground/50 hover:bg-destructive/10 hover:text-destructive transition-colors disabled:opacity-50" aria-label={`Remove percentage row ${index + 1}`}><Trash2 className="size-3" /></button></td>
                    </tr>)}</tbody>
                </table></div>
            ) : (
                <p className="text-xs text-muted-foreground">No percentage configuration has been created yet. <button type="button" onClick={addPercentageRow} disabled={disabled} className="inline text-blue-500 hover:underline">[+ Add Percentage Row]</button></p>
            )}
            <div className="mt-2 flex gap-2 justify-between items-center">
                <Button type="button" size="sm" variant="outline" onClick={addPercentageRow} disabled={disabled}> + Add Percentage Row</Button>
                <div className="text-xs text-muted-foreground">
                    Total: <span className={percentageTotalPercentage === 100 ? "text-green-600" : "text-yellow-600"}>{percentageTotalPercentage.toFixed(2)}%</span>
                    {percentageTotalPercentage !== 100 && <span className="ml-2">{percentageTotalPercentage < 100 ? `${(100 - percentageTotalPercentage).toFixed(2)}% remaining` : `${(percentageTotalPercentage - 100).toFixed(2)}% over`}</span>}
                </div>
            </div>
            {errors.split && <p className="mt-2 text-xs text-destructive">{errors.split}</p>}
        </div>}
    </section>;
}
