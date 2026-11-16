import { useQuery } from "@tanstack/react-query";

import api from "@/api/axios";
import { qk } from "@/lib/queryKeys";
import { EmptyState, InlineError, LoadingState } from "@/components/shared";

import { FieldGrid, type FieldSpec } from "@/components/shared/FieldGrid";

const ALLOTMENT_FIELDS: FieldSpec[] = [
    { key: "invoice", label: "Invoice" },
    { key: "item_name", label: "Item" },
    { key: "company_name", label: "Company" },
    { key: "port_name", label: "Port" },
    { key: "required_quantity", label: "Required Qty" },
    { key: "cif_fc", label: "CIF (FC)" },
    { key: "cif_inr", label: "CIF (INR)" },
    { key: "is_approved", label: "Approved" },
];

/** `allotment` on a BOE row is a list of ids (or, defensively, `{ id }` objects). */
function allotmentIds(value: unknown): number[] {
    if (!Array.isArray(value)) return [];
    return value
        .map((a) => (typeof a === "object" && a !== null ? (a as { id?: unknown }).id : a))
        .filter((id): id is number => typeof id === "number");
}

function LinkedAllotment({ id }: { id: number }) {
    const { data, isPending, isError, error, refetch } = useQuery({
        queryKey: qk.allotments.detail(id),
        queryFn: async ({ signal }) => (await api.get(`allotments/${id}/`, { signal })).data as Record<string, unknown>,
        staleTime: 30_000,
        refetchOnWindowFocus: false,
    });
    return (
        <section aria-label={`Allotment ${id}`} className="rounded-md border border-border/70 p-3">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">Allotment #{id}</h4>
            {isPending ? <LoadingState variant="skeleton-rows" rows={2} label={`Loading allotment ${id}`} />
                : isError || !data ? <InlineError error={error} onRetry={() => { void refetch(); }} title={`Could not load allotment ${id}`} />
                    : <FieldGrid record={data} fields={ALLOTMENT_FIELDS} />}
        </section>
    );
}

/** Linked allotments via the existing `allotments/:id/` endpoint, one request per linked id (no multi-id endpoint), deduplicated via `qk.allotments.detail(id)`; on open only. */
export function AllotmentMappingTab({ allotment }: { allotment: unknown }) {
    const ids = allotmentIds(allotment);
    if (ids.length === 0) return <EmptyState title="No linked allotments" description="This BOE is not linked to an allotment." />;
    return (
        <div className="space-y-3">
            {ids.map((id) => <LinkedAllotment key={id} id={id} />)}
        </div>
    );
}
