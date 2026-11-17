import { useCallback, useEffect, useRef } from "react";

export const UNSAVED_CHANGES_MESSAGE = "You have unsaved changes. Leave this page and discard them?";

interface Options {
    /** True only when the form genuinely differs from its loaded snapshot. */
    dirty: boolean;
    /** Disable the guard entirely (e.g. non-BOE entities). */
    enabled?: boolean;
    message?: string;
}

/**
 * Unsaved-change protection for apps using a non-data router (BrowserRouter),
 * where react-router's useBlocker is unavailable.
 *
 * - beforeunload: tab close / reload / external navigation.
 * - capture-phase click on same-origin in-app anchors (sidebar, links).
 * - `confirmLeave()` for programmatic navigation (Cancel / Back buttons).
 * - `bypass()` lets a confirmed successful save leave without a prompt.
 */
export function useUnsavedChangesGuard({ dirty, enabled = true, message = UNSAVED_CHANGES_MESSAGE }: Options) {
    const active = enabled && dirty;
    const activeRef = useRef(active);
    const bypassRef = useRef(false);
    activeRef.current = active;

    // Re-arm after a successful save: once the form is clean again (new
    // baseline), later edits must be protected even if the form stays mounted.
    useEffect(() => {
        if (!dirty) bypassRef.current = false;
    }, [dirty]);

    useEffect(() => {
        if (!active) return;

        const onBeforeUnload = (e: BeforeUnloadEvent) => {
            if (bypassRef.current) return;
            e.preventDefault();
            e.returnValue = "";
        };

        const onClick = (e: MouseEvent) => {
            if (bypassRef.current || e.defaultPrevented || e.button !== 0) return;
            if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
            const anchor = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
            if (!anchor) return;
            if (anchor.target && anchor.target !== "_self") return;
            if (anchor.hasAttribute("download")) return;
            let url: URL;
            try {
                url = new URL(anchor.href, window.location.href);
            } catch {
                return;
            }
            if (url.origin !== window.location.origin) return;
            if (url.pathname === window.location.pathname && url.search === window.location.search) return;
            if (!window.confirm(message)) {
                e.preventDefault();
                e.stopPropagation();
            }
        };

        window.addEventListener("beforeunload", onBeforeUnload);
        document.addEventListener("click", onClick, true);
        return () => {
            window.removeEventListener("beforeunload", onBeforeUnload);
            document.removeEventListener("click", onClick, true);
        };
    }, [active, message]);

    /** Returns true if it is OK to leave (clean, bypassed, or user confirmed). */
    const confirmLeave = useCallback((): boolean => {
        if (bypassRef.current || !activeRef.current) return true;
        return window.confirm(message);
    }, [message]);

    /** Call after a confirmed successful save, before navigating away. */
    const bypass = useCallback(() => {
        bypassRef.current = true;
    }, []);

    return { confirmLeave, bypass };
}
