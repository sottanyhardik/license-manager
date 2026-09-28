import * as React from "react";
import { Chip as MuiChip, ChipProps as MuiChipProps } from "@mui/material";

export type BadgeVariant = "default" | "secondary" | "destructive" | "success" | "warning" | "info" | "outline";

interface BadgeProps extends Omit<MuiChipProps, 'variant' | 'label'> {
    variant?: BadgeVariant;
    label?: React.ReactNode;
    children?: React.ReactNode;
}

/**
 * Badge component wrapper around MUI Chip
 * Maps shadcn-style variants to MUI color/variant combinations
 */
const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
    ({ className, variant = "default", color = "default", label, children, ...props }, ref) => {
        // Map badge variant to MUI color
        let muiColor: MuiChipProps['color'] = 'default';
        let muiVariant: MuiChipProps['variant'] = 'filled';

        switch (variant) {
            case "default":
                muiColor = 'primary';
                muiVariant = 'filled';
                break;
            case "secondary":
                muiColor = 'default';
                muiVariant = 'filled';
                break;
            case "destructive":
                muiColor = 'error';
                muiVariant = 'filled';
                break;
            case "success":
                muiColor = 'success';
                muiVariant = 'filled';
                break;
            case "warning":
                muiColor = 'warning';
                muiVariant = 'filled';
                break;
            case "info":
                muiColor = 'info';
                muiVariant = 'filled';
                break;
            case "outline":
                muiVariant = 'outlined';
                break;
        }

        // Support both label prop and children for flexibility
        const chipLabel = label ?? children;

        return (
            <MuiChip
                ref={ref}
                label={chipLabel}
                color={muiColor}
                variant={muiVariant}
                data-slot="badge"
                className={className}
                size="small"
                {...props}
            />
        );
    }
);

Badge.displayName = 'Badge';

export { Badge };
