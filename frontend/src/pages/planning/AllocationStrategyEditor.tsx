import type { RuleAllocationStrategy, SplitAllocationBucket, SplitAllocationConfig } from "@/services/api/planningRuleApi";

const DEFAULT_SPLIT_CONFIG: SplitAllocationConfig = {
    algorithm: "SPLIT_BY_UNIT_VALUE",
    basis: "BALANCE_CIF_PER_QUANTITY",
    buckets: [
        { code: "SWP", min_price: "0.00", max_price: "1.50", reference_price: "1.50" },
        { code: "DWP", min_price: "1.50", max_price: "6.50", reference_price: "6.50" },
    ],
};

type Props = {
    value: RuleAllocationStrategy;
    onChange: (value: RuleAllocationStrategy) => void;
    disabled?: boolean;
};

const decimalPattern = /^\d*(\.\d*)?$/;

/** Configures boundaries only. Split arithmetic remains exclusively backend-owned. */
export function AllocationStrategyEditor({ value, onChange, disabled = false }: Props) {
    const splitConfig = value.strategy === "SPLIT_BY_UNIT_VALUE" ? value.config : null;
    const changeStrategy = (strategy: string) => onChange(strategy === "SPLIT_BY_UNIT_VALUE"
        ? { strategy: "SPLIT_BY_UNIT_VALUE", config: DEFAULT_SPLIT_CONFIG }
        : { strategy: "STANDARD" });
    const changeBucket = (index: number, field: keyof SplitAllocationBucket, nextValue: string) => {
        if (!splitConfig || (field !== "code" && !decimalPattern.test(nextValue))) return;
        const buckets = splitConfig.buckets.map((bucket, bucketIndex) => bucketIndex === index ? { ...bucket, [field]: nextValue } : bucket);
        onChange({ strategy: "SPLIT_BY_UNIT_VALUE", action_id: value.action_id, config: { ...splitConfig, buckets } });
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
            </select>
        </label>
        {splitConfig && <div className="rounded-md border bg-muted/20 p-3">
            <p className="mb-2 text-xs text-muted-foreground"><strong>Split Allocation</strong> · Basis: Balance CIF / Available Quantity. Price boundaries are saved in the planning action configuration.</p>
            <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-xs">
                <thead><tr className="border-b text-left text-muted-foreground"><th className="pb-2">Bucket</th><th className="pb-2">Minimum</th><th className="pb-2">Maximum</th><th className="pb-2">Reference Price</th></tr></thead>
                <tbody>{splitConfig.buckets.map((bucket, index) => <tr key={`${bucket.code}-${index}`} className="border-b last:border-0">
                    <td className="py-2"><input aria-label={`Bucket ${index + 1} code`} value={bucket.code} disabled={disabled} onChange={(event) => changeBucket(index, "code", event.target.value.toUpperCase())} className="h-8 w-24 rounded border bg-background px-2 font-medium" /></td>
                    {(["min_price", "max_price", "reference_price"] as const).map((field) => <td key={field} className="py-2"><input aria-label={`${bucket.code} ${field.replace(/_/g, " ")}`} inputMode="decimal" value={bucket[field]} disabled={disabled} onChange={(event) => changeBucket(index, field, event.target.value)} className="h-8 w-28 rounded border bg-background px-2 tabular-nums" /></td>)}
                </tr>)}</tbody>
            </table></div>
        </div>}
    </section>;
}
