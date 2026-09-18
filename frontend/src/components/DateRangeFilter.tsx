import type { ComponentType } from "react";
import { XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export interface DateRangePreset {
    label: string;
    icon?: ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
    range: () => { from: string; to: string };
}

interface DateRangeFilterProps {
    label: string;
    icon?: ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
    hint?: string;
    fromValue: string;
    toValue: string;
    onFromChange: (value: string) => void;
    onToChange: (value: string) => void;
    /** Relative-date shortcut buttons (e.g. Today, Last 7 Days, Current FY).
     * Omit entirely for a filter with no meaningful presets — the button
     * row is only rendered when at least one is passed. */
    presets?: DateRangePreset[];
    onClear?: () => void;
    fromId?: string;
    toId?: string;
    className?: string;
}

/**
 * Shared From/To date-range filter block — label, optional relative-date
 * preset buttons, and a two-column native `<input type="date">` grid.
 * Generalizes the block that used to be independently copy-pasted across
 * `AdvancedFilter.tsx`, `LicenseLedger.tsx`, `AllotmentFilters.tsx`,
 * `admin/ActivityLog.tsx`, and both item-report filter panels — same
 * shadcn `Input`/`Button` primitives those already used, native OS date
 * picker kept (no new dependency), just no longer duplicated six times.
 */
export default function DateRangeFilter({
    label, icon: Icon, hint, fromValue, toValue, onFromChange, onToChange,
    presets, onClear, fromId, toId, className,
}: DateRangeFilterProps) {
    const hasValue = Boolean(fromValue || toValue);

    return (
        <div className={cn("space-y-3", className)}>
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                    {Icon && <Icon className="size-4" aria-hidden />}
                    {label}
                    {hint && <span className="text-xs font-normal">{hint}</span>}
                </div>
                {(presets?.length || onClear) && (
                    <div className="flex flex-wrap gap-2">
                        {presets?.map((preset) => {
                            const PresetIcon = preset.icon;
                            return (
                                <Button
                                    key={preset.label}
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    onClick={() => {
                                        const { from, to } = preset.range();
                                        onFromChange(from);
                                        onToChange(to);
                                    }}
                                >
                                    {PresetIcon && <PresetIcon className="size-4" aria-hidden />}
                                    {preset.label}
                                </Button>
                            );
                        })}
                        {onClear && (
                            <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="text-destructive hover:bg-destructive/10"
                                onClick={onClear}
                                disabled={!hasValue}
                            >
                                <XCircle className="size-4" aria-hidden />Clear
                            </Button>
                        )}
                    </div>
                )}
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                    <Label htmlFor={fromId} className="mb-2 block text-xs font-medium text-muted-foreground">
                        From
                    </Label>
                    <Input id={fromId} type="date" value={fromValue} onChange={(e) => onFromChange(e.target.value)} />
                </div>
                <div>
                    <Label htmlFor={toId} className="mb-2 block text-xs font-medium text-muted-foreground">
                        To
                    </Label>
                    <Input id={toId} type="date" value={toValue} onChange={(e) => onToChange(e.target.value)} />
                </div>
            </div>
        </div>
    );
}
