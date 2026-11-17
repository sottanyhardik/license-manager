import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, fireEvent } from "@testing-library/react";
import { useUnsavedChangesGuard } from "./useUnsavedChangesGuard";

afterEach(() => vi.restoreAllMocks());

describe("useUnsavedChangesGuard", () => {
  it("does not prompt when clean", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { result } = renderHook(() => useUnsavedChangesGuard({ dirty: false }));
    expect(result.current.confirmLeave()).toBe(true);
    expect(confirm).not.toHaveBeenCalled();
    const ev = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(ev);
    expect(ev.defaultPrevented).toBe(false);
  });

  it("prompts on confirmLeave and beforeunload when dirty", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { result } = renderHook(() => useUnsavedChangesGuard({ dirty: true }));
    expect(result.current.confirmLeave()).toBe(false);
    expect(confirm).toHaveBeenCalledTimes(1);
    const ev = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(ev);
    expect(ev.defaultPrevented).toBe(true);
  });

  it("blocks in-app link clicks unless confirmed, ignores external/new-tab", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderHook(() => useUnsavedChangesGuard({ dirty: true }));
    const a = document.createElement("a");
    a.href = "/somewhere";
    document.body.appendChild(a);
    expect(fireEvent.click(a)).toBe(false); // default prevented
    confirm.mockReturnValue(true);
    expect(fireEvent.click(a)).toBe(true);
    confirm.mockClear();
    a.target = "_blank";
    fireEvent.click(a);
    expect(confirm).not.toHaveBeenCalled();
    a.remove();
  });

  it("bypass skips prompts after a successful save", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { result } = renderHook(() => useUnsavedChangesGuard({ dirty: true }));
    result.current.bypass();
    expect(result.current.confirmLeave()).toBe(true);
    expect(confirm).not.toHaveBeenCalled();
  });

  it("re-arms after bypass once the form is clean again (modal save, form stays mounted)", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { result, rerender } = renderHook(({ dirty }) => useUnsavedChangesGuard({ dirty }), {
      initialProps: { dirty: true },
    });
    result.current.bypass();
    rerender({ dirty: false }); // new baseline after save
    rerender({ dirty: true }); // user edits again
    expect(result.current.confirmLeave()).toBe(false);
    expect(confirm).toHaveBeenCalledTimes(1);
  });

  it("is inert when disabled", () => {
    const { result } = renderHook(() => useUnsavedChangesGuard({ dirty: true, enabled: false }));
    expect(result.current.confirmLeave()).toBe(true);
  });
});
