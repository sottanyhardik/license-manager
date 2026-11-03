/**
 * The licence operations that used to live in the legacy accordion's action
 * panel. Balance PDF and Excel are read-only. Auto plan, Fetch from DGFT and
 * Delete need LICENSE_MANAGER. Delete and DGFT are owned by the list page
 * (they change the list and the open licence), so they arrive as callbacks.
 */
import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Ellipsis, FileSpreadsheet, FileText, ScanSearch, Trash2 } from "lucide-react";
import api from "@/api/axios";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { autoPlanLicense } from "@/services/api/planningRuleApi";
import { openAuthedFile } from "@/utils/documentDownload";
import { openPdfPreview } from "@/utils/pdfPreview";
import { LICENSE_LIST_QUERY_ROOT } from "../useLicenseListQuery";
import { refreshLicenceWorkspace } from "./licenceWorkspaceQueries";

/** Callbacks the list page owns. The workspace only passes the licence id. */
export interface LicenceListActions {
  onDelete: (licenceId: number) => void;
  onFetchOwnership: (licenceId: number) => void;
  /** True while this licence's ownership fetch is running. */
  fetchingOwnership: boolean;
}

interface LicenceActionsMenuProps extends LicenceListActions {
  licenceId: number;
  /** Used in download file names. Falls back to the id. */
  licenceNumber: string | null;
  canWrite: boolean;
}

export default function LicenceActionsMenu({
  licenceId,
  licenceNumber,
  canWrite,
  fetchingOwnership,
  onDelete,
  onFetchOwnership,
}: LicenceActionsMenuProps) {
  const queryClient = useQueryClient();
  const [isPlanning, setIsPlanning] = useState(false);
  const fileBase = licenceNumber || String(licenceId);

  const downloadPdf = useCallback(async () => {
    try {
      const response = await api.get(`licenses/${licenceId}/balance-pdf/`, { responseType: "blob" });
      openPdfPreview(response.data as Blob, `${fileBase}-balance.pdf`);
    } catch (err: unknown) {
      toast.error((err as { response?: { data?: { error?: string } } })?.response?.data?.error || "Failed to generate PDF");
    }
  }, [fileBase, licenceId]);

  const downloadExcel = useCallback(async () => {
    try {
      toast.info("Generating Excel file...");
      await openAuthedFile(`licenses/${licenceId}/balance-excel/`, `${fileBase}-balance.xlsx`);
      toast.success("Excel file downloaded successfully!");
    } catch (err: unknown) {
      console.error("Excel download error:", err);
      let message = "Failed to download Excel file";
      if (err && typeof err === "object") {
        if ("response" in err && (err as { response?: { data?: { error?: string } } }).response?.data?.error) {
          message = (err as { response: { data: { error: string } } }).response.data.error;
        } else if ("message" in err) {
          message = String((err as { message: unknown }).message);
        }
      }
      toast.error(message);
    }
  }, [fileBase, licenceId]);

  const autoPlan = useCallback(async () => {
    if (isPlanning) return;
    setIsPlanning(true);
    try {
      const result = await autoPlanLicense(licenceId);
      await Promise.all([
        refreshLicenceWorkspace(queryClient, licenceId),
        queryClient.invalidateQueries({ queryKey: LICENSE_LIST_QUERY_ROOT }),
      ]);
      toast.success(result.message || "Licence planning has completed.");
    } catch {
      toast.error("Failed to auto-plan licence.");
    } finally {
      setIsPlanning(false);
    }
  }, [isPlanning, licenceId, queryClient]);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" aria-label="Licence actions">
          <Ellipsis className="size-4" aria-hidden="true" />
          Actions
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-56">
        <DropdownMenuItem onSelect={() => void downloadPdf()}>
          <FileText className="size-4" aria-hidden="true" />
          Balance PDF
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void downloadExcel()}>
          <FileSpreadsheet className="size-4" aria-hidden="true" />
          Balance Excel
        </DropdownMenuItem>
        {canWrite && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled={isPlanning} onSelect={() => void autoPlan()}>
              <ScanSearch className="size-4" aria-hidden="true" />
              {isPlanning ? "Auto planning…" : "Auto plan"}
            </DropdownMenuItem>
            <DropdownMenuItem disabled={fetchingOwnership} onSelect={() => onFetchOwnership(licenceId)}>
              {fetchingOwnership ? "Fetching from DGFT…" : "Fetch from DGFT"}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-destructive focus:text-destructive"
              onSelect={() => onDelete(licenceId)}
            >
              <Trash2 className="size-4" aria-hidden="true" />
              Delete licence
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
