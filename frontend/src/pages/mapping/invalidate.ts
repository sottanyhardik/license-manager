import type { QueryClient } from "@tanstack/react-query";

/** Every Mapping view reads overlapping data: refresh all of them after any approval in any tab. */
export function invalidateMappingQueries(qc: QueryClient) {
    for (const key of ["item-name-mapping", "item-name-mapping-counts", "item-name-mapping-history", "mapping-changes", "item-pivot-matching", "item-name-mapping-import-approved"]) {
        void qc.invalidateQueries({ queryKey: [key] });
    }
}
