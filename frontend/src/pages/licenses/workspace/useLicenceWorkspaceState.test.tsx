import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useLicenceWorkspaceState } from "./useLicenceWorkspaceState";
import { asWorkspaceTab, WORKSPACE_TABS } from "./workspaceTabs";

describe("useLicenceWorkspaceState", () => {
  it("starts with no licence open, on Overview", () => {
    const { result } = renderHook(() => useLicenceWorkspaceState());
    expect(result.current.licenceId).toBeNull();
    expect(result.current.tab).toBe("overview");
    expect(result.current.itemId).toBeNull();
  });

  it("opens a licence on Overview with no item selected", () => {
    const { result } = renderHook(() => useLicenceWorkspaceState());
    act(() => result.current.openLicence(7));
    expect(result.current.licenceId).toBe(7);
    expect(result.current.tab).toBe("overview");
    expect(result.current.itemId).toBeNull();
  });

  it("opening another licence replaces the open one and resets its tab and item", () => {
    const { result } = renderHook(() => useLicenceWorkspaceState());
    act(() => result.current.openLicence(7));
    act(() => result.current.selectTab("items", 101));

    act(() => result.current.openLicence(8));

    expect(result.current.licenceId).toBe(8);
    expect(result.current.tab).toBe("overview");
    expect(result.current.itemId).toBeNull();
  });

  it("closing removes the licence and leaves the state closed", () => {
    const { result } = renderHook(() => useLicenceWorkspaceState());
    act(() => result.current.openLicence(7));
    act(() => result.current.closeLicence());
    expect(result.current.licenceId).toBeNull();
    expect(result.current.tab).toBe("overview");
  });

  it("selects a tab, and an item in the same update, without closing the licence", () => {
    const { result } = renderHook(() => useLicenceWorkspaceState());
    act(() => result.current.openLicence(7));

    act(() => result.current.selectTab("items", 101));
    expect(result.current.licenceId).toBe(7);
    expect(result.current.tab).toBe("items");
    expect(result.current.itemId).toBe(101);

    act(() => result.current.selectTab("invoices"));
    expect(result.current.tab).toBe("invoices");
    expect(result.current.itemId).toBe(101);
  });

  it("selects and clears an item", () => {
    const { result } = renderHook(() => useLicenceWorkspaceState());
    act(() => result.current.openLicence(7));
    act(() => result.current.selectItem(55));
    expect(result.current.itemId).toBe(55);
    act(() => result.current.selectItem(null));
    expect(result.current.itemId).toBeNull();
    expect(result.current.licenceId).toBe(7);
  });

  it("ignores tab and item updates while the workspace is closed", () => {
    const { result } = renderHook(() => useLicenceWorkspaceState());
    act(() => result.current.selectTab("items", 101));
    act(() => result.current.selectItem(55));
    expect(result.current.licenceId).toBeNull();
    expect(result.current.tab).toBe("overview");
    expect(result.current.itemId).toBeNull();
  });
});

describe("asWorkspaceTab", () => {
  it("keeps the four tabs and falls back to Overview for anything else", () => {
    expect(WORKSPACE_TABS).toEqual(["overview", "items", "invoices", "reconciliation"]);
    for (const tab of WORKSPACE_TABS) expect(asWorkspaceTab(tab)).toBe(tab);
    expect(asWorkspaceTab("boes")).toBe("overview");
    expect(asWorkspaceTab("ledger")).toBe("overview");
    expect(asWorkspaceTab("")).toBe("overview");
  });
});
