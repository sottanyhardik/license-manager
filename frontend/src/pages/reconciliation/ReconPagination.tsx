import DataPagination from "@/components/DataPagination";
import { RECON_DEFAULT_PAGE_SIZE, type ReconPaginationState } from "./useReconTabQuery";

/** Server-side pager for a reconciliation tab; hidden when everything fits on one page. */
export default function ReconPagination({ pagination }: { pagination: ReconPaginationState }) {
    if (pagination.totalItems <= RECON_DEFAULT_PAGE_SIZE) return null;
    return <DataPagination {...pagination} />;
}
