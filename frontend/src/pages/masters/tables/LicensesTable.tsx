/**
 * LicensesTable: the /licenses register. A list of compact licence cards; one
 * card is expanded at a time into its record workspace
 * (`features/licenses/LicenceCard`). The card owns presentation; the list owns
 * the single-expand state.
 */

import { useCallback, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared";
import { LicenceCard } from "@/features/licenses/LicenceCard";
import type { LicenseListItem } from "@/features/licenses/types";

export type { LicenseListItem };

export interface LicensesTableProps {
    loading: boolean;
    data: LicenseListItem[];
    canWrite: boolean;
    entityName: string;
    filterParams: Record<string, unknown>;
    currentPage: number;
    pageSize: number;
    navigate: (path: string) => void;
    onDelete: (item: LicenseListItem) => void;
    fetchingOwnershipIds: Set<number>;
    onFetchOwnership: (item: LicenseListItem) => void;
    invalidateList: () => void;
    onDGFTComplete?: (licenseId: number) => void;
}

function LicenseSkeleton() {
    return (
        <div role="status" aria-label="Loading licenses" className="space-y-2">
            {[80, 65, 90, 70, 75].map((w, i) => (
                <div key={i} className="flex items-center gap-4 rounded-lg border border-border bg-card px-4 py-3">
                    <Skeleton className="h-4" style={{ width: `${w * 2}px` }} />
                    <Skeleton className="h-3 w-24" />
                    <Skeleton className="h-3 w-28" />
                    <Skeleton className="ml-auto h-5 w-16 rounded-full" />
                    <Skeleton className="h-4 w-24" />
                </div>
            ))}
        </div>
    );
}

export default function LicensesTable({
    loading,
    data,
    canWrite,
    entityName,
    filterParams,
    currentPage,
    pageSize,
    navigate,
    onDelete,
    fetchingOwnershipIds,
    onFetchOwnership,
    onDGFTComplete,
}: LicensesTableProps) {
    // Only one card open at a time.
    const [expandedId, setExpandedId] = useState<number | null>(null);
    const handleToggle = useCallback((id: number) => {
        setExpandedId((prev) => (prev === id ? null : id));
    }, []);

    if (loading) return <LicenseSkeleton />;

    if (data.length === 0) {
        return <EmptyState size="page" title="No licenses found" description="Try adjusting your search or filters." />;
    }

    return (
        <ul className="flex min-w-0 flex-col gap-1.5" aria-label="Licenses">
            {data.map((item) => (
                <li key={item.id} className="min-w-0">
                    <LicenceCard
                        item={item}
                        expanded={expandedId === item.id}
                        onToggle={handleToggle}
                        canWrite={canWrite}
                        entityName={entityName}
                        filterParams={filterParams}
                        currentPage={currentPage}
                        pageSize={pageSize}
                        navigate={navigate}
                        onDelete={onDelete}
                        isFetchingDGFT={fetchingOwnershipIds.has(item.id)}
                        onFetchDGFT={onFetchOwnership}
                        onDGFTComplete={onDGFTComplete}
                    />
                </li>
            ))}
        </ul>
    );
}
