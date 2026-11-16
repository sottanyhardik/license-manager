import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { isLicenceOverUtilised } from "./licenseBalanceHelpers";

interface OverUtilisedBadgeProps {
    balance?: unknown;
    isOverUtilised?: boolean | null;
    className?: string;
}

/** Renders nothing unless the licence balance is negative / flagged over-utilised. */
export default function OverUtilisedBadge({ balance, isOverUtilised, className }: OverUtilisedBadgeProps) {
    if (!isLicenceOverUtilised(balance, isOverUtilised)) return null;
    return (
        <Badge
            variant="destructive"
            className={cn("ml-2 align-middle", className)}
            aria-label="Over-utilised: licence CIF balance is negative"
        >
            <AlertTriangle aria-hidden="true" />
            Over-utilised
        </Badge>
    );
}
