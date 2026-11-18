import { cn } from "@/lib/utils";
import { formatMasterValue, readMasterField } from "../masterDetailFields";
import type { MasterNestedCollection } from "../masterColumns";

/** One child collection of an expanded row as a compact table (same columns config as the rows). */
export function NestedRows({ collection, rows }: { collection: MasterNestedCollection; rows: Record<string, unknown>[] }) {
    return (
        <section aria-label={collection.label} className="mt-2 first:mt-0">
            <h3 className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                {collection.label} <span className="tabular-nums">({rows.length})</span>
            </h3>
            <div className="overflow-x-auto">
                <table className="w-full text-xs">
                    <thead>
                        <tr className="text-left text-muted-foreground">
                            {collection.columns.map(col => (
                                <th key={col.field} scope="col" className={cn("px-2 py-1 font-medium", col.align === "end" && "text-right")}>{col.label}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row, i) => (
                            <tr key={String(row.id ?? i)} className="border-t border-border/60">
                                {collection.columns.map(col => (
                                    <td key={col.field} className={cn("px-2 py-1 text-foreground/80", col.align === "end" && "text-right tabular-nums", col.mono && "font-mono")}>
                                        {formatMasterValue(readMasterField(row, col.field)) ?? "—"}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
}
