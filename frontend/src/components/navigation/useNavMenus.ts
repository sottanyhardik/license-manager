import { useCallback, useEffect, useMemo, useRef, useState } from "react";

/** Delay before a hover opens a menu when none is open (filters cursor fly-bys). */
export const HOVER_OPEN_DELAY_MS = 60;
/** Grace period after the pointer leaves before the open menu closes. */
export const HOVER_CLOSE_DELAY_MS = 180;

export type FocusTarget = "first" | "last";

export interface NavMenusController {
    openId: string | null;
    /** Pending keyboard focus request for the menu that just opened. */
    focusRequest: { id: string; target: FocusTarget } | null;
    open: (id: string, focus?: FocusTarget) => void;
    close: () => void;
    toggle: (id: string) => void;
    hoverEnter: (id: string) => void;
    hoverLeave: () => void;
    consumeFocusRequest: () => void;
}

/**
 * One shared open-state for every dropdown in the bar, so at most one menu is
 * ever rendered: hovering another category swaps menus in a single render
 * instead of briefly showing two (the old per-menu state did).
 */
export function useNavMenus(): NavMenusController {
    const [openId, setOpenId] = useState<string | null>(null);
    const [focusRequest, setFocusRequest] = useState<NavMenusController["focusRequest"]>(null);
    const openIdRef = useRef<string | null>(null);
    const timerRef = useRef<number | undefined>(undefined);

    const clearTimer = useCallback(() => {
        window.clearTimeout(timerRef.current);
        timerRef.current = undefined;
    }, []);

    const setOpen = useCallback((id: string | null) => {
        openIdRef.current = id;
        setOpenId(id);
    }, []);

    useEffect(() => clearTimer, [clearTimer]);

    const open = useCallback((id: string, focus?: FocusTarget) => {
        clearTimer();
        setOpen(id);
        setFocusRequest(focus ? { id, target: focus } : null);
    }, [clearTimer, setOpen]);

    const close = useCallback(() => {
        clearTimer();
        setOpen(null);
        setFocusRequest(null);
    }, [clearTimer, setOpen]);

    const toggle = useCallback((id: string) => {
        if (openIdRef.current === id) close();
        else open(id);
    }, [close, open]);

    const hoverEnter = useCallback((id: string) => {
        clearTimer();
        if (openIdRef.current === id) return;
        if (openIdRef.current !== null) { setOpen(id); return; }   // switching: no delay
        timerRef.current = window.setTimeout(() => setOpen(id), HOVER_OPEN_DELAY_MS);
    }, [clearTimer, setOpen]);

    const hoverLeave = useCallback(() => {
        clearTimer();
        if (openIdRef.current === null) return;
        timerRef.current = window.setTimeout(() => setOpen(null), HOVER_CLOSE_DELAY_MS);
    }, [clearTimer, setOpen]);

    const consumeFocusRequest = useCallback(() => setFocusRequest(null), []);

    return useMemo(() => ({
        openId, focusRequest, open, close, toggle, hoverEnter, hoverLeave, consumeFocusRequest,
    }), [openId, focusRequest, open, close, toggle, hoverEnter, hoverLeave, consumeFocusRequest]);
}

/** Move focus to the previous/next top-level trigger in the same menu bar. */
export function siblingTrigger(from: HTMLElement, dir: 1 | -1): HTMLElement | null {
    const bar = from.closest("[data-nav-bar]");
    if (!bar) return null;
    const triggers = Array.from(bar.querySelectorAll<HTMLElement>("[data-nav-trigger]"));
    const anchor = from.closest("[data-nav-menu-root]")?.querySelector<HTMLElement>("[data-nav-trigger]") ?? from;
    const index = triggers.indexOf(anchor);
    if (index < 0 || triggers.length === 0) return null;
    return triggers[(index + dir + triggers.length) % triggers.length];
}
