import { AlertCircle, TrendingDown, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * RestrictionValueCard displays license restriction budgets clearly.
 * Shows restriction percentage, total value, restricted limit, used, and available.
 *
 * This component appears on:
 * - LicenseOverviewPage (above tabs)
 * - MasterList detail drawer
 * - MasterForm (current restrictions section)
 * - LicensePlanningWorkspace (planning view)
 */
export interface RestrictionValueCardProps {
  /** Restriction percentage (e.g., 5 for 5%) */
  restrictionPercentage: number | null;
  /** Total licensed value */
  totalValue: number;
  /** Calculated restricted limit (totalValue × restrictionPercentage ÷ 100) */
  restrictedLimit: number;
  /** Amount already used against the restriction */
  restrictedUsed: number;
  /** Amount available (restrictedLimit - restrictedUsed) */
  restrictedAvailable: number;
  /** Currency symbol (default: ₹) */
  currency?: string;
  /** Show loading state */
  loading?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Compact mode for use in drawers/modals */
  compact?: boolean;
}

export default function RestrictionValueCard({
  restrictionPercentage,
  totalValue,
  restrictedLimit,
  restrictedUsed,
  restrictedAvailable,
  currency = "₹",
  loading: _loading = false,
  className,
  compact = false,
}: RestrictionValueCardProps) {
  if (restrictionPercentage === null || restrictionPercentage === 0) {
    return null;
  }

  const usagePercentage = restrictedLimit > 0 ? (restrictedUsed / restrictedLimit) * 100 : 0;
  const isNearLimit = usagePercentage > 80;
  const isExceeded = restrictedUsed > restrictedLimit;

  const formatValue = (value: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value).replace("₹", currency);
  };

  const StatItem = ({
    label,
    value,
    unit = currency,
    highlight = false,
    trend = null,
  }: {
    label: string;
    value: number | string;
    unit?: string;
    highlight?: boolean;
    trend?: "up" | "down" | null;
  }) => (
    <div className={cn("space-y-1", compact && "space-y-0.5")}>
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className={cn("flex items-center gap-1", highlight && "text-base font-semibold")}>
        <span className={cn(highlight && "text-primary")}>
          {typeof value === "number" ? formatValue(value) : value}
        </span>
        {typeof value === "number" && unit && !unit.includes("₹") && (
          <span className="text-xs text-muted-foreground">{unit}</span>
        )}
        {trend === "up" && <TrendingUp className="size-3.5 text-orange-600 dark:text-orange-400" />}
        {trend === "down" && <TrendingDown className="size-3.5 text-green-600 dark:text-green-400" />}
      </div>
    </div>
  );

  if (compact) {
    return (
      <Card className={cn("border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-950/30", className)}>
        <CardContent className="p-3 space-y-2">
          <div className="flex items-start justify-between">
            <div>
              <h4 className="font-semibold text-sm text-amber-900 dark:text-amber-100">
                {restrictionPercentage}% Restriction Active
              </h4>
              <p className="text-xs text-amber-800/70 dark:text-amber-200/70">
                {formatValue(restrictedUsed)} of {formatValue(restrictedLimit)} used
              </p>
            </div>
            {isNearLimit && (
              <AlertCircle className="size-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
            )}
          </div>

          {/* Usage bar */}
          <div className="w-full bg-amber-200 dark:bg-amber-900/40 rounded-full h-2 overflow-hidden">
            <div
              className={cn(
                "h-full transition-all rounded-full",
                isExceeded
                  ? "bg-red-600 dark:bg-red-500"
                  : isNearLimit
                    ? "bg-orange-600 dark:bg-orange-500"
                    : "bg-emerald-600 dark:bg-emerald-500"
              )}
              style={{ width: `${Math.min(usagePercentage, 100)}%` }}
            />
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-2 gap-2 pt-1">
            <StatItem label="Used" value={restrictedUsed} highlight={isNearLimit} trend={restrictedUsed > 0 ? "up" : undefined} />
            <StatItem label="Available" value={restrictedAvailable} highlight={isNearLimit} />
          </div>

          {isExceeded && (
            <div className="flex gap-2 items-start bg-red-50 dark:bg-red-950/40 p-2 rounded border border-red-200 dark:border-red-900/40">
              <AlertCircle className="size-3.5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-red-700 dark:text-red-300 font-medium">Exceeded by {formatValue(restrictedUsed - restrictedLimit)}</p>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn("border-blue-200 dark:border-blue-900/50", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-base">License Restriction Budget</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              {restrictionPercentage}% restriction limit with current utilization
            </p>
          </div>
          {isNearLimit && (
            <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-amber-50 dark:bg-amber-950/30">
              <AlertCircle className="size-4 text-amber-600 dark:text-amber-400" />
              <span className="text-xs font-medium text-amber-900 dark:text-amber-200">Near Limit</span>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Usage bar with percentage */}
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium">Usage</span>
            <span
              className={cn(
                "text-sm font-semibold",
                isExceeded
                  ? "text-red-600 dark:text-red-400"
                  : isNearLimit
                    ? "text-orange-600 dark:text-orange-400"
                    : "text-emerald-600 dark:text-emerald-400"
              )}
            >
              {isExceeded
                ? `Exceeded by ${formatValue(restrictedUsed - restrictedLimit)}`
                : `${usagePercentage.toFixed(1)}% used`}
            </span>
          </div>
          <div
            className={cn(
              "w-full rounded-full h-3 overflow-hidden",
              isExceeded
                ? "bg-red-100 dark:bg-red-950/40"
                : isNearLimit
                  ? "bg-amber-100 dark:bg-amber-950/40"
                  : "bg-emerald-100 dark:bg-emerald-950/40"
            )}
          >
            <div
              className={cn(
                "h-full transition-all rounded-full",
                isExceeded
                  ? "bg-red-600 dark:bg-red-500"
                  : isNearLimit
                    ? "bg-orange-600 dark:bg-orange-500"
                    : "bg-emerald-600 dark:bg-emerald-500"
              )}
              style={{ width: `${Math.min(usagePercentage, 100)}%` }}
            />
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <StatItem label="Total Value" value={totalValue} highlight />
          <StatItem label="Restricted Limit" value={restrictedLimit} highlight />
          <StatItem label="Restriction %" value={`${restrictionPercentage}%`} unit="" highlight />
          <StatItem label="Used" value={restrictedUsed} trend="up" />
          <StatItem label="Available" value={restrictedAvailable} trend="down" />
          {restrictedUsed > 0 && (
            <StatItem label="Usage Rate" value={`${usagePercentage.toFixed(1)}%`} unit="" />
          )}
        </div>

        {/* Warning states */}
        {isExceeded && (
          <div className="flex gap-2 items-start p-3 rounded-lg border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/20">
            <AlertCircle className="size-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-red-900 dark:text-red-200">Restriction limit exceeded</p>
              <p className="text-xs text-red-800 dark:text-red-300 mt-0.5">
                Current usage exceeds the {restrictionPercentage}% limit by {formatValue(restrictedUsed - restrictedLimit)}.
                Review and adjust allocations.
              </p>
            </div>
          </div>
        )}

        {isNearLimit && !isExceeded && (
          <div className="flex gap-2 items-start p-3 rounded-lg border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-950/20">
            <AlertCircle className="size-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-amber-900 dark:text-amber-200">Approaching restriction limit</p>
              <p className="text-xs text-amber-800 dark:text-amber-300 mt-0.5">
                Only {formatValue(restrictedAvailable)} remaining ({(100 - usagePercentage).toFixed(1)}%).
                Plan additional items carefully.
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
