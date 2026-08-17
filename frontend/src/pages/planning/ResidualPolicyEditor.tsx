import type { RuleAllocationStrategy, SplitAllocationBucket } from "@/services/api/planningRuleApi";

export type ResidualPolicy =
    | { policy: "LEAVE_UNPLANNED" }
    | { policy: "ALLOCATE_TO_OUTPUT"; target_item_id: number | null }
    | { policy: "REBALANCE_WITHIN_SPLIT"; source_item_id: number | null; target_item_id: number | null };

interface Props {
    value: ResidualPolicy | null;
    onChange: (policy: ResidualPolicy) => void;
    splitBuckets?: SplitAllocationBucket[];
    disabled?: boolean;
    error?: string;
}

/**
 * Editor for residual (unallocated) CIF handling policy.
 * - Leave Unplanned: Default, no action taken on unallocated quantity
 * - Allocate To: Route unallocated to a specific output item
 * - Rebalance Within Split: Shift to higher-price output within the split
 */
export function ResidualPolicyEditor({
    value,
    onChange,
    splitBuckets = [],
    disabled = false,
    error,
}: Props) {
    const policy = value?.policy ?? "LEAVE_UNPLANNED";

    return (
        <section aria-labelledby="residual-policy-heading" className="space-y-3 border-t pt-4">
            <div>
                <h3 id="residual-policy-heading" className="text-sm font-semibold">Residual Quantity Handling</h3>
                <p className="text-xs text-muted-foreground">Configure what happens to unallocated (residual) quantities after split allocation.</p>
            </div>

            <fieldset className="space-y-2">
                <label className="flex items-center gap-2 text-xs">
                    <input
                        type="radio"
                        name="residual_policy"
                        value="LEAVE_UNPLANNED"
                        checked={policy === "LEAVE_UNPLANNED"}
                        onChange={() => onChange({ policy: "LEAVE_UNPLANNED" })}
                        disabled={disabled}
                        className="cursor-pointer"
                    />
                    <span>Leave Unplanned (default)</span>
                </label>

                <label className="flex items-center gap-2 text-xs">
                    <input
                        type="radio"
                        name="residual_policy"
                        value="ALLOCATE_TO_OUTPUT"
                        checked={policy === "ALLOCATE_TO_OUTPUT"}
                        onChange={() => onChange({ policy: "ALLOCATE_TO_OUTPUT", target_item_id: null })}
                        disabled={disabled}
                        className="cursor-pointer"
                    />
                    <span>Allocate to specific output</span>
                </label>
                {policy === "ALLOCATE_TO_OUTPUT" && (
                    <div className="ml-6 text-xs">
                        <label className="block">
                            Target Item
                            <input
                                type="text"
                                placeholder="Enter target item ID or name"
                                disabled={disabled}
                                className="mt-1 h-8 w-full rounded-md border bg-background px-2 text-xs"
                            />
                        </label>
                    </div>
                )}

                {splitBuckets.length >= 2 && (
                    <label className="flex items-center gap-2 text-xs">
                        <input
                            type="radio"
                            name="residual_policy"
                            value="REBALANCE_WITHIN_SPLIT"
                            checked={policy === "REBALANCE_WITHIN_SPLIT"}
                            onChange={() => onChange({ policy: "REBALANCE_WITHIN_SPLIT", source_item_id: null, target_item_id: null })}
                            disabled={disabled}
                            className="cursor-pointer"
                        />
                        <span>Rebalance within split (to higher price)</span>
                    </label>
                )}
            </fieldset>

            {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
        </section>
    );
}
