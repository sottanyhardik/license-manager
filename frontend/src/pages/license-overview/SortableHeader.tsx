import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SortDirection } from "./licenseOverviewHelpers";

interface SortableHeaderProps<K extends string> {
    label: string;
    sortKey: K;
    activeKey: K | null;
    direction: SortDirection;
    onSort: (key: K) => void;
    align?: "left" | "right";
    className?: string;
}

/**
 * Click-to-sort `<th>` — this codebase has no existing sort-header
 * convention to copy (`DataTable.tsx` doesn't support column sorting), so
 * this is a small new shared primitive used by the Items/Allotments/BOEs
 * tabs rather than duplicating the same button+icon markup three times.
 */
export default function SortableHeader<K extends string>({
    label,
    sortKey,
    activeKey,
    direction,
    onSort,
    align = "left",
    className,
}: SortableHeaderProps<K>) {
    const isActive = activeKey === sortKey;
    const Icon = isActive ? (direction === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;
    return (
        <th scope="col" className={cn("whitespace-nowrap px-3 py-2 font-semibold", align === "right" ? "text-right" : "text-left", className)}>
            <button
                type="button"
                onClick={() => onSort(sortKey)}
                className={cn(
                    "inline-flex cursor-pointer items-center gap-1 hover:text-foreground",
                    align === "right" && "flex-row-reverse",
                    isActive ? "text-foreground" : "text-muted-foreground"
                )}
            >
                {label}
                <Icon className={cn("size-3", isActive ? "opacity-100" : "opacity-40")} />
            </button>
        </th>
    );
}
