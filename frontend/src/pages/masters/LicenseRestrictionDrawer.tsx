
import { X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import RestrictionValueCard from "@/components/RestrictionValueCard";
import { useRestrictionData } from "@/pages/license-overview/useRestrictionData";
import { cn } from "@/lib/utils";

/**
 * LicenseRestrictionDrawer displays restriction budgets in a modal dialog.
 * Used in MasterList to show restrictions when clicking on a license row.
 */
interface LicenseRestrictionDrawerProps {
  licenseId?: number | string | null;
  licenseNumber?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onViewDetails?: () => void;
  onEdit?: () => void;
}

export default function LicenseRestrictionDrawer({
  licenseId,
  licenseNumber,
  open,
  onOpenChange,
  onViewDetails,
  onEdit,
}: LicenseRestrictionDrawerProps) {
  const { data, isLoading } = useRestrictionData(licenseId);

  // Don't render drawer if no license ID or no restrictions
  if (!licenseId || !data || data.restrictions.length === 0) {
    return null;
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md max-h-96 overflow-y-auto">
        <DialogHeader className="space-y-1">
          <DialogTitle className="text-lg">License Restrictions</DialogTitle>
          {licenseNumber && (
            <DialogDescription className="text-sm">{licenseNumber}</DialogDescription>
          )}
        </DialogHeader>

        <div className="mt-4 space-y-3">
          {/* Restrictions */}
          {data.restrictions.map((restriction) => (
            <RestrictionValueCard
              key={`restriction-${restriction.percentage}`}
              restrictionPercentage={restriction.percentage}
              totalValue={data.total_value}
              restrictedLimit={restriction.limit}
              restrictedUsed={restriction.used}
              restrictedAvailable={restriction.available}
              currency="₹"
              compact
              loading={isLoading}
            />
          ))}

          {/* Action buttons */}
          <div className={cn("space-y-2 border-t pt-3", data.restrictions.length === 0 && "border-t-0 pt-0")}>
            {onViewDetails && (
              <Button
                onClick={() => {
                  onViewDetails();
                  onOpenChange(false);
                }}
                variant="outline"
                className="w-full text-xs h-9"
              >
                View Full Details
              </Button>
            )}
            {onEdit && (
              <Button
                onClick={() => {
                  onEdit();
                  onOpenChange(false);
                }}
                className="w-full text-xs h-9"
              >
                Edit License
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
