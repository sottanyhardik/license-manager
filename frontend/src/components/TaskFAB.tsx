import { lazy, Suspense, useState } from "react";

const TaskDrawer = lazy(() => import("./TaskDrawer"));
import { CheckSquare } from "lucide-react";

/**
 * Floating action button that opens the global task drawer.
 * Compact bottom-right button; AdminLayout reserves bottom padding for it and hides it on form routes.
 */
export default function TaskFAB({ bottomOffset = 16 }) {
    const [show, setShow] = useState(false);
    const [hovered, setHovered] = useState(false);

    return (
        <>
            <button
                type="button"
                className="task-fab-btn"
                onClick={() => setShow(true)}
                onMouseEnter={() => setHovered(true)}
                onMouseLeave={() => setHovered(false)}
                aria-label="Open tasks"
                title="Tasks"
                style={{
                    position: "fixed",
                    right: 64,
                    bottom: bottomOffset,
                    height: 40,
                    paddingInline: hovered ? 18 : 0,
                    minWidth: 40,
                    borderRadius: 999,
                    border: "1px solid var(--border)",
                    background: "var(--surface-raised)",
                    color: "var(--text-primary)",
                    boxShadow: hovered
                        ? "var(--elevation-3)"
                        : "var(--elevation-2)",
                    zIndex: 30,
                    fontSize: "0.9rem",
                    fontWeight: 500,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    transform: hovered ? "translateY(-1px)" : "none",
                    transition: "transform 180ms cubic-bezier(0.16,1,0.3,1), box-shadow 180ms cubic-bezier(0.16,1,0.3,1), padding-inline 180ms cubic-bezier(0.16,1,0.3,1)",
                    overflow: "hidden",
                }}
            >
                <span
                    aria-hidden="true"
                    style={{
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: 24,
                        height: 24,
                        borderRadius: 999,
                        background: "var(--indigo-50)",
                        color: "var(--primary-color)",
                        marginLeft: hovered ? 0 : 7,
                        marginRight: hovered ? 0 : 7,
                        transition: "margin 180ms cubic-bezier(0.16,1,0.3,1)",
                    }}
                >
                    <CheckSquare className="size-4" aria-hidden="true" />
                </span>
                <span
                    style={{
                        maxWidth: hovered ? 90 : 0,
                        opacity: hovered ? 1 : 0,
                        overflow: "hidden",
                        whiteSpace: "nowrap",
                        transition: "max-width 180ms cubic-bezier(0.16,1,0.3,1), opacity 120ms ease",
                    }}
                >
                    Tasks
                </span>
            </button>
            {show && (
                <Suspense fallback={null}>
                    <TaskDrawer show={show} onClose={() => setShow(false)} />
                </Suspense>
            )}
        </>
    );
}
