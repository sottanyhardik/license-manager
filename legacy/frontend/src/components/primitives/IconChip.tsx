/*
 * IconChip — small/medium icon container, used as a visual anchor
 * for section headers, list items, or inline labels.
 *
 *   <IconChip icon="check2-square" tone="primary" />
 */
import Icon from "@/components/Icon";

const ALLOWED_TONES = new Set(["primary", "success", "warning", "danger", "info", "neutral"]);
const ALLOWED_SIZES = new Set(["sm", "md", "lg"]);

export default function IconChip({
    icon = "circle",
    tone = "primary",
    size = "md",
    className = "",
    style,
}) {
    const safeTone = ALLOWED_TONES.has(tone) ? tone : "primary";
    const safeSize = ALLOWED_SIZES.has(size) ? size : "md";
    return (
        <span
            aria-hidden="true"
            className={`tb-icon-chip size-${safeSize} tone-${safeTone} ${className}`.trim()}
            style={style}
        >
            <Icon name={icon} className="size-4" />
        </span>
    );
}
