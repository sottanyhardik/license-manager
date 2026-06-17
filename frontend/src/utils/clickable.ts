import type { KeyboardEvent } from "react";

/**
 * Spread onto a non-button element that has an onClick handler to make it
 * keyboard-operable (WCAG AA): focusable + activates on Enter/Space.
 *
 *   <div {...clickable(() => doThing())}>…</div>
 */
export function clickable(fn: () => void) {
    return {
        onClick: fn,
        role: "button",
        tabIndex: 0,
        onKeyDown: (e: KeyboardEvent) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                fn();
            }
        },
    };
}
