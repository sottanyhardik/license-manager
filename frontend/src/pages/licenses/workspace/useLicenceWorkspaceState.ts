/**
 * The open licence workspace, held in page state.
 *
 * Nothing here is written to the URL, to storage or to history. A reload therefore
 * starts with no licence open. Only one licence can be open, and opening another
 * replaces it.
 */
import { useCallback, useMemo, useState } from "react";
import { DEFAULT_WORKSPACE_TAB, type WorkspaceTab } from "./workspaceTabs";

interface OpenWorkspace {
  licenceId: number;
  tab: WorkspaceTab;
  itemId: number | null;
}

export interface LicenceWorkspaceState {
  /** The open licence, or null when the workspace is closed. */
  licenceId: number | null;
  tab: WorkspaceTab;
  itemId: number | null;
  /** Opens a licence on Overview. Any workspace already open is replaced. */
  openLicence: (licenceId: number) => void;
  closeLicence: () => void;
  /** Selects a tab. Pass `itemId` to select an item in the same update. */
  selectTab: (tab: WorkspaceTab, itemId?: number) => void;
  selectItem: (itemId: number | null) => void;
}

export function useLicenceWorkspaceState(): LicenceWorkspaceState {
  const [open, setOpen] = useState<OpenWorkspace | null>(null);

  const openLicence = useCallback((licenceId: number) => {
    setOpen({ licenceId, tab: DEFAULT_WORKSPACE_TAB, itemId: null });
  }, []);

  const closeLicence = useCallback(() => setOpen(null), []);

  const selectTab = useCallback((tab: WorkspaceTab, itemId?: number) => {
    setOpen((current) => (current ? { ...current, tab, itemId: itemId ?? current.itemId } : current));
  }, []);

  const selectItem = useCallback((itemId: number | null) => {
    setOpen((current) => (current ? { ...current, itemId } : current));
  }, []);

  return useMemo(
    () => ({
      licenceId: open?.licenceId ?? null,
      tab: open?.tab ?? DEFAULT_WORKSPACE_TAB,
      itemId: open?.itemId ?? null,
      openLicence,
      closeLicence,
      selectTab,
      selectItem,
    }),
    [open, openLicence, closeLicence, selectTab, selectItem],
  );
}
