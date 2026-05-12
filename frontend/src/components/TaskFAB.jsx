import { useState } from "react";
import TaskDrawer from "./TaskDrawer";

/**
 * Floating action button that opens the global task drawer.
 * Positioned bottom-right, above the AdminLayout footer (~90px tall).
 */
export default function TaskFAB({ bottomOffset = 110 }) {
    const [show, setShow] = useState(false);

    return (
        <>
            <button
                type="button"
                onClick={() => setShow(true)}
                aria-label="Open tasks"
                title="Tasks"
                style={{
                    position: "fixed",
                    right: 24,
                    bottom: bottomOffset,
                    width: 56,
                    height: 56,
                    borderRadius: "50%",
                    border: "none",
                    background: "var(--primary-gradient, linear-gradient(135deg,#6366f1,#3b82f6))",
                    color: "#fff",
                    boxShadow: "0 6px 20px rgba(0,0,0,0.18)",
                    zIndex: 1040,
                    fontSize: "1.4rem",
                    cursor: "pointer",
                }}
            >
                <i className="bi bi-check2-square"></i>
            </button>
            <TaskDrawer show={show} onClose={() => setShow(false)} />
        </>
    );
}
