import * as React from "react";
import { Button as MuiButton, ButtonProps as MuiButtonProps } from "@mui/material";

export type ButtonVariant = "default" | "secondary" | "destructive" | "accent" | "ghost" | "outline" | "link";
export type ButtonSize = "sm" | "default" | "lg" | "icon";

interface ButtonProps extends Omit<MuiButtonProps, 'variant' | 'size'> {
    variant?: ButtonVariant;
    size?: ButtonSize;
    asChild?: boolean; // Ignored, for compatibility with shadcn usage
}

/**
 * Button component wrapper around MUI Button
 * Maps shadcn-style variants to MUI variants
 *
 * Variants:
 * - default → contained blue
 * - secondary → outlined gray
 * - destructive → contained error
 * - accent → contained success
 * - ghost → text (no background)
 * - outline → outlined
 * - link → text with underline
 */
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    (
        {
            variant = "default",
            size = "default",
            className,
            children,
            ...props
        },
        ref
    ) => {
        // Map shadcn variants to MUI variants
        let muiVariant: MuiButtonProps['variant'] = 'contained';
        let muiColor: MuiButtonProps['color'] = 'primary';
        let sxOverrides: Record<string, any> = {};

        switch (variant) {
            case "default":
                muiVariant = 'contained';
                muiColor = 'primary';
                break;
            case "secondary":
                muiVariant = 'outlined';
                muiColor = 'inherit';
                break;
            case "destructive":
                muiVariant = 'contained';
                muiColor = 'error';
                break;
            case "accent":
                muiVariant = 'contained';
                muiColor = 'success';
                break;
            case "ghost":
                muiVariant = 'text';
                muiColor = 'inherit';
                break;
            case "outline":
                muiVariant = 'outlined';
                muiColor = 'inherit';
                break;
            case "link":
                muiVariant = 'text';
                muiColor = 'primary';
                sxOverrides.textDecoration = 'underline';
                break;
        }

        // Map size to MUI sizes
        let muiSize: MuiButtonProps['size'] = 'medium';
        switch (size) {
            case "sm":
                muiSize = 'small';
                break;
            case "default":
                muiSize = 'medium';
                break;
            case "lg":
                muiSize = 'large';
                break;
            case "icon":
                muiSize = 'small';
                sxOverrides.minWidth = 'auto';
                sxOverrides.width = 40;
                sxOverrides.height = 40;
                sxOverrides.padding = 0;
                break;
        }

        return (
            <MuiButton
                ref={ref}
                variant={muiVariant}
                color={muiColor}
                size={muiSize}
                className={className}
                sx={{
                    textTransform: 'capitalize',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 1,
                    whiteSpace: 'nowrap',
                    ...sxOverrides,
                }}
                {...props}
            >
                {children}
            </MuiButton>
        );
    }
);

Button.displayName = 'Button';

export { Button };
