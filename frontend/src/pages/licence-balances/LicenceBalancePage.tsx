import PageHeader from "@/components/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import BalancePagination from "./BalancePagination";
import ColumnVisibilityMenu from "./ColumnVisibilityMenu";
import { formatCount } from "./format";
import ListToolbar from "./ListToolbar";
import LicenceBalanceTable from "./LicenceBalanceTable";
import LoadErrorPanel from "./LoadErrorPanel";
import { useLicenceBalanceList } from "./licenceBalanceQueries";
import { useLicenceBalanceParams } from "./useLicenceBalanceParams";
import { useOptionalColumns } from "./useOptionalColumns";

/** `/licence-balances`. Search, expiry, page and page size live in the URL. */
export default function LicenceBalancePage() {
  const balance = useLicenceBalanceParams();
  const { params } = balance;
  const columns = useOptionalColumns();
  const query = useLicenceBalanceList(params, columns.visible.has("legacy"));
  const data = query.data;

  const subtitle = data
    ? `${formatCount(data.count)} ${data.count === 1 ? "licence" : "licences"}`
    : "Item-level CIF and quantity balances, reconciled from the item ledgers";

  return (
    <div className="flex flex-col gap-4 p-4 md:p-6">
      <PageHeader title="Licence balances" description={subtitle} />

      <div className="flex flex-wrap items-center gap-3">
        <ListToolbar
          searchDraft={balance.searchDraft}
          onSearchChange={balance.setSearchDraft}
          expiry={params.expiry}
          onExpiryChange={balance.setExpiry}
          pageSize={params.pageSize}
          onPageSizeChange={balance.setPageSize}
        />
        <div className="ml-auto">
          <ColumnVisibilityMenu visible={columns.visible} onToggle={columns.setColumn} />
        </div>
      </div>

      {!data && !query.isError ? <TableSkeleton /> : null}
      {!data && query.isError ? (
        <LoadErrorPanel
          title="Licence balances could not be loaded."
          error={query.error}
          onRetry={() => void query.refetch()}
        />
      ) : null}

      {data ? (
        <>
          {query.isError ? (
            <LoadErrorPanel
              title="Licence balances could not be refreshed."
              error={query.error}
              onRetry={() => void query.refetch()}
              compact
            />
          ) : null}
          {data.results.length === 0 ? (
            <div
              data-testid="empty-state"
              className="rounded-lg border border-dashed bg-card p-8 text-center text-sm text-muted-foreground"
            >
              No licences match these filters
            </div>
          ) : (
            <div
              aria-busy={query.isFetching}
              className={cn("transition-opacity", query.isPlaceholderData && "opacity-60")}
            >
              <LicenceBalanceTable rows={data.results} visible={columns.visible} />
            </div>
          )}
          <BalancePagination
            page={data.page}
            pageSize={data.page_size}
            count={data.count}
            totalPages={data.total_pages}
            hasPrevious={data.has_previous}
            hasNext={data.has_next}
            onPageChange={balance.setPage}
          />
        </>
      ) : null}
    </div>
  );
}

function TableSkeleton() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Loading licence balances"
      className="flex flex-col gap-2 rounded-lg border bg-card p-4"
    >
      {Array.from({ length: 8 }, (_, index) => (
        <Skeleton key={index} className="h-10 w-full" />
      ))}
    </div>
  );
}
