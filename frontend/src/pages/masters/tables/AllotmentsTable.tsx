/**
 * AllotmentsTable: the /allotments register. A list of compact allotment rows;
 * one row is expanded at a time into its record workspace
 * (`features/allotment/AllotmentCard`) — the Licence register's interaction.
 * The row owns presentation; the list owns the single-expand state.
 */
import { useCallback, useMemo, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared";
import { AllotmentCard } from "@/features/allotment/AllotmentCard";
import type { AllotmentActionContext, AllotmentRecord } from "@/features/allotment/types";

interface AllotmentsTableProps {
    loading: boolean;
    data: AllotmentRecord[];
    canWrite: boolean;
    entityName: string;
    filterParams: Record<string, unknown>;
    currentPage: number;
    pageSize: number;
    navigate: (path: string) => void;
    onDelete: (item: AllotmentRecord) => void;
}

function AllotmentSkeleton() {
    return (
        <div role="status" aria-label="Loading allotments" className="space-y-1.5">
            {[80, 65, 90, 70, 75].map((w, i) => (
                <div key={i} className="flex items-center gap-4 rounded-lg border border-border bg-card px-4 py-3">
                    <Skeleton className="h-4 w-28" />
                    <Skeleton className="h-3" style={{ width: `${w * 2}px` }} />
                    <Skeleton className="ml-auto h-5 w-16 rounded-full" />
                    <Skeleton className="h-4 w-20" />
                    <Skeleton className="h-4 w-20" />
                </div>
            ))}
        </div>
    );
}

export default function AllotmentsTable({
    loading, data, canWrite, entityName, filterParams, currentPage, pageSize, navigate, onDelete,
}: AllotmentsTableProps) {
    // Only one row open at a time (Licence register convention).
    const [expandedId, setExpandedId] = useState<number | null>(null);
    const handleToggle = useCallback((id: number) => setExpandedId((prev) => (prev === id ? null : id)), []);
    const ctx = useMemo<AllotmentActionContext>(
        () => ({ canWrite, entityName, filterParams, currentPage, pageSize, navigate, onDelete }),
        [canWrite, entityName, filterParams, currentPage, pageSize, navigate, onDelete],
    );

    if (loading) return <AllotmentSkeleton />;
    if (data.length === 0) {
        return <EmptyState size="page" title="No allotments found" description="Try adjusting your search or filters, or create a new allotment." />;
    }
    return (
        <ul className="flex min-w-0 flex-col gap-1.5" aria-label="Allotments">
            {data.map((item) => (
                <li key={item.id} className="min-w-0">
                    <AllotmentCard item={item} expanded={expandedId === item.id} onToggle={handleToggle} ctx={ctx} />
                </li>
            ))}
        </ul>
    );
}
