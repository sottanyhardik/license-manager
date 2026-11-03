import { useEffect, useId, useRef, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { LicenceDetail } from "@/pages/licence-balances/types";
import AsyncGate from "./AsyncGate";
import InvoicesTab from "./InvoicesTab";
import LicenceWorkspaceHeader, { type DataState } from "./LicenceWorkspaceHeader";
import type { LicenceListActions } from "./LicenceWorkspaceActions";
import ItemsTab from "./ItemsTab";
import OverviewTab from "./OverviewTab";
import ReconciliationTab from "./ReconciliationTab";
import { refreshLicenceWorkspace, useLicenceHeader, useWorkspaceDetail } from "./licenceWorkspaceQueries";
import { WORKSPACE_TABS, WORKSPACE_TAB_LABELS, asWorkspaceTab, type WorkspaceTab } from "./workspaceTabs";

export interface LicenceWorkspaceProps {
  licenceId: number;
  tab: WorkspaceTab;
  itemId: number | null;
  canWrite: boolean;
  actions: LicenceListActions;
  onClose: () => void;
  onTabChange: (tab: WorkspaceTab, itemId?: number) => void;
  onItemChange: (itemId: number | null) => void;
}

/**
 * The licence workspace. It renders inside the open licence's accordion row on
 * `/licenses`, and only while that licence is open, so its queries run only then.
 * Each tab mounts only while selected, so a tab fetches only when it is opened.
 */
export default function LicenceWorkspace({
  licenceId,
  tab,
  itemId,
  canWrite,
  actions,
  onClose,
  onTabChange,
  onItemChange,
}: LicenceWorkspaceProps) {
  const queryClient = useQueryClient();
  const headingId = useId();
  const sectionRef = useRef<HTMLElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  const detailQuery = useWorkspaceDetail(licenceId);
  const headerQuery = useLicenceHeader(licenceId);

  // Scroll the panel into view and move focus to its heading once, when it opens.
  // The parent keys this component by licence, so each open runs this effect again.
  useEffect(() => {
    const section = sectionRef.current;
    if (section && typeof section.scrollIntoView === "function") {
      section.scrollIntoView({ block: "start", behavior: "smooth" });
    }
    headingRef.current?.focus({ preventScroll: true });
  }, []);

  // Placeholder data from a previously open licence must never reach the screen.
  const detail = detailQuery.data?.licence_id === licenceId ? detailQuery.data : undefined;
  const header = headerQuery.data?.id === licenceId ? headerQuery.data : undefined;
  const detailState: DataState = detail ? "ready" : detailQuery.isError ? "error" : "loading";

  const detailGate = (render: (ready: LicenceDetail) => ReactNode) => (
    <AsyncGate
      data={detail}
      isError={detailQuery.isError}
      error={detailQuery.error}
      onRetry={() => void detailQuery.refetch()}
      loadingLabel="Loading licence balance"
      errorTitle="This licence balance could not be loaded."
    >
      {render}
    </AsyncGate>
  );

  return (
    <section
      ref={sectionRef}
      aria-labelledby={headingId}
      data-testid="licence-workspace"
      className="flex scroll-mt-4 flex-col gap-3 rounded-xl border bg-card p-3 shadow-sm md:p-4"
    >
      <LicenceWorkspaceHeader
        licenceId={licenceId}
        headingId={headingId}
        headingRef={headingRef}
        detail={detail}
        detailState={detailState}
        header={header}
        canWrite={canWrite}
        actions={actions}
        onClose={onClose}
        onRefresh={() => void refreshLicenceWorkspace(queryClient, licenceId)}
      />

      <Tabs value={tab} onValueChange={(value) => onTabChange(asWorkspaceTab(value))}>
        <TabsList aria-label="Licence sections" className="h-auto w-full flex-wrap justify-start">
          {WORKSPACE_TABS.map((value) => (
            <TabsTrigger key={value} value={value}>
              {WORKSPACE_TAB_LABELS[value]}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="overview" className="pt-3">
          {detailGate((ready) => (
            <OverviewTab detail={ready} />
          ))}
        </TabsContent>
        <TabsContent value="items" className="pt-3">
          {detailGate((ready) => (
            <ItemsTab detail={ready} itemId={itemId} onItemChange={onItemChange} />
          ))}
        </TabsContent>
        <TabsContent value="invoices" className="pt-3">
          <InvoicesTab licenceId={licenceId} licenceNumber={header?.license_number ?? detail?.licence_number ?? null} />
        </TabsContent>
        <TabsContent value="reconciliation" className="pt-3">
          {detailGate((ready) => (
            <ReconciliationTab detail={ready} licenceId={licenceId} onOpenItem={(id) => onTabChange("items", id)} />
          ))}
        </TabsContent>
      </Tabs>
    </section>
  );
}
