/*
 * StatCard — Tabler-style KPI card. Pure CSS classes, no inline styling.
 *
 *   <StatCard
 *     label="Licenses"
 *     value="1,284"
 *     icon="file-earmark-text"
 *     tone="primary"
 *     delta={{ direction: "up", value: "+4.2%" }}
 *     onClick={() => navigate("/licenses")}
 *   />
 */
const ALLOWED_TONES = new Set(["primary", "success", "warning", "danger", "info", "neutral"]);
import { ArrowDown, ArrowUp } from "lucide-react";

export default function StatCard({
    label,
    value,
    icon,
    tone = "primary",
    delta,
    onClick,
    loading = false,
    className = "",
    style,
}) {
    const safeTone = ALLOWED_TONES.has(tone) ? tone : "primary";
    const interactive = !!onClick;
    const Element = interactive ? "button" : "div";

    return (
        <Element
            type={interactive ? "button" : undefined}
            onClick={onClick}
            className={[
                "tb-stat",
                interactive ? "tb-stat-hover" : "",
                interactive ? "text-start border-0 w-full" : "",
                className,
            ].filter(Boolean).join(" ")}
            style={style}
        >
            {icon && (
                <span className={`tb-stat-icon tone-${safeTone}`} aria-hidden="true">
                    <i className={`bi bi-${icon}`} />
                </span>
            )}
            <div className="tb-stat-body">
                <div className="tb-stat-label">{label}</div>
                {loading ? (
                    <div className="skeleton" style={{ width: 90, height: 24, borderRadius: 6 }} />
                ) : (
                    <div className="tb-stat-value">{value ?? "—"}</div>
                )}
                {delta && (
                    <div
                        className={[
                            "tb-stat-delta",
                            delta.direction === "up"   ? "is-up"   : "",
                            delta.direction === "down" ? "is-down" : "",
                        ].filter(Boolean).join(" ")}
                    >
                        {delta.direction === "up" && <ArrowUp className="size-4" aria-hidden="true" />}
                        {delta.direction === "down" && <ArrowDown className="size-4" aria-hidden="true" />}
                        {delta.value}{delta.label ? ` ${delta.label}` : ""}
                    </div>
                )}
            </div>
        </Element>
    );
}
