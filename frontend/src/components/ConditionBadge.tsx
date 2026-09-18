import { cn } from "@/lib/utils";
import { CONDITION_BADGE_PALETTE as CONDITION_BADGE_STYLES } from "../theme/tokens";

export default function ConditionBadge({ type, size = "sm" }) {
    if (!type) return null;
    const style = CONDITION_BADGE_STYLES[type] || {
        bg: "#E5E7EB", color: "#374151", label: type,
    };
    const sizeClasses = size === "xs"
        ? "px-1.5 py-0.5 text-[0.6rem]"
        : "px-2 py-1 text-[0.65rem]";
    return (
        <span
            className={cn(
                "ml-1.5 inline-flex items-center whitespace-nowrap rounded font-bold leading-tight",
                sizeClasses
            )}
            style={{
                background: style.bg,
                color: style.color,
            }}
            title={type === "AU"
                ? "Actual-user condition (non-transferable for this item)"
                : `Restricted: CIF shall not exceed ${type} of total licence CIF`}
        >
            {style.label}
        </span>
    );
}
