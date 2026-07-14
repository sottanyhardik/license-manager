import Icon from "@/components/Icon";

export default function EmptyState({
    icon = "inbox",
    title = "Nothing here yet",
    description,
    action,
    compact = false,
    style = {},
}) {
    return (
        <div
            className="empty-state"
            style={{
                padding: compact ? "28px 16px" : undefined,
                ...style,
            }}
        >
            <div className="empty-icon" aria-hidden="true">
                <Icon name={icon} className="size-8" />
            </div>
            <div className="empty-title">{title}</div>
            {description && <div className="empty-sub">{description}</div>}
            {action && <div style={{ marginTop: 16 }}>{action}</div>}
        </div>
    );
}
