import React, { forwardRef } from "react";

/*
 * Button — thin wrapper around Bootstrap's .btn classes plus tabler.css.
 *
 *   <Button>Save</Button>                        // primary
 *   <Button variant="outline-secondary">Cancel</Button>
 *   <Button variant="danger" size="sm">Delete</Button>
 *   <Button icon="plus-lg">New</Button>
 *   <Button icon="download" iconOnly aria-label="Download" />
 *   <Button loading>Saving</Button>
 */

interface ButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
    variant?: string;
    size?: 'sm' | 'lg';
    icon?: string;
    iconRight?: string;
    iconOnly?: boolean;
    loading?: boolean;
    block?: boolean;
    children?: React.ReactNode;
}

const VARIANTS = new Set([
    "primary", "secondary", "success", "danger", "warning", "info", "light", "dark", "link",
    "outline-primary", "outline-secondary", "outline-success", "outline-danger",
    "outline-warning", "outline-info", "outline-light", "outline-dark",
]);

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
    {
        variant = "primary",
        size,
        icon,
        iconRight,
        iconOnly = false,
        loading = false,
        block = false,
        disabled,
        className = "",
        children,
        type = "button",
        ...rest
    },
    ref
) {
    const safeVariant = VARIANTS.has(variant) ? variant : "primary";
    const classes = [
        "btn",
        `btn-${safeVariant}`,
        size === "sm" ? "btn-sm" : size === "lg" ? "btn-lg" : "",
        block ? "w-full" : "",
        className,
    ].filter(Boolean).join(" ");

    return (
        <button
            ref={ref}
            type={type}
            className={classes}
            disabled={disabled || loading}
            aria-busy={loading || undefined}
            {...rest}
        >
            {loading && (
                <span
                    className="inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
                    role="status"
                    aria-hidden="true"
                    style={{ width: 14, height: 14, marginRight: iconOnly ? 0 : 6 }}
                />
            )}
            {!loading && icon && (
                <i
                    className={`bi bi-${icon}`}
                    aria-hidden="true"
                    style={{ marginRight: iconOnly ? 0 : 6, fontSize: "0.95em" }}
                />
            )}
            {!iconOnly && children}
            {!loading && iconRight && (
                <i
                    className={`bi bi-${iconRight}`}
                    aria-hidden="true"
                    style={{ marginLeft: 6, fontSize: "0.95em" }}
                />
            )}
        </button>
    );
});

export default Button;
