import { Loader2 } from "lucide-react";
import RestrictionValueCard from "@/components/RestrictionValueCard";
import { useRestrictionData } from "./useRestrictionData";

/**
 * RestrictionSummary displays all active restriction budgets for a license.
 * Shows one RestrictionValueCard per restriction type (2%, 3%, 5%, 10%).
 * Appears on the License Overview page above the tabs.
 */
export default function RestrictionSummary({ licenseId }: { licenseId?: string }) {
  const { data, isLoading, error } = useRestrictionData(licenseId);

  // Don't render if no restrictions
  if (!data || data.restrictions.length === 0) {
    return null;
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">Loading restrictions...</span>
      </div>
    );
  }

  if (error) {
    console.warn("Error loading restrictions:", error);
    return null; // Silently fail - restrictions are not critical
  }

  return (
    <div className="space-y-3">
      {data.restrictions.map((restriction) => (
        <RestrictionValueCard
          key={`restriction-${restriction.percentage}`}
          restrictionPercentage={restriction.percentage}
          totalValue={data.total_value}
          restrictedLimit={restriction.limit}
          restrictedUsed={restriction.used}
          restrictedAvailable={restriction.available}
          currency="₹"
        />
      ))}
    </div>
  );
}
