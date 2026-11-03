import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import { cn } from "@/lib/utils";
import type { SortDirection } from "./tableSort";

type SortableThProps<K extends string> = {
    label: string;
    sortKey: K;
    align?: "left" | "right";
    ariaSort: SortDirection | "none";
    onSort: (key: K) => void;
};

/** Column header with a real button, so sorting works from the keyboard. */
export function SortableTh<K extends string>({ label, sortKey, align = "left", ariaSort, onSort }: SortableThProps<K>) {
    const Icon = ariaSort === "ascending" ? ArrowUp : ariaSort === "descending" ? ArrowDown : ArrowUpDown;
    return (
        <th
            scope="col"
            aria-sort={ariaSort}
            className={cn("px-4 py-2.5 font-semibold", align === "right" ? "text-right" : "text-left")}
        >
            <button
                type="button"
                onClick={() => onSort(sortKey)}
                className={cn(
                    "inline-flex items-center gap-1 rounded-sm text-xs font-semibold uppercase tracking-wide text-slate-600 hover:text-slate-900 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:text-slate-300 dark:hover:text-slate-100",
                    align === "right" && "flex-row-reverse",
                )}
            >
                {label}
                <Icon className="size-3 opacity-60" aria-hidden="true" />
            </button>
        </th>
    );
}
