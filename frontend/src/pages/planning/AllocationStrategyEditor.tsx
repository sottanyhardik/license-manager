import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { RuleAllocationStrategy, SplitAllocationBucket, SplitAllocationConfig } from "@/services/api/planningRuleApi";

const DEFAULT_SPLIT_CONFIG: SplitAllocationConfig = {
    algorithm: "SPLIT_BY_UNIT_VALUE",
    basis: "BALANCE_CIF_PER_QUANTITY",
    buckets: [
        { code: "SWP", min_price: "0.00", max_price: "1.50", reference_price: "1.50" },
        { code: "DWP", min_price: "1.50", max_price: "6.50", reference_price: "6.50" },
    ],
};

type PercentageAllocationInfo = {
    strategy: "SPLIT_BY_PERCENTAGE";
    sion_id?: number;
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
};

const decimalPattern = /^\d*(\.\d*)?$/;

/** Configures boundaries only. Split arithmetic remains exclusively backend-owned. */
export function AllocationStrategyEditor({ value, onChange, disabled = false, errors = {} }: Props) {
    const splitConfig = value.strategy === "SPLIT_BY_UNIT_VALUE" ? value.config : null;
    const percentageConfig = value.strategy === "SPLIT_BY_PERCENTAGE" ? (value.config as PercentageAllocationInfo) : null;

    const changeStrategy = (strategy: string) => {
        if (strategy === "SPLIT_BY_UNIT_VALUE") {
            onChange({ strategy: "SPLIT_BY_UNIT_VALUE", config: DEFAULT_SPLIT_CONFIG });
        } else if (strategy === "SPLIT_BY_PERCENTAGE") {
            onChange({ strategy: "SPLIT_BY_PERCENTAGE", config: {} });
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

        {percentageConfig && <div className="rounded-md border bg-muted/20 p-3">
            <p className="mb-2 text-xs text-muted-foreground"><strong>Percentage Allocation</strong> · Quantity is allocated according to configured percentage constraints.</p>
            {percentageConfig.percentage_rules && percentageConfig.percentage_rules.length > 0 ? (
                <div className="overflow-x-auto"><table className="w-full text-xs">
                    <thead><tr className="border-b text-left text-muted-foreground"><th className="pb-2">Input</th><th className="pb-2 text-right">Percentage</th></tr></thead>
                    <tbody>{percentageConfig.percentage_rules.map((rule) => (
                        <tr key={rule.rule_id} className="border-b last:border-0">
                            <td className="py-2">{rule.output_code}</td>
                            <td className="py-2 text-right">{rule.percentage}%</td>
                        </tr>
                    ))}</tbody>
                </table></div>
            ) : (
                <p className="text-xs text-muted-foreground">No percentage rules configured for this SION.</p>
            )}
            {errors.split && <p className="mt-2 text-xs text-destructive">{errors.split}</p>}
        </div>}
    </section>;
}
