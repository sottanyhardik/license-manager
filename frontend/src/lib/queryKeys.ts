import type { QueryClient } from "@tanstack/react-query";
import type { ListParams } from "@/lib/listContract";

/**
 * Query-key factory (04 §4). Shape: [resource, 'list' | 'detail', ...].
 * Keys are plain serialisable tuples so they are stable across renders.
 */
export type Id = string | number;

function resource<R extends string>(name: R) {
    const all = [name] as const;
    return {
        all,
        lists: () => [name, "list"] as const,
        list: (p: ListParams) => [name, "list", p] as const,
        detail: (id: Id) => [name, "detail", id] as const,
        sub: (id: Id, part: string, ...rest: unknown[]) => [name, "detail", id, part, ...rest] as const,
    };
}

export const qk = {
    licenses: {
        ...resource("licenses"),
        overview: (id: Id, part: string) => ["licenses", "detail", id, "overview", part] as const,
        /** `balance-ledger/` dataset (register card + overview Overview tab). */
        ledger: (id: Id, showHidden?: boolean) =>
            (showHidden
                ? (["licenses", "detail", id, "ledger", "show-hidden"] as const)
                : (["licenses", "detail", id, "ledger"] as const)),
    },
    boes: resource("boes"),
    allotments: resource("allotments"),
    trades: resource("trades"),
    incentiveLicenses: resource("incentive-licenses"),
    ledger: resource("ledger"),
    planning: resource("planning"),
    reports: resource("reports"),
    recon: resource("recon"),
    users: resource("users"),
    tasks: resource("tasks"),
    masters: (entity: string) => resource(`masters:${entity}`),
} as const;

/**
 * Invalidate every cached query of one licence (detail `licenses/:id/`, ledger,
 * overview projections). All share the `["licenses","detail",id]` prefix.
 * Ids are stringified so "7" and 7 hit the same entries.
 */
export function invalidateLicence(queryClient: QueryClient, id: Id) {
    return queryClient.invalidateQueries({ queryKey: qk.licenses.detail(String(id)) });
}
