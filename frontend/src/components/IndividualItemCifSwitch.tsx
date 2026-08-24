import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/api/axios";
import { Switch } from "@/components/ui/switch";
import { extractApiError } from "@/pages/license-overview/licenseOverviewHelpers";
import { licenseOverviewKeys } from "@/pages/license-overview/useLicenseOverviewSummary";
import { licenseBalanceKeys } from "@/pages/license-balance/useLicenseBalanceLedger";

interface IndividualItemCifSwitchProps {
    licenseId: string | number;
    override?: boolean | null;
    canWrite: boolean;
    className?: string;
}

/**
 * The one UI control for the licence-level CIF selector. `null` and `false`
 * deliberately render the same OFF state; only true changes calculation mode.
 */
export default function IndividualItemCifSwitch({ licenseId, override, canWrite, className }: IndividualItemCifSwitchProps) {
    const queryClient = useQueryClient();
    const [isSaving, setIsSaving] = useState(false);
    const [optimisticOverride, setOptimisticOverride] = useState<boolean | undefined>();
    const checked = (optimisticOverride ?? override) === true;

    const invalidateConsumers = useCallback(() => {
        const id = String(licenseId);
        void queryClient.invalidateQueries({ queryKey: licenseOverviewKeys.summary(id) });
        void queryClient.invalidateQueries({ queryKey: licenseOverviewKeys.items(id) });
        void queryClient.invalidateQueries({ queryKey: licenseOverviewKeys.planning(id) });
        void queryClient.invalidateQueries({ queryKey: licenseBalanceKeys.ledger(id) });
        void queryClient.invalidateQueries({ queryKey: ["license-allotment-candidates", id] });
        void queryClient.invalidateQueries({ queryKey: ["licenses"] });
    }, [licenseId, queryClient]);

    const onCheckedChange = useCallback(async (next: boolean) => {
        if (!canWrite || isSaving) return;
        setIsSaving(true);
        setOptimisticOverride(next);
        // Cancel first so a late response cannot replace the mutation result.
        await queryClient.cancelQueries({ queryKey: licenseOverviewKeys.summary(String(licenseId)) });
        try {
            await api.patch(`licenses/${licenseId}/individual-item-cif-override/`, { individual_item_cif_override: next });
            toast.success(next ? "Individual Item CIF enabled" : "Existing balance behavior restored");
            invalidateConsumers();
        } catch (error) {
            setOptimisticOverride(undefined);
            toast.error(extractApiError(error, "Unable to update Individual Item CIF."));
            invalidateConsumers();
        } finally {
            setIsSaving(false);
        }
    }, [canWrite, invalidateConsumers, isSaving, licenseId, queryClient]);

    return (
        <div className={className} aria-live="polite">
            <div className="flex items-center gap-2">
                <Switch
                    checked={checked}
                    onCheckedChange={onCheckedChange}
                    disabled={!canWrite || isSaving}
                    aria-label="Individual Item CIF"
                />
                <span className="text-sm font-medium">Individual Item CIF</span>
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">
                {checked ? "Using each import item’s CIF balance" : "Using existing balance behavior"}
            </p>
        </div>
    );
}
