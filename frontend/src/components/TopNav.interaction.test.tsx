import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthContext } from "../context/AuthContext";
import { ThemeContext } from "../context/ThemeContext";
import TopNav from "./TopNav";
import { HOVER_CLOSE_DELAY_MS, HOVER_OPEN_DELAY_MS } from "./navigation/useNavMenus";

vi.mock("./CommandPalette", () => ({ default: () => null }));

// jsdom ships no PointerEvent, so fireEvent would drop `pointerType`.  A
// minimal MouseEvent-based stand-in keeps mouse vs touch distinguishable.
if (typeof globalThis.PointerEvent === "undefined") {
    class PointerEventPolyfill extends MouseEvent {
        pointerType: string;
        constructor(type: string, init: PointerEventInit = {}) {
            super(type, init);
            this.pointerType = init.pointerType ?? "";
        }
    }
    globalThis.PointerEvent = PointerEventPolyfill as unknown as typeof PointerEvent;
}

const ROLES_ALL = ["LICENSE_MANAGER", "TRADE_MANAGER", "BOE_MANAGER", "ALLOTMENT_MANAGER", "REPORT_VIEWER", "LEDGER_MANAGER", "INCENTIVE_LICENSE_MANAGER"];

function LocationProbe() {
    const location = useLocation();
    return <output data-testid="location">{location.pathname}</output>;
}

function renderNav(path = "/dashboard", roles = ROLES_ALL) {
    const auth = {
        user: { id: 1, username: "operator", roles, is_superuser: false },
        loading: false,
        loginSuccess: vi.fn(),
        logout: vi.fn(),
        hasRole: (r: string) => roles.includes(r),
        hasAnyRole: (required: string[]) => required.some(r => roles.includes(r)),
        isSuperAdmin: () => false,
        canManageUsers: () => false,
    };
    return render(
        <MemoryRouter initialEntries={[path]}>
            <ThemeContext.Provider value={{ theme: "light", toggleTheme: vi.fn() }}>
                <AuthContext.Provider value={auth as never}>
                    <TopNav />
                    <Routes><Route path="*" element={<LocationProbe />} /></Routes>
                </AuthContext.Provider>
            </ThemeContext.Provider>
        </MemoryRouter>,
    );
}

const trigger = (name: string) => screen.getByRole("button", { name });
const rootOf = (name: string) => trigger(name).closest("[data-nav-menu-root]") as HTMLElement;
const mouse = { pointerType: "mouse" };
const hover = (name: string) => fireEvent.pointerEnter(rootOf(name), mouse);
const unhover = (name: string) => fireEvent.pointerLeave(rootOf(name), mouse);
const advance = (ms: number) => act(() => { vi.advanceTimersByTime(ms); });

describe("TopNav hover interaction", () => {
    beforeEach(() => { vi.useFakeTimers(); });
    afterEach(() => { vi.useRealTimers(); });

    it("opens on hover after the intent delay and exposes ARIA state", () => {
        renderNav();
        hover("Licenses");
        expect(screen.queryByRole("menu")).toBeNull();
        advance(HOVER_OPEN_DELAY_MS);
        const menu = screen.getByRole("menu");
        expect(trigger("Licenses")).toHaveAttribute("aria-expanded", "true");
        expect(trigger("Licenses")).toHaveAttribute("aria-controls", menu.id);
        expect(menu).toHaveAttribute("aria-labelledby", trigger("Licenses").id);
        expect(within(menu).getAllByRole("menuitem").map(i => i.textContent)).toEqual([
            "Licenses", "Auto Plan", "Incentive Licenses", "License Ledger", "Ledger Upload",
        ]);
    });

    it("switches category immediately without ever rendering two menus", () => {
        renderNav();
        hover("Licenses"); advance(HOVER_OPEN_DELAY_MS);
        unhover("Licenses");
        hover("Reports");
        expect(screen.getAllByRole("menu")).toHaveLength(1);
        expect(trigger("Reports")).toHaveAttribute("aria-expanded", "true");
        expect(trigger("Licenses")).toHaveAttribute("aria-expanded", "false");
        advance(HOVER_CLOSE_DELAY_MS * 2);
        expect(screen.getAllByRole("menu")).toHaveLength(1);
    });

    it("stays open while the pointer travels into the dropdown, closes after leaving", () => {
        renderNav();
        hover("Masters"); advance(HOVER_OPEN_DELAY_MS);
        const menu = screen.getByRole("menu");
        // Moving into the dropdown stays inside the menu root: no leave event.
        fireEvent.pointerEnter(menu, mouse);
        advance(HOVER_CLOSE_DELAY_MS * 2);
        expect(screen.getByRole("menu")).toBeInTheDocument();
        unhover("Masters");
        advance(HOVER_CLOSE_DELAY_MS - 1);
        expect(screen.getByRole("menu")).toBeInTheDocument();   // grace period
        hover("Masters");                                        // came back in time
        advance(HOVER_CLOSE_DELAY_MS * 2);
        expect(screen.getByRole("menu")).toBeInTheDocument();
        unhover("Masters");
        advance(HOVER_CLOSE_DELAY_MS);
        expect(screen.queryByRole("menu")).toBeNull();
    });

    it("a quick fly-by over a trigger does not open anything", () => {
        renderNav();
        hover("Operations");
        unhover("Operations");
        advance(HOVER_OPEN_DELAY_MS * 3);
        expect(screen.queryByRole("menu")).toBeNull();
    });

    it("re-opens on the next mouse move after an item was selected (no fresh pointerenter)", () => {
        renderNav();
        hover("Reports"); advance(HOVER_OPEN_DELAY_MS);
        fireEvent.click(screen.getByRole("menuitem", { name: "Item Report" }));
        expect(screen.queryByRole("menu")).toBeNull();
        fireEvent.pointerMove(trigger("Reports"), mouse);
        advance(HOVER_OPEN_DELAY_MS);
        expect(trigger("Reports")).toHaveAttribute("aria-expanded", "true");
    });

    it("Escape-closed menu does not re-open on a pointer jiggle", () => {
        renderNav();
        hover("Reports"); advance(HOVER_OPEN_DELAY_MS);
        fireEvent.keyDown(document, { key: "Escape" });
        fireEvent.pointerMove(trigger("Reports"), mouse);
        advance(HOVER_OPEN_DELAY_MS * 3);
        expect(screen.queryByRole("menu")).toBeNull();
    });

    it("hovering Dashboard closes an open dropdown", () => {
        renderNav();
        hover("Reports"); advance(HOVER_OPEN_DELAY_MS);
        fireEvent.pointerEnter(screen.getByRole("link", { name: "Dashboard" }), mouse);
        expect(screen.queryByRole("menu")).toBeNull();
    });

    it("clears pending hover timers on unmount", () => {
        const { unmount } = renderNav();
        const before = vi.getTimerCount();
        hover("Licenses");
        expect(vi.getTimerCount()).toBe(before + 1);
        unmount();
        expect(vi.getTimerCount()).toBe(before);
    });
});

describe("TopNav click / touch interaction", () => {
    it("touch: emulated hover is ignored and a tap toggles the menu", () => {
        renderNav();
        fireEvent.pointerEnter(rootOf("Reports"), { pointerType: "touch" });
        expect(screen.queryByRole("menu")).toBeNull();
        fireEvent.pointerDown(trigger("Reports"), { pointerType: "touch" });
        fireEvent.click(trigger("Reports"));
        expect(screen.getByRole("menu")).toBeInTheDocument();
        fireEvent.pointerDown(trigger("Reports"), { pointerType: "touch" });
        fireEvent.click(trigger("Reports"));
        expect(screen.queryByRole("menu")).toBeNull();
    });

    it("a mouse click on a hover-opened trigger keeps it open", () => {
        renderNav();
        fireEvent.pointerDown(trigger("Masters"), mouse);
        fireEvent.click(trigger("Masters"));
        expect(screen.getByRole("menu")).toBeInTheDocument();
        fireEvent.pointerDown(trigger("Masters"), mouse);
        fireEvent.click(trigger("Masters"));
        expect(screen.getByRole("menu")).toBeInTheDocument();
    });

    it("clicking outside closes; clicking an item navigates and closes", () => {
        renderNav();
        fireEvent.click(trigger("Operations"));
        fireEvent.pointerDown(document.body);
        expect(screen.queryByRole("menu")).toBeNull();

        fireEvent.click(trigger("Operations"));
        fireEvent.click(screen.getByRole("menuitem", { name: "Bill of Entry" }));
        expect(screen.getByTestId("location")).toHaveTextContent("/bill-of-entries");
        expect(screen.queryByRole("menu")).toBeNull();
    });

    it("every menu item links to its existing route", () => {
        renderNav();
        const hrefs: string[] = [];
        for (const name of ["Licenses", "Operations", "Reports", "Masters"]) {
            fireEvent.click(trigger(name));
            hrefs.push(...within(screen.getByRole("menu")).getAllByRole("menuitem").map(a => a.getAttribute("href") ?? ""));
            fireEvent.click(trigger(name));
        }
        // Masters: overview + 13 registered masters (masterEntities, grouped by category).
        expect(hrefs).toHaveLength(5 + 5 + 12 + 14);
        expect(hrefs).toContain("/reports/parle/sion-e132");
        expect(hrefs).toContain("/masters/exchange-rates");
        expect(hrefs).toContain("/masters");
        expect(hrefs).toContain("/masters/notification-numbers");
    });
});

describe("TopNav keyboard + active route", () => {
    it("ArrowDown opens and focuses the first item; arrows rove; Escape returns focus", () => {
        renderNav();
        const t = trigger("Licenses");
        t.focus();
        fireEvent.keyDown(t, { key: "ArrowDown" });
        const items = within(screen.getByRole("menu")).getAllByRole("menuitem");
        expect(items[0]).toHaveFocus();
        fireEvent.keyDown(items[0], { key: "ArrowDown" });
        expect(items[1]).toHaveFocus();
        fireEvent.keyDown(items[1], { key: "End" });
        expect(items[items.length - 1]).toHaveFocus();
        fireEvent.keyDown(items[items.length - 1], { key: "ArrowDown" });
        expect(items[0]).toHaveFocus();                       // wraps
        fireEvent.keyDown(items[0], { key: "Escape" });
        expect(screen.queryByRole("menu")).toBeNull();
        expect(t).toHaveFocus();
    });

    it("ArrowRight inside a menu moves to the next category's first item", () => {
        renderNav();
        fireEvent.keyDown(trigger("Licenses"), { key: "Enter" });
        fireEvent.keyDown(screen.getAllByRole("menuitem")[0], { key: "ArrowRight" });
        expect(trigger("Operations")).toHaveAttribute("aria-expanded", "true");
        expect(screen.getByRole("menuitem", { name: "Allotments" })).toHaveFocus();
    });

    it("ArrowLeft/Right on the bar moves between top-level triggers", () => {
        renderNav();
        const dash = screen.getByRole("link", { name: "Dashboard" });
        dash.focus();
        fireEvent.keyDown(dash, { key: "ArrowRight" });
        expect(trigger("Licenses")).toHaveFocus();
        fireEvent.keyDown(trigger("Licenses"), { key: "ArrowLeft" });
        expect(dash).toHaveFocus();
        fireEvent.keyDown(dash, { key: "ArrowLeft" });
        expect(trigger("Masters")).toHaveFocus();             // wraps
    });

    it("highlights the current route and its category, most specific path only", () => {
        renderNav("/license-ledger/download-requests");
        expect(trigger("Reports")).toHaveClass("is-active");
        expect(trigger("Licenses")).not.toHaveClass("is-active");
        fireEvent.click(trigger("Reports"));
        expect(screen.getByRole("menuitem", { name: "License Downloads" })).toHaveAttribute("aria-current", "page");
    });

    it("Reports renders as compact labelled sections", () => {
        renderNav();
        fireEvent.click(trigger("Reports"));
        const groups = within(screen.getByRole("menu")).getAllByRole("group");
        expect(groups.map(g => g.getAttribute("aria-labelledby") && document.getElementById(g.getAttribute("aria-labelledby")!)?.textContent))
            .toEqual(["Reports", "Licence status", "SION norms"]);
    });
});
