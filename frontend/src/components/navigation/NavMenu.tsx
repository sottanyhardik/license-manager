import { createContext, useCallback, useContext, useEffect, useId, useLayoutEffect, useRef } from "react";
import type { CSSProperties, KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent, ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import Icon from "@/components/Icon";
import { siblingTrigger } from "./useNavMenus";
import type { NavMenusController } from "./useNavMenus";

/** Minimum gap kept between an open dropdown and the viewport edge. */
const VIEWPORT_MARGIN_PX = 8;

const NavMenuCloseContext = createContext<() => void>(() => {});

const menuItems = (menu: HTMLElement | null) =>
    Array.from(menu?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);

type NavMenuProps = {
    id: string;
    label: ReactNode;
    icon: string;
    controller: NavMenusController;
    isActive?: boolean;
    align?: "start" | "end";
    columns?: number;
    /** Rows per column for single-section menus (items flow column by column). */
    rows?: number;
    /** Accessible name when `label` is not plain text. */
    ariaLabel?: string;
    children: ReactNode;
};

export function NavMenu({
    id, label, icon, controller, isActive = false, align = "start", columns = 1, rows = 1, ariaLabel, children,
}: NavMenuProps) {
    const { openId, focusRequest, open, close, toggle, hoverEnter, hoverLeave, consumeFocusRequest } = controller;
    const isOpen = openId === id;
    const uid = useId();
    const triggerId = `nav-trigger-${id}-${uid}`;
    const menuId = `nav-menu-${id}-${uid}`;
    const rootRef = useRef<HTMLDivElement | null>(null);
    const triggerRef = useRef<HTMLButtonElement | null>(null);
    const menuRef = useRef<HTMLDivElement | null>(null);
    const lastPointerType = useRef<string>("");
    /** Whether the mouse is (as far as we know) inside this menu's root. */
    const pointerInsideRef = useRef(false);

    const closeAndFocusTrigger = useCallback(() => {
        close();
        triggerRef.current?.focus();
    }, [close]);

    // Outside press / Escape while this menu is open.  Only one menu is open at
    // a time, so at most one set of document listeners is attached.
    useEffect(() => {
        if (!isOpen) return;
        const onPointerDown = (event: PointerEvent) => {
            if (!rootRef.current?.contains(event.target as Node)) close();
        };
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key !== "Escape") return;
            if (rootRef.current?.contains(document.activeElement)) closeAndFocusTrigger();
            else close();
        };
        document.addEventListener("pointerdown", onPointerDown);
        document.addEventListener("keydown", onKeyDown);
        return () => {
            document.removeEventListener("pointerdown", onPointerDown);
            document.removeEventListener("keydown", onKeyDown);
        };
    }, [isOpen, close, closeAndFocusTrigger]);

    // Keep the dropdown inside the viewport (shift, never resize the trigger row).
    useLayoutEffect(() => {
        const menu = menuRef.current;
        if (!isOpen || !menu) return;
        const clamp = () => {
            menu.style.setProperty("--tb-nav-menu-shift", "0px");
            const rect = menu.getBoundingClientRect();
            const maxRight = window.innerWidth - VIEWPORT_MARGIN_PX;
            let shift = 0;
            if (rect.right > maxRight) shift = maxRight - rect.right;
            if (rect.left + shift < VIEWPORT_MARGIN_PX) shift = VIEWPORT_MARGIN_PX - rect.left;
            menu.style.setProperty("--tb-nav-menu-shift", `${Math.round(shift)}px`);
        };
        clamp();
        window.addEventListener("resize", clamp);
        return () => window.removeEventListener("resize", clamp);
    }, [isOpen]);

    // Keyboard-initiated open: move focus into the menu once it has rendered.
    useEffect(() => {
        if (!isOpen || focusRequest?.id !== id) return;
        const items = menuItems(menuRef.current);
        (focusRequest.target === "last" ? items[items.length - 1] : items[0])?.focus();
        consumeFocusRequest();
    }, [isOpen, focusRequest, id, consumeFocusRequest]);

    const moveToSibling = (from: HTMLElement, dir: 1 | -1, focusInto: boolean) => {
        const next = siblingTrigger(from, dir);
        if (!next) return;
        const nextMenuId = next.dataset.navMenuId;
        if (nextMenuId) open(nextMenuId, focusInto ? "first" : undefined);
        else close();
        next.focus();
    };

    const onTriggerKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
        switch (event.key) {
            case "ArrowDown": case "Enter": case " ":
                event.preventDefault(); open(id, "first"); break;
            case "ArrowUp":
                event.preventDefault(); open(id, "last"); break;
            case "ArrowRight": case "ArrowLeft":
                event.preventDefault();
                moveToSibling(event.currentTarget, event.key === "ArrowRight" ? 1 : -1, false);
                break;
            default:
        }
    };

    const onMenuKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
        const items = menuItems(menuRef.current);
        const index = items.indexOf(document.activeElement as HTMLElement);
        const focusAt = (i: number) => items[(i + items.length) % items.length]?.focus();
        switch (event.key) {
            case "ArrowDown": event.preventDefault(); focusAt(index + 1); break;
            case "ArrowUp":   event.preventDefault(); focusAt(index < 0 ? -1 : index - 1); break;
            case "Home":      event.preventDefault(); focusAt(0); break;
            case "End":       event.preventDefault(); focusAt(-1); break;
            case "Escape":    event.preventDefault(); event.stopPropagation(); closeAndFocusTrigger(); break;
            case "Tab":       close(); break;
            case "ArrowRight": case "ArrowLeft":
                event.preventDefault();
                if (triggerRef.current) moveToSibling(triggerRef.current, event.key === "ArrowRight" ? 1 : -1, true);
                break;
            default:
        }
    };

    // Hover is a mouse-only affordance; touch/pen rely on tap (click) so the
    // emulated hover of a tap can never open-then-immediately-close a menu.
    const onPointerEnter = (event: ReactPointerEvent) => {
        if (event.pointerType !== "mouse") return;
        pointerInsideRef.current = true;
        hoverEnter(id);
    };
    const onPointerLeave = (event: ReactPointerEvent) => {
        if (event.pointerType !== "mouse") return;
        pointerInsideRef.current = false;
        hoverLeave();
    };
    // Selecting an item removes the dropdown from under the cursor, and the
    // browser then sends no pointerenter if the mouse goes straight back to the
    // trigger.  Treat the first move after such a close as a fresh enter.
    const onPointerMove = (event: ReactPointerEvent) => {
        if (event.pointerType === "mouse" && !pointerInsideRef.current) onPointerEnter(event);
    };
    const closeAfterSelect = useCallback(() => {
        pointerInsideRef.current = false;
        close();
    }, [close]);

    const onTriggerClick = () => {
        // A mouse click lands on a menu hover already opened: keep it open.
        if (lastPointerType.current === "mouse") open(id);
        else toggle(id);
        lastPointerType.current = "";
    };

    const menuStyle = { "--tb-nav-menu-cols": columns, "--tb-nav-menu-rows": rows } as CSSProperties;

    return (
        <div ref={rootRef} className={`tb-nav-menu-root${isOpen ? " is-open" : ""}`} data-nav-menu-root=""
            onPointerEnter={onPointerEnter}
            onPointerLeave={onPointerLeave}
            onPointerMove={onPointerMove}
        >
            <button
                ref={triggerRef}
                id={triggerId}
                type="button"
                className={`tb-nav-trigger${isActive ? " is-active" : ""}${isOpen ? " is-open" : ""}`}
                aria-haspopup="menu"
                aria-expanded={isOpen}
                aria-controls={isOpen ? menuId : undefined}
                aria-label={ariaLabel}
                data-nav-trigger=""
                data-nav-menu-id={id}
                onPointerDown={(event) => { lastPointerType.current = event.pointerType; }}
                onClick={onTriggerClick}
                onKeyDown={onTriggerKeyDown}
            >
                <Icon name={icon} className="size-4" aria-hidden="true" />
                <span className="tb-nav-trigger-label">{label}</span>
                <ChevronDown className="tb-nav-chevron size-3.5" aria-hidden="true" />
            </button>

            {isOpen && (
                <div
                    ref={menuRef}
                    id={menuId}
                    role="menu"
                    aria-labelledby={triggerId}
                    className={`tb-nav-menu${align === "end" ? " is-end" : ""}${columns > 1 ? " is-multi" : ""}`}
                    style={menuStyle}
                    onKeyDown={onMenuKeyDown}
                >
                    <NavMenuCloseContext.Provider value={closeAfterSelect}>{children}</NavMenuCloseContext.Provider>
                </div>
            )}
        </div>
    );
}

export function NavMenuSection({ label, children }: { label?: string; children: ReactNode }) {
    const headingId = useId();
    if (!label) return <>{children}</>;
    return (
        <div role="group" aria-labelledby={headingId} className="tb-nav-menu-section">
            <div id={headingId} role="presentation" className="tb-nav-menu-heading">{label}</div>
            {children}
        </div>
    );
}

type NavMenuItemProps = {
    icon?: string;
    label: ReactNode;
    to?: string;
    active?: boolean;
    danger?: boolean;
    onSelect?: () => void;
};

export function NavMenuItem({ icon, label, to, active = false, danger = false, onSelect }: NavMenuItemProps) {
    const close = useContext(NavMenuCloseContext);
    const className = ["tb-nav-menu-item", active && "is-active", danger && "is-danger"].filter(Boolean).join(" ");
    const inner = (
        <>
            {icon && <Icon name={icon} className="size-4" aria-hidden="true" />}
            <span className="tb-nav-menu-item-label">{label}</span>
        </>
    );
    const handleClick = () => { close(); onSelect?.(); };
    if (!to) {
        return <button type="button" role="menuitem" tabIndex={-1} className={className} onClick={handleClick}>{inner}</button>;
    }
    return (
        <Link role="menuitem" tabIndex={-1} to={to} className={className} aria-current={active ? "page" : undefined} onClick={handleClick}>
            {inner}
        </Link>
    );
}

export function NavMenuSeparator() {
    return <div role="separator" className="tb-nav-menu-divider" />;
}

export function NavMenuHeader({ children }: { children: ReactNode }) {
    return <div role="presentation" className="tb-nav-menu-header">{children}</div>;
}
