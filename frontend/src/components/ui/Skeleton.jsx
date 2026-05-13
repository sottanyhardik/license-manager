/**
 * Skeleton — animated placeholder for loading states.
 */
export default function Skeleton({
    variant = "line",
    width = "100%",
    height,
    style = {},
    className = "",
}) {
    const presetHeight =
        variant === "title"  ? 18 :
        variant === "text"   ? 14 :
        variant === "block"  ? 80 :
        variant === "avatar" ? 36 : 14;

    const finalHeight = height ?? presetHeight;
    const borderRadius = variant === "avatar" ? 999 : 8;

    return (
        <div
            className={`skeleton ${className}`.trim()}
            style={{
                width: variant === "avatar" ? finalHeight : width,
                height: finalHeight,
                borderRadius,
                ...style,
            }}
            aria-hidden="true"
        />
    );
}
