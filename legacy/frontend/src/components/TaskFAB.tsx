import { useState } from "react";
import TaskDrawer from "./TaskDrawer";
import { CheckSquare } from "lucide-react";

/**
 * Floating action button that opens the global task drawer.
 * Positioned bottom-right, above the AdminLayout footer.
 */
export default function TaskFAB({ bottomOffset = 110 }) {
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
                    right: 24,
                    bottom: bottomOffset,
                    height: 48,
                    paddingInline: hovered ? 18 : 0,
                    minWidth: 48,
                    borderRadius: 999,
                    border: "1px solid rgba(15,23,42,0.06)",
                    background: "var(--surface-raised)",
                    color: "var(--text-primary)",
                    boxShadow: hovered
                        ? "var(--elevation-3)"
                        : "var(--elevation-2)",
                    zIndex: 1040,
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
                        width: 28,
                        height: 28,
                        borderRadius: 999,
                        background: "var(--indigo-50)",
                        color: "var(--primary-color)",
                        marginLeft: hovered ? 0 : 10,
                        marginRight: hovered ? 0 : 10,
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
            <TaskDrawer show={show} onClose={() => setShow(false)} />
        </>
    );
}
