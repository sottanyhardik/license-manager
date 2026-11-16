import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

/** `?expanded=<id>` sync for ExpandableDataTable. Other params are preserved. */
export function useExpandedParam(key = "expanded"): [number | null, (id: number | null) => void] {
    const [sp, setSp] = useSearchParams();
    const raw = sp.get(key);
    const parsed = raw === null ? NaN : Number(raw);
    const value = Number.isFinite(parsed) ? parsed : null;
    const set = useCallback(
        (id: number | null) =>
            setSp(
                (prev) => {
                    const next = new URLSearchParams(prev);
                    if (id === null) next.delete(key);
                    else next.set(key, String(id));
                    return next;
                },
                { replace: true },
            ),
        [setSp, key],
    );
    return [value, set];
}
