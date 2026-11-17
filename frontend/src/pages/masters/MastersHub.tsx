import { useContext, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { ChevronRight, Lock } from "lucide-react";
import api from "../../api/axios";
import Icon from "../../components/Icon";
import { EmptyState, SearchInput } from "@/components/shared";
import { Skeleton } from "@/components/ui/skeleton";
import { AuthContext } from "../../context/AuthContext";
import { MASTER_CATEGORIES, masterEntities, type EntityRouteConfig } from "../../routes/config";
import { ROLES } from "../../routes/authorizationRoles";

/** `count` of a generic master list (`/api/masters/<entity>/`), fetched with one row. */
async function fetchMasterCount(entity: string, signal?: AbortSignal): Promise<number> {
    const { data } = await api.get(`masters/${entity}/`, { params: { page_size: 1 }, signal });
    return typeof data?.count === "number" ? data.count : (data?.results ?? data ?? []).length;
}

function matches(master: EntityRouteConfig, term: string): boolean {
    if (!term) return true;
    const haystack = `${master.label} ${master.description ?? ""} ${master.category}`.toLowerCase();
    return term.toLowerCase().split(/\s+/).every(word => haystack.includes(word));
}

/**
 * Masters hub (`/masters`): one entry point to every generic master, grouped by
 * category. The list itself is the `masterEntities` registry — registering a
 * master there adds it here, to the Masters menu and to the command palette.
 * Each master opens the shared config-driven `MasterList` at `/masters/:entity`.
 */
export default function MastersHub() {
    const [search, setSearch] = useState("");
    const { isSuperAdmin, hasRole } = useContext(AuthContext);
    const canWrite = isSuperAdmin() || hasRole(ROLES.USER_MANAGER);
    const masters = useMemo(() => masterEntities.filter(m => !m.deprecated), []);

    const counts = useQueries({
        queries: masters.map(master => ({
            queryKey: ["master-count", master.entity],
            queryFn: ({ signal }: { signal?: AbortSignal }) => fetchMasterCount(master.entity, signal),
            staleTime: 60_000,
            retry: 1,
        })),
    });
    const countByEntity = new Map(masters.map((master, index) => [master.entity, counts[index]]));

    const visible = masters.filter(master => matches(master, search));
    const groups = MASTER_CATEGORIES
        .map(category => ({ category, items: visible.filter(master => master.category === category) }))
        .filter(group => group.items.length > 0);

    return (
        <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
            <header className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                    <h1 className="text-xl font-semibold tracking-tight text-foreground">Masters</h1>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                        {masters.length} reference lists shared by licences, allotments, BOEs and trades.
                    </p>
                </div>
                <SearchInput
                    value={search}
                    onChange={setSearch}
                    label="Search masters"
                    placeholder="Search masters…"
                    delay={0}
                    size="sm"
                    className="w-full sm:w-64"
                />
            </header>

            {!canWrite && (
                <p className="mb-4 flex items-center gap-1.5 text-xs text-muted-foreground" data-testid="masters-read-only">
                    <Lock className="size-3.5" aria-hidden="true" />
                    View only — creating and editing masters needs the User Manager role.
                </p>
            )}

            {groups.length === 0 ? (
                <EmptyState title="No masters match your search" description={`Nothing matches “${search}”.`} />
            ) : (
                <div className="flex flex-col gap-6">
                    {groups.map(({ category, items }) => (
                        <section key={category} aria-labelledby={`masters-${category}`}>
                            <h2 id={`masters-${category}`} className="mb-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">
                                {category}
                            </h2>
                            <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card">
                                {items.map(master => {
                                    const count = countByEntity.get(master.entity);
                                    return (
                                        <li key={master.entity}>
                                            <Link
                                                to={master.path}
                                                className="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                                            >
                                                <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                                                    <Icon name={master.icon} className="size-4" aria-hidden="true" />
                                                </span>
                                                <span className="min-w-0 flex-1">
                                                    <span className="block truncate text-sm font-medium text-foreground">{master.label}</span>
                                                    {master.description && (
                                                        <span className="block truncate text-xs text-muted-foreground">{master.description}</span>
                                                    )}
                                                </span>
                                                <span className="shrink-0 text-sm tabular-nums text-muted-foreground" data-testid={`master-count-${master.entity}`}>
                                                    {count?.isPending ? (
                                                        <Skeleton className="h-4 w-10" aria-label="Loading count" />
                                                    ) : count?.isError ? (
                                                        <span title="Count unavailable" aria-label="Count unavailable">—</span>
                                                    ) : (
                                                        <span aria-label={`${count?.data} records`}>{(count?.data ?? 0).toLocaleString("en-IN")}</span>
                                                    )}
                                                </span>
                                                <ChevronRight className="size-4 shrink-0 text-muted-foreground/60 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                                            </Link>
                                        </li>
                                    );
                                })}
                            </ul>
                        </section>
                    ))}
                </div>
            )}
        </div>
    );
}
