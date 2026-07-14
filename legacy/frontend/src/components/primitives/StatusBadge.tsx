/*
 * StatusBadge — pill with consistent tone palette.
 *
 *   <StatusBadge tone="success">Active</StatusBadge>
 *   <StatusBadge tone="warning" icon="exclamation-circle">Pending</StatusBadge>
 */
import Icon from "@/components/Icon";

const ALLOWED = new Set(["primary", "success", "warning", "danger", "info", "neutral"]);

export default function StatusBadge({
    tone = "neutral",
    icon,
    children,
    className = "",
    ...rest
}) {
    const safeTone = ALLOWED.has(tone) ? tone : "neutral";
    return (
        <span className={`tb-status tone-${safeTone} ${className}`.trim()} {...rest}>
            {icon && <Icon name={icon} className="size-3.5" />}
            {children}
        </span>
    );
}
