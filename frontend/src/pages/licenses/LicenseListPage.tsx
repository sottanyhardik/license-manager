import { useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { toast } from "sonner";
import { FileSpreadsheet, FileText, Inbox, Loader2, Plus, RefreshCw, TriangleAlert } from "lucide-react";
import api from "@/api/axios";
import DataPagination from "@/components/DataPagination";
import PageHeader from "@/components/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { AuthContext } from "@/context/AuthContext";
import { useConfirmDialog } from "@/hooks/useConfirmDialog";
import { openPdfPreview } from "@/utils/pdfPreview";
import { LicenseListFilters } from "./components/LicenseListFilters";
import LicenseAccordionList from "./LicenseAccordionList";
import {
  DEFAULT_PAGE_SIZE,
  serializeLicenseListSearch,
  toFilterApiParams,
  validateLicenseListFilters,
  type LicenseListPageSize,
} from "./licenseListFilters";
import { useLicenseLabelLookup } from "./useLicenseFilterOptions";
import {
  LICENSE_LIST_QUERY_ROOT,
  useLicenseListQuery,
} from "./useLicenseListQuery";
import { useLicenseListState } from "./useLicenseListState";
import LicenceWorkspace from "./workspace/LicenceWorkspace";
import { refreshLicenceWorkspace } from "./workspace/licenceWorkspaceQueries";
import { useLicenceWorkspaceState } from "./workspace/useLicenceWorkspaceState";

const XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

interface OwnershipResponse {
  current_owner?: { name?: string } | null;
  transfers_count?: number;
}

/** Reads a string field from an axios error body (`detail`, `error`, ...). */
function errorBodyField(error: unknown, field: string): string | undefined {
  if (!isAxiosError(error)) return undefined;
  const body = error.response?.data as Record<string, unknown> | undefined;
  const value = body?.[field];
  return typeof value === "string" ? value : undefined;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * `/licenses`. Filters, page and page size live in the URL (see useLicenseListState).
 * The open licence is page state only, so a reload starts with none open. Only one
 * row is open. Changing the filters or search closes it. Changing the page does not,
 * and if the licence is not on the new page, its workspace stays open above the list.
 */
export default function LicenseListPage() {
  const { hasAnyRole } = useContext(AuthContext);
  const canWrite = hasAnyRole(["LICENSE_MANAGER"]);
  const list = useLicenseListState();
  const { state } = list;
  const workspace = useLicenceWorkspaceState();
  const { licenceId: openLicenceId, openLicence, closeLicence } = workspace;

  // A filter or search change closes the open licence. The check runs during render, so
  // the closed workspace is never shown beside the new results. Page and page size do not
  // count, so paging keeps the licence open.
  const selectionKey = serializeLicenseListSearch({ ...state, page: 1, pageSize: DEFAULT_PAGE_SIZE });
  const [appliedSelectionKey, setAppliedSelectionKey] = useState(selectionKey);
  if (appliedSelectionKey !== selectionKey) {
    setAppliedSelectionKey(selectionKey);
    closeLicence();
  }
  const query = useLicenseListQuery(state);
  const labels = useLicenseLabelLookup(state.filters);
  const errors = useMemo(() => validateLicenseListFilters(state.filters), [state.filters]);
  const queryClient = useQueryClient();
  const { confirmDelete, confirmDialog } = useConfirmDialog();
  const [fetchingOwnershipIds, setFetchingOwnershipIds] = useState<Set<number>>(() => new Set());
  const [pdfLoading, setPdfLoading] = useState(false);

  const data = query.data;
  const rows = data?.results ?? [];
  const isPageOutOfRange =
    isAxiosError(query.error) && query.error.response?.status === 404 && state.page > 1;
  const openIsOnPage = openLicenceId !== null && rows.some((row) => row.id === openLicenceId);

  const invalidateList = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: LICENSE_LIST_QUERY_ROOT });
  }, [queryClient]);

  /** Clicking the open row closes it. Clicking any other row opens that one instead. */
  const handleToggleLicence = useCallback(
    (licenceId: number) => {
      if (licenceId === openLicenceId) closeLicence();
      else openLicence(licenceId);
    },
    [openLicenceId, openLicence, closeLicence],
  );

  const handleDelete = useCallback(
    async (licenceId: number) => {
      const confirmed = await confirmDelete("this record");
      if (!confirmed) return;
      try {
        await api.delete(`licenses/${licenceId}/`);
        toast.success("Record deleted successfully");
        if (licenceId === openLicenceId) closeLicence();
        invalidateList();
      } catch (err) {
        toast.error(errorBodyField(err, "detail") || "Failed to delete record");
      }
    },
    [confirmDelete, invalidateList, openLicenceId, closeLicence],
  );

  const handleFetchOwnership = useCallback(
    async (licenceId: number) => {
      setFetchingOwnershipIds((prev) => new Set(prev).add(licenceId));
      try {
        const response = await api.post<OwnershipResponse>(`license-actions/${licenceId}/fetch-ownership/`);
        const owner = response.data?.current_owner?.name || "—";
        toast.success(`Ownership updated: ${owner} (${response.data?.transfers_count ?? 0} transfers)`);
        invalidateList();
        void refreshLicenceWorkspace(queryClient, licenceId);
      } catch (err) {
        const message =
          errorBodyField(err, "error") || (err instanceof Error ? err.message : "") || "Failed to fetch ownership";
        toast.error(message);
      } finally {
        setFetchingOwnershipIds((prev) => {
          const next = new Set(prev);
          next.delete(licenceId);
          return next;
        });
      }
    },
    [invalidateList, queryClient],
  );

  /** Same endpoint and parameters as the licence branch of MasterList's export, with the canonical filter params. */
  const handleExport = async (format: "xlsx" | "pdf") => {
    const params = { ...toFilterApiParams(state), _export: format };
    const today = new Date().toISOString().split("T")[0];
    try {
      if (format === "pdf") {
        setPdfLoading(true);
        try {
          const response = await api.get("licenses/export/", {
            params,
            responseType: "blob",
            headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
          });
          const blob = new Blob([response.data], { type: "application/pdf" });
          const opened = openPdfPreview(blob, `licenses_${today}.pdf`);
          if (!opened) toast.error("Pop-up blocked. Allow pop-ups for this site to view the PDF.");
        } finally {
          setPdfLoading(false);
        }
      } else {
        const response = await api.get("licenses/export/", { params, responseType: "blob" });
        downloadBlob(new Blob([response.data], { type: XLSX_MIME }), `licenses_${today}.xlsx`);
      }
    } catch (err) {
      toast.error(errorBodyField(err, "detail") || `Failed to export as ${format.toUpperCase()}`);
    }
  };

  const countText = useMemo(() => {
    if (!data) return "";
    if (data.count === 0) return "No licences";
    const from = (data.current_page - 1) * data.page_size + 1;
    const to = Math.min(data.current_page * data.page_size, data.count);
    return `Showing ${from}–${to} of ${data.count.toLocaleString("en-IN")} licences`;
  }, [data]);

  const toolbarEnd: ReactNode = (
    <>
      <span data-testid="licence-result-count" className="text-sm tabular-nums text-muted-foreground">
        {countText}
      </span>
      {query.isFetching && !query.isPending && (
        <span role="status" className="text-xs text-muted-foreground">
          Updating…
        </span>
      )}
      <Button variant="outline" onClick={() => void handleExport("xlsx")} aria-label="Export to Excel" title="Export to Excel">
        <FileSpreadsheet className="size-4" aria-hidden="true" />
        <span className="hidden sm:inline">Excel</span>
      </Button>
      <Button
        variant="outline"
        onClick={() => void handleExport("pdf")}
        disabled={pdfLoading}
        aria-label={pdfLoading ? "Generating PDF export" : "Export to PDF"}
        title="Export to PDF"
      >
        {pdfLoading ? (
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        ) : (
          <FileText className="size-4" aria-hidden="true" />
        )}
        <span className="hidden sm:inline">{pdfLoading ? "Generating…" : "PDF"}</span>
      </Button>
      {canWrite && (
        <Button asChild>
          <Link to="/licenses/create">
            <Plus className="size-4" aria-hidden="true" />
            Add New
          </Link>
        </Button>
      )}
    </>
  );

  /** The one workspace for the open licence. The accordion row or the pinned panel below renders it, never both. */
  const workspacePanel: ReactNode =
    openLicenceId !== null ? (
      <LicenceWorkspace
        key={openLicenceId}
        licenceId={openLicenceId}
        tab={workspace.tab}
        itemId={workspace.itemId}
        canWrite={canWrite}
        actions={{
          onDelete: handleDelete,
          onFetchOwnership: handleFetchOwnership,
          fetchingOwnership: fetchingOwnershipIds.has(openLicenceId),
        }}
        onClose={closeLicence}
        onTabChange={workspace.selectTab}
        onItemChange={workspace.selectItem}
      />
    ) : null;

  /**
   * Shown only when the open licence is not in the rows on this page, and only once
   * the rows have settled. Before that the licence may simply not have loaded yet.
   * Rendering it then would mount the workspace twice when the row appears.
   */
  const listSettled = !query.isPending && !query.isPlaceholderData;
  const pinnedPanel =
    listSettled && openLicenceId !== null && !openIsOnPage ? (
      <div className="flex flex-col gap-2">
        <p role="status" className="text-sm text-muted-foreground">
          The open licence is not on this page of results. Its workspace stays open here until you close it.
        </p>
        {workspacePanel}
      </div>
    ) : null;

  let body: ReactNode;
  if (query.isError && !data) {
    body = (
      <Alert variant="destructive" className="bg-card">
        <TriangleAlert aria-hidden="true" />
        <AlertTitle>Could not load licences</AlertTitle>
        <AlertDescription>
          <p>
            {isPageOutOfRange
              ? "This page is out of range for the current filters."
              : "The licence list did not load. Check the connection and try again."}
          </p>
          <div className="mt-3">
            {isPageOutOfRange ? (
              <Button type="button" variant="outline" onClick={() => list.setPage(1)}>
                Go to page 1
              </Button>
            ) : (
              <Button type="button" variant="outline" onClick={() => void query.refetch()}>
                <RefreshCw className="size-4" aria-hidden="true" />
                Retry
              </Button>
            )}
          </div>
        </AlertDescription>
      </Alert>
    );
  } else if (query.isPending) {
    body = (
      <LicenseAccordionList
        loading
        data={[]}
        expandedLicenceId={openLicenceId}
        onToggleLicence={handleToggleLicence}
        workspace={workspacePanel}
      />
    );
  } else if (rows.length === 0) {
    body = (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <div className="flex size-14 items-center justify-center rounded-full bg-muted">
          <Inbox className="size-7 text-muted-foreground/60" aria-hidden="true" />
        </div>
        <h3 className="text-base font-semibold text-foreground">No licences match these filters</h3>
        <p className="text-sm text-muted-foreground">Try a different search, or return to the default view.</p>
        <Button type="button" variant="outline" onClick={list.clearToBaseline}>
          Clear all
        </Button>
      </div>
    );
  } else {
    body = (
      <>
        <LicenseAccordionList
          loading={false}
          data={rows}
          expandedLicenceId={openLicenceId}
          onToggleLicence={handleToggleLicence}
          workspace={workspacePanel}
        />
        {data && (
          <DataPagination
            currentPage={state.page}
            totalPages={data.total_pages}
            pageSize={state.pageSize}
            hasNext={data.has_next}
            hasPrevious={data.has_previous}
            totalItems={data.count}
            onPageChange={list.setPage}
            onPageSizeChange={(size) => list.setPageSize(size as LicenseListPageSize)}
          />
        )}
      </>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Licences" />

      <LicenseListFilters
        state={state}
        labels={labels}
        errors={errors}
        searchDraft={list.searchDraft}
        onSearchDraftChange={list.setSearchDraft}
        onSearchSubmit={list.commitSearchNow}
        onFilterChange={list.setFilters}
        onRemoveChip={(chip) => list.commit(chip.remove)}
        onClearAll={list.clearToBaseline}
        toolbarEnd={toolbarEnd}
      />

      {pinnedPanel}

      <div data-testid="licence-results" aria-busy={query.isFetching} className="flex flex-col gap-2">
        {body}
      </div>

      {confirmDialog}
    </div>
  );
}
